"""
Party override module for DigiTax Nigeria Compliance integration.

Handles synchronization of Customer/Supplier party data with DigiTax API.
"""

import frappe
from typing import Optional, Dict, Any, Union
from frappe import _
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
	DigitaxClient,
	DigitaxAPIException,
)

NIGERIA_COUNTRY_CODE = "234"
DIGITAX_PARTY_ENDPOINT = "/parties"
CUSTOM_DIGITAX_ID_FIELD = "custom_digitax_id"
CUSTOM_DIGITAX_IS_ACTIVE_FIELD = "is_active"


def get_digitax_party_code(doc, method: Optional[str] = None) -> None:
	"""
	Synchronize party data with DigiTax API and store the party code.

	This function is called via hooks on Customer/Supplier save.
	It retrieves party address information, formats it according to DigiTax
	requirements, and creates/updates the party record in DigiTax.

	Args:
			doc: The Customer or Supplier document being saved
			method: Hook method name (optional, not used)
	"""
	if not _should_sync_party(doc):
		return

	address = _get_party_address(doc)
	if not address:
		return

	party_data = _build_party_payload(doc, address)
	_sync_with_digitax(doc, party_data)


def _should_sync_party(doc) -> bool:
	"""
	Determine if the party should be synced with DigiTax.

	Args:
			doc: The party document

	Returns:
			True if the party has a Tax ID and should be synced
	"""
	if not doc.tax_id:
		frappe.logger().info(
			f"Party {doc.name} does not have Tax ID. Skipping DigiTax sync."
		)
		return False
	return True


def _get_party_address(doc) -> None | Any:
	"""
	Retrieve the primary or first available address for a party.

	Args:
			doc: The party document (Customer/Supplier)

	Returns:
			Address document if found, None otherwise
	"""
	address_links = _fetch_address_links(doc)

	if not address_links:
		_show_address_required_message(doc)
		return None

	address_name = _find_primary_address(address_links)
	return frappe.get_doc("Address", address_name)


def _fetch_address_links(doc) -> list:
	"""
	Fetch all address links for a party document.

	Args:
			doc: The party document

	Returns:
			List of address link records
	"""
	return frappe.get_all(
		"Dynamic Link",
		filters={
			"link_doctype": doc.doctype,
			"link_name": doc.name,
			"parenttype": "Address",
		},
		fields=["parent"],
	)


def _find_primary_address(address_links: list) -> str:
	"""
	Find the primary address from a list of address links.

	Args:
			address_links: List of address link records

	Returns:
			Name of the primary address, or first address if no primary found
	"""
	for link in address_links:
		addr = frappe.get_value(
			"Address", link.parent, ["name", "is_primary_address"], as_dict=True
		)
		if addr and addr.is_primary_address:
			return addr.name

	return address_links[0].parent


def _build_party_payload(doc, address) -> Dict[str, Any]:
	"""
	Build the payload for DigiTax party API request.

	Args:
			doc: The party document
			address: The address document

	Returns:
			Dictionary containing formatted party data for DigiTax API
	"""
	return {
		"name": doc.name,
		"tax_identification_number": doc.tax_id,
		"email": address.email_id or "",
		"phone": _format_phone_number(address.phone) if address.phone else "",
		"address": {
			"street_name": address.address_line1 or "",
			"city_name": address.city or "",
			"postal_zone": address.pincode or "",
			"country_code": _get_country_alpha3_code(address.country),
			"local_government_code": "",
			"state_code": address.state or "",
		},
	}


def _sync_with_digitax(doc, party_data: Dict[str, Any]) -> None:
	"""
	Send party data to DigiTax API and save the returned party code.

	Args:
			doc: The party document
			party_data: Formatted party data payload
	"""
	try:
		results = _call_digitax_api(party_data)
		digitax_id, is_active = "", False
		
		if results:
			digitax_id, is_active = results

		if not digitax_id:
			_handle_missing_party_code(doc, party_data)
			return

		doc.db_set(CUSTOM_DIGITAX_ID_FIELD, digitax_id)
		doc.db_set(CUSTOM_DIGITAX_IS_ACTIVE_FIELD, 1 if is_active else 0)
		frappe.logger().info(f"Party {doc.name} synced with DigiTax. ID: {digitax_id}")

	except DigitaxAPIException as e:
		_handle_api_exception(doc, e)
	except Exception as e:
		_handle_unexpected_exception(doc, e)


def _call_digitax_api(party_data: Dict[str, Any]) -> Optional[tuple[str, bool]]:
	"""
	Make API call to DigiTax to create/update party.

	Args:
			party_data: The party data payload

	Returns:
			The DigiTax party ID and is_active if successful, None otherwise
	"""
	client = DigitaxClient()
	response = client.post(DIGITAX_PARTY_ENDPOINT, party_data)

	if not response:
		frappe.logger().warning("DigiTax API returned empty response")
		return None

	return response.get("id", ""), response.get("active", False)


def _handle_missing_party_code(doc, party_data: Dict[str, Any]) -> None:
	"""Handle the case when DigiTax API doesn't return a party code."""
	frappe.log_error(
		title="DigiTax Party Sync Failed",
		message=(
			f"Party: {doc.name}\n"
			f"Error: No party code returned from DigiTax API.\n"
			f"Request Data: {party_data}"
		),
	)
	_show_sync_warning_message(
		"Failed to sync party with DigiTax. No party code returned from API. "
		"The party has been saved locally."
	)


def _handle_api_exception(doc, error: DigitaxAPIException) -> None:
	"""Handle DigiTax API specific exceptions."""
	frappe.log_error(
		title="DigiTax Party Sync Failed",
		message=f"Party: {doc.name}\nError: {str(error)}",
	)
	_show_sync_warning_message(
		"Failed to sync party with DigiTax. The party has been saved locally."
	)


def _handle_unexpected_exception(doc, error: Exception) -> None:
	"""Handle unexpected exceptions during DigiTax sync."""
	frappe.log_error(
		title="DigiTax Party Sync Error",
		message=(
			f"Party: {doc.name}\n" f"Error: {str(error)}\n" f"{frappe.get_traceback()}"
		),
	)
	_show_sync_warning_message(
		"An unexpected error occurred while syncing with DigiTax. "
		"The party has been saved locally."
	)


def _show_address_required_message(doc) -> None:
	"""Show message to user that an address is required."""
	frappe.msgprint(
		_("No address found for {0} {1}. Please add an address first.").format(
			doc.doctype, doc.name
		)
	)


def _show_sync_warning_message(message: str) -> None:
	"""Show a standardized sync warning message to the user."""
	frappe.msgprint(
		msg=_(message),
		title=_("Sync Warning"),
		indicator="orange",
	)


def _get_country_alpha3_code(country_name: str) -> str:
	"""
	Get the ISO Alpha-3 country code from FIRS Country Codes.

	Args:
			country_name: Name of the country

	Returns:
			The Alpha-3 country code, or empty string if not found
	"""
	if not country_name:
		return ""

	code = frappe.db.get_value(
		"FIRS Country Codes", {"country": country_name}, "alpha3"
	)

	if not code:
		frappe.logger().warning(f"Country code not found for {country_name}")
		return ""

	return code


def _format_phone_number(phone: str) -> str:
	"""
	Format phone number to international format with Nigeria country code.

	Removes all non-digit characters and ensures the number starts with
	the Nigeria country code (+234).

	Args:
			phone: The phone number to format

	Returns:
			Formatted phone number with + prefix (e.g., +234801234567)
	"""
	if not phone:
		return ""

	digits = "".join(filter(str.isdigit, phone))

	if not digits:
		return ""

	# Add Nigeria country code if not present
	if not digits.startswith(NIGERIA_COUNTRY_CODE):
		digits = NIGERIA_COUNTRY_CODE + digits.lstrip("0")

	return f"+{digits}"
