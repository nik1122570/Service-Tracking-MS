// Copyright (c) 2026, Nickson and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Card Recharge", {
	litres(frm) {
		calculate_amount(frm);
	},

	rate(frm) {
		calculate_amount(frm);
	},
});

function calculate_amount(frm) {
	frm.set_value("amount", flt(frm.doc.litres) * flt(frm.doc.rate));
}
