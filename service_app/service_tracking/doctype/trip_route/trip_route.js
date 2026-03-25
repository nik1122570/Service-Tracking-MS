frappe.ui.form.on("Trip Route", {
	refresh(frm) {
		recalculate_route_totals(frm);
	}
});

frappe.ui.form.on("Trip Route Step", {
	distance_km(frm) {
		recalculate_route_totals(frm);
	},
	fuel_consumption_qty_ltr(frm) {
		recalculate_route_totals(frm);
	},
	route_steps_remove(frm) {
		recalculate_route_totals(frm);
	}
});

function recalculate_route_totals(frm) {
	const rows = frm.doc.route_steps || [];
	const total_distance = rows.reduce((sum, row) => sum + flt(row.distance_km), 0);
	const total_fuel = rows.reduce((sum, row) => sum + flt(row.fuel_consumption_qty_ltr), 0);

	frm.set_value("total_distance_km", total_distance);
	frm.set_value("total_fuel_consumption_qty_ltr", total_fuel);
}

