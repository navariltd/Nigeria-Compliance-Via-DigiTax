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
    Update payment status in DigiTax when a Journal Entry is submitted.

    This function is called via hooks on Journal Entry submission.
    It inspects each account row for references to Sales Invoices tracked by
    NRS, then updates the payment status in DigiTax to "PAID" for any
    invoice whose outstanding amount has reached zero.

    Args:
		doc: The Journal Entry document
		method: Hook method name (optional, not used)
    """
    # Collect unique Sales Invoice names referenced in this journal entry
    sales_invoices = set()
    for row in doc.accounts:
        if row.reference_type == "Sales Invoice" and row.reference_name:
            sales_invoices.add(row.reference_name)

    if not sales_invoices:
        return

    for invoice_name in sales_invoices:
        try:
            _process_invoice_payment_update(invoice_name, doc)
        except Exception as e:
            frappe.log_error(
                title="Payment Status Update Failed",
                message=(
                    f"Sales Invoice: {invoice_name}\n"
                    f"Journal Entry: {doc.name}\n"
                    f"Error: {str(e)}\n{frappe.get_traceback()}"
                ),
            )
            frappe.msgprint(
                _(
                    "Failed to update payment status for invoice {0} in DigiTax: {1}"
                ).format(invoice_name, str(e)),
                title=_("DigiTax Update Warning"),
                indicator="orange",
            )
            raise


def _process_invoice_payment_update(invoice_name: str, journal_entry_doc) -> None:
    """
    Process payment status update for a single Sales Invoice.

    Args:
		invoice_name: Name of the Sales Invoice
		journal_entry_doc: Journal Entry document
    """
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

    invoice.reload()
    if invoice.outstanding_amount > 0:
        frappe.log_error(
            title="Payment Status Update Skipped",
            message=(
                f"Sales Invoice {invoice_name} is not fully paid. "
                f"Outstanding amount: {invoice.outstanding_amount}"
            ),
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
                f"Payment status updated for Sales Invoice {invoice_name} in DigiTax: PAID "
                f"(cleared by Journal Entry {journal_entry_doc.name})"
            )

    except DigitaxAPIException as e:
        frappe.log_error(
            title="DigiTax Payment Status Update Failed",
            message=(
                f"Sales Invoice: {invoice_name}\n"
                f"Payment Status: PAID\n"
                f"Error: {str(e)}"
            ),
        )
        raise
