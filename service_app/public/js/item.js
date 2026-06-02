frappe.ui.form.on("Item", {
	setup(frm) {
		ensure_warranty_field_visibility(frm);
		set_warranty_field_read_only(frm);
	},

	refresh(frm) {
		ensure_warranty_field_visibility(frm);
		set_warranty_field_read_only(frm);
	}
});

function set_warranty_field_read_only(frm) {
	const candidates = ["warranty_period", "warranty_period_in_days", "warranty_period__in_days"];
	candidates.forEach((fieldname) => {
		if (frm.fields_dict && frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "read_only", 1);
		}
	});
}

function ensure_warranty_field_visibility(frm) {
	const candidates = ["warranty_period", "warranty_period_in_days", "warranty_period__in_days"];
	candidates.forEach((fieldname) => {
		if (frm.fields_dict && frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "hidden", 0);
		}
	});
}
