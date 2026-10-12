from typing import Any, Dict, List

import frappe

from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice import (
    _update_invoice_from_response,
    get_invoice_from_digitax,
    submit_sales_invoice,
)
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
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


def _ensure_invoice_has_digitax_id(invoice) -> bool:
    if invoice.get("nc_invoice_id"):
        return True

    invoice_reference_number = invoice.get("nc_invoice_reference_number")

    if invoice_reference_number:
        try:
            get_invoice_from_digitax(invoice.name, invoice_reference_number)
            invoice.reload()
        except Exception as error:
            frappe.logger().warning(
                "Failed to fetch Sales Invoice %s from DigiTax using reference number %s before payment-status retry: %s",
                invoice.name,
                invoice_reference_number,
                str(error),
            )

    if invoice.get("nc_invoice_id"):
        return True

    submit_sales_invoice(invoice)
    invoice.reload()

    return bool(invoice.get("nc_invoice_id"))


def _empty_retry_result() -> Dict[str, Any]:
    return {
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "failed_invoices": [],
    }


def _get_pending_paid_invoice_names() -> List[str]:
    invoice_rows = frappe.get_all(
        "Sales Invoice",
        filters={
            "docstatus": 1,
            "outstanding_amount": ["<=", 0],
        },
        fields=["name", "nc_payment_status"],
    )

    return [
        row.name
        for row in invoice_rows
        if (row.get("nc_payment_status") or "").upper() != "PAID"
    ]


def _is_invoice_pending_paid_status_sync(invoice) -> bool:
    invoice.reload()

    if invoice.docstatus != 1:
        return False

    if invoice.outstanding_amount > 0:
        return False

    return invoice.get("nc_payment_status") != "PAID"


def _update_digitax_payment_status_to_paid(invoice) -> bool:
    client = DigitaxClient(company=invoice.company)
    response = client.put(
        endpoint="/invoices",
        path_param=f"{invoice.nc_invoice_id}/payment-status",
        data={"payment_status": "PAID"},
        reference_doctype="Sales Invoice",
        reference_docname=invoice.name,
    )

    if not response:
        return False

    _update_invoice_from_response(invoice, response)
    return True


def _sync_paid_invoice_payment_status(invoice_name: str) -> bool:
    invoice = frappe.get_doc("Sales Invoice", invoice_name)

    if not _is_invoice_pending_paid_status_sync(invoice):
        return False

    if not _ensure_invoice_has_digitax_id(invoice):
        return False

    return _update_digitax_payment_status_to_paid(invoice)


def _log_paid_invoice_payment_status_failure(invoice_name: str, error: Exception) -> None:
    frappe.log_error(
        title="Hourly DigiTax Payment Status Retry Failed",
        message=(
            f"Sales Invoice: {invoice_name}\n"
            f"Payment Status: PAID\n"
            f"Error: {str(error)}\n{frappe.get_traceback()}"
        ),
    )


def _build_retry_result(
    processed_count: int, success_count: int, failed_invoices: List[str]
) -> Dict[str, Any]:
    result = {
        "processed": processed_count,
        "successful": success_count,
        "failed": len(failed_invoices),
        "failed_invoices": failed_invoices,
    }

    return result


def _log_paid_invoice_payment_status_retry_result(result: Dict[str, Any]) -> None:
    if not result["successful"] and not result["failed_invoices"]:
        return

    summary = [
        f"Processed: {result['processed']}",
        f"Successful: {result['successful']}",
        f"Failed: {result['failed']}",
    ]

    if result["failed_invoices"]:
        summary.append(
            "Invoices still pending DigiTax payment status: "
            + ", ".join(result["failed_invoices"])
        )
        frappe.log_error(
            title="Hourly DigiTax Payment Status Retry",
            message="\n".join(summary),
        )
        return

    frappe.logger().info("Hourly DigiTax Payment Status Retry\n" + "\n".join(summary))


def _sync_paid_invoice_payment_statuses(log_result: bool = True) -> Dict[str, Any]:
    """Retry DigiTax payment-status sync for fully-paid Sales Invoices."""
    invoice_names = _get_pending_paid_invoice_names()

    if not invoice_names:
        return _empty_retry_result()

    previous_mute_messages = getattr(frappe.flags, "mute_messages", False)
    frappe.flags.mute_messages = True

    success_count = 0
    failed_invoices: List[str] = []

    try:
        for invoice_name in invoice_names:
            try:
                if _sync_paid_invoice_payment_status(invoice_name):
                    success_count += 1
                else:
                    failed_invoices.append(invoice_name)
            except Exception as error:
                failed_invoices.append(invoice_name)
                _log_paid_invoice_payment_status_failure(invoice_name, error)
    finally:
        frappe.flags.mute_messages = previous_mute_messages

    result = _build_retry_result(len(invoice_names), success_count, failed_invoices)

    if log_result:
        _log_paid_invoice_payment_status_retry_result(result)

    return result


def sync_pending_paid_invoice_payment_statuses() -> None:
    """Scheduled task entrypoint for retrying DigiTax payment-status sync."""
    _sync_paid_invoice_payment_statuses(log_result=True)


def run_pending_paid_invoice_payment_status_retry() -> Dict[str, Any]:
    """Bench helper for manually retrying DigiTax payment-status sync.

    Run with:
        bench execute nigeria_compliance_via_digitax.tasks.run_pending_paid_invoice_payment_status_retry
    """
    return _sync_paid_invoice_payment_statuses(log_result=False)


def run_pending_sales_invoice_digitax_retry() -> Dict[str, Any]:
    """Bench helper for manually retrying DigiTax submission.

    Run with:
        bench execute nigeria_compliance_via_digitax.tasks.run_pending_sales_invoice_digitax_retry
    """
    return _retry_pending_sales_invoices_to_digitax(log_result=False)
