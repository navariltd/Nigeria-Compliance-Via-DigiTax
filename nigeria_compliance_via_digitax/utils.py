# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

"""
Utility functions for managing NRS HS Codes, Service Codes, and Tax Categories.
These can be called from the Frappe console or programmatically.
"""


import frappe
from frappe import _
from nigeria_compliance_via_digitax.install import (
    load_hs_codes,
    load_service_codes,
    reload_digitax_category_codes,
)
from nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.api.classes.client import (
    DigitaxClient,
)
from typing import Union


@frappe.whitelist()
def reload_codes():
    """
    Reload all Digitax codes from remote sources.
    This will clear existing codes and reload them.

    Usage from Frappe console:
                frappe.call("nigeria_compliance_via_digitax.utils.reload_codes")
    """
    if not frappe.has_permission("NRS HS Code", "write"):
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
    if frappe.db.exists("DocType", "NRS Tax Category"):
        tax_category_count = frappe.db.count("NRS Tax Category")

    return {
        "total_codes": frappe.db.count("NRS HS Code"),
        "item_codes": frappe.db.count("NRS HS Code", {"category": "Item"}),
        "service_codes": frappe.db.count("NRS HS Code", {"category": "Service"}),
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

    new_stats = get_codes_stats()
    return {"message": "Loaded missing codes successfully", "stats": new_stats}


def _fetch_resources_from_api(client, endpoint, reference_doctype):
    """
    Generic function to fetch resources from DigiTax API.

    Args:
        client: DigitaxClient instance
        endpoint: API endpoint to fetch from
        reference_doctype: DocType making the request

    Returns:
        list: List of resource dictionaries
    """
    reference_docname = (
        client.settings.name
        if reference_doctype == "NRS Settings" and getattr(client, "settings", None)
        else client.company
    )

    response = client.get(
        endpoint=endpoint,
        reference_doctype=reference_doctype,
        reference_docname=reference_docname,
    )

    if not response:
        frappe.throw(
            _("Failed to fetch data from DigiTax API endpoint: {0}").format(endpoint)
        )

    if not isinstance(response, list):
        frappe.throw(_("Invalid response format. Expected an array of resources."))

    return response or []


def _process_resources(resources, doctype, mapper_func):
    """
    Generic function to process resources and create/update documents.

    Args:
        resources: List of resource dictionaries
        doctype: DocType name to create/update
        mapper_func: Function to map API response to document fields

    Returns:
        tuple: (stats dict, errors list)
    """
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    errors = []

    for resource in resources:
        try:
            action = _process_single_resource(resource, doctype, mapper_func)
            stats[action] += 1

        except Exception as e:
            resource_id = resource.get("code") or resource.get("id", "Unknown")
            error_msg = f"Failed to process {doctype} {resource_id}: {str(e)}"
            frappe.logger().error(error_msg)
            errors.append(error_msg)
            stats["errors"] += 1

    return stats, errors


def _process_single_resource(resource_data, doctype, mapper_func):
    """
    Process a single resource and create/update the document.

    Args:
        resource_data: Dictionary with resource data
        doctype: DocType name to create/update
        mapper_func: Function to map API response to document fields

    Returns:
        str: Action taken - 'created', 'updated', or 'skipped'
    """
    doc_data = mapper_func(resource_data)

    if not doc_data:
        raise ValueError(f"Invalid resource data: {resource_data}")

    # Get the unique identifier field for this doctype
    unique_field, unique_value = _get_unique_identifier(doctype, doc_data)

    if frappe.db.exists(doctype, {unique_field: unique_value}):
        return _update_existing_document(doctype, unique_field, unique_value, doc_data)

    # Create new document
    doc = frappe.get_doc(doc_data)
    doc.insert(ignore_permissions=True)
    return "created"


def _get_unique_identifier(doctype, doc_data):
    """
    Get the unique identifier field and value for a doctype.

    Args:
        doctype: DocType name
        doc_data: Document data dictionary

    Returns:
        tuple: (field_name, field_value)
    """
    # Map doctypes to their unique identifier fields
    unique_fields = {
        "NRS Invoice Type": "code",
        "NRS Tax Category": "category_name",
        "NRS Country Codes": "country",
    }

    field_name = unique_fields.get(doctype, "name")
    field_value = doc_data.get(field_name)

    return field_name, field_value


def _update_existing_document(doctype, unique_field, unique_value, new_data):
    """
    Update an existing document if any fields have changed.

    Args:
        doctype: DocType name
        unique_field: Unique identifier field name
        unique_value: Unique identifier value
        new_data: New document data

    Returns:
        str: 'updated' if changes were made, 'skipped' if no changes
    """
    doc = frappe.get_doc(doctype, {unique_field: unique_value})

    # Check if any fields need updating
    has_changes = False
    for field, value in new_data.items():
        if field != "doctype" and getattr(doc, field, None) != value:
            setattr(doc, field, value)
            has_changes = True

    if has_changes:
        doc.save(ignore_permissions=True)
        return "updated"

    return "skipped"


def _build_result_message(stats, resource_name):
    """
    Build a user-friendly result message from processing statistics.

    Args:
        stats: Dictionary containing processing statistics
        resource_name: Name of the resource type (e.g., "Invoice Type Codes")

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

    message = f"{resource_name} fetched successfully."
    if result_parts:
        message += " " + ", ".join(result_parts) + "."

    if stats["errors"]:
        message += f" {stats['errors']} error(s) occurred."

    return message


def _map_invoice_type(api_data):
    """
    Map API response to NRS Invoice Type document fields.

    Args:
        api_data: Dictionary from API response

    Returns:
        dict: Mapped document data
    """
    code = api_data.get("code")
    value = api_data.get("value")

    if not code or not value:
        return None

    return {"doctype": "NRS Invoice Type", "code": code, "value": value}


@frappe.whitelist()
def fetch_invoice_type_codes(company: Union[str, None] = None):
    """
    Fetch Invoice Type Codes from DigiTax API and create NRS Invoice Type documents.

    Args:
        company: Company name (optional, defaults to user's default company)

    Returns:
        dict: Result containing success status, message, and statistics
    """
    try:
        client = DigitaxClient(company=company)
        resources = _fetch_resources_from_api(
            client, "resources/invoice-types", "NRS Settings"
        )
        stats, errors = _process_resources(
            resources, "NRS Invoice Type", _map_invoice_type
        )

        frappe.db.commit()

        result_message = _build_result_message(stats, "Invoice Type Codes")

        return {
            "success": True,
            "message": result_message,
            "stats": {
                "total_fetched": len(resources),
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


def _map_tax_category(api_data):
    """
    Map API response to NRS Tax Category document fields.

    API Response fields:
        - code -> tax_code
        - name -> category_name
        - tax_rate -> tax_rate
        - has_rate -> has_tax_rate

    Args:
        api_data: Dictionary from API response

    Returns:
        dict: Mapped document data
    """
    code = api_data.get("code")
    name = api_data.get("name")
    tax_rate = api_data.get("tax_rate")
    has_rate = api_data.get("has_rate", False)

    if not code or not name:
        return None

    return {
        "doctype": "NRS Tax Category",
        "tax_code": code,
        "category_name": name,
        "tax_rate": tax_rate,
        "has_tax_rate": 1 if has_rate else 0,
    }


@frappe.whitelist()
def fetch_tax_category_codes(company: Union[str, None] = None):
    """
    Fetch Tax Category Codes from DigiTax API and create NRS Tax Category documents.

    Args:
        company: Company name (optional, defaults to user's default company)

    Returns:
        dict: Result containing success status, message, and statistics
    """
    try:
        client = DigitaxClient(company=company)
        resources = _fetch_resources_from_api(
            client, "resources/tax-categories", "NRS Settings"
        )
        stats, errors = _process_resources(
            resources, "NRS Tax Category", _map_tax_category
        )

        frappe.db.commit()

        result_message = _build_result_message(stats, "Tax Category Codes")

        return {
            "success": True,
            "message": result_message,
            "stats": {
                "total_fetched": len(resources),
                "created": stats["created"],
                "updated": stats["updated"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
            },
            "errors": errors if errors else None,
        }

    except Exception as e:
        frappe.log_error(
            title="Fetch Tax Category Codes Error", message=frappe.get_traceback()
        )
        frappe.throw(_("Error fetching tax category codes: {0}").format(str(e)))


def _map_country_codes(api_data):
    """
    Map API response to NRS Country Codes document fields.

    API Response fields:
        - name -> country
        - alpha2 -> alpha2
        - alpha3 -> alpha3

    Args:
        api_data: Dictionary from API response

    Returns:
        dict: Mapped document data
    """
    name = api_data.get("name")
    alpha2 = api_data.get("alpha2")
    alpha3 = api_data.get("alpha3")

    if not name or not alpha2 or not alpha3:
        return None

    return {
        "doctype": "NRS Country Codes",
        "country": name,
        "alpha2": alpha2,
        "alpha3": alpha3,
    }


@frappe.whitelist()
def fetch_country_codes(company: Union[str, None] = None):
    """
    Fetch Country Codes from DigiTax API and create NRS Country Codes documents.

    Args:
        company: Company name (optional, defaults to user's default company)

    Returns:
        dict: Result containing success status, message, and statistics
    """
    try:
        client = DigitaxClient(company=company)
        resources = _fetch_resources_from_api(
            client, "resources/countries", "NRS Settings"
        )
        stats, errors = _process_resources(
            resources, "NRS Country Codes", _map_country_codes
        )

        frappe.db.commit()

        result_message = _build_result_message(stats, "Country Codes")

        return {
            "success": True,
            "message": result_message,
            "stats": {
                "total_fetched": len(resources),
                "created": stats["created"],
                "updated": stats["updated"],
                "skipped": stats["skipped"],
                "errors": stats["errors"],
            },
            "errors": errors if errors else None,
        }

    except Exception as e:
        frappe.log_error(
            title="Fetch Country Codes Error", message=frappe.get_traceback()
        )
        frappe.throw(_("Error fetching country codes: {0}").format(str(e)))
