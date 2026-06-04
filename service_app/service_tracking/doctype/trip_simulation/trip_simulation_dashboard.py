from frappe import _


def get_data():
	return {
		"fieldname": "custom_trip_simulation",
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["Quotation", "Purchase Order"],
			}
		],
	}
