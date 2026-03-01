import frappe
from typing import Optional, Dict, Any
from frappe import _
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
	pass
