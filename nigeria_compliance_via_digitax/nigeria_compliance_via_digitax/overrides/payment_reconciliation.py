import frappe

from frappe import _
from typing import Any
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice import (
    _update_invoice_from_response,
)
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
    DigitaxAPIException,
)


class PaymentReconciliationMixin:
    @frappe.whitelist()
    def reconcile(self) -> Any:
        invoice_names = [
            row.invoice_number
            for row in self.get("invoices", [])
            if row.invoice_type == "Sales Invoice" and row.invoice_number
        ]

        result = super().reconcile()

        for invoice_name in invoice_names:
            try:
                _process_reconciled_invoice(invoice_name)
            except Exception as e:
                frappe.log_error(
                    title="DigiTax Payment Reconciliation Update Failed",
                    message=(
                        f"Sales Invoice: {invoice_name}\n"
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

        return result


def _process_reconciled_invoice(invoice_name: str) -> None:
    """
    Update DigiTax payment status to PAID for a fully-reconciled Sales Invoice.

    Args:
        invoice_name: Name of the Sales Invoice to check and update.
    """
    if not frappe.db.exists("Sales Invoice", invoice_name):
        return

    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    if invoice.docstatus != 1:
        return

    if not invoice.get("nc_invoice_id"):
        return

    invoice.reload()

    if invoice.outstanding_amount > 0:
        return

    if invoice.get("nc_payment_status") == "PAID":
        return

    try:
        client = DigitaxClient(company=invoice.company)
        response = client.put(
            endpoint="/invoices",
            path_param=f"{invoice.nc_invoice_id}/payment-status",
            data={"payment_status": "PAID"},
            reference_doctype="Sales Invoice",
            reference_docname=invoice.name,
        )

        if response:
            _update_invoice_from_response(invoice, response)
            frappe.logger().info(
                f"Payment status updated for Sales Invoice {invoice_name} in DigiTax: PAID "
                f"(cleared via Payment Reconciliation)"
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
