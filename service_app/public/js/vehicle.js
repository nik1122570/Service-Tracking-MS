frappe.ui.form.on("Vehicle", {
	setup(frm) {
		set_make_query(frm);
	},

	refresh(frm) {
		set_make_query(frm);
	}
});

function set_make_query(frm) {
	if (!frm.fields_dict || !frm.fields_dict.make) {
		return;
	}

	frm.set_query("make", () => ({
		filters: {
			enabled: 1
		}
	}));
}
