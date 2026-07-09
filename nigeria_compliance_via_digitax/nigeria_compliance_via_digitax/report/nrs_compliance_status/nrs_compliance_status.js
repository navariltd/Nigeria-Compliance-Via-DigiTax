frappe.query_reports["NRS Compliance Status"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
		},
		{
			fieldname: "sales_invoice",
			label: __("Sales Invoice"),
			fieldtype: "Link",
			options: "Sales Invoice",
			get_query() {
				const company = frappe.query_report.get_filter_value("company");

				return {
					filters: {
						...(company ? { company } : {}),
						docstatus: 1,
					},
				};
			},
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nREJECTED\nPAID\nPENDING",
		},
		{
			fieldname: "compliant_status",
			label: __("Compliant Status"),
			fieldtype: "Select",
			options: "\nCompliant\nPending DigiTax Submission\nPending NRS Submission",
		},
	],
};
