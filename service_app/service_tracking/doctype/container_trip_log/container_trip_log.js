// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Container Trip Log", {
	refresh(frm) {
		set_trip_totals(frm);
	},

	validate(frm) {
		set_trip_totals(frm);
	},

	expected_revenue(frm) {
		set_trip_totals(frm);
	},

	driver_mileage_per_trip(frm) {
		set_trip_totals(frm);
	},

	container_add(frm) {
		set_trip_totals(frm);
	},

	container_remove(frm) {
		set_trip_totals(frm);
	},
});

function set_trip_totals(frm) {
	const total_qty = (frm.doc.container || []).length;
	const expected_revenue = flt(frm.doc.expected_revenue);
	const driver_mileage_per_trip = flt(frm.doc.driver_mileage_per_trip);

	frm.set_value("total_qty", total_qty);
	frm.set_value("total_expected_revenue", expected_revenue * total_qty);
	frm.set_value("expected_mileage_pay", driver_mileage_per_trip * total_qty);
}
