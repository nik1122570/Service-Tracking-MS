# Copyright (c) 2026, Nickson  and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from service_app.service_tracking.doctype.trip_simulation.trip_simulation import (
	TripSimulation,
	get_allowed_expense_amount,
	get_fuel_item_price,
	get_net_profit_margin_percentage,
	get_tyre_cost_per_km,
)


class TestTripSimulation(FrappeTestCase):
	def test_net_profit_margin_percentage(self):
		self.assertEqual(get_net_profit_margin_percentage(20, 100), 20)
		self.assertEqual(get_net_profit_margin_percentage(0, 0), 0)

	def test_percentage_of_expected_revenue_expense(self):
		self.assertEqual(
			get_allowed_expense_amount(
				{
					"calculation_method": "Percentage of Expected Revenue",
					"percentage": 3,
				},
				days_in_trip=1,
				expected_revenue=1000000,
			),
			30000,
		)

	def test_tyre_cost_per_km(self):
		self.assertEqual(get_tyre_cost_per_km(200000, 10, 50000), 40)
		self.assertEqual(get_tyre_cost_per_km(200000, 10, 0), 0)

	@patch("service_app.service_tracking.doctype.trip_simulation.trip_simulation.frappe.db.get_value")
	def test_fuel_price_comes_from_item_price_for_price_list(self, get_value):
		get_value.return_value = frappe._dict(name="IP-0001", price_list_rate=3150)

		result = get_fuel_item_price("Diesel", "Operations Buying")

		self.assertEqual(result, {"rate": 3150, "source_name": "IP-0001"})
		get_value.assert_called_once_with(
			"Item Price",
			{"item_code": "Diesel", "price_list": "Operations Buying"},
			["name", "price_list_rate"],
			as_dict=True,
		)

	@patch("service_app.service_tracking.doctype.trip_simulation.trip_simulation.frappe.db.get_value")
	def test_fuel_price_requires_fuel_item_and_price_list(self, get_value):
		self.assertEqual(get_fuel_item_price("Diesel", None), {"rate": 0, "source_name": None})
		get_value.assert_not_called()

	@patch(
		"service_app.service_tracking.doctype.trip_simulation.trip_simulation."
		"get_fuel_litres_per_km_from_truck_type",
		return_value=0.4,
	)
	def test_legacy_fuel_row_without_load_status_or_ratio(self, get_fuel_ratio):
		trip = frappe._dict(vehicle="T678 EDT", fuel=[frappe._dict(distance=100)])

		TripSimulation.apply_calculated_fuel_consumption(trip)

		self.assertEqual(trip.fuel[0].fuel_load_status, "Loaded")
		self.assertEqual(trip.fuel[0].fuel_consumption_ratio, 0.4)
		self.assertEqual(trip.fuel[0].fuel_consumption_qty, 40)
		get_fuel_ratio.assert_called_once_with("T678 EDT")
