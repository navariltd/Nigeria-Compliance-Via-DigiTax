# Copyright (c) 2026, Navari Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DigitaxProductCategory(Document):
    def before_save(self):
        commodity_type = frappe.db.get_value(
            "Digitax HS Code", self.hs_code, "category"
        )

        self.is_service = commodity_type == "Service"
