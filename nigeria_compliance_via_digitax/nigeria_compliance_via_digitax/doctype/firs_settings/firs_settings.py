# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from nigeria_compliance_via_digitax.utils import (
    fetch_country_codes,
    fetch_invoice_type_codes,
    fetch_tax_category_codes,
)


class FIRSSettings(Document):
    def after_insert(self):
        # Fetch reference codes when FIRS Settings is created for the first time
        fetch_digitax_reference_codes(self)

    def on_update(self):
        # Fetch reference codes on every update to ensure we have the latest data
        fetch_digitax_reference_codes(self)

def fetch_digitax_reference_codes(doc, method=None) -> None:
    """Fetch DigiTax reference data whenever FIRS Settings is saved or updated."""
    if not doc.company:
        return

    try:
        fetch_invoice_type_codes(company=doc.company)
        fetch_tax_category_codes(company=doc.company)
        fetch_country_codes(company=doc.company)
    except Exception:
        frappe.log_error(
            title="FIRS Settings Auto Fetch Failed",
            message=(
                f"FIRS Settings: {doc.name}\n"
                f"Company: {doc.company}\n"
                f"{frappe.get_traceback()}"
            ),
        )
        frappe.msgprint(
            msg=_(
                "FIRS Settings was saved, but automatic DigiTax reference code fetch failed. "
                "You can retry using the Fetch buttons."
            ),
            title=_("Auto Fetch Warning"),
            indicator="orange",
        )
