// Copyright (c) 2026, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("FIRS Settings", {
	refresh(frm) {
		// Set up button click handlers
		frm.trigger("setup_fetch_buttons");
	},

	setup_fetch_buttons(frm) {
		// Handle Invoice Type Codes button click
		frm.fields_dict.fetch_invoice_type_codes.$input.on("click", () => {
			frm.trigger("fetch_invoice_type_codes");
		});
	},

	fetch_invoice_type_codes(frm) {
		frappe.confirm(
			__(
				"This will fetch Invoice Type Codes from DigiTax API and create/update FIRS Invoice Type documents. Continue?",
			),
			() => {
				frappe.call({
					method: "nigeria_compliance_via_digitax.utils.fetch_invoice_type_codes",
					args: {
						company: frm.doc.company,
					},
					freeze: true,
					freeze_message: __("Fetching Invoice Type Codes..."),
					callback: function (r) {
						if (r.message && r.message.success) {
							frappe.show_alert(
								{
									message: __(r.message.message),
									indicator: "green",
								},
								5,
							);

							// Show detailed stats
							const stats = r.message.stats;
							let details = `
								<div class="text-muted small">
									<div>Total Fetched: ${stats.total_fetched}</div>
									<div>Created: ${stats.created}</div>
									<div>Updated: ${stats.updated}</div>
									<div>Unchanged: ${stats.skipped}</div>
									${stats.errors ? `<div class="text-danger">Errors: ${stats.errors}</div>` : ""}
								</div>
							`;

							frappe.msgprint({
								title: __("Invoice Type Codes Fetched"),
								message: details,
								indicator: stats.errors ? "orange" : "green",
							});

							// Show errors if any
							if (r.message.errors && r.message.errors.length > 0) {
								console.error("Errors during fetch:", r.message.errors);
							}
						}
					},
					error: function (r) {
						frappe.show_alert(
							{
								message: __("Failed to fetch Invoice Type Codes"),
								indicator: "red",
							},
							5,
						);
					},
				});
			},
		);
	},
});
