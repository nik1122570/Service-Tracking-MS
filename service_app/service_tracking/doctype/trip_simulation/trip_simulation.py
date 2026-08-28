# Copyright (c) 2026, Nickson  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, date_diff, flt, get_first_day, get_last_day, getdate, nowdate
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from service_app.service_tracking.expense_labels import canonical_expense_label, normalize_expense_name
from service_app.service_tracking.doctype.fuel_card_ledger_entry.fuel_card_ledger_entry import (
	create_fuel_card_ledger_entry,
)

TRIP_SETTINGS_DEFAULTS = {
	"management_fee_percentage": 3,
	"salaries_percentage": 10,
	"driver_mileage_per_day": 0,
	"heavy_truck_vehicle_cost": 85000000,
	"light_truck_vehicle_cost": 45000000,
	"heavy_truck_tyre_price": 0,
	"heavy_truck_number_of_tyres": 0,
	"heavy_truck_tyre_lifecycle_km": 0,
	"light_truck_tyre_price": 0,
	"light_truck_number_of_tyres": 0,
	"light_truck_tyre_lifecycle_km": 0,
	"heavy_truck_litres_per_km": 0,
	"light_truck_litres_per_km": 0,
}

PURCHASE_ORDER_JOB_CARD_LINK_FIELDS = ("custom_job_card_link", "eah_job_card", "job_card_link")


class TripSimulation(Document):
	def validate(self):
		self.calculate_days_in_trip()
		self.set_fuel_price_from_last_purchase_price()

		if self.route and (
			self.has_value_changed("route") or (not self.fuel and not self.trip_expenses_outline)
		):
			self.load_route_details()
		else:
			self.apply_calculated_expenses()
			self.validate_trip_expenses()
			self.calculate_totals()

		self.validate_targeted_net_profit()

	def on_submit(self):
		self.create_fuel_card_trip_usage_entry()

	def on_cancel(self):
		self.reverse_fuel_card_trip_usage_entry()

	def set_fuel_price_from_last_purchase_price(self):
		fuel_price_details = get_last_fuel_purchase_price(self.fuel_item)
		if flt(fuel_price_details.get("rate")):
			self.fuel_price = flt(fuel_price_details.get("rate"))

	def create_fuel_card_trip_usage_entry(self):
		if not self.fuel_card or flt(self.total_fuel_consumption_qty_ratio) <= 0:
			return

		if flt(self.fuel_price) <= 0:
			frappe.throw(
				_(
					"Fuel Price is required before deducting from Fuel Card. "
					"Please make sure the Fuel Item has a purchase price or recharge/issue the Fuel Card with a valid rate."
				)
			)

		if self.fuel_card_ledger_entry:
			return

		ledger_entry = create_fuel_card_ledger_entry(
			fuel_card=self.fuel_card,
			transaction_type="Trip Usage",
			litres_out=self.total_fuel_consumption_qty_ratio,
			rate=self.fuel_price,
			reference_doctype=self.doctype,
			reference_name=self.name,
			posting_date=self.transaction_date,
			vehicle=self.vehicle,
			driver=self.driver,
			remarks=_("Fuel used by Trip Simulation {0}").format(self.name),
		)
		self.db_set("fuel_card_ledger_entry", ledger_entry.name, update_modified=False)

	def reverse_fuel_card_trip_usage_entry(self):
		if not self.fuel_card or flt(self.total_fuel_consumption_qty_ratio) <= 0:
			return

		create_fuel_card_ledger_entry(
			fuel_card=self.fuel_card,
			transaction_type="Cancellation",
			litres_in=self.total_fuel_consumption_qty_ratio,
			rate=self.fuel_price,
			reference_doctype=self.doctype,
			reference_name=self.name,
			posting_date=self.transaction_date,
			vehicle=self.vehicle,
			driver=self.driver,
			remarks=_("Cancellation of Trip Simulation {0} fuel usage").format(self.name),
		)

	def calculate_days_in_trip(self):
		if not self.departure_date or not self.return_date:
			self.days_in_trip = 0
			return

		if self.return_date < self.departure_date:
			frappe.throw(_("Return Date cannot be before Departure Date."))

		self.days_in_trip = date_diff(self.return_date, self.departure_date) + 1

	def validate_trip_expenses(self):
		self.validate_duplicate_trip_expenses()
		self.validate_expenses_against_route()

	def validate_duplicate_trip_expenses(self):
		seen_expenses = set()

		for row in self.trip_expenses_outline:
			if not row.expense:
				continue

			row.expense = canonical_expense_label(row.expense)
			expense_key = normalize_expense_name(row.expense)
			if expense_key in seen_expenses:
				frappe.throw(
					_("Expense {0} is already added in Trip Expenses Outline. Remove the duplicate row {1}.").format(
						frappe.bold(row.expense),
						frappe.bold(row.idx),
					)
				)

			seen_expenses.add(expense_key)

	def validate_expenses_against_route(self):
		if not self.route:
			return

		route_expense_limits = get_route_expense_limits(self.route)

		for row in self.trip_expenses_outline:
			if not row.expense:
				continue

			row.expense = canonical_expense_label(row.expense)
			if normalize_expense_name(row.expense) == "tyres":
				continue

			if row.expense not in route_expense_limits:
				frappe.throw(
					_("Expense {0} in row {1} is not defined in Simulation Route {2}.").format(
						frappe.bold(row.expense),
						frappe.bold(row.idx),
						frappe.bold(self.route),
					)
				)

			expense_limit = route_expense_limits[row.expense]
			max_amount = get_allowed_expense_amount(
				expense_limit,
				self.days_in_trip,
				self.salaries,
				self.active_vehicles,
				get_vehicle_cost_from_truck_type(self.vehicle),
				0,
				self.get_depreciation_month_number(),
				self.expected_revenue,
				row.quantity,
				sum(flt(step.distance) for step in self.fuel),
				self.vehicle,
				self.departure_date or self.transaction_date,
			)
			if flt(row.amount) > max_amount:
				frappe.throw(
					_(
						"Expense {0} in row {1} cannot exceed the route predefined amount {2}."
					).format(
						frappe.bold(row.expense),
						frappe.bold(row.idx),
						frappe.bold(frappe.format_value(max_amount, {"fieldtype": "Currency"})),
					)
				)

	def apply_calculated_expenses(self):
		if not self.route:
			return

		route_expense_limits = get_route_expense_limits(self.route)
		trip_settings = get_trip_settings()
		tyre_settings = get_tyre_settings_from_truck_type(self.vehicle)
		for row in self.trip_expenses_outline:
			if not row.expense:
				continue

			row.expense = canonical_expense_label(row.expense)
			if normalize_expense_name(row.expense) == "tyres":
				row.rate = get_tyre_cost_per_km(
					tyre_settings.get("tyre_price"),
					tyre_settings.get("number_of_tyres"),
					tyre_settings.get("tyre_lifecycle_km"),
				)
				row.quantity = sum(flt(step.distance) for step in self.fuel)
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(tyre_settings.get('tyre_price'))} x "
					f"{format_formula_number(tyre_settings.get('number_of_tyres'))} tyres / "
					f"{format_formula_number(tyre_settings.get('tyre_lifecycle_km'))} km x "
					f"{format_formula_number(row.quantity)} km"
				)
				continue

			if row.expense not in route_expense_limits:
				continue

			expense_limit = route_expense_limits[row.expense]
			if normalize_expense_name(row.expense) == "maintenance fee":
				maintenance_details = get_previous_month_maintenance_cost_details(
					self.vehicle,
					self.departure_date or self.transaction_date,
				)
				row.rate = get_maintenance_fee_daily_rate(maintenance_details.get("amount"))
				row.quantity = self.days_in_trip or 0
				row.previous_month_maintenance_cost = flt(maintenance_details.get("amount"))
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(maintenance_details.get('amount'))} previous month maintenance "
					f"({maintenance_details.get('from_date') or 'N/A'} to {maintenance_details.get('to_date') or 'N/A'}) / 30 days "
					f"x {format_formula_number(row.quantity)} trip days"
				)
			elif normalize_expense_name(row.expense) == "management fee":
				row.quantity = get_trip_setting_value(trip_settings, "management_fee_percentage")
				row.rate = flt(self.expected_revenue) / 100
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(row.quantity)}% of {format_formula_number(self.expected_revenue)}"
				)
			elif normalize_expense_name(row.expense) == "salaries":
				row.quantity = get_trip_setting_value(trip_settings, "salaries_percentage")
				row.rate = flt(self.expected_revenue) / 100
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(row.quantity)}% of {format_formula_number(self.expected_revenue)}"
				)
			elif normalize_expense_name(row.expense) == "driver mileage":
				row.rate = get_trip_setting_value(trip_settings, "driver_mileage_per_day")
				row.quantity = self.days_in_trip or 0
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(row.rate)} per day x "
					f"{format_formula_number(row.quantity)} trip days"
				)
			elif expense_limit.get("calculation_method") == "Per Trip Day":
				row.rate = flt(expense_limit.get("amount"))
				row.quantity = self.days_in_trip or 0
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = f"{row.rate:g} x {flt(row.quantity):g} trip days"
			elif expense_limit.get("calculation_method") == "Salary Allocation":
				row.rate = get_salary_allocation_rate(self.salaries, self.active_vehicles)
				row.quantity = self.days_in_trip or 0
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(self.salaries)} / 30 / {format_formula_number(self.active_vehicles)} "
					f"x {format_formula_number(row.quantity)} trip days"
				)
			elif expense_limit.get("calculation_method") == "Vehicle Depreciation":
				month_number = self.get_depreciation_month_number()
				vehicle_cost = get_vehicle_cost_from_truck_type(self.vehicle)
				row.rate = get_vehicle_depreciation_rate(vehicle_cost, month_number)
				row.quantity = self.days_in_trip or 0
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(vehicle_cost)} / {format_formula_number(month_number)} / 12 / 30 "
					f"x {format_formula_number(row.quantity)} trip days"
				)
			elif expense_limit.get("calculation_method") == "Percentage of Expected Revenue":
				row.quantity = flt(row.quantity)
				row.rate = flt(self.expected_revenue) / 100
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate) * flt(row.quantity)
				row.description = (
					f"{format_formula_number(row.quantity)}% of {format_formula_number(self.expected_revenue)}"
				)
			else:
				row.rate = flt(expense_limit.get("amount"))
				row.quantity = 1
				row.previous_month_maintenance_cost = 0
				row.amount = flt(row.rate)
				row.description = "Fixed amount"

	def get_depreciation_month_number(self):
		return get_depreciation_month_number(self.departure_date or self.transaction_date)

	def calculate_totals(self):
		self.apply_calculated_fuel_consumption()
		self.total_distance_km = sum(flt(row.distance) for row in self.fuel)
		self.total_fuel_consumption_qty_ratio = sum(flt(row.fuel_consumption_qty) for row in self.fuel)
		self.total_fuel_costs = flt(self.total_fuel_consumption_qty_ratio) * flt(self.fuel_price)
		self.total_trip_cost = flt(self.total_fuel_costs) + sum(
			flt(row.amount) for row in self.trip_expenses_outline
		)
		expected_revenue = flt(self.expected_revenue)
		self.net_profit = flt(expected_revenue - flt(self.total_trip_cost), 2)
		self.net_profit_ = get_net_profit_margin_percentage(
			self.net_profit,
			expected_revenue,
		)

	def apply_calculated_fuel_consumption(self):
		for row in self.fuel:
			row.fuel_load_status = row.fuel_load_status or "Loaded"
			row.fuel_consumption_ratio = flt(
				row.fuel_consumption_ratio
				or get_fuel_litres_per_km_from_truck_type(self.vehicle)
			)
			row.fuel_consumption_qty = get_fuel_consumption_qty(
				row.distance,
				row.fuel_consumption_ratio,
			)

	def validate_targeted_net_profit(self):
		if flt(self.net_profit_) >= flt(self.targeted_net_profit):
			return

		frappe.throw(
			_("Net Profit Margin {0} cannot be below the Targeted Net Profit {1}.").format(
				frappe.bold(frappe.format_value(self.net_profit_, {"fieldtype": "Percent"})),
				frappe.bold(frappe.format_value(self.targeted_net_profit, {"fieldtype": "Percent"})),
			),
			title=_("Targeted Net Profit Not Met"),
		)

	def load_route_details(self):
		route_details = get_route_details(
			self.route,
			self.days_in_trip,
			self.salaries,
			self.active_vehicles,
			get_vehicle_cost_from_truck_type(self.vehicle),
			0,
			self.get_depreciation_month_number(),
			self.expected_revenue,
			self.vehicle,
			self.departure_date or self.transaction_date,
		)

		self.set("fuel", [])
		for row in route_details.get("trip_steps", []):
			self.append("fuel", row)

		self.set("trip_expenses_outline", [])
		for row in route_details.get("fixed_expenses", []):
			self.append("trip_expenses_outline", row)

		self.total_distance_km = flt(route_details.get("total_distance"))
		self.total_fuel_consumption_qty_ratio = flt(route_details.get("total_fuel_consumption_qty"))

		self.validate_trip_expenses()
		self.calculate_totals()


@frappe.whitelist()
def get_route_details(
	route,
	days_in_trip=0,
	salaries=0,
	active_vehicles=0,
	vehicle_costs=0,
	maintenance_costs=0,
	depreciation_month_number=0,
	expected_revenue=0,
	vehicle=None,
	maintenance_reference_date=None,
):
	if not route:
		return {
			"trip_steps": [],
			"fixed_expenses": [],
			"total_distance": 0,
			"total_fuel_consumption_qty": 0,
			"fuel_litres_per_km": get_fuel_litres_per_km_from_truck_type(vehicle),
			"maintenance_details": get_previous_month_maintenance_cost_details(
				vehicle,
				maintenance_reference_date,
			),
		}

	route_doc = frappe.get_doc("Simulation Routes", route)
	trip_steps = []
	fixed_expenses = []

	for row in route_doc.trip_steps:
		fuel_load_status = row.fuel_load_status or "Loaded"
		fuel_consumption_ratio = flt(
			row.fuel_consumption_ratio
			or get_fuel_litres_per_km_from_truck_type(vehicle)
		)
		trip_steps.append(
			{
				"location": row.location,
				"unloading_location": row.unloading_location,
				"distance": flt(row.distance),
				"fuel_load_status": fuel_load_status,
				"fuel_consumption_ratio": fuel_consumption_ratio,
				"fuel_consumption_qty": get_fuel_consumption_qty(
					row.distance,
					fuel_consumption_ratio,
				),
			}
		)

	total_distance = sum(flt(row.get("distance")) for row in trip_steps)
	total_fuel_consumption_qty = sum(flt(row.get("fuel_consumption_qty")) for row in trip_steps)
	trip_settings = get_trip_settings()
	vehicle_costs = get_vehicle_cost_from_truck_type(vehicle)
	tyre_settings = get_tyre_settings_from_truck_type(vehicle)
	fuel_litres_per_km = get_fuel_litres_per_km_from_truck_type(vehicle)
	maintenance_details = get_previous_month_maintenance_cost_details(
		vehicle,
		maintenance_reference_date,
	)

	seen_expenses = set()
	for row in route_doc.fixed_expenses:
		expense = canonical_expense_label(row.expense)
		expense_key = normalize_expense_name(expense)
		if not expense or expense_key in seen_expenses:
			continue

		seen_expenses.add(expense_key)
		expense_meta = get_fixed_expense_meta(expense)
		rate = flt(row.amount)
		quantity = 1
		amount = rate
		description = f"Fetched from route {route_doc.name}"

		if expense_key == "tyres":
			rate = get_tyre_cost_per_km(
				tyre_settings.get("tyre_price"),
				tyre_settings.get("number_of_tyres"),
				tyre_settings.get("tyre_lifecycle_km"),
			)
			quantity = total_distance
			amount = rate * quantity
			description = (
				f"{format_formula_number(tyre_settings.get('tyre_price'))} x "
				f"{format_formula_number(tyre_settings.get('number_of_tyres'))} tyres / "
				f"{format_formula_number(tyre_settings.get('tyre_lifecycle_km'))} km x "
				f"{format_formula_number(quantity)} km"
			)
		elif expense_key == "maintenance fee":
			rate = get_maintenance_fee_daily_rate(maintenance_details.get("amount"))
			quantity = flt(days_in_trip)
			amount = rate * quantity
			previous_month_maintenance_cost = flt(maintenance_details.get("amount"))
			description = (
				f"{format_formula_number(maintenance_details.get('amount'))} previous month maintenance "
				f"({maintenance_details.get('from_date') or 'N/A'} to {maintenance_details.get('to_date') or 'N/A'}) / 30 days "
				f"x {format_formula_number(quantity)} trip days"
			)
		elif expense_key == "management fee":
			quantity = get_trip_setting_value(trip_settings, "management_fee_percentage")
			rate = flt(expected_revenue) / 100
			amount = rate * quantity
			description = f"{format_formula_number(quantity)}% of {format_formula_number(expected_revenue)}"
		elif expense_key == "salaries":
			quantity = get_trip_setting_value(trip_settings, "salaries_percentage")
			rate = flt(expected_revenue) / 100
			amount = rate * quantity
			description = f"{format_formula_number(quantity)}% of {format_formula_number(expected_revenue)}"
		elif expense_key == "driver mileage":
			rate = get_trip_setting_value(trip_settings, "driver_mileage_per_day")
			quantity = flt(days_in_trip)
			amount = rate * quantity
			description = f"{format_formula_number(rate)} per day x {format_formula_number(quantity)} trip days"
		elif expense_meta.get("calculation_method") == "Per Trip Day":
			quantity = flt(days_in_trip)
			amount = rate * quantity
			description = f"{rate:g} x {quantity:g} trip days"
		elif expense_meta.get("calculation_method") == "Salary Allocation":
			rate = get_salary_allocation_rate(salaries, active_vehicles)
			quantity = flt(days_in_trip)
			amount = rate * quantity
			description = (
				f"{format_formula_number(salaries)} / 30 / {format_formula_number(active_vehicles)} "
				f"x {format_formula_number(quantity)} trip days"
			)
		elif expense_meta.get("calculation_method") == "Vehicle Depreciation":
			rate = get_vehicle_depreciation_rate(vehicle_costs, depreciation_month_number)
			quantity = flt(days_in_trip)
			amount = rate * quantity
			description = (
				f"{format_formula_number(vehicle_costs)} / {format_formula_number(depreciation_month_number)} / 12 / 30 "
				f"x {format_formula_number(quantity)} trip days"
			)
		elif expense_meta.get("calculation_method") == "Percentage of Expected Revenue":
			quantity = flt(expense_meta.get("percentage"))
			rate = flt(expected_revenue) / 100
			amount = rate * quantity
			description = f"{format_formula_number(quantity)}% of {format_formula_number(expected_revenue)}"

		fixed_expenses.append(
			{
				"expense": expense,
				"quantity": quantity,
				"rate": rate,
				"amount": amount,
				"previous_month_maintenance_cost": previous_month_maintenance_cost
				if expense_key == "maintenance fee"
				else 0,
				"description": description,
			}
		)

	return {
		"trip_steps": trip_steps,
		"fixed_expenses": fixed_expenses,
		"total_distance": total_distance,
		"total_fuel_consumption_qty": total_fuel_consumption_qty,
		"tyre_settings": tyre_settings,
		"fuel_litres_per_km": fuel_litres_per_km,
		"maintenance_details": maintenance_details,
	}


@frappe.whitelist()
def get_route_fixed_expenses(route):
	return get_route_details(route).get("fixed_expenses", [])


@frappe.whitelist()
def get_route_expense_limits(route):
	if not route:
		return {}

	route_doc = frappe.get_doc("Simulation Routes", route)
	limits = {}
	seen_expenses = set()

	for row in route_doc.fixed_expenses:
		if row.expense:
			expense = canonical_expense_label(row.expense)
			expense_key = normalize_expense_name(expense)
			if expense_key in seen_expenses:
				continue

			seen_expenses.add(expense_key)
			expense_meta = get_fixed_expense_meta(expense)
			limits[expense] = {
				"expense": expense,
				"amount": flt(row.amount),
				"calculation_method": expense_meta.get("calculation_method"),
				"percentage": flt(expense_meta.get("percentage")),
			}

	return limits


@frappe.whitelist()
def get_payable_expenses(trip_simulation):
	if not trip_simulation:
		return []

	doc = frappe.get_doc("Trip Simulation", trip_simulation)
	payable_expenses = frappe.get_all(
		"Fixed Expenses",
		filters={"is_payable": 1},
		fields=["name", "item"],
	)
	payable_expense_map = {expense.name: expense for expense in payable_expenses}
	expenses = []

	for row in doc.trip_expenses_outline:
		if row.expense not in payable_expense_map:
			continue
		if row.purchase_order:
			continue

		expenses.append(
			{
				"row_name": row.name,
				"expense": row.expense,
				"item": payable_expense_map[row.expense].item,
				"quantity": flt(row.quantity),
				"rate": flt(row.rate),
				"amount": flt(row.amount),
				"description": row.description,
			}
		)

	return expenses


@frappe.whitelist()
def create_purchase_order(trip_simulation, selected_expenses):
	if isinstance(selected_expenses, str):
		selected_expenses = frappe.parse_json(selected_expenses)

	if not selected_expenses:
		frappe.throw(_("Please select at least one payable expense."))

	doc = frappe.get_doc("Trip Simulation", trip_simulation)
	if doc.docstatus != 1:
		frappe.throw(_("Purchase Order can only be created from a submitted Trip Simulation."))

	if not doc.supplier:
		frappe.throw(_("Please set Supplier in Trip Simulation before creating a Purchase Order."))

	selected_row_names = {row.get("row_name") for row in selected_expenses if row.get("row_name")}
	if not selected_row_names:
		frappe.throw(_("Please select at least one payable expense."))

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		company = frappe.db.get_value("Company", {}, "name")

	purchase_order = frappe.new_doc("Purchase Order")
	purchase_order.naming_series = "PUR-ORD-.YYYY.-"
	purchase_order.title = doc.supplier
	purchase_order.supplier = doc.supplier
	purchase_order.company = company
	purchase_order.currency = frappe.db.get_value("Company", company, "default_currency")
	purchase_order.conversion_rate = 1
	purchase_order.transaction_date = doc.transaction_date or nowdate()
	purchase_order.schedule_date = doc.return_date or doc.departure_date or doc.transaction_date or nowdate()
	if frappe.get_meta("Purchase Order").has_field("custom_trip_simulation"):
		purchase_order.custom_trip_simulation = doc.name
	if frappe.get_meta("Purchase Order").has_field("custom_vehicle"):
		purchase_order.custom_vehicle = doc.vehicle
	if frappe.get_meta("Purchase Order").has_field("project"):
		purchase_order.project = doc.project
	if frappe.get_meta("Purchase Order").has_field("cost_center"):
		purchase_order.cost_center = doc.cost_center
	purchase_order.set("items", [])

	expense_rows = {row.name: row for row in doc.trip_expenses_outline}
	selected_expense_rows = []
	purchase_order_item_meta = frappe.get_meta("Purchase Order Item")
	for row_name in selected_row_names:
		row = expense_rows.get(row_name)
		if not row:
			frappe.throw(_("Selected expense row {0} was not found.").format(frappe.bold(row_name)))
		if row.purchase_order:
			frappe.throw(
				_("Expense {0} already has Purchase Order {1}.").format(
					frappe.bold(row.expense),
					frappe.bold(row.purchase_order),
				)
			)

		expense = frappe.db.get_value(
			"Fixed Expenses",
			row.expense,
			["is_payable", "item"],
			as_dict=True,
		)
		if not expense or not expense.is_payable:
			frappe.throw(_("Expense {0} is not payable.").format(frappe.bold(row.expense)))
		if not expense.item:
			frappe.throw(
				_("Please set Item in Fixed Expenses {0} before creating a Purchase Order.").format(
					frappe.bold(row.expense)
				)
			)

		qty = flt(row.quantity) or 1
		rate = flt(row.rate) if flt(row.rate) else flt(row.amount) / qty
		item_row = {
			"item_code": expense.item,
			"schedule_date": purchase_order.schedule_date,
			"qty": qty,
			"rate": rate,
			"description": row.description or row.expense,
		}
		if purchase_order_item_meta.has_field("project"):
			item_row["project"] = doc.project
		if purchase_order_item_meta.has_field("cost_center"):
			item_row["cost_center"] = doc.cost_center
		if purchase_order_item_meta.has_field("custom_vehicle"):
			item_row["custom_vehicle"] = doc.vehicle

		purchase_order.append("items", item_row)
		selected_expense_rows.append(row)

	if not purchase_order.items:
		frappe.throw(_("No Purchase Order items were created."))

	purchase_order.insert()
	for selected_expense_row in selected_expense_rows:
		frappe.db.set_value(
			selected_expense_row.doctype,
			selected_expense_row.name,
			"purchase_order",
			purchase_order.name,
			update_modified=False,
		)

	return {
		"name": purchase_order.name,
		"doctype": purchase_order.doctype,
	}


@frappe.whitelist()
def create_fuel_purchase_order(trip_simulation):
	if not trip_simulation:
		frappe.throw(_("Trip Simulation is required."))

	doc = frappe.get_doc("Trip Simulation", trip_simulation)
	if doc.docstatus != 1:
		frappe.throw(_("Fuel Purchase Order can only be created from a submitted Trip Simulation."))

	if doc.fuel_purchase_order:
		frappe.throw(
			_("Fuel Purchase Order {0} already exists for this Trip Simulation.").format(
				frappe.bold(doc.fuel_purchase_order)
			)
		)
	if not doc.fuel_supplier:
		frappe.throw(_("Please set Fuel Supplier before creating the Fuel Purchase Order."))
	if not doc.fuel_item:
		frappe.throw(_("Please set Fuel Item before creating the Fuel Purchase Order."))

	qty = flt(doc.total_fuel_consumption_qty_ratio)
	rate = flt(doc.fuel_price)
	if not qty:
		frappe.throw(_("Total Fuel Consumption Qty must be greater than zero."))
	if not rate:
		frappe.throw(_("Fuel Price must be greater than zero."))

	company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)
	if not company:
		company = frappe.db.get_value("Company", {}, "name")

	purchase_order = frappe.new_doc("Purchase Order")
	purchase_order.naming_series = "PUR-ORD-.YYYY.-"
	purchase_order.title = doc.fuel_supplier
	purchase_order.supplier = doc.fuel_supplier
	purchase_order.company = company
	purchase_order.currency = frappe.db.get_value("Company", company, "default_currency")
	purchase_order.conversion_rate = 1
	purchase_order.transaction_date = doc.transaction_date or nowdate()
	purchase_order.schedule_date = doc.return_date or doc.departure_date or doc.transaction_date or nowdate()
	if frappe.get_meta("Purchase Order").has_field("custom_trip_simulation"):
		purchase_order.custom_trip_simulation = doc.name
	if frappe.get_meta("Purchase Order").has_field("custom_vehicle"):
		purchase_order.custom_vehicle = doc.vehicle
	if frappe.get_meta("Purchase Order").has_field("project"):
		purchase_order.project = doc.project
	if frappe.get_meta("Purchase Order").has_field("cost_center"):
		purchase_order.cost_center = doc.cost_center

	item_row = {
		"item_code": doc.fuel_item,
		"schedule_date": purchase_order.schedule_date,
		"qty": qty,
		"rate": rate,
		"description": _("Fuel for Trip Simulation {0}").format(doc.name),
	}
	purchase_order_item_meta = frappe.get_meta("Purchase Order Item")
	if purchase_order_item_meta.has_field("project"):
		item_row["project"] = doc.project
	if purchase_order_item_meta.has_field("cost_center"):
		item_row["cost_center"] = doc.cost_center
	if purchase_order_item_meta.has_field("custom_vehicle"):
		item_row["custom_vehicle"] = doc.vehicle

	purchase_order.append("items", item_row)
	purchase_order.insert()

	frappe.db.set_value(
		doc.doctype,
		doc.name,
		"fuel_purchase_order",
		purchase_order.name,
		update_modified=False,
	)

	return {
		"name": purchase_order.name,
		"doctype": purchase_order.doctype,
	}


@frappe.whitelist()
def create_quotation(trip_simulation):
	if not trip_simulation:
		frappe.throw(_("Trip Simulation is required."))

	doc = frappe.get_doc("Trip Simulation", trip_simulation)
	if doc.docstatus != 1:
		frappe.throw(_("Quotation can only be created from a submitted Trip Simulation."))
	if doc.quotation:
		frappe.throw(
			_("Quotation {0} already exists for this Trip Simulation.").format(
				frappe.bold(doc.quotation)
			)
		)
	if not flt(doc.expected_revenue):
		frappe.throw(_("Expected Revenue must be greater than zero before creating a Quotation."))

	project = frappe.get_cached_doc("Project", doc.project)
	customer = doc.customer
	if not customer:
		frappe.throw(_("Please set Customer in Trip Simulation before creating a Quotation."))

	sales_item = project.get("custom_sales_item")
	if not sales_item:
		frappe.throw(_("Please set Sales Item on Project {0} before creating a Quotation.").format(
			frappe.bold(doc.project)
		))

	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = customer
	quotation.transaction_date = doc.transaction_date or nowdate()
	quotation.valid_till = doc.return_date or doc.departure_date or doc.transaction_date or nowdate()
	quotation.order_type = "Sales"
	if quotation.meta.has_field("project"):
		quotation.project = doc.project
	if quotation.meta.has_field("custom_trip_simulation"):
		quotation.custom_trip_simulation = doc.name

	item_row = {
		"item_code": sales_item,
		"qty": 1,
		"rate": flt(doc.expected_revenue),
		"description": _("Trip quotation for {0} via route {1}").format(doc.name, doc.route),
	}
	quotation_item_meta = frappe.get_meta("Quotation Item")
	if quotation_item_meta.has_field("project"):
		item_row["project"] = doc.project
	if quotation_item_meta.has_field("cost_center"):
		item_row["cost_center"] = doc.cost_center
	if quotation_item_meta.has_field("custom_vehicle"):
		item_row["custom_vehicle"] = doc.vehicle

	quotation.append("items", item_row)
	quotation.insert()

	frappe.db.set_value(
		doc.doctype,
		doc.name,
		"quotation",
		quotation.name,
		update_modified=False,
	)

	return {
		"name": quotation.name,
		"doctype": quotation.doctype,
	}


@frappe.whitelist()
def ensure_purchase_order_custom_fields():
	create_custom_fields(
		{
			"Purchase Order": [
				{
					"fieldname": "custom_trip_simulation",
					"label": "Trip Simulation",
					"fieldtype": "Link",
					"options": "Trip Simulation",
					"insert_after": "supplier",
					"read_only": 1,
					"no_copy": 1,
					"allow_on_submit": 1,
				},
				{
					"fieldname": "custom_vehicle",
					"label": "Vehicle",
					"fieldtype": "Link",
					"options": "Vehicle",
					"insert_after": "custom_trip_simulation",
					"read_only": 1,
					"no_copy": 1,
					"allow_on_submit": 1,
				}
			]
		},
		update=True,
	)


def get_fixed_expense_meta(expense):
	if not expense:
		return {}

	expense = canonical_expense_label(expense)
	return frappe.db.get_value(
		"Fixed Expenses",
		expense,
		["calculation_method", "percentage"],
		as_dict=True,
	) or {}


@frappe.whitelist()
def get_trip_settings():
	settings = {}
	for fieldname, default_value in TRIP_SETTINGS_DEFAULTS.items():
		try:
			value = frappe.db.get_single_value("Trip Settings", fieldname)
		except Exception:
			value = None

		settings[fieldname] = flt(value) if value not in (None, "") else default_value

	return settings


@frappe.whitelist()
def get_vehicle_cost_from_truck_type(vehicle):
	truck_type = get_vehicle_truck_type(vehicle)
	if not truck_type:
		return 0

	truck_type_key = normalize_expense_name(truck_type)
	settings = get_trip_settings()
	if truck_type_key == "heavy truck":
		return get_trip_setting_value(settings, "heavy_truck_vehicle_cost")
	if truck_type_key == "light truck":
		return get_trip_setting_value(settings, "light_truck_vehicle_cost")

	return 0


@frappe.whitelist()
def get_tyre_settings_from_truck_type(vehicle):
	truck_type = get_vehicle_truck_type(vehicle)
	if not truck_type:
		return {
			"tyre_price": 0,
			"number_of_tyres": 0,
			"tyre_lifecycle_km": 0,
		}

	truck_type_key = normalize_expense_name(truck_type)
	settings = get_trip_settings()
	if truck_type_key == "heavy truck":
		prefix = "heavy_truck"
	elif truck_type_key == "light truck":
		prefix = "light_truck"
	else:
		return {
			"tyre_price": 0,
			"number_of_tyres": 0,
			"tyre_lifecycle_km": 0,
		}

	return {
		"tyre_price": get_trip_setting_value(settings, f"{prefix}_tyre_price"),
		"number_of_tyres": get_trip_setting_value(settings, f"{prefix}_number_of_tyres"),
		"tyre_lifecycle_km": get_trip_setting_value(settings, f"{prefix}_tyre_lifecycle_km"),
	}


@frappe.whitelist()
def get_fuel_litres_per_km_from_truck_type(vehicle, fuel_load_status=None):
	truck_type = get_vehicle_truck_type(vehicle)
	if not truck_type:
		return 0

	truck_type_key = normalize_expense_name(truck_type)
	settings = get_trip_settings()
	if truck_type_key == "heavy truck":
		return get_trip_setting_value(settings, "heavy_truck_litres_per_km")
	if truck_type_key == "light truck":
		return get_trip_setting_value(settings, "light_truck_litres_per_km")

	return 0


@frappe.whitelist()
def get_fuel_km_per_litre_from_truck_type(vehicle):
	"""Backward-compatible alias for cached clients using the old method name."""
	return get_fuel_litres_per_km_from_truck_type(vehicle)


def get_vehicle_truck_type(vehicle):
	if not vehicle:
		return None

	vehicle_meta = frappe.get_meta("Vehicle")
	fieldnames = ["truck_type", "custom_truck_type"]
	for df in vehicle_meta.fields:
		if df.options == "Truck Type" or normalize_expense_name(df.label) == "truck type":
			fieldnames.insert(0, df.fieldname)

	existing_columns = set(get_existing_table_columns("Vehicle", fieldnames))
	for fieldname in dict.fromkeys(fieldnames):
		if not vehicle_meta.has_field(fieldname) and fieldname not in existing_columns:
			continue

		truck_type = frappe.db.get_value("Vehicle", vehicle, fieldname)
		if truck_type:
			return truck_type

	return None


def get_trip_setting_value(settings, fieldname):
	default_value = TRIP_SETTINGS_DEFAULTS.get(fieldname, 0)
	value = settings.get(fieldname) if settings else None
	return flt(value) if value not in (None, "") else default_value


def get_fuel_consumption_qty(distance, fuel_litres_per_km):
	return flt(distance) * flt(fuel_litres_per_km)


@frappe.whitelist()
def get_last_fuel_purchase_price(fuel_item):
	if not fuel_item:
		return {
			"rate": 0,
			"source_doctype": None,
			"source_name": None,
			"posting_date": None,
			"supplier": None,
		}

	purchase_invoice_rate = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(pii.base_net_rate, 0), NULLIF(pii.net_rate, 0), pii.rate, 0) AS rate,
			pi.name AS source_name,
			pi.posting_date,
			pi.supplier
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi
			ON pi.name = pii.parent
		WHERE pi.docstatus = 1
		  AND pii.parenttype = 'Purchase Invoice'
		  AND pii.item_code = %(fuel_item)s
		ORDER BY pi.posting_date DESC, pi.creation DESC, pii.idx DESC
		LIMIT 1
		""",
		{"fuel_item": fuel_item},
		as_dict=True,
	)
	if purchase_invoice_rate:
		return {
			"rate": flt(purchase_invoice_rate[0].rate),
			"source_doctype": "Purchase Invoice",
			"source_name": purchase_invoice_rate[0].source_name,
			"posting_date": purchase_invoice_rate[0].posting_date,
			"supplier": purchase_invoice_rate[0].supplier,
		}

	purchase_order_rate = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(poi.base_net_rate, 0), NULLIF(poi.net_rate, 0), poi.rate, 0) AS rate,
			po.name AS source_name,
			po.transaction_date AS posting_date,
			po.supplier
		FROM `tabPurchase Order Item` poi
		INNER JOIN `tabPurchase Order` po
			ON po.name = poi.parent
		WHERE po.docstatus = 1
		  AND poi.parenttype = 'Purchase Order'
		  AND poi.item_code = %(fuel_item)s
		ORDER BY po.transaction_date DESC, po.creation DESC, poi.idx DESC
		LIMIT 1
		""",
		{"fuel_item": fuel_item},
		as_dict=True,
	)
	if purchase_order_rate:
		return {
			"rate": flt(purchase_order_rate[0].rate),
			"source_doctype": "Purchase Order",
			"source_name": purchase_order_rate[0].source_name,
			"posting_date": purchase_order_rate[0].posting_date,
			"supplier": purchase_order_rate[0].supplier,
		}

	return {
		"rate": 0,
		"source_doctype": None,
		"source_name": None,
		"posting_date": None,
		"supplier": None,
	}


@frappe.whitelist()
def get_previous_month_maintenance_cost_details(vehicle, reference_date=None):
	if not vehicle:
		return {
			"amount": 0,
			"from_date": None,
			"to_date": None,
		}

	from_date, to_date = get_previous_month_date_range(reference_date)
	po_job_card_link_expression = get_purchase_order_job_card_link_expression()
	if not po_job_card_link_expression:
		return {
			"amount": 0,
			"from_date": from_date,
			"to_date": to_date,
		}

	amount = frappe.db.sql(
		f"""
		SELECT COALESCE(SUM(pii.base_net_amount), 0)
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi
			ON pi.name = pii.parent
		INNER JOIN `tabPurchase Order` po
			ON po.name = pii.purchase_order
		INNER JOIN `tabEAH Job Card` jc
			ON jc.name = {po_job_card_link_expression}
		WHERE pi.docstatus = 1
		  AND pii.parenttype = 'Purchase Invoice'
		  AND COALESCE(pii.purchase_order, '') != ''
		  AND jc.vehicle = %(vehicle)s
		  AND pi.posting_date BETWEEN %(from_date)s AND %(to_date)s
		""",
		{
			"vehicle": vehicle,
			"from_date": from_date,
			"to_date": to_date,
		},
	)[0][0] or 0

	return {
		"amount": flt(amount),
		"from_date": from_date,
		"to_date": to_date,
	}


def get_previous_month_date_range(reference_date=None):
	reference_date = getdate(reference_date or nowdate())
	previous_month_date = add_months(reference_date, -1)
	return get_first_day(previous_month_date), get_last_day(previous_month_date)


def get_purchase_order_job_card_link_expression():
	link_fields = get_existing_table_columns("Purchase Order", PURCHASE_ORDER_JOB_CARD_LINK_FIELDS)
	if not link_fields:
		return ""

	return "COALESCE({0})".format(
		", ".join(f"NULLIF(po.`{fieldname}`, '')" for fieldname in link_fields)
	)


def get_existing_table_columns(doctype, candidate_fields):
	if not frappe.db.exists("DocType", doctype):
		return []

	try:
		columns = set(frappe.db.get_table_columns(doctype))
	except Exception:
		return []

	return [fieldname for fieldname in candidate_fields if fieldname in columns]


def get_allowed_expense_amount(
	expense_limit,
	days_in_trip,
	salaries=0,
	active_vehicles=0,
	vehicle_costs=0,
	maintenance_costs=0,
	depreciation_month_number=0,
	expected_revenue=0,
	percentage_override=None,
	total_distance_km=0,
	vehicle=None,
	maintenance_reference_date=None,
):
	if normalize_expense_name(expense_limit.get("expense")) == "maintenance fee":
		maintenance_details = get_previous_month_maintenance_cost_details(
			vehicle,
			maintenance_reference_date,
		)
		return get_maintenance_fee_daily_rate(maintenance_details.get("amount")) * flt(days_in_trip)
	if normalize_expense_name(expense_limit.get("expense")) == "management fee":
		return flt(expected_revenue) * get_trip_setting_value(
			get_trip_settings(),
			"management_fee_percentage",
		) / 100
	if normalize_expense_name(expense_limit.get("expense")) == "salaries":
		return flt(expected_revenue) * get_trip_setting_value(
			get_trip_settings(),
			"salaries_percentage",
		) / 100
	if normalize_expense_name(expense_limit.get("expense")) == "driver mileage":
		return get_trip_setting_value(
			get_trip_settings(),
			"driver_mileage_per_day",
		) * flt(days_in_trip)

	amount = flt(expense_limit.get("amount"))
	if expense_limit.get("calculation_method") == "Per Trip Day":
		return amount * flt(days_in_trip)
	if expense_limit.get("calculation_method") == "Salary Allocation":
		return get_salary_allocation_rate(salaries, active_vehicles) * flt(days_in_trip)
	if expense_limit.get("calculation_method") == "Vehicle Depreciation":
		return get_vehicle_depreciation_rate(vehicle_costs, depreciation_month_number) * flt(days_in_trip)
	if expense_limit.get("calculation_method") == "Percentage of Expected Revenue":
		percentage = (
			flt(expense_limit.get("percentage"))
			if percentage_override is None
			else flt(percentage_override)
		)
		return flt(expected_revenue) * percentage / 100
	return amount


def get_salary_allocation_rate(salaries, active_vehicles):
	active_vehicles = flt(active_vehicles)
	if not active_vehicles:
		return 0

	return flt(salaries) / 30 / active_vehicles


def get_vehicle_depreciation_rate(vehicle_costs, month_number):
	month_number = flt(month_number)
	if not month_number:
		return 0

	return flt(vehicle_costs) / month_number / 12 / 30


def get_maintenance_fee_daily_rate(maintenance_costs):
	return flt(maintenance_costs) / 30


def get_tyre_cost_per_km(tyre_price, vehicle_wheels, tyre_lifecycle_km):
	tyre_lifecycle_km = flt(tyre_lifecycle_km)
	if not tyre_lifecycle_km:
		return 0

	return flt(tyre_price) * flt(vehicle_wheels) / tyre_lifecycle_km


def get_net_profit_margin_percentage(net_profit, revenue):
	revenue = flt(revenue)
	if not revenue:
		return 0

	return flt(flt(net_profit) / revenue * 100, 4)


def get_depreciation_month_number(date_value):
	if not date_value:
		return 0

	return getdate(date_value).month


def format_formula_number(value):
	return f"{flt(value):,.0f}"
