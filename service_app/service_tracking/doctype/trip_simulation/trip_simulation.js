// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trip Simulation", {
	onload(frm) {
		frm._trip_simulation_refreshing = true;
		frm._trip_settings = get_default_trip_settings();
		frm._tyre_settings = get_default_tyre_settings();
		frm._fuel_litres_per_km = 0;
		frm._maintenance_details = get_default_maintenance_details();
		load_trip_settings(frm);
	},

	refresh(frm) {
		frm._trip_simulation_refreshing = true;
		apply_fuel_tab_layout_styles(frm);
		update_trip_financial_dashboard(frm);
		update_fuel_card_status_dashboard(frm);
		load_fuel_card_balance(frm, { silent: true });

		if (frm.doc.docstatus === 1) {
			load_route_expense_limits(frm, { recalculate: false });
			add_submitted_buttons(frm);
			release_refresh_guard(frm);
			return;
		}

		if (frm.is_new()) {
			calculate_days_in_trip(frm);
			load_route_expense_limits(frm);
			load_vehicle_cost_from_truck_type(frm);
			load_tyre_settings_from_truck_type(frm);
			load_fuel_litres_per_km_from_truck_type(frm);
			load_previous_month_maintenance_cost(frm);
			load_last_fuel_purchase_price(frm);
			release_refresh_guard(frm);
			return;
		}

		load_route_expense_limits(frm, { recalculate: false });
		load_vehicle_cost_from_truck_type(frm, { recalculate: false });
		load_tyre_settings_from_truck_type(frm, { recalculate: false });
		load_fuel_litres_per_km_from_truck_type(frm, { recalculate: false });
		load_previous_month_maintenance_cost(frm, { recalculate: false });
		load_last_fuel_purchase_price(frm, { recalculate: false });
		release_refresh_guard(frm);
	},

	after_save(frm) {
		frm._trip_simulation_refreshing = true;
		release_refresh_guard(frm);
	},

	route(frm) {
		if (!should_recalculate(frm)) {
			return;
		}

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
				depreciation_month_number: get_depreciation_month_number(frm),
				expected_revenue: frm.doc.expected_revenue || 0,
				vehicle: frm.doc.vehicle,
				maintenance_reference_date: get_maintenance_reference_date(frm),
			},
			callback(response) {
				const route_details = response.message || {};
				frm._tyre_settings = Object.assign(get_default_tyre_settings(), route_details.tyre_settings || {});
				frm._fuel_litres_per_km = flt(route_details.fuel_litres_per_km);
				frm._maintenance_details = Object.assign(get_default_maintenance_details(), route_details.maintenance_details || {});
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
					row.expense = canonical_expense_label(expense.expense);
					row.quantity = expense.quantity;
					row.rate = expense.rate;
					row.amount = expense.amount;
					row.previous_month_maintenance_cost = expense.previous_month_maintenance_cost;
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
		load_previous_month_maintenance_cost(frm);
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	return_date(frm) {
		calculate_days_in_trip(frm);
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	transaction_date(frm) {
		load_previous_month_maintenance_cost(frm);
		apply_calculated_expenses(frm);
		calculate_totals(frm);
	},

	fuel_price(frm) {
		calculate_totals(frm);
	},

	fuel_card(frm) {
		load_fuel_card_balance(frm);
	},

	fuel_item(frm) {
		load_last_fuel_purchase_price(frm);
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

	vehicle(frm) {
		load_vehicle_cost_from_truck_type(frm);
		load_tyre_settings_from_truck_type(frm);
		load_fuel_litres_per_km_from_truck_type(frm);
		load_previous_month_maintenance_cost(frm);
	},
});

function apply_fuel_tab_layout_styles(frm) {
	const fuel_grid = frm.get_field("fuel")?.grid;
	if (fuel_grid?.wrapper) {
		fuel_grid.wrapper.find(".grid-heading-row, .grid-row").css("min-width", "760px");
		fuel_grid.wrapper.find(".grid-body").css("overflow-x", "auto");
	}

	const dashboard_field = frm.get_field("fuel_card_status_dashboard");
	if (dashboard_field?.$wrapper) {
		dashboard_field.$wrapper.css({
			"margin-bottom": "16px",
			"display": "block",
		});
	}
}

frappe.ui.form.on("Trip Steps", {
	distance(frm) {
		if (frm.doctype === "Trip Simulation") {
			apply_calculated_fuel_consumption(frm);
			calculate_totals(frm);
		}
	},

	fuel_consumption_qty(frm) {
		if (frm.doctype === "Trip Simulation") {
			apply_calculated_fuel_consumption(frm);
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
	if (!should_recalculate(frm)) {
		return;
	}

	const total_distance = (frm.doc.fuel || []).reduce((total, row) => {
		return total + flt(row.distance);
	}, 0);
	apply_calculated_fuel_consumption(frm);
	apply_calculated_expenses(frm);

	const total_fuel_consumption_qty = (frm.doc.fuel || []).reduce((total, row) => {
		return total + flt(row.fuel_consumption_qty);
	}, 0);
	const total_fuel_costs = total_fuel_consumption_qty * flt(frm.doc.fuel_price);
	const total_expenses = (frm.doc.trip_expenses_outline || []).reduce((total, row) => {
		return total + flt(row.amount);
	}, 0);
	const total_trip_cost = total_fuel_costs + total_expenses;

	const expected_revenue = flt(frm.doc.expected_revenue);
	const net_profit = flt(expected_revenue - total_trip_cost, 2);
	const net_profit_margin = expected_revenue
		? flt(net_profit / expected_revenue * 100, 4)
		: 0;

	set_value_if_changed(frm, "total_distance_km", total_distance);
	set_value_if_changed(frm, "total_fuel_consumption_qty_ratio", total_fuel_consumption_qty);
	set_value_if_changed(frm, "total_fuel_costs", total_fuel_costs);
	set_value_if_changed(frm, "total_trip_cost", total_trip_cost);
	set_value_if_changed(frm, "net_profit", net_profit);
	set_value_if_changed(frm, "net_profit_", net_profit_margin);
	update_fuel_card_status_dashboard(frm, {
		total_fuel_costs,
		total_fuel_consumption_qty,
	});
	update_trip_financial_dashboard(frm, {
		expected_revenue,
		total_trip_cost,
		net_profit,
		net_profit_margin,
	});
}

function load_fuel_card_balance(frm) {
	if (!frm.doc.fuel_card) {
		frm._fuel_card_balance = null;
		update_fuel_card_status_dashboard(frm);
		return;
	}

	frappe.db.get_value("Fuel Card", frm.doc.fuel_card, [
		"current_balance_litres",
		"current_balance_value",
		"status",
		"currency",
	]).then((response) => {
		frm._fuel_card_balance = response.message || {};
		update_fuel_card_status_dashboard(frm);
	}).catch(() => {
		frm._fuel_card_balance = null;
		show_fuel_card_dashboard_error(frm);
	});
}

function show_fuel_card_dashboard_error(frm) {
	const field = frm.get_field("fuel_card_status_dashboard");
	if (!field) {
		return;
	}

	const dashboard_html = `
		<div style="margin: 10px 0 18px; border: 1px solid #fecaca; border-radius: 14px; padding: 14px 16px; color: #991b1b; background: #fef2f2; font-weight: 700;">
			${__("Could not load Fuel Card balance. Please refresh or check Fuel Card permissions.")}
		</div>
	`;
	field.df.options = dashboard_html;
	field.refresh();
	field.$wrapper.html(dashboard_html);
}

function update_fuel_card_status_dashboard(frm, values = {}) {
	const field = frm.get_field("fuel_card_status_dashboard");
	if (!field) {
		return;
	}

	const requested_amount = flt(values.total_fuel_costs ?? frm.doc.total_fuel_costs);
	const requested_litres = flt(values.total_fuel_consumption_qty ?? frm.doc.total_fuel_consumption_qty_ratio);
	const balance = frm._fuel_card_balance || {};
	const balance_amount = flt(balance.current_balance_value);
	const balance_litres = flt(balance.current_balance_litres);
	const remaining_amount = balance_amount - requested_amount;
	const remaining_litres = balance_litres - requested_litres;
	const has_card = Boolean(frm.doc.fuel_card);
	const card_status = balance.status || __("Not Selected");
	const has_available_amount = has_card && remaining_amount >= 0;
	const has_available_litres = has_card && remaining_litres >= 0;
	const is_available = has_available_amount && has_available_litres && card_status !== "Blocked";
	const status_label = !has_card ? __("Select Fuel Card") : is_available ? __("Available") : __("Refill Needed");
	const status_color = !has_card ? "#64748b" : is_available ? "#16a34a" : "#dc2626";
	const status_note = get_fuel_card_status_note({
		has_card,
		card_status,
		has_available_amount,
		has_available_litres,
	});
	const fuel_card_label = has_card ? escape_html(frm.doc.fuel_card) : __("Choose a Fuel Card to check balance");

	update_fuel_card_dashboard_indicator(frm, {
		status_label,
		is_available,
		requested_amount,
		balance_amount,
		remaining_amount,
		has_card,
	});

	const dashboard_html = `
		<div style="
			margin: 10px 0 18px;
			border: 1px solid var(--border-color);
			border-radius: 16px;
			overflow: hidden;
			background: linear-gradient(135deg, #ffffff 0%, #f8fafc 45%, #eef6ff 100%);
			box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
		">
			<div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 14px 16px; border-bottom: 1px solid var(--border-color);">
				<div>
					<div style="font-size: 13px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: .05em;">
						${__("Fuel Card Availability")}
					</div>
					<div style="font-size: 12px; color: var(--text-muted); margin-top: 3px;">
						${fuel_card_label}
					</div>
				</div>
				<div style="background: ${status_color}; color: #fff; border-radius: 999px; padding: 7px 13px; font-weight: 800; font-size: 12px;">
					${status_label}
				</div>
			</div>
			<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; padding: 14px 16px;">
				${get_fuel_card_status_card(__("Card Amount Balance"), format_currency(balance_amount), "#2563eb")}
				${get_fuel_card_status_card(__("Requested Amount"), format_currency(requested_amount), "#f97316")}
				${get_fuel_card_status_card(__("Amount After Request"), format_currency(remaining_amount), remaining_amount >= 0 ? "#16a34a" : "#dc2626")}
				${get_fuel_card_status_card(__("Card Qty Balance"), `${format_dashboard_number(balance_litres)} Ltr`, "#0f766e")}
				${get_fuel_card_status_card(__("Requested Qty"), `${format_dashboard_number(requested_litres)} Ltr`, "#7c3aed")}
				${get_fuel_card_status_card(__("Qty After Request"), `${format_dashboard_number(remaining_litres)} Ltr`, remaining_litres >= 0 ? "#16a34a" : "#dc2626")}
			</div>
			<div style="padding: 0 16px 14px; color: ${status_color}; font-size: 12px; font-weight: 700;">
				${status_note}
			</div>
		</div>
	`;

	field.df.options = dashboard_html;
	field.refresh();
	field.$wrapper.html(dashboard_html);
}

function update_fuel_card_dashboard_indicator(frm, values) {
	if (!frm.dashboard || !values.has_card) {
		return;
	}

	frm.dashboard.parent.find(".fuel-card-availability-headline").remove();
	const indicator_color = values.is_available ? "green" : "red";
	frm.dashboard.add_section(
		`
			<div class="fuel-card-availability-headline" style="display: flex; flex-wrap: wrap; gap: 10px; align-items: center;">
				<span class="indicator ${indicator_color}">${__("Fuel Card")}: ${values.status_label}</span>
				<span style="font-weight: 700;">${__("Balance")}: ${format_currency(values.balance_amount)}</span>
				<span style="font-weight: 700;">${__("Requested")}: ${format_currency(values.requested_amount)}</span>
				<span style="font-weight: 700;">${__("After Request")}: ${format_currency(values.remaining_amount)}</span>
			</div>
		`,
		null,
		"custom fuel-card-availability-headline"
	);
}

function get_fuel_card_status_card(label, value, accent) {
	return `
		<div style="background: #fff; border: 1px solid var(--border-color); border-radius: 13px; padding: 12px 13px;">
			<div style="display: flex; align-items: center; gap: 7px; color: var(--text-muted); font-size: 11px; font-weight: 700; text-transform: uppercase;">
				<span style="width: 8px; height: 8px; border-radius: 999px; background: ${accent}; display: inline-block;"></span>
				${label}
			</div>
			<div style="font-size: 20px; font-weight: 800; margin-top: 7px; color: var(--text-color);">
				${value}
			</div>
		</div>
	`;
}

function get_fuel_card_status_note(options) {
	if (!options.has_card) {
		return __("No Fuel Card selected yet.");
	}
	if (options.card_status === "Blocked") {
		return __("This Fuel Card is blocked. Please use another card or unblock it before submitting.");
	}
	if (!options.has_available_amount) {
		return __("Requested fuel amount is higher than available card value. Please refill the Fuel Card.");
	}
	if (!options.has_available_litres) {
		return __("Requested fuel litres are higher than available card litres. Please refill the Fuel Card.");
	}
	return __("Fuel Card has enough value and litres for this request.");
}

function escape_html(value) {
	return String(value || "")
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}

function update_trip_financial_dashboard(frm, values = {}) {
	if (!frm.dashboard) {
		return;
	}

	const expected_revenue = flt(values.expected_revenue ?? frm.doc.expected_revenue);
	const total_trip_cost = flt(values.total_trip_cost ?? frm.doc.total_trip_cost);
	const net_profit = flt(values.net_profit ?? frm.doc.net_profit);
	const net_profit_margin = flt(values.net_profit_margin ?? frm.doc.net_profit_);
	const target_margin = flt(frm.doc.targeted_net_profit);
	const cost_ratio = expected_revenue ? flt(total_trip_cost / expected_revenue * 100, 2) : 0;
	const margin_color = net_profit_margin >= target_margin ? "green" : "red";
	const profit_color = net_profit >= 0 ? "green" : "red";
	const profit_label = net_profit >= 0 ? __("Profit") : __("Loss");
	const margin_status = net_profit_margin >= target_margin ? __("On Target") : __("Below Target");

	frm.dashboard.stats_area_row.empty();
	frm.dashboard.add_indicator(`${__("Revenue")}: ${format_currency(expected_revenue)}`, "blue");
	frm.dashboard.add_indicator(`${__("Total Cost")}: ${format_currency(total_trip_cost)}`, "orange");
	frm.dashboard.add_indicator(`${profit_label}: ${format_currency(net_profit)}`, profit_color);
	frm.dashboard.add_indicator(`${__("Margin")}: ${format_percentage_value(net_profit_margin)}`, margin_color);

	frm.dashboard.parent.find(".trip-financial-dashboard").remove();
	const cards = [
		{
			label: __("Revenue"),
			value: format_currency(expected_revenue),
			accent: "#2563eb",
			subtitle: __("Expected trip income"),
		},
		{
			label: __("Total Cost"),
			value: format_currency(total_trip_cost),
			accent: "#f97316",
			subtitle: `${__("Cost Ratio")}: ${format_percentage_value(cost_ratio)}`,
		},
		{
			label: profit_label,
			value: format_currency(net_profit),
			accent: net_profit >= 0 ? "#16a34a" : "#dc2626",
			subtitle: __("Revenue less total trip cost"),
		},
		{
			label: __("Net Margin"),
			value: format_percentage_value(net_profit_margin),
			accent: net_profit_margin >= target_margin ? "#16a34a" : "#dc2626",
			subtitle: `${margin_status} | ${__("Target")}: ${format_percentage_value(target_margin)}`,
		},
	];

	const card_html = cards.map((card) => `
		<div style="
			flex: 1 1 180px;
			min-width: 180px;
			border: 1px solid var(--border-color);
			border-radius: 14px;
			padding: 14px 16px;
			background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
			box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
		">
			<div style="display: flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em;">
				<span style="width: 9px; height: 9px; border-radius: 999px; background: ${card.accent}; display: inline-block;"></span>
				${card.label}
			</div>
			<div style="font-size: 24px; font-weight: 800; color: var(--text-color); margin-top: 8px; line-height: 1.15;">
				${card.value}
			</div>
			<div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
				${card.subtitle}
			</div>
		</div>
	`).join("");

	frm.dashboard.add_section(
		`<div class="trip-financial-dashboard" style="display: flex; flex-wrap: wrap; gap: 12px;">${card_html}</div>`,
		__("Trip Financial Snapshot"),
		"custom trip-financial-dashboard"
	);
}

function apply_calculated_expenses(frm) {
	if (!should_recalculate(frm)) {
		return;
	}

	const limits = frm._route_expense_limits || {};
	let changed = false;

	(frm.doc.trip_expenses_outline || []).forEach((row) => {
		const expense = canonical_expense_label(row.expense);
		if (row.expense !== expense) {
			row.expense = expense;
			changed = true;
		}

		if (normalize_expense_name(row.expense) === "tyres") {
			const tyre_settings = get_tyre_settings(frm);
			const rate = get_tyre_cost_per_km(
				tyre_settings.tyre_price,
				tyre_settings.number_of_tyres,
				tyre_settings.tyre_lifecycle_km
			);
			const quantity = (frm.doc.fuel || []).reduce((total, step) => total + flt(step.distance), 0);
			changed = update_row_if_changed(row, {
				rate,
				quantity,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(tyre_settings.tyre_price)} x ${format_formula_number(tyre_settings.number_of_tyres)} tyres / ${format_formula_number(tyre_settings.tyre_lifecycle_km)} km x ${format_formula_number(quantity)} km`,
			}) || changed;
			return;
		}

		const expense_limit = limits[row.expense];
		if (!expense_limit) {
			return;
		}

		if (normalize_expense_name(row.expense) === "maintenance fee") {
			const rate = get_maintenance_fee_daily_rate(frm);
			const quantity = flt(frm.doc.days_in_trip);
			const maintenance_details = get_maintenance_details(frm);
			changed = update_row_if_changed(row, {
				rate,
				quantity,
				previous_month_maintenance_cost: flt(maintenance_details.amount),
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(maintenance_details.amount)} previous month maintenance (${maintenance_details.from_date || "N/A"} to ${maintenance_details.to_date || "N/A"}) / 30 days x ${format_formula_number(quantity)} trip days`,
			}) || changed;
		} else if (normalize_expense_name(row.expense) === "management fee") {
			const quantity = get_trip_setting_value(frm, "management_fee_percentage");
			const rate = flt(frm.doc.expected_revenue) / 100;
			changed = update_row_if_changed(row, {
				quantity,
				rate,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(quantity)}% of ${format_formula_number(frm.doc.expected_revenue)}`,
			}) || changed;
		} else if (normalize_expense_name(row.expense) === "salaries") {
			const quantity = get_trip_setting_value(frm, "salaries_percentage");
			const rate = flt(frm.doc.expected_revenue) / 100;
			changed = update_row_if_changed(row, {
				quantity,
				rate,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(quantity)}% of ${format_formula_number(frm.doc.expected_revenue)}`,
			}) || changed;
		} else if (expense_limit.calculation_method === "Per Trip Day") {
			const rate = flt(expense_limit.amount);
			const quantity = flt(frm.doc.days_in_trip);
			changed = update_row_if_changed(row, {
				rate,
				quantity,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${rate} x ${quantity} trip days`,
			}) || changed;
		} else if (expense_limit.calculation_method === "Salary Allocation") {
			const rate = get_salary_allocation_rate(frm);
			const quantity = flt(frm.doc.days_in_trip);
			changed = update_row_if_changed(row, {
				rate,
				quantity,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(frm.doc.salaries)} / 30 / ${format_formula_number(frm.doc.active_vehicles)} x ${format_formula_number(quantity)} trip days`,
			}) || changed;
		} else if (expense_limit.calculation_method === "Vehicle Depreciation") {
			const month_number = get_depreciation_month_number(frm);
			const vehicle_cost = get_vehicle_cost(frm);
			const rate = get_vehicle_depreciation_rate(frm, month_number);
			const quantity = flt(frm.doc.days_in_trip);
			changed = update_row_if_changed(row, {
				rate,
				quantity,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(vehicle_cost)} / ${format_formula_number(month_number)} / 12 / 30 x ${format_formula_number(quantity)} trip days`,
			}) || changed;
		} else if (expense_limit.calculation_method === "Percentage of Expected Revenue") {
			const quantity = flt(row.quantity);
			const rate = flt(frm.doc.expected_revenue) / 100;
			changed = update_row_if_changed(row, {
				quantity,
				rate,
				previous_month_maintenance_cost: 0,
				amount: flt(rate) * flt(quantity),
				description: `${format_formula_number(quantity)}% of ${format_formula_number(frm.doc.expected_revenue)}`,
			}) || changed;
		} else {
			const rate = flt(expense_limit.amount);
			changed = update_row_if_changed(row, {
				rate,
				quantity: 1,
				previous_month_maintenance_cost: 0,
				amount: flt(rate),
				description: __("Fixed amount"),
			}) || changed;
		}
	});

	if (changed) {
		frm.refresh_field("trip_expenses_outline");
	}
}

function calculate_days_in_trip(frm) {
	if (!should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.departure_date || !frm.doc.return_date) {
		set_value_if_changed(frm, "days_in_trip", 0);
		return;
	}

	const days_in_trip = frappe.datetime.get_day_diff(frm.doc.return_date, frm.doc.departure_date) + 1;

	if (days_in_trip < 1) {
		frappe.msgprint(__("Return Date cannot be before Departure Date."));
		set_value_if_changed(frm, "days_in_trip", 0);
		return;
	}

	set_value_if_changed(frm, "days_in_trip", days_in_trip);
}

function load_route_expense_limits(frm, options = {}) {
	const recalculate = options.recalculate !== false;
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
			if (!recalculate || !should_recalculate(frm)) {
				return;
			}

			apply_calculated_expenses(frm);
			calculate_totals(frm);
			validate_trip_expenses(frm);
		},
	});
}

function add_submitted_buttons(frm) {
	frm.add_custom_button(__("Create Purchase Order"), () => {
		show_payable_expenses_dialog(frm);
	});

	if (!frm.doc.quotation) {
		frm.add_custom_button(__("Create Quotation"), () => {
			make_quotation(frm);
		});
	}
}

function validate_trip_expenses(frm) {
	if (!should_recalculate(frm)) {
		return;
	}

	(frm.doc.trip_expenses_outline || []).forEach((row) => {
		validate_row_expense(frm, row);
		validate_row_amount(frm, row);
	});
}

function validate_row_expense(frm, row) {
	if (!should_recalculate(frm)) {
		return;
	}

	if (!row || !row.expense) {
		return;
	}
	row.expense = canonical_expense_label(row.expense);
	if (normalize_expense_name(row.expense) === "tyres") {
		return;
	}

	const duplicate = (frm.doc.trip_expenses_outline || []).some((other_row) => {
		return other_row.name !== row.name
			&& normalize_expense_name(other_row.expense) === normalize_expense_name(row.expense);
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
	if (!should_recalculate(frm)) {
		return;
	}

	if (!row || !row.expense) {
		return;
	}

	row.expense = canonical_expense_label(row.expense);
	if (normalize_expense_name(row.expense) === "tyres") {
		return;
	}

	const limits = frm._route_expense_limits || {};
	const expense_limit = limits[row.expense] || {};
	const max_amount = get_allowed_expense_amount(expense_limit, frm, row.quantity);

	if (frm.doc.route && limits[row.expense] !== undefined && flt(row.amount) > max_amount) {
		frappe.msgprint(
			__(`${row.expense} cannot exceed the route predefined amount ${format_currency(max_amount)}.`)
		);
		frappe.model.set_value(row.doctype, row.name, "amount", max_amount);
	}
}

function get_allowed_expense_amount(expense_limit, frm, percentage_override = null) {
	if (normalize_expense_name(expense_limit.expense) === "maintenance fee") {
		return get_maintenance_fee_daily_rate(frm) * flt(frm.doc.days_in_trip);
	}
	if (normalize_expense_name(expense_limit.expense) === "management fee") {
		return flt(frm.doc.expected_revenue) * get_trip_setting_value(frm, "management_fee_percentage") / 100;
	}
	if (normalize_expense_name(expense_limit.expense) === "salaries") {
		return flt(frm.doc.expected_revenue) * get_trip_setting_value(frm, "salaries_percentage") / 100;
	}

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
	if (expense_limit.calculation_method === "Percentage of Expected Revenue") {
		const percentage = percentage_override === null
			? flt(expense_limit.percentage)
			: flt(percentage_override);
		return flt(frm.doc.expected_revenue) * percentage / 100;
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

	return get_vehicle_cost(frm) / month_number / 12 / 30;
}

function get_maintenance_fee_daily_rate(frm) {
	return flt(get_maintenance_details(frm).amount) / 30;
}

function get_default_trip_settings() {
	return {
		management_fee_percentage: 3,
		salaries_percentage: 10,
		heavy_truck_vehicle_cost: 85000000,
		light_truck_vehicle_cost: 45000000,
		heavy_truck_tyre_price: 0,
		heavy_truck_number_of_tyres: 0,
			heavy_truck_tyre_lifecycle_km: 0,
			light_truck_tyre_price: 0,
			light_truck_number_of_tyres: 0,
			light_truck_tyre_lifecycle_km: 0,
			heavy_truck_litres_per_km: 0,
			light_truck_litres_per_km: 0,
	};
}

function load_trip_settings(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_trip_settings",
		callback(response) {
			frm._trip_settings = Object.assign(get_default_trip_settings(), response.message || {});
			if (!should_recalculate(frm)) {
				return;
			}

			apply_calculated_expenses(frm);
			calculate_totals(frm);
			validate_trip_expenses(frm);
		},
	});
}

function get_trip_setting_value(frm, fieldname) {
	const settings = frm._trip_settings || get_default_trip_settings();
	const value = settings[fieldname];
	if (value === undefined || value === null || value === "") {
		return flt(get_default_trip_settings()[fieldname]);
	}

	return flt(value);
}

function get_vehicle_cost(frm) {
	return flt(frm._vehicle_cost);
}

function get_default_tyre_settings() {
	return {
		tyre_price: 0,
		number_of_tyres: 0,
		tyre_lifecycle_km: 0,
	};
}

function get_tyre_settings(frm) {
	return Object.assign(get_default_tyre_settings(), frm._tyre_settings || {});
}

function get_default_maintenance_details() {
	return {
		amount: 0,
		from_date: null,
		to_date: null,
	};
}

function get_maintenance_details(frm) {
	return Object.assign(get_default_maintenance_details(), frm._maintenance_details || {});
}

function get_maintenance_reference_date(frm) {
	return frm.doc.departure_date || frm.doc.transaction_date || frappe.datetime.get_today();
}

function get_fuel_litres_per_km(frm) {
	return flt(frm._fuel_litres_per_km);
}

function get_fuel_consumption_qty(distance, fuel_litres_per_km) {
	return flt(distance) * flt(fuel_litres_per_km);
}

function apply_calculated_fuel_consumption(frm) {
	if (!should_recalculate(frm)) {
		return;
	}

	const fuel_litres_per_km = get_fuel_litres_per_km(frm);
	let changed = false;
	(frm.doc.fuel || []).forEach((row) => {
		const fuel_consumption_qty = get_fuel_consumption_qty(row.distance, fuel_litres_per_km);
		if (flt(row.fuel_consumption_qty) !== flt(fuel_consumption_qty)) {
			row.fuel_consumption_qty = fuel_consumption_qty;
			changed = true;
		}
	});

	if (changed) {
		frm.refresh_field("fuel");
	}
}

function get_tyre_cost_per_km(tyre_price, vehicle_wheels, tyre_lifecycle_km) {
	tyre_lifecycle_km = flt(tyre_lifecycle_km);
	if (!tyre_lifecycle_km) {
		return 0;
	}

	return flt(tyre_price) * flt(vehicle_wheels) / tyre_lifecycle_km;
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
	const numeric_fields = new Set([
		"quantity",
		"rate",
		"amount",
		"previous_month_maintenance_cost",
		"exchange_rate",
		"base_amount",
	]);
	let changed = false;
	Object.keys(values).forEach((fieldname) => {
		const value = values[fieldname];
		const is_same = numeric_fields.has(fieldname)
			? flt(row[fieldname]) === flt(value)
			: row[fieldname] === value;
		if (!is_same) {
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

function load_tyre_settings_from_truck_type(frm, options = {}) {
	const recalculate = options.recalculate !== false;
	if (recalculate && !should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.vehicle) {
		frm._tyre_settings = get_default_tyre_settings();
		if (recalculate && should_recalculate(frm)) {
			apply_calculated_expenses(frm);
			calculate_totals(frm);
		}
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_tyre_settings_from_truck_type",
		args: {
			vehicle: frm.doc.vehicle,
		},
		callback(response) {
			frm._tyre_settings = Object.assign(get_default_tyre_settings(), response.message || {});
			if (recalculate && should_recalculate(frm)) {
				apply_calculated_expenses(frm);
				calculate_totals(frm);
			}
		},
	});
}

function load_vehicle_cost_from_truck_type(frm, options = {}) {
	const recalculate = options.recalculate !== false;
	if (recalculate && !should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.vehicle) {
		frm._vehicle_cost = 0;
		if (recalculate && should_recalculate(frm)) {
			apply_calculated_expenses(frm);
			calculate_totals(frm);
		}
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_vehicle_cost_from_truck_type",
		args: {
			vehicle: frm.doc.vehicle,
		},
		callback(response) {
			const vehicle_cost = flt(response.message);
			frm._vehicle_cost = vehicle_cost;
			if (recalculate && should_recalculate(frm)) {
				apply_calculated_expenses(frm);
				calculate_totals(frm);
			}
		},
	});
}

function load_fuel_litres_per_km_from_truck_type(frm, options = {}) {
	const recalculate = options.recalculate !== false;
	if (recalculate && !should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.vehicle) {
		frm._fuel_litres_per_km = 0;
		if (recalculate && should_recalculate(frm)) {
			apply_calculated_fuel_consumption(frm);
			calculate_totals(frm);
		}
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_fuel_litres_per_km_from_truck_type",
		args: {
			vehicle: frm.doc.vehicle,
		},
		callback(response) {
			frm._fuel_litres_per_km = flt(response.message);
			if (recalculate && should_recalculate(frm)) {
				apply_calculated_fuel_consumption(frm);
				calculate_totals(frm);
			}
		},
	});
}

function load_previous_month_maintenance_cost(frm, options = {}) {
	const recalculate = options.recalculate !== false;
	if (recalculate && !should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.vehicle) {
		frm._maintenance_details = get_default_maintenance_details();
		if (recalculate && should_recalculate(frm)) {
			apply_calculated_expenses(frm);
			calculate_totals(frm);
		}
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_previous_month_maintenance_cost_details",
		args: {
			vehicle: frm.doc.vehicle,
			reference_date: get_maintenance_reference_date(frm),
		},
		callback(response) {
			frm._maintenance_details = Object.assign(get_default_maintenance_details(), response.message || {});
			if (recalculate && should_recalculate(frm)) {
				apply_calculated_expenses(frm);
				calculate_totals(frm);
			}
		},
	});
}

function load_last_fuel_purchase_price(frm, options = {}) {
	const recalculate = options.recalculate !== false;
	if (recalculate && !should_recalculate(frm)) {
		return;
	}

	if (!frm.doc.fuel_item) {
		if (recalculate && should_recalculate(frm)) {
			set_value_if_changed(frm, "fuel_price", 0);
			calculate_totals(frm);
		}
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_last_fuel_purchase_price",
		args: {
			fuel_item: frm.doc.fuel_item,
		},
		callback(response) {
			const price_details = response.message || {};
			const rate = flt(price_details.rate);
			if (!rate) {
				return;
			}

			if (recalculate && should_recalculate(frm)) {
				set_value_if_changed(frm, "fuel_price", rate);
				calculate_totals(frm);
			}
		},
	});
}

function should_recalculate(frm) {
	if (!frm || !frm.doc) {
		return false;
	}
	if (frm.is_new()) {
		return true;
	}
	if (frm._trip_simulation_refreshing) {
		return false;
	}
	return frm.is_dirty();
}

function release_refresh_guard(frm) {
	setTimeout(() => {
		frm._trip_simulation_refreshing = false;
	}, 300);
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

function format_percentage_value(value) {
	return `${flt(value).toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	})}%`;
}

function format_dashboard_number(value) {
	return flt(value).toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2,
	});
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

function make_quotation(frm) {
	if (frm.doc.docstatus !== 1) {
		frappe.msgprint(__("Please submit the Trip Simulation before creating a Quotation."));
		return;
	}
	if (frm.doc.quotation) {
		frappe.set_route("Form", "Quotation", frm.doc.quotation);
		return;
	}
	if (!flt(frm.doc.expected_revenue)) {
		frappe.msgprint(__("Expected Revenue must be greater than zero before creating a Quotation."));
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.create_quotation",
		args: {
			trip_simulation: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Creating Quotation..."),
		callback(response) {
			const quotation = response.message;
			if (!quotation) {
				return;
			}

			frappe.set_route("Form", quotation.doctype, quotation.name);
		},
	});
}
