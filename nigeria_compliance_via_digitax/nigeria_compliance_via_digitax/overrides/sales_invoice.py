import re
import frappe
import json
from typing import Optional, Dict, Any, List
from frappe import _
from frappe.model.naming import make_autoname
from frappe.utils import nowdate, get_datetime
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
    DigitaxAPIException,
)


def autoname_sales_invoice(doc, method: Optional[str] = None) -> None:
    """
    Custom autoname for Sales Invoice.

    Generates names in the format: ACC-SINV-{CUSTOMER}-####
    where #### is a zero-padded 4-digit sequence tracked per customer.

    Args:
        doc: The Sales Invoice document
        method: Hook method name (optional, not used)
    """
    customer_part = re.sub(r"[^A-Za-z0-9]", "-", doc.customer or "").upper()
    customer_part = re.sub(r"-+", "-", customer_part).strip("-")
    customer_part = customer_part[:12].strip("-")
    doc.name = make_autoname(f"ACC-SINV-{customer_part}-.####")


def submit_sales_invoice(doc, method: Optional[str] = None) -> None:
    """
    Handle Sales Invoice submission to synchronize with DigiTax API.

    This function is called via hooks on Sales Invoice submission.
    It checks if the invoice is linked to a DigiTax party and item, then
    prepares the payload and submits the invoice data to DigiTax.

    Args:
        doc: The Sales Invoice document being submitted
        method: Hook method name (optional, not used)
    """

    try:
        _validate_invoice_data(doc)

        invoice_payload = _build_invoice_payload(doc)
        client = DigitaxClient(company=doc.company)

        # Determine endpoint based on invoice type
        if doc.is_return:
            endpoint = "/credit-notes"
        else:
            endpoint = "/invoices"

        response = client.post(
            endpoint=endpoint,
            data=invoice_payload,
            reference_doctype="Sales Invoice",
            reference_docname=doc.name,
        )

        if response:
            # Map response fields to document fields
            _update_invoice_from_response(doc, response)

            if doc.is_return and doc.get("return_against"):
                _sync_original_invoice_payment_status_after_credit_note(doc)

            frappe.msgprint(
                _("Invoice successfully submitted to DigiTax"),
                title=_("DigiTax Submission"),
                indicator="green",
            )

    except DigitaxAPIException as e:
        _handle_digitax_error(doc, e)
    except Exception as e:
        _handle_unexpected_error(doc, e)


def sync_paid_invoice_payment_status(doc, method: Optional[str] = None) -> None:
    """
    Sync payment status to PAID in DigiTax for invoices that are fully paid on submit.

    This primarily covers POS flows where the invoice is submitted at checkout and
    no later Payment Entry/Journal Entry hook is expected to update DigiTax.

    Args:
        doc: The submitted Sales Invoice document
        method: Hook method name (optional, not used)
    """
    if doc.docstatus != 1:
        return

    if not doc.get("is_pos"):
        return

    if not doc.get("nc_invoice_id"):
        return

    if doc.get("nc_payment_status") == "PAID":
        return

    if doc.outstanding_amount > 0:
        return

    try:
        client = DigitaxClient(company=doc.company)
        response = client.put(
            endpoint="/invoices",
            path_param=f"{doc.nc_invoice_id}/payment-status",
            data={"payment_status": "PAID"},
            reference_doctype="Sales Invoice",
            reference_docname=doc.name,
        )

        if response:
            _update_invoice_from_response(doc, response)
            frappe.logger().info(
                f"Payment status updated for Sales Invoice {doc.name} in DigiTax: PAID "
                f"(fully paid on submit)"
            )

    except DigitaxAPIException as e:
        frappe.log_error(
            title="DigiTax Payment Status Sync Failed",
            message=(
                f"Sales Invoice: {doc.name}\n"
                f"Payment Status: PAID\n"
                f"Error: {str(e)}"
            ),
        )
    except Exception as e:
        frappe.log_error(
            title="DigiTax Payment Status Sync Error",
            message=(
                f"Sales Invoice: {doc.name}\n"
                f"Payment Status: PAID\n"
                f"Error: {str(e)}\n{frappe.get_traceback()}"
            ),
        )


def sync_cancelled_invoice_payment_status(doc, method: Optional[str] = None) -> None:
    """
    Sync payment status to REJECTED in DigiTax when a Sales Invoice is cancelled.

    Args:
        doc: The cancelled Sales Invoice document
        method: Hook method name (optional, not used)
    """
    if doc.docstatus != 2:
        return

    if not doc.get("nc_invoice_id"):
        return

    if doc.get("nc_payment_status") == "REJECTED":
        return

    try:
        client = DigitaxClient(company=doc.company)
        response = client.put(
            endpoint="/invoices",
            path_param=f"{doc.nc_invoice_id}/payment-status",
            data={"payment_status": "REJECTED"},
            reference_doctype="Sales Invoice",
            reference_docname=doc.name,
        )

        if response:
            _update_invoice_from_response(doc, response)
            frappe.logger().info(
                f"Payment status updated for cancelled Sales Invoice {doc.name} in DigiTax: REJECTED"
            )

    except DigitaxAPIException as e:
        frappe.log_error(
            title="DigiTax Cancelled Invoice Status Sync Failed",
            message=(
                f"Sales Invoice: {doc.name}\n"
                f"Payment Status: REJECTED\n"
                f"Error: {str(e)}"
            ),
        )
    except Exception as e:
        frappe.log_error(
            title="DigiTax Cancelled Invoice Status Sync Error",
            message=(
                f"Sales Invoice: {doc.name}\n"
                f"Payment Status: REJECTED\n"
                f"Error: {str(e)}\n{frappe.get_traceback()}"
            ),
        )


def _update_invoice_from_response(doc, response: Dict[str, Any]) -> None:
    """
    Update Sales Invoice fields from DigiTax API response.

    Args:
        doc: Sales Invoice document
        response: DigiTax API response dictionary
    """
    field_mapping = {
        "id": "nc_invoice_id",
        "invoice_number": "nc_invoice_number",
        "signed_at": "nc_signed_at",
        "validated_at": "nc_validated_at",
        "payment_status": "nc_payment_status",
        "invoice_reference_number": "nc_invoice_reference_number",
    }

    datetime_fields = ["signed_at", "validated_at"]

    is_valid = True if response.get("is_valid") else False

    doc.db_set("nc_is_nrs_valid", is_valid)

    if response.get("signed_at") and is_valid:
        doc.db_set("nc_submitted_to_nrs", True)

    for response_field, doc_field in field_mapping.items():
        if response.get(response_field) is not None:
            value = response.get(response_field)

            # Convert datetime strings to proper datetime objects
            if response_field in datetime_fields and isinstance(value, str):
                try:
                    value = get_datetime(value)
                except Exception as e:
                    frappe.log_error(
                        title="DateTime Conversion Error",
                        message=f"Failed to convert {response_field}: {value}\nError: {str(e)}",
                    )
                    continue

            doc.db_set(doc_field, value, update_modified=False)


def _validate_invoice_data(doc) -> None:
    """
    Validate that the invoice has all required data for DigiTax submission.

    Args:
        doc: Sales Invoice document

    Raises:
        frappe.ValidationError: If required data is missing
    """
    errors = []

    if not doc.get("nrs_invoice_type"):
        errors.append(_("NRS Invoice Type is required"))

    if not doc.items:
        errors.append(_("Invoice must have at least one item"))

    for item in doc.items:
        if not item.get("digitax_id"):
            errors.append(
                _("Item {0} must be synced with DigiTax").format(item.item_code)
            )

    if errors:
        frappe.throw("<br>".join(errors), title=_("DigiTax Validation Failed"))


def _build_invoice_payload(doc) -> Dict[str, Any]:
    """
    Build the invoice payload for DigiTax API.

    Args:
        doc: Sales Invoice document

    Returns:
        Dictionary containing invoice data for DigiTax API
    """
    payload = {
        "invoice_date": doc.posting_date,
        "issue_date": nowdate(),
        "invoice_type_code": _get_invoice_type_code(doc.get("nrs_invoice_type")),
        "document_currency_code": doc.currency,
        "trader_invoice_number": doc.name,
        "items": _map_invoice_items(doc.items),
    }

    # For credit notes
    if doc.is_return and doc.get("return_against"):
        original_invoice = frappe.get_doc("Sales Invoice", doc.return_against)
        if original_invoice.get("nc_invoice_id"):
            payload["invoice_id"] = original_invoice.nc_invoice_id
            payload["return_date"] = doc.posting_date
        else:
            frappe.throw(
                _(
                    "Original invoice {0} does not have a DigiTax invoice ID. "
                    "Please ensure the original invoice has been submitted to DigiTax."
                ).format(doc.return_against)
            )

    return payload


def _get_invoice_type_code(invoice_type_name: str) -> str:
    """
    Get the invoice type code from NRS Invoice Type.

    Args:
        invoice_type_name: Name/value of the NRS Invoice Type

    Returns:
        Invoice type code

    Raises:
        frappe.ValidationError: If invoice type not found
    """
    if not invoice_type_name:
        frappe.throw(_("Invoice type is required"))

    invoice_type = frappe.db.get_value(
        "NRS Invoice Type", {"value": invoice_type_name}, ["code"], as_dict=False
    )

    if not invoice_type:
        frappe.throw(
            _(
                "NRS Invoice Type '{0}' not found. Please fetch invoice types from DigiTax API."
            ).format(invoice_type_name)
        )

    return invoice_type


def _map_invoice_items(items: List) -> List[Dict[str, Any]]:
    """
    Map Sales Invoice items to DigiTax API format.

    Args:
        items: List of Sales Invoice Item documents

    Returns:
        List of mapped item dictionaries
    """
    mapped_items = []

    for item in items:
        mapped_items.append(
            {
                "item_id": item.get("digitax_id"),
                "quantity": abs(item.qty),
                "unit_price": item.rate,
                "tax_rate": _get_calculated_tax_rate(item),
            }
        )

    return mapped_items


def _get_tax_rate_from_nrs_tax_category(tax_category_name: str) -> float:
    """
    Fetch the tax rate from NRS Tax Category.

    Args:
        tax_category_name: Name of the NRS Tax Category

    Returns:
        Tax rate as a float if found, otherwise 0
    """
    if not tax_category_name:
        return 0.0

    tax_rate = frappe.db.get_value(
        "NRS Tax Category", {"category_name": tax_category_name}, "tax_rate"
    )

    return float(tax_rate) if tax_rate else 0.0


def _get_calculated_tax_rate(item) -> float:
    """
    Extracts the tax rate from the item's calculated tax rate JSON.
    """
    if not item.get("item_tax_rate"):
        return _get_tax_rate_from_nrs_tax_category(item.get("nrs_tax_category"))

    try:
        tax_map = json.loads(item.item_tax_rate)
        rates = list(tax_map.values())
        return (float(rates[0]) / 100) if rates else 0.0
    except (json.JSONDecodeError, ValueError, IndexError):
        return 0.0


def _handle_digitax_error(doc, error: DigitaxAPIException) -> None:
    """
    Handle DigiTax API errors during invoice submission.

    Args:
        doc: Sales Invoice document
        error: DigiTax API exception
    """
    frappe.log_error(
        title="DigiTax Invoice Submission Failed",
        message=f"Sales Invoice: {doc.name}\nError: {str(error)}",
    )

    frappe.msgprint(
        _(
            "Failed to submit invoice to DigiTax: {0}<br>The invoice has been submitted locally."
        ).format(str(error)),
        title=_("DigiTax Submission Warning"),
        indicator="orange",
    )


def _handle_unexpected_error(doc, error: Exception) -> None:
    """
    Handle unexpected errors during invoice submission.

    Args:
        doc: Sales Invoice document
        error: Exception raised
    """
    frappe.log_error(
        title="DigiTax Invoice Submission Error",
        message=f"Sales Invoice: {doc.name}\nError: {str(error)}\n{frappe.get_traceback()}",
    )

    error_message = (
        f"Sales Invoice: {doc.name}\nError: {str(error)}\n{frappe.get_traceback()}"
    )
    frappe.msgprint(
        error_message,
        title=_("DigiTax Submission Warning"),
        indicator="orange",
    )


def set_nrs_invoice_type(doc, method=None):
    """
    Auto-set NRS Invoice Type based on invoice type.

    Args:
        doc: Sales Invoice document
        method: Hook method name (optional)
    """
    if not doc.get("nrs_invoice_type"):
        if doc.is_return:
            doc.nrs_invoice_type = "Credit Note"
        elif doc.is_debit_note:
            doc.nrs_invoice_type = "Debit Note"
        else:
            doc.nrs_invoice_type = "Commercial Invoice"


@frappe.whitelist()
def get_invoice_from_digitax(
    sales_invoice: str, invoice_reference_number: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch invoice data from DigiTax API and update the Sales Invoice.

    This function is called from the 'Get Invoice' button on Sales Invoice.
    It retrieves the latest invoice data from DigiTax and updates the document.

    Args:
        sales_invoice: Name of the Sales Invoice document
        invoice_reference_number: The invoice reference number from DigiTax

    Returns:
        Dictionary containing the updated invoice data

    Raises:
        frappe.ValidationError: If the invoice is not found or not submitted
    """
    # Validate that the invoice exists and is submitted
    if not frappe.db.exists("Sales Invoice", sales_invoice):
        frappe.throw(_("Sales Invoice {0} not found").format(sales_invoice))

    doc = frappe.get_doc("Sales Invoice", sales_invoice)

    if doc.docstatus != 1:
        frappe.throw(_("Sales Invoice must be submitted"))

    if not invoice_reference_number:
        frappe.throw(_("Invoice Reference Number is required"))

    try:
        # Make GET request to DigiTax API
        client = DigitaxClient(company=doc.company)
        response = client.get(
            endpoint=f"/invoices/irn/{invoice_reference_number}",
            reference_doctype="Sales Invoice",
            reference_docname=doc.name,
        )

        if response:
            # Update invoice fields from response
            _update_invoice_from_response(doc, response)

            frappe.msgprint(
                _("Invoice data successfully fetched from DigiTax"),
                title=_("DigiTax Get Invoice"),
                indicator="green",
            )

            return response

    except DigitaxAPIException as e:
        frappe.log_error(
            title="DigiTax Get Invoice Failed",
            message=f"Sales Invoice: {doc.name}\nError: {str(e)}",
        )
        frappe.throw(
            _("Failed to fetch invoice from DigiTax: {0}").format(str(e)),
            title=_("DigiTax Error"),
        )

    except Exception as e:
        frappe.log_error(
            title="DigiTax Get Invoice Error",
            message=f"Sales Invoice: {doc.name}\nError: {str(e)}\n{frappe.get_traceback()}",
        )
        frappe.throw(
            _("An unexpected error occurred: {0}").format(str(e)),
            title=_("Error"),
        )


def _sync_original_invoice_payment_status_after_credit_note(credit_note_doc) -> None:
    """
    Synchronize the payment status of the original sales invoice after a credit note is created.

    This function retrieves the original sales invoice referenced in the credit note and updates
    its payment status to "PAID" in DigiTax when the remaining outstanding amount becomes zero
    (i.e., when the credit note fully offsets the invoice balance).

    Args:
        credit_note_doc: The credit note document object containing the reference to the
                         original sales invoice via the "return_against" field.

    Returns:
        None

    Raises:
        Logs errors to Frappe's error log in the following cases:
        - DigitaxAPIException: When the API call to update payment status fails.
        - Exception: For any other unexpected errors during execution.

    Notes:
        - Requires the original invoice to exist and be in submitted state (docstatus == 1).
        - Requires the original invoice to have a DigiTax invoice ID (nc_invoice_id).
        - Only updates payment status when remaining_amount equals zero.
        - Updates the invoice document with the response data from DigiTax.
    """
    try:
        original_invoice_name = credit_note_doc.get("return_against")
        if not original_invoice_name:
            return

        if not frappe.db.exists("Sales Invoice", original_invoice_name):
            return

        invoice = frappe.get_doc("Sales Invoice", original_invoice_name)
        invoice.reload()

        if invoice.docstatus != 1:
            return

        if not invoice.get("nc_invoice_id"):
            frappe.log_error(
                title="Credit Note Payment Status Sync Skipped",
                message=(
                    f"Original Sales Invoice {invoice.name} has no DigiTax invoice ID. "
                    f"Credit Note: {credit_note_doc.name}"
                ),
            )
            return

        remaining_amount = invoice.outstanding_amount + credit_note_doc.grand_total

        if remaining_amount != 0:
            return

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

    except DigitaxAPIException as e:
        frappe.log_error(
            title="Credit Note Payment Status Sync Failed",
            message=(
                f"Credit Note: {credit_note_doc.name}\n"
                f"Original Invoice: {credit_note_doc.get('return_against')}\n"
                f"Error: {str(e)}"
            ),
        )
    except Exception as e:
        frappe.log_error(
            title="Credit Note Payment Status Sync Error",
            message=(
                f"Credit Note: {credit_note_doc.name}\n"
                f"Original Invoice: {credit_note_doc.get('return_against')}\n"
                f"Error: {str(e)}\n{frappe.get_traceback()}"
            ),
        )
