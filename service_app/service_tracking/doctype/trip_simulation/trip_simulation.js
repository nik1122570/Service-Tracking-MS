// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trip Simulation", {
	refresh(frm) {
		calculate_days_in_trip(frm);
		load_route_expense_limits(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Create Purchase Order"), () => {
				show_payable_expenses_dialog(frm);
			});
		}
	},

	route(frm) {
		if (!frm.doc.route) {
			frm._route_expense_limits = {};
			frm.clear_table("fuel");
			frm.clear_table("trip_expenses_outline");
			calculate_totals(frm);
			frm.refresh_field("fuel");
			frm.refresh_field("trip_expenses_outline");
			return;
		}

		frappe.call({
			method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_route_details",
			args: {
				route: frm.doc.route,
				days_in_trip: frm.doc.days_in_trip || 0,
				salaries: frm.doc.salaries || 0,
				active_vehicles: frm.doc.active_vehicles || 0,
				vehicle_costs: frm.doc.vehicle_costs || 0,
				depreciation_month_number: get_depreciation_month_number(frm),
			},
			callback(response) {
				const route_details = response.message || {};
				frm.clear_table("fuel");
				frm.clear_table("trip_expenses_outline");

				(route_details.trip_steps || []).forEach((step) => {
					const row = frm.add_child("fuel");
					row.location = step.location;
					row.unloading_location = step.unloading_location;
					row.distance = step.distance;
					row.fuel_consumption_qty = step.fuel_consumption_qty;
				});

				(route_details.fixed_expenses || []).forEach((expense) => {
					const row = frm.add_child("trip_expenses_outline");
					row.expense = expense.expense;
					row.quantity = expense.quantity;
					row.rate = expense.rate;
					row.amount = expense.amount;
					row.description = expense.description;
				});

				calculate_totals(frm);
				frm.refresh_field("fuel");
				frm.refresh_field("trip_expenses_outline");
				load_route_expense_limits(frm);
			},
		});
	},

	expected_revenue(frm) {
		calculate_totals(frm);
	},

	departure_date(frm) {
		calculate_days_in_trip(frm);
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	return_date(frm) {
		calculate_days_in_trip(frm);
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	transaction_date(frm) {
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	fuel_price(frm) {
		calculate_totals(frm);
	},

	create_fuel_purchase_order(frm) {
		make_fuel_purchase_order(frm);
	},

	salaries(frm) {
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	active_vehicles(frm) {
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	vehicle_costs(frm) {
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},
});

frappe.ui.form.on("Trip Steps", {
	distance(frm) {
		if (frm.doctype === "Trip Simulation") {
			calculate_totals(frm);
		}
	},

	fuel_consumption_qty(frm) {
		if (frm.doctype === "Trip Simulation") {
			calculate_totals(frm);
		}
	},

	fuel_remove(frm) {
		if (frm.doctype === "Trip Simulation") {
			calculate_totals(frm);
		}
	},
});

frappe.ui.form.on("Trip Simulation Table", {
	expense(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		validate_row_expense(frm, row);
	},

	quantity(frm) {
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	amount(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		validate_row_amount(frm, row);
		calculate_totals(frm);
	},

	trip_expenses_outline_remove(frm) {
		calculate_totals(frm);
	},
});

function calculate_totals(frm) {
	apply_calculated_expenses(frm);

	const total_distance = (frm.doc.fuel || []).reduce((total, row) => {
		return total + flt(row.distance);
	}, 0);
	const total_fuel_consumption_qty = (frm.doc.fuel || []).reduce((total, row) => {
		return total + flt(row.fuel_consumption_qty);
	}, 0);
	const total_fuel_costs = total_fuel_consumption_qty * flt(frm.doc.fuel_price);
	const total_expenses = (frm.doc.trip_expenses_outline || []).reduce((total, row) => {
		return total + flt(row.amount);
	}, 0);
	const total_trip_cost = total_fuel_costs + total_expenses;

	const expected_revenue = flt(frm.doc.expected_revenue);
	const trip_gross_profit_amount = flt(expected_revenue - total_trip_cost, 2);
	const trip_gross_profit = expected_revenue
		? flt(trip_gross_profit_amount / expected_revenue * 100, 4)
		: 0;

	frm.set_value("total_distance_km", total_distance);
	frm.set_value("total_fuel_consumption_qty_ratio", total_fuel_consumption_qty);
	frm.set_value("total_fuel_costs", total_fuel_costs);
	frm.set_value("total_trip_cost", total_trip_cost);
	frm.set_value("trip_gross_profit_amount", trip_gross_profit_amount);
	frm.set_value("trip_gross_profit", trip_gross_profit);
}

function apply_calculated_expenses(frm) {
	const limits = frm._route_expense_limits || {};

	(frm.doc.trip_expenses_outline || []).forEach((row) => {
		const expense_limit = limits[row.expense];
		if (!expense_limit) {
			return;
		}

		if (expense_limit.calculation_method === "Per Trip Day") {
			row.rate = flt(expense_limit.amount);
			row.quantity = flt(frm.doc.days_in_trip);
			row.amount = flt(row.rate) * flt(row.quantity);
			row.description = `${row.rate} x ${row.quantity} trip days`;
		} else if (expense_limit.calculation_method === "Salary Allocation") {
			row.rate = get_salary_allocation_rate(frm);
			row.quantity = flt(frm.doc.days_in_trip);
			row.amount = flt(row.rate) * flt(row.quantity);
			row.description = `${format_formula_number(frm.doc.salaries)} / 30 / ${format_formula_number(frm.doc.active_vehicles)} x ${format_formula_number(row.quantity)} trip days`;
		} else if (expense_limit.calculation_method === "Vehicle Depreciation") {
			const month_number = get_depreciation_month_number(frm);
			row.rate = get_vehicle_depreciation_rate(frm, month_number);
			row.quantity = flt(frm.doc.days_in_trip);
			row.amount = flt(row.rate) * flt(row.quantity);
			row.description = `${format_formula_number(frm.doc.vehicle_costs)} / ${format_formula_number(month_number)} / 12 / 30 x ${format_formula_number(row.quantity)} trip days`;
		} else {
			row.rate = flt(expense_limit.amount);
			row.quantity = 1;
			row.amount = flt(row.rate);
			row.description = __("Fixed amount");
		}
	});

	frm.refresh_field("trip_expenses_outline");
}

function calculate_days_in_trip(frm) {
	if (!frm.doc.departure_date || !frm.doc.return_date) {
		frm.set_value("days_in_trip", 0);
		return;
	}

	const days_in_trip = frappe.datetime.get_day_diff(frm.doc.return_date, frm.doc.departure_date) + 1;

	if (days_in_trip < 1) {
		frappe.msgprint(__("Return Date cannot be before Departure Date."));
		frm.set_value("days_in_trip", 0);
		return;
	}

	frm.set_value("days_in_trip", days_in_trip);
}

function load_route_expense_limits(frm) {
	if (!frm.doc.route) {
		frm._route_expense_limits = {};
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_route_expense_limits",
		args: {
			route: frm.doc.route,
		},
		callback(response) {
			frm._route_expense_limits = response.message || {};
			apply_calculated_expenses(frm);
			calculate_totals(frm);
			validate_trip_expenses(frm);
		},
	});
}

function validate_trip_expenses(frm) {
	(frm.doc.trip_expenses_outline || []).forEach((row) => {
		validate_row_expense(frm, row);
		validate_row_amount(frm, row);
	});
}

function validate_row_expense(frm, row) {
	if (!row || !row.expense) {
		return;
	}

	const duplicate = (frm.doc.trip_expenses_outline || []).some((other_row) => {
		return other_row.name !== row.name && other_row.expense === row.expense;
	});

	if (duplicate) {
		frappe.msgprint(__(`${row.expense} is already added in Trip Expenses Outline.`));
		frappe.model.set_value(row.doctype, row.name, "expense", "");
		return;
	}

	const limits = frm._route_expense_limits || {};
	if (frm.doc.route && Object.keys(limits).length && limits[row.expense] === undefined) {
		frappe.msgprint(__(`${row.expense} is not defined in the selected Simulation Route.`));
		frappe.model.set_value(row.doctype, row.name, "expense", "");
	}
}

function validate_row_amount(frm, row) {
	if (!row || !row.expense) {
		return;
	}

	const limits = frm._route_expense_limits || {};
	const expense_limit = limits[row.expense] || {};
	const max_amount = get_allowed_expense_amount(expense_limit, frm);

	if (frm.doc.route && limits[row.expense] !== undefined && flt(row.amount) > max_amount) {
		frappe.msgprint(
			__(`${row.expense} cannot exceed the route predefined amount ${format_currency(max_amount)}.`)
		);
		frappe.model.set_value(row.doctype, row.name, "amount", max_amount);
	}
}

function get_allowed_expense_amount(expense_limit, frm) {
	const amount = flt(expense_limit.amount);
	if (expense_limit.calculation_method === "Per Trip Day") {
		return amount * flt(frm.doc.days_in_trip);
	}
	if (expense_limit.calculation_method === "Salary Allocation") {
		return get_salary_allocation_rate(frm) * flt(frm.doc.days_in_trip);
	}
	if (expense_limit.calculation_method === "Vehicle Depreciation") {
		return get_vehicle_depreciation_rate(frm, get_depreciation_month_number(frm)) * flt(frm.doc.days_in_trip);
	}

	return amount;
}

function get_salary_allocation_rate(frm) {
	const active_vehicles = flt(frm.doc.active_vehicles);
	if (!active_vehicles) {
		return 0;
	}

	return flt(frm.doc.salaries) / 30 / active_vehicles;
}

function get_vehicle_depreciation_rate(frm, month_number) {
	month_number = flt(month_number);
	if (!month_number) {
		return 0;
	}

	return flt(frm.doc.vehicle_costs) / month_number / 12 / 30;
}

function get_depreciation_month_number(frm) {
	const date_value = frm.doc.departure_date || frm.doc.transaction_date;
	if (!date_value) {
		return 0;
	}

	return frappe.datetime.str_to_obj(date_value).getMonth() + 1;
}

function format_formula_number(value) {
	return flt(value).toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function show_payable_expenses_dialog(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_payable_expenses",
		args: {
			trip_simulation: frm.doc.name,
		},
		callback(response) {
			const payable_expenses = response.message || [];
			if (!payable_expenses.length) {
				frappe.msgprint(__("All Trip Expenses Paid"));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Select Payable Expenses"),
				size: "large",
				fields: [
					{
						fieldname: "payable_expenses",
						fieldtype: "Table",
						label: __("Payable Expenses"),
						cannot_add_rows: true,
						cannot_delete_rows: true,
						in_place_edit: true,
						data: payable_expenses.map((expense) => ({
							row_name: expense.row_name,
							select_expense: 0,
							expense: expense.expense,
							item: expense.item,
							quantity: expense.quantity,
							rate: expense.rate,
							amount: expense.amount,
							description: expense.description,
						})),
						fields: [
							{
								fieldname: "row_name",
								fieldtype: "Data",
								label: __("Row Name"),
								hidden: 1,
							},
							{
								fieldname: "select_expense",
								fieldtype: "Check",
								label: __("Select"),
								in_list_view: 1,
							},
							{
								fieldname: "expense",
								fieldtype: "Data",
								label: __("Expense"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "item",
								fieldtype: "Link",
								options: "Item",
								label: __("Item"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "quantity",
								fieldtype: "Float",
								label: __("Quantity"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "rate",
								fieldtype: "Currency",
								label: __("Rate"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "amount",
								fieldtype: "Currency",
								label: __("Amount"),
								in_list_view: 1,
								read_only: 1,
							},
							{
								fieldname: "description",
								fieldtype: "Small Text",
								label: __("Description"),
								read_only: 1,
							},
						],
					},
				],
				primary_action_label: __("Create Purchase Order"),
				primary_action(values) {
					const selected = (values.payable_expenses || []).filter((row) => row.select_expense);
					if (!selected.length) {
						frappe.msgprint(__("Please select at least one expense."));
						return;
					}

					const missing_item = selected.find((row) => !row.item);
					if (missing_item) {
						frappe.msgprint(
							__(`Please set Item in Fixed Expenses ${missing_item.expense} before creating a Purchase Order.`)
						);
						return;
					}

					frappe.call({
						method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.create_purchase_order",
						args: {
							trip_simulation: frm.doc.name,
							selected_expenses: selected,
						},
						callback(create_response) {
							const purchase_order = create_response.message;
							if (!purchase_order) {
								return;
							}

							dialog.hide();
							frappe.msgprint({
								title: __("Purchase Order Created"),
								message: __("Created Purchase Order {0}", [
									`<a href="/app/purchase-order/${purchase_order.name}">${purchase_order.name}</a>`,
								]),
								indicator: "green",
							});
							frm.reload_doc();
						},
					});
				},
			});

			dialog.show();
		},
	});
}

function make_fuel_purchase_order(frm) {
	if (frm.doc.docstatus !== 1) {
		frappe.msgprint(__("Please submit the Trip Simulation before creating the Fuel Purchase Order."));
		return;
	}
	if (frm.doc.fuel_purchase_order) {
		frappe.msgprint(
			__("Fuel Purchase Order {0} already exists for this Trip Simulation.", [
				`<a href="/app/purchase-order/${frm.doc.fuel_purchase_order}">${frm.doc.fuel_purchase_order}</a>`,
			])
		);
		return;
	}
	if (!frm.doc.fuel_supplier) {
		frappe.msgprint(__("Please set Fuel Supplier before creating the Fuel Purchase Order."));
		return;
	}
	if (!frm.doc.fuel_item) {
		frappe.msgprint(__("Please set Fuel Item before creating the Fuel Purchase Order."));
		return;
	}
	if (!flt(frm.doc.total_fuel_consumption_qty_ratio)) {
		frappe.msgprint(__("Total Fuel Consumption Qty must be greater than zero."));
		return;
	}
	if (!flt(frm.doc.fuel_price)) {
		frappe.msgprint(__("Fuel Price must be greater than zero."));
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.create_fuel_purchase_order",
		args: {
			trip_simulation: frm.doc.name,
		},
		callback(response) {
			const purchase_order = response.message;
			if (!purchase_order) {
				return;
			}

			frappe.msgprint({
				title: __("Fuel Purchase Order Created"),
				message: __("Created Purchase Order {0}", [
					`<a href="/app/purchase-order/${purchase_order.name}">${purchase_order.name}</a>`,
				]),
				indicator: "green",
			});
			frm.reload_doc();
		},
	});
}
