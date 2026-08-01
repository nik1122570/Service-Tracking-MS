import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_trip_simulation_document_link_fields()


def create_trip_simulation_document_link_fields():
	custom_fields = {}

	if frappe.db.exists("DocType", "Quotation"):
		custom_fields["Quotation"] = [
			{
				"fieldname": "custom_trip_simulation",
				"label": "Trip Simulation",
				"fieldtype": "Link",
				"options": "Trip Simulation",
				"insert_after": "party_name",
				"read_only": 1,
				"no_copy": 1,
				"allow_on_submit": 1,
			}
		]

	if frappe.db.exists("DocType", "Purchase Order"):
		custom_fields["Purchase Order"] = [
			{
				"fieldname": "custom_trip_simulation",
				"label": "Trip Simulation",
				"fieldtype": "Link",
				"options": "Trip Simulation",
				"insert_after": "supplier",
				"read_only": 1,
				"no_copy": 1,
				"allow_on_submit": 1,
			},
			{
				"fieldname": "custom_vehicle",
				"label": "Vehicle",
				"fieldtype": "Link",
				"options": "Vehicle",
				"insert_after": "custom_trip_simulation",
				"read_only": 1,
				"no_copy": 1,
				"allow_on_submit": 1,
			},
		]

	if not custom_fields:
		return

	create_custom_fields(custom_fields, update=True)
	for doctype in custom_fields:
		frappe.clear_cache(doctype=doctype)
