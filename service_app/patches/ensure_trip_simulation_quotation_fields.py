import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Quotation": [
				{
					"fieldname": "custom_trip_simulation",
					"label": "Trip Simulation",
					"fieldtype": "Link",
					"options": "Trip Simulation",
					"insert_after": "party_name",
					"read_only": 1,
					"no_copy": 1,
				}
			],
		},
		update=True,
	)
	frappe.clear_cache(doctype="Quotation")
