import frappe
from frappe.utils import flt, get_first_day, get_last_day, nowdate

@frappe.whitelist()
def get_spare_parts_consumption(**kwargs):
    data = frappe.db.sql("""
        SELECT item, item_name, SUM(qty) as total_qty
        FROM `tabSupplied Parts`
        GROUP BY item
        ORDER BY total_qty DESC
        LIMIT 10
    """, as_dict=True)
    
    chart_data = {
        "labels": [d.item_name for d in data],
        "datasets": [
            {
                "name": "Quantity",
                "values": [d.total_qty for d in data]
            }
        ]
    }

    return chart_data


def _get_current_month_trip_totals():
    today = nowdate()
    first_day = get_first_day(today)
    last_day = get_last_day(today)

    row = frappe.db.sql(
        """
        SELECT
            COALESCE(SUM(expected_revenue), 0) AS revenue,
            COALESCE(SUM(total_trip_cost), 0) AS cost,
            COALESCE(SUM(net_profit), 0) AS profit_loss,
            COALESCE(SUM(total_fuel_costs), 0) AS fuel_cost
        FROM `tabTrip Simulation`
        WHERE docstatus = 1
          AND transaction_date BETWEEN %s AND %s
        """,
        (first_day, last_day),
        as_dict=True,
    )[0]

    return row


@frappe.whitelist()
def get_trip_revenue_cost_profit(**kwargs):
    totals = _get_current_month_trip_totals()

    return {
        "labels": ["Revenue", "Total Cost", "Profit/Loss"],
        "datasets": [
            {
                "name": "Amount",
                "values": [
                    flt(totals.revenue),
                    flt(totals.cost),
                    flt(totals.profit_loss),
                ],
            }
        ],
    }


@frappe.whitelist()
def get_trip_cost_breakdown(**kwargs):
    today = nowdate()
    first_day = get_first_day(today)
    last_day = get_last_day(today)
    totals = _get_current_month_trip_totals()

    expense_rows = frappe.db.sql(
        """
        SELECT
            expense,
            COALESCE(SUM(amount), 0) AS amount
        FROM `tabTrip Simulation Table` expense_row
        INNER JOIN `tabTrip Simulation` trip
            ON trip.name = expense_row.parent
        WHERE trip.docstatus = 1
          AND trip.transaction_date BETWEEN %s AND %s
          AND expense_row.parenttype = 'Trip Simulation'
          AND expense_row.parentfield = 'trip_expenses_outline'
        GROUP BY expense
        """,
        (first_day, last_day),
        as_dict=True,
    )

    amounts_by_label = {
        "Fuel": flt(totals.fuel_cost),
        "Maintenance": 0,
        "Management Fee": 0,
        "Salaries": 0,
        "Tyres": 0,
        "Other Expenses": 0,
    }

    known_labels = {
        "maintenance fee": "Maintenance",
        "management fee": "Management Fee",
        "salaries": "Salaries",
        "tyres": "Tyres",
    }

    known_expense_total = 0
    for row in expense_rows:
        amount = flt(row.amount)
        known_expense_total += amount
        label = known_labels.get((row.expense or "").strip().lower(), "Other Expenses")
        amounts_by_label[label] += amount

    other_from_trip_cost = flt(totals.cost) - flt(totals.fuel_cost) - known_expense_total
    if other_from_trip_cost > 0:
        amounts_by_label["Other Expenses"] += other_from_trip_cost

    labels = []
    values = []
    for label, amount in amounts_by_label.items():
        if flt(amount) <= 0:
            continue
        labels.append(label)
        values.append(flt(amount))

    if not labels:
        labels = ["No Submitted Trip Cost"]
        values = [0]

    return {
        "labels": labels,
        "datasets": [
            {
                "name": "Cost",
                "values": values,
            }
        ],
    }
