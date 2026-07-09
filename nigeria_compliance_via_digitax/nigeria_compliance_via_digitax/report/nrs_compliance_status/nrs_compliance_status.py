import frappe
from frappe import _


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
	conditions, values = _get_conditions(filters)

	return frappe.db.sql(
		f"""
		select *
		from (
			select
				si.name as invoice,
				si.customer,
				si.posting_date,
				si.nrs_invoice_type as invoice_type,
				si.grand_total,
				si.outstanding_amount,
				si.nc_invoice_id as digitax_invoice_id,
				si.nc_invoice_number as digitax_invoice_number,
				si.nc_invoice_reference_number as invoice_reference_number,
				si.nc_submitted_to_nrs as submitted_to_nrs,
				si.nc_is_nrs_valid as is_nrs_valid,
				si.nc_payment_status as payment_status,
				si.nc_signed_at as signed_at,
				si.nc_validated_at as validated_at,
				case
					when ifnull(si.nc_invoice_id, '') = '' then 'Pending DigiTax Submission'
					when ifnull(si.nc_submitted_to_nrs, 0) = 0 then 'Pending NRS Submission'
					when ifnull(si.nc_is_nrs_valid, 0) = 0 then 'Pending NRS Validation'
					when si.outstanding_amount <= 0
						and upper(ifnull(si.nc_payment_status, '')) != 'PAID'
						then 'Pending Payment Status Sync'
					else 'Compliant'
				end as compliance_status,
				si.currency
			from `tabSales Invoice` si
			where si.docstatus = 1
				and si.company = %(company)s
				{conditions}
		) compliance
		where (
			%(compliant_status)s is null
			or compliance.compliance_status = %(compliant_status)s
		)
		order by compliance.posting_date desc, compliance.invoice desc
		""",
		values,
		as_dict=True,
	)


def _get_conditions(filters: dict) -> tuple[str, dict]:
	conditions = []
	values = {
		"company": filters["company"],
		"compliant_status": filters.get("compliant_status") or None,
	}

	if filters.get("from_date"):
		conditions.append("and si.posting_date >= %(from_date)s")
		values["from_date"] = filters["from_date"]

	if filters.get("to_date"):
		conditions.append("and si.posting_date <= %(to_date)s")
		values["to_date"] = filters["to_date"]

	if filters.get("sales_invoice"):
		conditions.append("and si.name = %(sales_invoice)s")
		values["sales_invoice"] = filters["sales_invoice"]

	if filters.get("payment_status"):
		payment_status = filters["payment_status"].upper()
		values["payment_status"] = payment_status

		if payment_status == "PENDING":
			conditions.append(
				"and upper(ifnull(nullif(si.nc_payment_status, ''), 'PENDING')) = %(payment_status)s"
			)
		else:
			conditions.append("and upper(ifnull(si.nc_payment_status, '')) = %(payment_status)s")

	return "\n\t\t\t\t".join(conditions), values
