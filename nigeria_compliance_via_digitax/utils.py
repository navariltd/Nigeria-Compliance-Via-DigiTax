# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

"""
Utility functions for managing FIRS HS Codes, Service Codes, and Tax Categories.
These can be called from the Frappe console or programmatically.
"""


import frappe
from frappe import _
from nigeria_compliance_via_digitax.install import (
    load_hs_codes,
    load_service_codes,
    load_tax_categories,
    reload_digitax_category_codes,
)
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
)
from typing import Union, Any, Dict, List


@frappe.whitelist()
def reload_codes():
    """
    Reload all Digitax codes from remote sources.
    This will clear existing codes and reload them.

    Usage from Frappe console:
                frappe.call("nigeria_compliance_via_digitax.utils.reload_codes")
    """
    if not frappe.has_permission("FIRS HS Code", "write"):
        frappe.throw(_("You don't have permission to reload Digitax codes."))

    reload_digitax_category_codes()
    frappe.msgprint(_("Digitax codes have been reloaded successfully."))


@frappe.whitelist()
def get_codes_stats():
    """
    Get statistics about loaded Digitax codes and Tax Categories.

    Returns:
                dict: Statistics including counts of Items, Services, and Tax Categories
    """
    tax_category_count = 0
    if frappe.db.exists("DocType", "Tax Category"):
        tax_category_count = frappe.db.count("Tax Category")

    return {
        "total_codes": frappe.db.count("FIRS HS Code"),
        "item_codes": frappe.db.count("FIRS HS Code", {"category": "Item"}),
        "service_codes": frappe.db.count("FIRS HS Code", {"category": "Service"}),
        "tax_categories": tax_category_count,
    }


@frappe.whitelist()
def load_codes_if_missing():
    """
    Load codes and tax categories only if they don't exist.
    Useful for ensuring codes are available without duplicating.

    Usage from Frappe console:
                frappe.call("nigeria_compliance_via_digitax.utils.load_codes_if_missing")
    """
    stats = get_codes_stats()

    if stats["item_codes"] == 0:
        frappe.logger().info("Loading HS codes (Items)...")
        load_hs_codes()

    if stats["service_codes"] == 0:
        frappe.logger().info("Loading service codes...")
        load_service_codes()

    if stats["tax_categories"] == 0:
        frappe.logger().info("Loading tax categories...")
        load_tax_categories()

    new_stats = get_codes_stats()
    return {"message": "Loaded missing codes successfully", "stats": new_stats}


@frappe.whitelist()
def fetch_invoice_type_codes(company: Union[str, None] = None) -> dict[Any, Any]:
    """
    Fetch Invoice Type Codes from DigiTax API and create FIRS Invoice Type documents.

    Args:
        company: Company name (optional, defaults to user's default company)

    Returns:
        dict: Result containing success status, message, and statistics
    """
    try:
        client = DigitaxClient(company=company)
        invoice_types = _fetch_invoice_types_from_api(client)
        stats, errors = _process_invoice_types(invoice_types)

        frappe.db.commit()

        result_message = _build_result_message(stats)

        return {
            "success": True,
            "message": result_message,
            "stats": {
                "total_fetched": len(invoice_types),
                "created": stats["created"],
                "updated": stats["updated"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
            },
            "errors": errors if errors else None,
        }

    except Exception as e:
        frappe.log_error(
            title="Fetch Invoice Type Codes Error", message=frappe.get_traceback()
        )
        frappe.throw(_("Error fetching invoice type codes: {0}").format(str(e)))
        return {"success": False, "message": str(e), "stats": None, "errors": [str(e)]}


def _validate_invoice_types_response(response):
    """
    Validate the API response for invoice types.

    Args:
        response: API response to validate

    Raises:
        frappe.ValidationError: If response is invalid
    """
    if not response:
        frappe.throw(_("Failed to fetch invoice type codes from DigiTax API"))

    if not isinstance(response, list):
        frappe.throw(_("Invalid response format. Expected an array of invoice types."))


def _process_single_invoice_type(invoice_type_data):
    """
    Process a single invoice type and create/update the FIRS Invoice Type document.

    Args:
        invoice_type_data: Dictionary with 'code' and 'value' fields

    Returns:
        str: Action taken - 'created', 'updated', 'skipped', or 'error'

    Raises:
        Exception: If processing fails
    """
    code = invoice_type_data.get("code")
    value = invoice_type_data.get("value")

    if not code or not value:
        raise ValueError(f"Invalid invoice type data: {invoice_type_data}")

    if frappe.db.exists("FIRS Invoice Type", {"code": code}):
        doc = frappe.get_doc("FIRS Invoice Type", {"code": code})
        if doc.value != value:
            doc.value = value
            doc.save(ignore_permissions=True)
            return "updated"
        return "skipped"

    doc = frappe.get_doc({"doctype": "FIRS Invoice Type", "code": code, "value": value})
    doc.insert(ignore_permissions=True)
    return "created"


def _build_result_message(stats):
    """
    Build a user-friendly result message from processing statistics.

    Args:
        stats: Dictionary containing processing statistics

    Returns:
        str: Formatted result message
    """
    result_parts = []

    if stats["created"]:
        result_parts.append(f"{stats['created']} created")
    if stats["updated"]:
        result_parts.append(f"{stats['updated']} updated")
    if stats["skipped"]:
        result_parts.append(f"{stats['skipped']} unchanged")

    message = "Invoice Type Codes fetched successfully."
    if result_parts:
        message += " " + ", ".join(result_parts) + "."

    if stats["errors"]:
        message += f" {stats['errors']} error(s) occurred."

    return message


def _fetch_invoice_types_from_api(client):
    """
    Fetch invoice types from DigiTax API.

    Args:
        client: DigitaxClient instance

    Returns:
        list: List of invoice type dictionaries

    Raises:
        frappe.ValidationError: If response is invalid
    """
    response = client.get(
        endpoint="resources/invoice-types",
        reference_doctype="FIRS Settings",
        reference_docname=client.company,
    )
    _validate_invoice_types_response(response)
    return response or []


def _process_invoice_types(invoice_types):
    """
    Process all invoice types and create/update documents.

    Args:
        invoice_types: List of invoice type dictionaries

    Returns:
        dict: Statistics including counts and errors
    """
    stats = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }
    errors = []

    for invoice_type in invoice_types:
        try:
            action = _process_single_invoice_type(invoice_type)
            stats[action] += 1

        except Exception as e:
            code = invoice_type.get("code", "Unknown")
            error_msg = f"Failed to process invoice type {code}: {str(e)}"
            frappe.logger().error(error_msg)
            errors.append(error_msg)
            stats["errors"] += 1

    return stats, errors
