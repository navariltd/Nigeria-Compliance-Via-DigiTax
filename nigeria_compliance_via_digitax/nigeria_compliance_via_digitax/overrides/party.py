import frappe
from typing import Tuple, Optional
from frappe import _
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
    DigitaxAPIException,
)


def get_digitax_party_code(doc, method: Optional[str] = None) -> None:
	if not doc.tax_id:
		frappe.logger().info(f"Party {doc.name} does not have Tax ID. Skipping DigiTax sync.")
		return

	# Required data
	req_data = {
		"name": doc.name,
		"tin": doc.tax_id,
		"email": "",
		"phone": "",
		"address": {
			"street_name": "",
			"city_name": "",
			"postal_zone": "", # postal code
			"country_code": "",
			"local_government_code": "",
			"state_code": "",
		}
	}

	# Fetch address details
	address = frappe.get_doc("Address", {"party_type": doc.doctype, "party": doc.name})
	if address:
		req_data["address"]["street_name"] = address.address_line1
		req_data["address"]["city_name"] = address.city
		req_data["address"]["postal_zone"] = address.pincode
		req_data["address"]["country_code"] = address.country
		req_data["address"]["state_code"] = address.state

