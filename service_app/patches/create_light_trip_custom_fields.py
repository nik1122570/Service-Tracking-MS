from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Customer": [
                {
                    "fieldname": "custom_target_profit_margin",
                    "label": "Target Profit Margin",
                    "fieldtype": "Percent",
                    "insert_after": "customer_group",
                    "description": "Default target profit margin control for light truck trip simulations."
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_trip_controls_section",
                    "label": "Light Trip Controls",
                    "fieldtype": "Section Break",
                    "insert_after": "project"
                },
                {
                    "fieldname": "custom_trip_cost_center",
                    "label": "Trip Cost Center",
                    "fieldtype": "Link",
                    "options": "Cost Center",
                    "insert_after": "custom_trip_controls_section",
                    "allow_on_submit": 1
                },
                {
                    "fieldname": "custom_trip_revenue_allocations",
                    "label": "Trip Revenue Allocations",
                    "fieldtype": "Table",
                    "options": "Sales Order Trip Revenue Allocation",
                    "insert_after": "custom_trip_cost_center",
                    "allow_on_submit": 1
                },
                {
                    "fieldname": "custom_total_allocated_trip_revenue",
                    "label": "Total Allocated Trip Revenue",
                    "fieldtype": "Currency",
                    "insert_after": "custom_trip_revenue_allocations",
                    "read_only": 1,
                    "allow_on_submit": 1
                },
                {
                    "fieldname": "custom_remaining_trip_revenue",
                    "label": "Remaining Trip Revenue",
                    "fieldtype": "Currency",
                    "insert_after": "custom_total_allocated_trip_revenue",
                    "read_only": 1,
                    "allow_on_submit": 1
                }
            ]
        },
        update=True,
    )
