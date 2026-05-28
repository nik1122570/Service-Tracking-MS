// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Simulation Routes", {
	refresh(frm) {
		ensure_permanent_fixed_expenses(frm);
		calculate_route_totals(frm);
	},
});

frappe.ui.form.on("Trip Steps", {
	distance(frm) {
		if (frm.doctype === "Simulation Routes") {
			calculate_route_totals(frm);
		}
	},

	fuel_consumption_qty(frm) {
		if (frm.doctype === "Simulation Routes") {
			calculate_route_totals(frm);
		}
	},

	trip_steps_remove(frm) {
		if (frm.doctype === "Simulation Routes") {
			calculate_route_totals(frm);
		}
	},
});

frappe.ui.form.on("Fixed Expenses Table", {
	expense(frm, cdt, cdn) {
		if (frm.doctype !== "Simulation Routes") {
			return;
		}

		const row = locals[cdt][cdn];
		if (!row.expense) {
			return;
		}

		const duplicate = (frm.doc.fixed_expenses || []).some((other_row) => {
			return other_row.name !== row.name && other_row.expense === row.expense;
		});

		if (duplicate) {
			frappe.msgprint(__(`${row.expense} is already added in Fixed Expenses.`));
			frappe.model.set_value(cdt, cdn, "expense", "");
		}
	},
});

function calculate_route_totals(frm) {
	const total_distance = (frm.doc.trip_steps || []).reduce((total, row) => {
		return total + flt(row.distance);
	}, 0);
	const total_fuel_consumption_qty = (frm.doc.trip_steps || []).reduce((total, row) => {
		return total + flt(row.fuel_consumption_qty);
	}, 0);

	frm.set_value("total_distance", total_distance);
	frm.set_value("total_fuel_consumption_qty", total_fuel_consumption_qty);
}

function ensure_permanent_fixed_expenses(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.simulation_routes.simulation_routes.get_permanent_fixed_expenses",
		callback(response) {
			let added = false;
			let updated = false;
			const existing_expenses = new Set(
				(frm.doc.fixed_expenses || []).map((row) => row.expense).filter(Boolean)
			);

			(response.message || []).forEach((expense) => {
				if (existing_expenses.has(expense.expense)) {
					(frm.doc.fixed_expenses || []).forEach((row) => {
						if (row.expense === expense.expense) {
							row.currency = expense.currency;
							row.amount = expense.amount;
							updated = true;
						}
					});
					return;
				}

				const row = frm.add_child("fixed_expenses");
				row.expense = expense.expense;
				row.currency = expense.currency;
				row.amount = expense.amount;
				existing_expenses.add(expense.expense);
				added = true;
			});

			if (added || updated) {
				frm.refresh_field("fixed_expenses");
			}
		},
	});
}
