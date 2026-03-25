# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class TripRoute(Document):

    def validate(self):
        self.ensure_route_steps()
        self.set_route_name()
        self.calculate_totals()

    def ensure_route_steps(self):
        if not self.route_steps:
            frappe.throw("At least one route step is required.")

    def set_route_name(self):
        if self.route_name:
            return

        if self.starting_point and self.ending_point:
            self.route_name = f"{self.starting_point} - {self.ending_point}"

    def calculate_totals(self):
        self.total_distance_km = sum(flt(row.distance_km) for row in self.route_steps)
        self.total_fuel_consumption_qty_ltr = sum(
            flt(row.fuel_consumption_qty_ltr) for row in self.route_steps
        )

