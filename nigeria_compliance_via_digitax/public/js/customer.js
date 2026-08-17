frappe.ui.form.on("Customer", {
	refresh(frm) {
		if (frm.doc.custom_digitax_id) {
			return;
		}

		frm.add_custom_button(
			__("Get Digitax Party Code"),
			() => {
				frappe.call({
					method: "nigeria_compliance_via_digitax.nigeria_compliance_via_digitax.overrides.party.get_digitax_party_code",
					args: {
						doc: frm.doc.name,
					},
					freeze: true,
					freeze_message: __("Getting Digitax party code..."),
					callback: () => frm.reload_doc(),
				});
			},
			__("Digitax Actions"),
		);
	},
});
