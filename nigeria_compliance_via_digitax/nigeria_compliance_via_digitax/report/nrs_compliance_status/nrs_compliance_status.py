import frappe
from frappe import _
from pypika import Case, Order
from pypika.functions import Upper


def execute(filters: dict | None = None):
	filters = filters or {}
	_validate_filters(filters)

	return get_columns(), get_data(filters)


def _validate_filters(filters: dict) -> None:
	if not filters.get("company"):
		frappe.throw(_("Company is required"))


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Invoice"),
			"fieldname": "invoice",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 190,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Posting Date"),
			"fieldname": "posting_date",
			"fieldtype": "Date",
			"width": 110,
		},
		{
			"label": _("Invoice Type"),
			"fieldname": "invoice_type",
			"fieldtype": "Data",
			"width": 140,
		},
		{
			"label": _("Grand Total"),
			"fieldname": "grand_total",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("Outstanding Amount"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 150,
		},
		{
			"label": _("DigiTax Invoice ID"),
			"fieldname": "digitax_invoice_id",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Invoice Number"),
			"fieldname": "digitax_invoice_number",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Reference Number"),
			"fieldname": "invoice_reference_number",
			"fieldtype": "Data",
			"width": 190,
		},
		{
			"label": _("Submitted To NRS"),
			"fieldname": "submitted_to_nrs",
			"fieldtype": "Check",
			"width": 130,
		},
		{
			"label": _("NRS Valid"),
			"fieldname": "is_nrs_valid",
			"fieldtype": "Check",
			"width": 100,
		},
		{
			"label": _("Payment Status"),
			"fieldname": "payment_status",
			"fieldtype": "Data",
			"width": 130,
		},
		{
			"label": _("Signed At"),
			"fieldname": "signed_at",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": _("Validated At"),
			"fieldname": "validated_at",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": _("Compliance Status"),
			"fieldname": "compliance_status",
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
	]


def get_data(filters: dict) -> list[dict]:
	sales_invoice = frappe.qb.DocType("Sales Invoice")
	compliance_status = _get_compliance_status_case(sales_invoice)

	query = (
		frappe.qb.from_(sales_invoice)
		.select(
			sales_invoice.name.as_("invoice"),
			sales_invoice.customer,
			sales_invoice.posting_date,
			sales_invoice.nrs_invoice_type.as_("invoice_type"),
			sales_invoice.grand_total,
			sales_invoice.outstanding_amount,
			sales_invoice.nc_invoice_id.as_("digitax_invoice_id"),
			sales_invoice.nc_invoice_number.as_("digitax_invoice_number"),
			sales_invoice.nc_invoice_reference_number.as_("invoice_reference_number"),
			sales_invoice.nc_submitted_to_nrs.as_("submitted_to_nrs"),
			sales_invoice.nc_is_nrs_valid.as_("is_nrs_valid"),
			sales_invoice.nc_payment_status.as_("payment_status"),
			sales_invoice.nc_signed_at.as_("signed_at"),
			sales_invoice.nc_validated_at.as_("validated_at"),
			compliance_status.as_("compliance_status"),
			sales_invoice.currency,
		)
		.where(sales_invoice.docstatus == 1)
		.where(sales_invoice.company == filters["company"])
		.orderby(sales_invoice.posting_date, order=Order.desc)
		.orderby(sales_invoice.name, order=Order.desc)
	)

	query = _apply_filters(query, sales_invoice, filters)

	return query.run(as_dict=True)


def _get_compliance_status_case(sales_invoice):
	return (
		Case()
		.when(
			_is_blank(sales_invoice.nc_invoice_id),
			"Pending DigiTax Submission",
		)
		.when(
			(sales_invoice.nc_submitted_to_nrs.isnull())
			| (sales_invoice.nc_submitted_to_nrs == 0),
			"Pending NRS Submission",
		)
		.when(
			(sales_invoice.nc_is_nrs_valid.isnull())
			| (sales_invoice.nc_is_nrs_valid == 0),
			"Pending NRS Validation",
		)
		.when(
			(sales_invoice.outstanding_amount <= 0)
			& (
				_is_blank(sales_invoice.nc_payment_status)
				| (Upper(sales_invoice.nc_payment_status) != "PAID")
			),
			"Pending Payment Status Sync",
		)
		.else_("Compliant")
	)


def _apply_filters(query, sales_invoice, filters: dict):
	if filters.get("from_date"):
		query = query.where(sales_invoice.posting_date >= filters["from_date"])

	if filters.get("to_date"):
		query = query.where(sales_invoice.posting_date <= filters["to_date"])

	if filters.get("sales_invoice"):
		query = query.where(sales_invoice.name == filters["sales_invoice"])

	if filters.get("customer"):
		query = query.where(sales_invoice.customer == filters["customer"])

	if filters.get("payment_status"):
		query = query.where(
			_get_payment_status_criterion(sales_invoice, filters["payment_status"])
		)

	if filters.get("compliant_status"):
		criterion = _get_compliant_status_criterion(
			sales_invoice, filters["compliant_status"]
		)
		if criterion is not None:
			query = query.where(criterion)

	return query


def _get_payment_status_criterion(sales_invoice, payment_status: str):
	payment_status = payment_status.upper()

	if payment_status == "PENDING":
		return _is_blank(sales_invoice.nc_payment_status) | (
			Upper(sales_invoice.nc_payment_status) == "PENDING"
		)

	return Upper(sales_invoice.nc_payment_status) == payment_status


def _get_compliant_status_criterion(sales_invoice, compliant_status: str):
	if compliant_status == "Compliant":
		return (
			_is_present(sales_invoice.nc_invoice_id)
			& (sales_invoice.nc_submitted_to_nrs == 1)
			& (sales_invoice.nc_is_nrs_valid == 1)
			& (
				(sales_invoice.outstanding_amount > 0)
				| (Upper(sales_invoice.nc_payment_status) == "PAID")
			)
		)

	if compliant_status == "Pending DigiTax Submission":
		return _is_blank(sales_invoice.nc_invoice_id)

	if compliant_status == "Pending NRS Submission":
		return _is_present(sales_invoice.nc_invoice_id) & (
			(sales_invoice.nc_submitted_to_nrs.isnull())
			| (sales_invoice.nc_submitted_to_nrs == 0)
		)

	return None


def _is_blank(field):
	return field.isnull() | (field == "")


def _is_present(field):
	return field.notnull() & (field != "")
