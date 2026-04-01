frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Only show button for submitted invoices with an invoice reference number
		if (frm.doc.docstatus === 1 && frm.doc.nc_invoice_reference_number) {
			frm.add_custom_button(
				__("Get Invoice"),
				function () {
					get_invoice_from_digitax(frm);
				},
				__("DigiTax Actions"),
			);
		}
	},
});

function get_invoice_from_digitax(frm) {
	frappe.call({
		method: "nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice.get_invoice_from_digitax",
		args: {
			sales_invoice: frm.doc.name,
			invoice_reference_number: frm.doc.nc_invoice_reference_number,
		},
		freeze: true,
		freeze_message: __("Fetching invoice from DigiTax..."),
		callback: function (r) {
			if (r.message) {
				frappe.msgprint({
					title: __("Invoice Updated"),
					indicator: "green",
					message: __(
						"Invoice data has been successfully fetched from DigiTax and updated.",
					),
				});
				frm.reload_doc();
			}
		},
		error: function (r) {
			frappe.msgprint({
				title: __("Error"),
				indicator: "red",
				message: __("Failed to fetch invoice from DigiTax. Please check the error log."),
			});
		},
	});
}
