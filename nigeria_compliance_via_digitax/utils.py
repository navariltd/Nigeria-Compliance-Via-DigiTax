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
