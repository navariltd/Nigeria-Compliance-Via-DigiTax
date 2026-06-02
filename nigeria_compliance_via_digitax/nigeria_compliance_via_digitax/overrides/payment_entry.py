import frappe

from frappe import _
from typing import Optional
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice import (
	_update_invoice_from_response,
)
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
	DigitaxClient,
	DigitaxAPIException,
)


def update_invoice_payment_status(doc, method: Optional[str] = None) -> None:
	"""
	Update payment status in DigiTax when a Payment Entry is submitted.

	This function is called via hooks on Payment Entry submission.
	It checks if the payment is against a Sales Invoice tracked by NRS,
	then updates the payment status in DigiTax to "PAID" if fully paid,
	or "REJECTED" if there is still an outstanding amount.

	Args:
		doc: The Payment Entry document
		method: Hook method name (optional, not used)
	"""
	if doc.payment_type != "Receive":
		return

	# Get all Sales Invoices referenced in this payment
	sales_invoices = []
	for reference in doc.references:
		if reference.reference_doctype == "Sales Invoice" and reference.reference_name:
			sales_invoices.append(reference.reference_name)

	if not sales_invoices:
		return

	# Process each Sales Invoice
	for invoice_name in sales_invoices:
		try:
			_process_invoice_payment_update(invoice_name, doc)
		except Exception as e:
			frappe.log_error(
				title="Payment Status Update Failed",
				message=f"Sales Invoice: {invoice_name}\nPayment Entry: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}",
			)
			frappe.msgprint(
				_(
					"Failed to update payment status for invoice {0} in DigiTax: {1}"
				).format(invoice_name, str(e)),
				title=_("DigiTax Update Warning"),
				indicator="orange",
			)
			raise


def _process_invoice_payment_update(invoice_name: str, payment_doc) -> None:
	"""
	Process payment status update for a single Sales Invoice.

	Args:
		invoice_name: Name of the Sales Invoice
		payment_doc: Payment Entry document
	"""
	# Get the Sales Invoice
	if not frappe.db.exists("Sales Invoice", invoice_name):
		return

	invoice = frappe.get_doc("Sales Invoice", invoice_name)

	if invoice.docstatus != 1:
		return

	if not invoice.get("nc_invoice_id"):
		frappe.log_error(
			title="Payment Status Update Skipped",
			message=f"Sales Invoice {invoice_name} has not been submitted to DigiTax yet.",
		)
		return

	if not _is_invoice_fully_paid(invoice):
		frappe.log_error(
			title="Payment Status Update Skipped",
			message=f"Sales Invoice {invoice_name} is not fully paid. Outstanding amount: {invoice.outstanding_amount}",
		)
		return

	payload = {"payment_status": "PAID"}

	try:
		client = DigitaxClient(company=invoice.company)
		response = client.put(
			endpoint="/invoices",
			path_param=f"{invoice.nc_invoice_id}/payment-status",
			data=payload,
			reference_doctype="Sales Invoice",
			reference_docname=invoice.name,
		)

		if response:
			_update_invoice_from_response(invoice, response)

			frappe.logger().info(
				f"Payment status updated for Sales Invoice {invoice_name} in DigiTax: {payload['payment_status']}"
			)

	except DigitaxAPIException as e:
		frappe.log_error(
			title="DigiTax Payment Status Update Failed",
			message=f"Sales Invoice: {invoice_name}\nPayment Status: {payload['payment_status']}\nError: {str(e)}",
		)
		raise


def _is_invoice_fully_paid(invoice):
	invoice.reload()

	return invoice.outstanding_amount <= 0
