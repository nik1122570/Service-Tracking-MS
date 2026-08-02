import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


PROJECT_CUSTOMER_DETAILS_FIELDS = (
	{
		"fieldname": "customer_details",
		"label": "Customer Details",
		"fieldtype": "Section Break",
		"insert_after": "department",
		"collapsible": 1,
	},
	{
		"fieldname": "customer",
		"label": "Customer",
		"fieldtype": "Link",
		"options": "Customer",
		"insert_after": "customer_details",
	},
	{
		"fieldname": "custom_rate_per_trip",
		"label": "Rate per trip",
		"fieldtype": "Currency",
		"insert_after": "customer",
	},
	{
		"fieldname": "custom_driver_mileage_per_trip",
		"label": "Driver Mileage per Trip",
		"fieldtype": "Currency",
		"insert_after": "custom_rate_per_trip",
	},
	{
		"fieldname": "custom_route",
		"label": "Route",
		"fieldtype": "Data",
		"insert_after": "custom_driver_mileage_per_trip",
	},
	{
		"fieldname": "custom_trip_items_column",
		"fieldtype": "Column Break",
		"insert_after": "custom_route",
	},
	{
		"fieldname": "sales_order",
		"label": "Sales Order",
		"fieldtype": "Link",
		"options": "Sales Order",
		"insert_after": "custom_trip_items_column",
	},
	{
		"fieldname": "custom_sales_item",
		"label": "Sales Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "sales_order",
	},
	{
		"fieldname": "custom_fuel_entitlement_litres",
		"label": "Fuel Entitlement Per Trip",
		"fieldtype": "Float",
		"insert_after": "custom_sales_item",
	},
	{
		"fieldname": "custom_fuel_item",
		"label": "Fuel Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_fuel_entitlement_litres",
	},
	{
		"fieldname": "custom_mileage_item",
		"label": "Mileage Item",
		"fieldtype": "Link",
		"options": "Item",
		"insert_after": "custom_fuel_item",
	},
)


def execute():
	if not frappe.db.exists("DocType", "Project"):
		return

	meta = frappe.get_meta("Project", cached=False)
	existing_fields = {field.fieldname for field in meta.fields}
	fields_to_create = []

	for field in PROJECT_CUSTOMER_DETAILS_FIELDS:
		if field["fieldname"] in existing_fields:
			continue

		field = field.copy()
		field["insert_after"] = get_safe_insert_after(field.get("insert_after"), existing_fields)
		fields_to_create.append(field)
		existing_fields.add(field["fieldname"])

	if fields_to_create:
		create_custom_fields({"Project": fields_to_create}, update=True)

	for field in PROJECT_CUSTOMER_DETAILS_FIELDS:
		if field["fieldname"] in existing_fields:
			make_property_setter("Project", field["fieldname"], "hidden", 0, "Check")
			make_property_setter("Project", field["fieldname"], "permlevel", 0, "Int")

	frappe.clear_cache(doctype="Project")


def get_safe_insert_after(preferred_field, existing_fields):
	if preferred_field in existing_fields:
		return preferred_field

	for fieldname in ("customer_details", "customer", "department", "project_template", "project_name"):
		if fieldname in existing_fields:
			return fieldname

	return None
