// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Tempelate", {
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
