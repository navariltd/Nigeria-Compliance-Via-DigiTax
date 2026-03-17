from typing import Any, Dict, List

import frappe

from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice import (
    get_invoice_from_digitax,
    submit_sales_invoice,
)


def _retry_pending_sales_invoices_to_digitax(log_result: bool = True) -> Dict[str, Any]:
    """Retry DigiTax submission for submitted invoices missing a DigiTax invoice ID."""
    invoice_names = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "nc_invoice_id": ["in", ["", None]],
        },
        pluck="name",
    )

    if not invoice_names:
        return {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "failed_invoices": [],
        }

    previous_mute_messages = getattr(frappe.flags, "mute_messages", False)
    frappe.flags.mute_messages = True

    success_count = 0
    failed_invoices: List[str] = []

    try:
        for invoice_name in invoice_names:
            invoice = frappe.get_doc("Sales Invoice", invoice_name)
            invoice_reference_number = invoice.get("nc_invoice_reference_number")

            if invoice_reference_number:
                try:
                    get_invoice_from_digitax(invoice.name, invoice_reference_number)
                    invoice.reload()

                    if invoice.get("nc_invoice_id"):
                        print(
                            "Invoice {invoice_name} already exists in DigiTax. Synced using reference number {reference_number}.".format(
                                invoice_name=invoice_name,
                                reference_number=invoice_reference_number,
                            )
                        )
                        success_count += 1
                        continue
                except Exception as error:
                    frappe.logger().warning(
                        "Failed to fetch Sales Invoice %s from DigiTax using reference number %s before retry: %s",
                        invoice.name,
                        invoice_reference_number,
                        str(error),
                    )

            submit_sales_invoice(invoice)
            invoice.reload()

            if invoice.get("nc_invoice_id"):
                print(
                    "Submitted invoice {invoice_name} to DigiTax.".format(
                        invoice_name=invoice_name
                    )
                )
                success_count += 1
            else:
                print(
                    "Invoice {invoice_name} is still missing a DigiTax invoice ID after lookup and submission retry.".format(
                        invoice_name=invoice_name
                    )
                )
                failed_invoices.append(invoice.name)
    finally:
        frappe.flags.mute_messages = previous_mute_messages

    result = {
        "processed": len(invoice_names),
        "successful": success_count,
        "failed": len(failed_invoices),
        "failed_invoices": failed_invoices,
    }

    if log_result and (success_count or failed_invoices):
        summary = [
            f"Processed: {len(invoice_names)}",
            f"Successful: {success_count}",
            f"Failed: {len(failed_invoices)}",
        ]

        if failed_invoices:
            summary.append(
                "Invoices still pending DigiTax ID: " + ", ".join(failed_invoices)
            )
            frappe.log_error(
                title="Daily DigiTax Sales Invoice Retry",
                message="\n".join(summary),
            )
        else:
            frappe.logger().info(
                "Daily DigiTax Sales Invoice Retry\n" + "\n".join(summary)
            )

    return result


def submit_pending_sales_invoices_to_digitax() -> None:
    """Scheduled task entrypoint for retrying DigiTax submission."""
    _retry_pending_sales_invoices_to_digitax(log_result=True)


def run_pending_sales_invoice_digitax_retry() -> Dict[str, Any]:
    """Bench helper for manually retrying DigiTax submission.

    Run with:
        bench execute nigeria_compliance_via_digitax.tasks.run_pending_sales_invoice_digitax_retry
    """
    return _retry_pending_sales_invoices_to_digitax(log_result=False)
