# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt

from service_app.service_tracking.tyre_analytics import (
    get_budget_amount_by_dimension,
    get_default_currency,
    get_tyre_purchase_rows,
    set_default_date_filters,
    validate_date_filters,
)


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    validate_date_filters(filters)
    filters.budget_dimension = filters.get("budget_dimension") or "Cost Center"

    columns = get_columns(filters)
    purchase_rows = get_tyre_purchase_rows(filters)
    data = build_rows(purchase_rows, filters)
    chart = get_chart_data(data)

    if not data:
        return columns, [], _("No tyre budget-versus-actual records found for the selected filters."), None

    return columns, data, None, chart


def get_columns(filters):
    dimension_label = filters.get("budget_dimension") or "Cost Center"
    return [
        {"label": _(dimension_label), "fieldname": "dimension_value", "fieldtype": "Data", "width": 170},
        {"label": _("Vehicles"), "fieldname": "vehicles", "fieldtype": "Int", "width": 80},
        {"label": _("Purchase Orders"), "fieldname": "purchase_orders", "fieldtype": "Int", "width": 105},
        {"label": _("Purchased Qty"), "fieldname": "purchased_qty", "fieldtype": "Float", "width": 110},
        {"label": _("Budget Amount"), "fieldname": "budget_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Actual Amount"), "fieldname": "actual_amount", "fieldtype": "Currency", "options": "currency", "width": 130},
        {"label": _("Variance"), "fieldname": "variance_amount", "fieldtype": "Currency", "options": "currency", "width": 120},
        {"label": _("Utilization %"), "fieldname": "utilization_pct", "fieldtype": "Percent", "width": 110},
        {"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
    ]


def build_rows(purchase_rows, filters):
    currency = get_default_currency()
    dimension_key = "cost_center" if filters.budget_dimension == "Cost Center" else "project"
    budget_map = get_budget_amount_by_dimension(dimension_key)
    unassigned_label = _("Unassigned {0}").format(filters.budget_dimension)
    grouped = defaultdict(
        lambda: {
            "vehicles": set(),
            "purchase_orders": set(),
            "purchased_qty": 0.0,
            "actual_amount": 0.0,
            "dimension_value_raw": None,
        }
    )

    for row in purchase_rows:
        dimension_value = row.get(dimension_key)
        label = dimension_value or unassigned_label
        bucket = grouped[label]
        bucket["dimension_value_raw"] = dimension_value
        if row.get("vehicle"):
            bucket["vehicles"].add(row.vehicle)
        bucket["purchase_orders"].add(row.purchase_order)
        bucket["purchased_qty"] += flt(row.qty)
        bucket["actual_amount"] += flt(row.amount)

    data = []
    for label, bucket in sorted(grouped.items()):
        budget_amount = flt(budget_map.get(bucket["dimension_value_raw"])) if bucket["dimension_value_raw"] else 0
        actual_amount = flt(bucket["actual_amount"])
        variance_amount = budget_amount - actual_amount
        utilization_pct = (actual_amount / budget_amount) * 100 if budget_amount else None

        data.append(
            {
                "dimension_value": label,
                "vehicles": len(bucket["vehicles"]),
                "purchase_orders": len(bucket["purchase_orders"]),
                "purchased_qty": flt(bucket["purchased_qty"]),
                "budget_amount": budget_amount,
                "actual_amount": actual_amount,
                "variance_amount": variance_amount,
                "utilization_pct": utilization_pct,
                "currency": currency,
            }
        )

    return data


def get_chart_data(data):
    labels = [row["dimension_value"] for row in data]
    if not labels:
        return None

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Budget Amount"), "values": [flt(row["budget_amount"]) for row in data]},
                {"name": _("Actual Amount"), "values": [flt(row["actual_amount"]) for row in data]},
            ],
        },
        "type": "bar",
        "fieldtype": "Currency",
    }
