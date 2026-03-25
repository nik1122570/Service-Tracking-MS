# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from service_app.service_tracking.sales_order import (
    get_sales_order_trip_context,
    release_sales_order_trip_allocation,
    reserve_sales_order_trip_allocation,
)


CALCULATION_METHODS = {
    "Fixed Amount",
    "Per Day",
    "Per KM",
    "Per Litre",
    "Percent of Revenue",
}


class TripSimulation(Document):

    def validate(self):
        self.ensure_required_fields()
        self.sync_sales_order_context()
        self.sync_route_context()
        self.ensure_estimated_cost_rows()
        self.recalculate_estimated_costs()
        self.calculate_profitability()
        self.validate_override_requirements()

    def before_submit(self):
        if self.below_target_margin and not self.override_target_margin:
            frappe.throw(
                _(
                    "Expected Profit Margin {0} is below the customer target of {1}. "
                    "Enable Override Target Margin and provide a reason before submitting."
                ).format(
                    frappe.format_value(self.expected_profit_margin, {"fieldtype": "Percent"}),
                    frappe.format_value(self.target_profit_margin, {"fieldtype": "Percent"}),
                ),
                title="Target Profit Margin Control",
            )

        reserve_sales_order_trip_allocation(
            self.sales_order,
            self.sales_order_revenue_allocation,
            self.name,
        )

    def on_cancel(self):
        release_sales_order_trip_allocation(
            self.sales_order,
            self.sales_order_revenue_allocation,
            self.name,
        )

    def ensure_required_fields(self):
        required_fields = {
            "simulation_date": "Simulation Date",
            "sales_order": "Sales Order",
            "driver": "Driver",
            "vehicle": "Vehicle",
            "trip_route": "Trip Route",
        }

        for fieldname, label in required_fields.items():
            if not getattr(self, fieldname, None):
                frappe.throw(f"{label} is required.")

    def sync_sales_order_context(self):
        context = get_sales_order_trip_context(
            self.sales_order,
            allocation_name=self.sales_order_revenue_allocation,
            simulation_name=self.name,
        )

        self.customer = context.customer
        self.cost_center = context.cost_center
        self.expected_revenue = context.expected_revenue
        self.target_profit_margin = context.target_profit_margin
        self.sales_order_revenue_allocation = context.selected_allocation or ""

        if not context.uses_allocations:
            self.validate_single_trip_sales_order()

    def ensure_estimated_cost_rows(self):
        if not self.estimated_costs:
            frappe.throw("At least one estimated cost row is required on the Trip Simulation.")

    def validate_single_trip_sales_order(self):
        existing_simulations = frappe.get_all(
            "Trip Simulation",
            filters={
                "sales_order": self.sales_order,
                "docstatus": 1,
                "name": ["!=", self.name or ""],
            },
            pluck="name",
        )
        if existing_simulations:
            frappe.throw(
                _(
                    "Sales Order {0} already has submitted trip simulations {1}. "
                    "Create trip revenue allocations on the Sales Order before adding another trip simulation."
                ).format(
                    frappe.bold(self.sales_order),
                    ", ".join(frappe.bold(name) for name in existing_simulations),
                ),
                title="Revenue Allocation Required",
            )

    def sync_route_context(self):
        route = frappe.get_doc("Trip Route", self.trip_route)

        self.total_distance_km = flt(route.total_distance_km)
        self.total_fuel_estimate_ltr = flt(route.total_fuel_consumption_qty_ltr)

        previous_route = None
        if not self.is_new():
            previous_route = frappe.db.get_value(self.doctype, self.name, "trip_route")

        if not flt(self.trip_days) or previous_route != self.trip_route:
            self.trip_days = flt(route.standard_trip_days)

        should_reset_cost_rows = not self.estimated_costs or previous_route != self.trip_route
        if should_reset_cost_rows:
            self.set("estimated_costs", [])
            for row in build_trip_route_expense_rows(
                route,
                trip_days=self.trip_days,
                total_distance_km=self.total_distance_km,
                total_fuel_estimate_ltr=self.total_fuel_estimate_ltr,
                expected_revenue=self.expected_revenue,
            ):
                self.append("estimated_costs", row)

    def recalculate_estimated_costs(self):
        for row in self.estimated_costs:
            row.calculation_method = row.calculation_method or "Fixed Amount"
            if row.calculation_method not in CALCULATION_METHODS:
                frappe.throw(f"Unsupported calculation method {row.calculation_method} in estimated costs.")

            if row.is_manual_override:
                if not row.override_reason:
                    frappe.throw(
                        f"Estimated Cost row {row.idx}: Override Reason is required when Manual Override is enabled."
                    )
                continue

            row.qty = get_expense_quantity(
                row.calculation_method,
                trip_days=self.trip_days,
                total_distance_km=self.total_distance_km,
                total_fuel_estimate_ltr=self.total_fuel_estimate_ltr,
            )
            row.amount = calculate_expense_amount(
                row.calculation_method,
                qty=row.qty,
                rate=row.rate,
                expected_revenue=self.expected_revenue,
            )

    def calculate_profitability(self):
        self.total_estimated_cost = sum(flt(row.amount) for row in self.estimated_costs)
        self.expected_gross_profit = flt(self.expected_revenue) - flt(self.total_estimated_cost)

        if flt(self.expected_revenue):
            self.expected_profit_margin = (
                flt(self.expected_gross_profit) / flt(self.expected_revenue)
            ) * 100
        else:
            self.expected_profit_margin = 0

        self.margin_gap_to_target = flt(self.expected_profit_margin) - flt(self.target_profit_margin)
        self.below_target_margin = flt(self.expected_profit_margin) < flt(self.target_profit_margin)

    def validate_override_requirements(self):
        if self.override_target_margin and not self.override_reason:
            frappe.throw("Override Reason is required when Override Target Margin is checked.")


def get_expense_quantity(
    calculation_method,
    trip_days,
    total_distance_km,
    total_fuel_estimate_ltr,
):
    if calculation_method == "Fixed Amount":
        return 1
    if calculation_method == "Per Day":
        return flt(trip_days)
    if calculation_method == "Per KM":
        return flt(total_distance_km)
    if calculation_method == "Per Litre":
        return flt(total_fuel_estimate_ltr)
    if calculation_method == "Percent of Revenue":
        return 1
    return 0


def calculate_expense_amount(calculation_method, qty, rate, expected_revenue):
    qty = flt(qty)
    rate = flt(rate)

    if calculation_method == "Percent of Revenue":
        return flt(expected_revenue) * rate / 100

    return qty * rate


def build_trip_route_expense_rows(
    route,
    trip_days,
    total_distance_km,
    total_fuel_estimate_ltr,
    expected_revenue,
):
    rows = []
    for row in route.fixed_expenses:
        qty = get_expense_quantity(
            row.calculation_method,
            trip_days=trip_days,
            total_distance_km=total_distance_km,
            total_fuel_estimate_ltr=total_fuel_estimate_ltr,
        )
        rows.append(
            {
                "expense_head": row.expense_head,
                "calculation_method": row.calculation_method,
                "qty": qty,
                "rate": row.rate,
                "amount": calculate_expense_amount(
                    row.calculation_method,
                    qty=qty,
                    rate=row.rate,
                    expected_revenue=expected_revenue,
                ),
                "source_doctype": route.doctype,
                "source_name": route.name,
            }
        )
    return rows


def build_trip_simulation_preview(sales_order, trip_route, allocation_name=None, simulation_name=None):
    sales_order_context = get_sales_order_trip_context(
        sales_order,
        allocation_name=allocation_name,
        simulation_name=simulation_name,
        require_allocation=False,
    )
    route = frappe.get_doc("Trip Route", trip_route)
    trip_days = flt(route.standard_trip_days)
    total_distance_km = flt(route.total_distance_km)
    total_fuel_estimate_ltr = flt(route.total_fuel_consumption_qty_ltr)
    estimated_costs = build_trip_route_expense_rows(
        route,
        trip_days=trip_days,
        total_distance_km=total_distance_km,
        total_fuel_estimate_ltr=total_fuel_estimate_ltr,
        expected_revenue=sales_order_context.expected_revenue,
    )
    total_estimated_cost = sum(flt(row["amount"]) for row in estimated_costs)
    expected_gross_profit = flt(sales_order_context.expected_revenue) - total_estimated_cost
    expected_profit_margin = 0
    if flt(sales_order_context.expected_revenue):
        expected_profit_margin = (expected_gross_profit / flt(sales_order_context.expected_revenue)) * 100

    return {
        "customer": sales_order_context.customer,
        "cost_center": sales_order_context.cost_center,
        "expected_revenue": sales_order_context.expected_revenue,
        "target_profit_margin": sales_order_context.target_profit_margin,
        "sales_order_revenue_allocation": sales_order_context.selected_allocation or "",
        "allocation_options": sales_order_context.allocation_options,
        "trip_days": trip_days,
        "total_distance_km": total_distance_km,
        "total_fuel_estimate_ltr": total_fuel_estimate_ltr,
        "estimated_costs": estimated_costs,
        "total_estimated_cost": total_estimated_cost,
        "expected_gross_profit": expected_gross_profit,
        "expected_profit_margin": expected_profit_margin,
        "below_target_margin": expected_profit_margin < flt(sales_order_context.target_profit_margin),
    }


@frappe.whitelist()
def get_trip_simulation_preview(sales_order, trip_route, allocation_name=None, simulation_name=None):
    if not sales_order or not trip_route:
        return {}

    return build_trip_simulation_preview(
        sales_order=sales_order,
        trip_route=trip_route,
        allocation_name=allocation_name,
        simulation_name=simulation_name,
    )
