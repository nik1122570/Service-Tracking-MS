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

	fuel_consumption_ratio(frm) {
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

		row.expense = canonical_expense_label(row.expense);
		const duplicate = (frm.doc.fixed_expenses || []).some((other_row) => {
			return other_row.name !== row.name
				&& normalize_expense_name(other_row.expense) === normalize_expense_name(row.expense);
		});

		if (duplicate) {
			frappe.msgprint(__(`${row.expense} is already added in Fixed Expenses.`));
			frappe.model.set_value(cdt, cdn, "expense", "");
		}
	},
});

function calculate_route_totals(frm) {
	let changed = false;
	const total_distance = (frm.doc.trip_steps || []).reduce((total, row) => {
		const fuel_consumption_qty = flt(row.distance) * flt(row.fuel_consumption_ratio);
		if (flt(row.fuel_consumption_qty) !== flt(fuel_consumption_qty)) {
			row.fuel_consumption_qty = fuel_consumption_qty;
			changed = true;
		}
		return total + flt(row.distance);
	}, 0);
	const total_fuel_consumption_qty = (frm.doc.trip_steps || []).reduce((total, row) => {
		return total + flt(row.fuel_consumption_qty);
	}, 0);

	set_value_if_changed(frm, "total_distance", total_distance);
	set_value_if_changed(frm, "total_fuel_consumption_qty", total_fuel_consumption_qty);
	if (changed) {
		frm.refresh_field("trip_steps");
	}
}

function ensure_permanent_fixed_expenses(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.simulation_routes.simulation_routes.get_permanent_fixed_expenses",
			callback(response) {
				let changed = false;
				const existing_expenses = {};
				const unique_rows = [];

				(frm.doc.fixed_expenses || []).forEach((row) => {
					if (!row.expense) {
						return;
					}

					const canonical_expense = canonical_expense_label(row.expense);
					const expense_key = normalize_expense_name(canonical_expense);
					if (existing_expenses[expense_key]) {
						changed = true;
						return;
					}

					if (row.expense !== canonical_expense) {
						row.expense = canonical_expense;
						changed = true;
					}

					existing_expenses[expense_key] = row;
					unique_rows.push(row);
				});

				if (unique_rows.length !== (frm.doc.fixed_expenses || []).length) {
					frm.doc.fixed_expenses = unique_rows;
					changed = true;
				}

				(response.message || []).forEach((expense) => {
					const canonical_expense = canonical_expense_label(expense.expense);
					const expense_key = normalize_expense_name(canonical_expense);
					const existing_row = existing_expenses[expense_key];

					if (existing_row) {
						changed = update_row_if_changed(existing_row, {
							expense: canonical_expense,
							currency: expense.currency,
							amount: expense.amount,
						}) || changed;
						return;
					}

					const row = frm.add_child("fixed_expenses");
					row.expense = canonical_expense;
					row.currency = expense.currency;
					row.amount = expense.amount;
					existing_expenses[expense_key] = row;
					changed = true;
				});

				if (changed) {
					frm.refresh_field("fixed_expenses");
				}
			},
	});
}

function normalize_expense_name(expense) {
	return (expense || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function canonical_expense_label(expense) {
	const labels = {
		"driver mileage": "Driver Mileage",
		"salaries": "Salaries",
		"car wash": "Car Wash",
		"maintenance fee": "Maintenance Fee",
		"depreciation": "Depreciation",
		"management fee": "Management Fee",
		"tyres": "Tyres",
	};
	return labels[normalize_expense_name(expense)] || (expense || "").trim();
}

function update_row_if_changed(row, values) {
	let changed = false;
	Object.keys(values).forEach((fieldname) => {
		const value = values[fieldname];
		if (row[fieldname] !== value) {
			row[fieldname] = value;
			changed = true;
		}
	});
	return changed;
}

function set_value_if_changed(frm, fieldname, value) {
	if (flt(frm.doc[fieldname]) !== flt(value)) {
		frm.set_value(fieldname, value);
	}
}
