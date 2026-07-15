frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		// Show "Get Invoice" for submitted invoices that have a reference number
		if (frm.doc.docstatus === 1 && frm.doc.nc_invoice_reference_number) {
			frm.add_custom_button(
				__("Sync Invoice Data"),
				function () {
					get_invoice_from_digitax(frm);
				},
				__("DigiTax Actions"),
			);
		}

		// Show "Resubmit to DigiTax" for submitted invoices with no DigiTax invoice ID
		if (frm.doc.docstatus === 1 && !frm.doc.nc_invoice_id) {
			frm.add_custom_button(
				__("Resubmit to DigiTax"),
				function () {
					resubmit_to_digitax(frm);
				},
				__("DigiTax Actions"),
			);
		}

		if (can_resend_digitax_payment_status(frm)) {
			frm.add_custom_button(
				__("Resend Payment Status"),
				function () {
					resend_digitax_payment_status(frm);
				},
				__("DigiTax Actions"),
			);
		}
	},
});

function can_resend_digitax_payment_status(frm) {
	if (!frm.doc.nc_invoice_id) {
		return false;
	}

	if (frm.doc.nc_signed_at) {
		return false;
	}

	if (frm.doc.docstatus === 2) {
		return true;
	}

	return frm.doc.docstatus === 1 && flt(frm.doc.outstanding_amount) <= 0;
}

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

function resubmit_to_digitax(frm) {
	frappe.confirm(
		__("Are you sure you want to resubmit <strong>{0}</strong> to DigiTax?", [frm.doc.name]),
		function () {
			frappe.call({
				method: "nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice.resubmit_to_digitax",
				args: {
					sales_invoice: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Resubmitting invoice to DigiTax..."),
				callback: function (r) {
					if (r.message) {
						frm.reload_doc();
					}
				},
				error: function (r) {
					frappe.msgprint({
						title: __("Error"),
						indicator: "red",
						message: __("Failed to resubmit invoice to DigiTax. Please check the error log."),
					});
				},
			});
		}
	);
}

function resend_digitax_payment_status(frm) {
	const payment_status = frm.doc.docstatus === 2 ? "REJECTED" : "PAID";

	frappe.confirm(
		__("Resend payment status <strong>{0}</strong> to DigiTax for <strong>{1}</strong>?", [
			payment_status,
			frm.doc.name,
		]),
		function () {
			frappe.call({
				method: "nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.sales_invoice.resend_digitax_payment_status",
				args: {
					sales_invoice: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Resending payment status to DigiTax..."),
				callback: function (r) {
					if (r.message) {
						frm.reload_doc();
					}
				},
				error: function (r) {
					frappe.msgprint({
						title: __("Error"),
						indicator: "red",
						message: __(
							"Failed to resend payment status to DigiTax. Please check the error log.",
						),
					});
				},
			});
		}
	);
}
