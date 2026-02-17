import frappe
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import DigitaxClient


def get_digitax_item_code(doc, method=None):
	frappe.logger().info(f"DEBUG: calling get_digitax_item_code for item {doc.name}")
	print(
		"DEBUG: calling get_digitax_item_code on item save"
	)  # This goes to bench console

	if not doc.allow_firs_tracking:
		frappe.logger().info(
			f"Skipping FIRS tracking for item {doc.name} - allow_firs_tracking is False"
		)
		return

	# Required data
	tax_category_code = get_tax_category_code(doc.firs_tax_category)
	hsn_code, is_service = get_hsn_code(doc.firs_product_category)
	item_name = doc.name
	description = doc.description or doc.name

	client = DigitaxClient()

	req_data = {
		"tax_category_code": tax_category_code,
		"product_category": doc.firs_product_category,
		"hsn_code": hsn_code,
		"item_name": item_name,
		"description": description,
		"is_service": bool(is_service),
	}

	print("Request data for DigiTax API: ", req_data)

	api_response = client.post("/items", req_data)
	print("DigiTax Item ID response: ", api_response.get("id") if api_response else "No response")  # Log the ID from the response

	if api_response:
		digitax_item_id = api_response.get("id")
		if digitax_item_id:
			doc.db_set("digitax_id", digitax_item_id, commit=True)
			frappe.logger().info(
				f"Updated item {doc.name} with DigiTax item ID: {digitax_item_id}"
			)

def get_tax_category_code(firs_tax_category):
	return frappe.db.get_value("FIRS Tax Category", firs_tax_category, "tax_code")


def get_hsn_code(firs_product_category):
	return frappe.db.get_value(
		"FIRS Product Category", firs_product_category, ["hs_code", "is_service"]
	)
