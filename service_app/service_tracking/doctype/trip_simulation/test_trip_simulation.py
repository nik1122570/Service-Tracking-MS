# Copyright (c) 2026, Nickson  and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from service_app.service_tracking.doctype.trip_simulation.trip_simulation import (
	TripSimulation,
	get_allowed_expense_amount,
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

	def test_targeted_net_profit_blocks_lower_net_profit_margin(self):
		doc = TripSimulation(
			{
				"doctype": "Trip Simulation",
				"net_profit_": 19,
				"targeted_net_profit": 20,
			}
		)

		with self.assertRaises(frappe.ValidationError):
			doc.validate_targeted_net_profit()
