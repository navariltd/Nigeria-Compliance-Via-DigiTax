# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

"""
Utility functions for managing Digitax HS Codes and Service Codes.
These can be called from the Frappe console or programmatically.
"""

import frappe
from nigeria_compliance_via_digitax.install import (
    load_hs_codes,
    load_service_codes,
    reload_digitax_codes,
)


@frappe.whitelist()
def reload_codes():
    """
    Reload all Digitax codes from remote sources.
    This will clear existing codes and reload them.

    Usage from Frappe console:
            frappe.call("nigeria_compliance_via_digitax.utils.reload_codes")
    """
    if not frappe.has_permission("Digitax HS Code", "write"):
        frappe.throw("You don't have permission to reload Digitax codes.")

    reload_digitax_codes()
    frappe.msgprint("Digitax codes have been reloaded successfully.")


@frappe.whitelist()
def get_codes_stats():
    """
    Get statistics about loaded Digitax codes.

    Returns:
            dict: Statistics including counts of Items and Services
    """
    return {
        "total_codes": frappe.db.count("Digitax HS Code"),
        "item_codes": frappe.db.count("Digitax HS Code", {"category": "Item"}),
        "service_codes": frappe.db.count("Digitax HS Code", {"category": "Service"}),
    }


@frappe.whitelist()
def load_codes_if_missing():
    """
    Load codes only if they don't exist.
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

    new_stats = get_codes_stats()
    return {"message": "Loaded missing codes successfully", "stats": new_stats}
