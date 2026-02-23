import frappe
from typing import Optional, Union
from frappe import _
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
	DigitaxClient,
	DigitaxAPIException,
)


def get_digitax_party_code(doc, method: Optional[str] = None) -> None:
	"""
	Get or create DigiTax party code for Customer/Supplier
	"""
	print("DEBUG: get_digitax_party_code called")
	if not doc.tax_id:
		frappe.logger().info(
			f"Party {doc.name} does not have Tax ID. Skipping DigiTax sync."
		)
		return

	# Get primary or billing address
	address_links = frappe.get_all(
		"Dynamic Link",
		filters={
			"link_doctype": doc.doctype,
			"link_name": doc.name,
			"parenttype": "Address",
		},
		fields=["parent"],
	)

	if not address_links:
		frappe.msgprint(
			f"No address found for {doc.doctype} {doc.name}. Please add an address first."
		)
		return

	# Try to get primary address first, otherwise take the first one
	address_name = None
	for link in address_links:
		addr = frappe.get_value(
			"Address", link.parent, ["name", "is_primary_address"], as_dict=True
		)
		if addr.is_primary_address:
			address_name = addr.name
			break

	if not address_name:
		address_name = address_links[0].parent

	address = frappe.get_doc("Address", address_name)

	# Required data
	req_data = {
		"name": doc.name,
		"tax_identification_number": doc.tax_id,
		"email": "",
		"phone": "",
		"address": {
			"street_name": "",
			"city_name": "",
			"postal_zone": "",  # postal code
			"country_code": "",
			"local_government_code": "",
			"state_code": "",
		},
	}

	req_data["address"]["street_name"] = address.address_line1
	req_data["address"]["city_name"] = address.city
	req_data["address"]["postal_zone"] = address.pincode
	req_data["address"]["country_code"] = _get_county_alpha3_code(address.country)
	req_data["address"]["state_code"] = address.state
	req_data["email"] = address.email_id
	req_data["phone"] = format_phone_number(address.phone)

	# Call Digitax API
	try:
		client = DigitaxClient()
		api_response = client.post("/parties", req_data) or {}

		print(api_response)
		# Save DigiTax party code in custom field
		id = api_response.get("id", None)

		if not id:
			frappe.log_error(
				title="DigiTax Party Sync Failed",
				message=f"Party: {doc.name}\nError: No party code returned from DigiTax API.\nResponse: {api_response}",
			)
			frappe.msgprint(
				msg=_(
					"Failed to sync party with DigiTax. No party code returned from API. The party has been saved locally."
				),
				title=_("Sync Warning"),
				indicator="orange",
			)
			return

		doc.db_set("custom_digitax_id", id)
	except DigitaxAPIException as e:
		frappe.log_error(
			title="DigiTax Party Sync Failed",
			message=f"Party: {doc.name}\nError: {str(e)}",
		)
		frappe.msgprint(
			msg=_(
				"Failed to sync party with DigiTax. The party has been saved locally."
			),
			title=_("Sync Warning"),
			indicator="orange",
		)
	except Exception as e:
		frappe.log_error(
			title="DigiTax Party Sync Error",
			message=f"Party: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}",
		)


def _get_county_alpha3_code(country_name: str) -> Union[str, None]:
	code = frappe.db.get_value(
		"FIRS Country Codes", {"country": country_name}, "alpha3"
	)
	if not code:
		frappe.logger().warning(f"Country code not found for {country_name}")

	return code


def format_phone_number(phone: str) -> str:
	# Remove non-digit characters
	digits = "".join(filter(str.isdigit, phone))

	# Ensure it starts with country code (e.g., +234 for Nigeria)
	if not digits.startswith("234"):
		digits = "234" + digits.lstrip("0")

	return "+" + digits
