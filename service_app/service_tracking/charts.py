import frappe

@frappe.whitelist()
def get_spare_parts_consumption():
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