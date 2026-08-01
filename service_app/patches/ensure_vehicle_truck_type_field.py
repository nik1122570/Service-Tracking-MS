import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	if not frappe.db.exists("DocType", "Vehicle") or not frappe.db.exists("DocType", "Truck Type"):
		return

	meta = frappe.get_meta("Vehicle")
	if meta.has_field("custom_truck_type") or meta.has_field("truck_type"):
		return

	create_custom_fields(
		{
			"Vehicle": [
				{
					"fieldname": "custom_truck_type",
					"label": "Truck Type",
					"fieldtype": "Link",
					"options": "Truck Type",
					"insert_after": get_vehicle_insert_after(meta),
					"in_list_view": 1,
					"in_standard_filter": 1,
				}
			]
		},
		update=True,
	)
	frappe.clear_cache(doctype="Vehicle")


def get_vehicle_insert_after(meta):
	fieldnames = {df.fieldname for df in meta.fields}
	for fieldname in ("make", "model", "license_plate", "vehicle_model", "last_odometer"):
		if fieldname in fieldnames:
			return fieldname

	return None
