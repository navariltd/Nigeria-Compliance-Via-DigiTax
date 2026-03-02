import frappe
from typing import Optional, Dict, Any, List
from frappe import _
from frappe.utils import nowdate, get_datetime
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
    DigitaxAPIException,
)


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
    print("DEBUG: SUBMISSION PROCESS STARTED...")
    # Check if FIRS tracking is enabled for this company
    if not _should_submit_to_digitax(doc):
        return

    try:
        # Validate required data
        _validate_invoice_data(doc)

        invoice_payload = _build_invoice_payload(doc)
        client = DigitaxClient(company=doc.company)
        response = client.post(
            endpoint="/invoices",
            data=invoice_payload,
            reference_doctype="Sales Invoice",
            reference_docname=doc.name,
        )

        if response:
            # Map response fields to document fields
            _update_invoice_from_response(doc, response)

            frappe.msgprint(
                _("Invoice successfully submitted to DigiTax"),
                title=_("DigiTax Submission"),
                indicator="green",
            )

    except DigitaxAPIException as e:
        _handle_digitax_error(doc, e)
    except Exception as e:
        _handle_unexpected_error(doc, e)


def _should_submit_to_digitax(doc) -> bool:
    """
    Check if the invoice should be submitted to DigiTax.

    Args:
            doc: Sales Invoice document

    Returns:
            True if invoice should be submitted, False otherwise
    """
    if not frappe.db.exists("FIRS Settings", {"company": doc.company}):
        return False

    firs_settings = frappe.get_doc("FIRS Settings", {"company": doc.company})

    if not firs_settings.allow_firs_tracking_sales:
        return False

    return True


def _update_invoice_from_response(doc, response: Dict[str, Any]) -> None:
    """
    Update Sales Invoice fields from DigiTax API response.

    Args:
            doc: Sales Invoice document
            response: DigiTax API response dictionary
    """
    field_mapping = {
        "invoice_number": "nc_invoice_number",
        "signed_at": "nc_signed_at",
        "validated_at": "nc_validated_at",
        "payment_status": "nc_payment_status",
        "invoice_reference_number": "nc_invoice_reference_number",
        "tax_currency_code": "nc_tax_currency_code",
        "line_extension_amount": "nc_line_extension_amount",
        "charge_total_amount": "nc_charge_total_amount",
        "allowance_total_amount": "nc_allowance_total_amount",
        "tax_exclusive_amount": "nc_tax_exclusive_amount",
        "tax_inclusive_amount": "nc_tax_inclusive_amount",
        "payable_amount": "nc_payable_amount",
        "tax_amount": "nc_tax_amount",
    }

    datetime_fields = ["signed_at", "validated_at"]

    is_valid = True if response.get("is_valid") else False

    doc.db_set("nc_is_firs_valid", is_valid)

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

    if not doc.get("firs_invoice_type"):
        errors.append(_("FIRS Invoice Type is required"))

    if not doc.items:
        errors.append(_("Invoice must have at least one item"))

    for item in doc.items:
        if not item.get("digitax_id"):
            errors.append(
                _("Item {0} must be synced with DigiTax").format(item.item_code)
            )

        if not item.get("firs_tax_category"):
            errors.append(
                _("Item {0} must have a FIRS Tax Category").format(item.item_code)
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
    return {
        "invoice_date": doc.posting_date,
        "issue_date": nowdate(),
        "invoice_type_code": _get_invoice_type_code(doc.get("firs_invoice_type")),
        "document_currency_code": doc.currency,
        "trader_invoice_number": doc.name,
        "items": _map_invoice_items(doc.items),
    }


def _get_invoice_type_code(invoice_type_name: str) -> str:
    """
    Get the invoice type code from FIRS Invoice Type.

    Args:
            invoice_type_name: Name/value of the FIRS Invoice Type

    Returns:
            Invoice type code

    Raises:
            frappe.ValidationError: If invoice type not found
    """
    if not invoice_type_name:
        frappe.throw(_("Invoice type is required"))

    invoice_type = frappe.db.get_value(
        "FIRS Invoice Type", {"value": invoice_type_name}, ["code"], as_dict=False
    )

    if not invoice_type:
        frappe.throw(
            _(
                "FIRS Invoice Type '{0}' not found. Please fetch invoice types from DigiTax API."
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
                "quantity": item.qty,
                "unit_price": item.rate,
                "tax_rate": _get_tax_rate_from_firs_tax_category(
                    item.get("firs_tax_category")
                ),
            }
        )

    return mapped_items


def _get_tax_rate_from_firs_tax_category(tax_category_name: str) -> float:
    """
    Fetch the tax rate from FIRS Tax Category.

    Args:
            tax_category_name: Name of the FIRS Tax Category

    Returns:
            Tax rate as a float if found, otherwise 0
    """
    if not tax_category_name:
        return 0.0

    tax_rate = frappe.db.get_value(
        "FIRS Tax Category", {"category_name": tax_category_name}, "tax_rate"
    )

    return float(tax_rate) if tax_rate else 0.0


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

    frappe.msgprint(
        _(f"Sales Invoice: {doc.name}\nError: {str(error)}\n{frappe.get_traceback()}"),
        title=_("DigiTax Submission Warning"),
        indicator="orange",
    )


def set_firs_invoice_type(doc, method=None):
    """
    Auto-set FIRS Invoice Type based on invoice type.

    Args:
            doc: Sales Invoice document
            method: Hook method name (optional)
    """
    if not doc.get("firs_invoice_type"):
        if doc.is_return:
            doc.firs_invoice_type = "Credit Note"
        elif doc.is_debit_note:
            doc.firs_invoice_type = "Debit Note"
        else:
            doc.firs_invoice_type = "Commercial Invoice"


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
