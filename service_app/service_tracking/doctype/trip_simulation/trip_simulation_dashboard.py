import frappe
from frappe import _


def get_data():
	items = []
	if frappe.db.has_column("Quotation", "custom_trip_simulation"):
		items.append("Quotation")
	if frappe.db.has_column("Purchase Order", "custom_trip_simulation"):
		items.append("Purchase Order")

	return {
		"fieldname": "custom_trip_simulation",
		"transactions": [
			{
				"label": _("Reference"),
				"items": items,
			}
		],
	}
