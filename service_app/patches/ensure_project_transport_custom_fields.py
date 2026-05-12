import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


PROJECT_TRANSPORT_FIELDS = [
	{
		"fieldname": "custom_transport_contract_section",
		"label": "Transport Contract Setup",
		"fieldtype": "Section Break",
		"insert_after": "project_template",
	},
	{
		"fieldname": "custom_route",
		"label": "Route",
		"fieldtype": "Data",
		"insert_after": "custom_transport_contract_section",
	},
	{
		"fieldname": "custom_rate_per_trip",
		"label": "Rate per trip",
		"fieldtype": "Currency",
		"insert_after": "custom_route",
	},
	{
		"fieldname": "custom_fuel_entitlement_litres",
		"label": "Fuel Entitlement Per Trip",
		"fieldtype": "Float",
		"insert_after": "custom_rate_per_trip",
	},
	{
		"fieldname": "custom_driver_mileage_per_trip",
		"label": "Driver Mileage per Trip",
		"fieldtype": "Currency",
		"insert_after": "custom_fuel_entitlement_litres",
	},
	{
		"fieldname": "custom_trip_items_column",
		"fieldtype": "Column Break",
		"insert_after": "custom_driver_mileage_per_trip",
	},
	{
		"fieldname": "custom_sales_item",
		"label": "Sales Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_trip_items_column",
	},
	{
		"fieldname": "custom_fuel_item",
		"label": "Fuel Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_sales_item",
	},
	{
		"fieldname": "custom_mileage_item",
		"label": "Mileage Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_fuel_item",
	},
]


def execute():
	if not frappe.db.exists("DocType", "Project"):
		return

	fields = get_project_fields_to_create()
	if not fields:
		return

	create_custom_fields({"Project": fields}, update=True)
	frappe.clear_cache(doctype="Project")


def get_project_fields_to_create():
	meta = frappe.get_meta("Project")
	existing_fields = {df.fieldname for df in meta.fields}
	fields = []

	for field in PROJECT_TRANSPORT_FIELDS:
		if field["fieldname"] in existing_fields:
			continue

		field = field.copy()
		field["insert_after"] = get_safe_insert_after(field.get("insert_after"), existing_fields)
		fields.append(field)
		existing_fields.add(field["fieldname"])

	return fields


def get_safe_insert_after(preferred_field, existing_fields):
	if preferred_field in existing_fields:
		return preferred_field

	for fieldname in ("project_name", "project_type", "status", "company"):
		if fieldname in existing_fields:
			return fieldname

	return None
