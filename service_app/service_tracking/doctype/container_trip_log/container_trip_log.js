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

frappe.ui.form.on("Container Holder", {
	container_id(frm, cdt, cdn) {
		clear_duplicate_container_in_current_trip(frm, cdt, cdn);
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

function clear_duplicate_container_in_current_trip(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.container_id) {
		return;
	}

	const duplicate = (frm.doc.container || []).some((container_row) => {
		return container_row.name !== row.name && container_row.container_id === row.container_id;
	});

	if (!duplicate) {
		return;
	}

	frappe.msgprint({
		title: __("Duplicate Container"),
		message: __("Container {0} has already been selected in this Trip Log.", [frappe.bold(row.container_id)]),
		indicator: "orange",
	});
	frappe.model.set_value(cdt, cdn, "container_id", "");
}
