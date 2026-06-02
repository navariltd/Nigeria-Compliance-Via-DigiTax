// Copyright (c) 2026, Navari Limited and contributors
// For license information, please see license.txt

frappe.ui.form.on("NRS Settings", {
	refresh(frm) {
		const fetchActions = [
			["Invoice Type Codes", "fetch_invoice_type_codes"],
			["Tax Category Codes", "fetch_tax_category_codes"],
			["Country Codes", "fetch_country_codes"],
		];

		fetchActions.forEach(([label, handler]) => {
			frm.add_custom_button(
				__(label),
				() => {
					frm.trigger(handler);
				},
				__("Actions"),
			);
		});
	},

	fetch_invoice_type_codes(frm) {
		frappe.confirm(
			__(
				"This will fetch Invoice Type Codes from DigiTax API and create/update NRS Invoice Type documents. Continue?",
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

	fetch_tax_category_codes(frm) {
		frappe.confirm(
			__(
				"This will fetch Tax Category Codes from DigiTax API and create/update NRS Tax Category documents. Continue?",
			),
			() => {
				frappe.call({
					method: "nigeria_compliance_via_digitax.utils.fetch_tax_category_codes",
					args: {
						company: frm.doc.company,
					},
					freeze: true,
					freeze_message: __("Fetching Tax Category Codes..."),
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
								title: __("Tax Category Codes Fetched"),
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
								message: __("Failed to fetch Tax Category Codes"),
								indicator: "red",
							},
							5,
						);
					},
				});
			},
		);
	},

	fetch_country_codes(frm) {
		frappe.confirm(
			__(
				"This will fetch Country Codes from DigiTax API and create/update NRS Country Codes documents. Continue?",
			),
			() => {
				frappe.call({
					method: "nigeria_compliance_via_digitax.utils.fetch_country_codes",
					args: {
						company: frm.doc.company,
					},
					freeze: true,
					freeze_message: __("Fetching Country Codes..."),
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
								title: __("Country Codes Fetched"),
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
								message: __("Failed to fetch Country Codes"),
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
