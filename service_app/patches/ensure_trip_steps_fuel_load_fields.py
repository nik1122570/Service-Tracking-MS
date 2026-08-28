import frappe


TRIP_STEP_FUEL_FIELDS = (
	{
		"fieldname": "fuel_load_status",
		"fieldtype": "Select",
		"label": "Fuel Load Status",
		"options": "Loaded\nEmpty",
		"default": "Loaded",
		"in_list_view": 1,
		"idx": 4,
	},
	{
		"fieldname": "fuel_consumption_ratio",
		"fieldtype": "Float",
		"label": "Fuel Ratio (Ltr/KM)",
		"read_only": 1,
		"in_list_view": 1,
		"idx": 5,
	},
)


def execute():
	if not frappe.db.exists("DocType", "Trip Steps"):
		return

	for field in TRIP_STEP_FUEL_FIELDS:
		upsert_docfield("Trip Steps", field)

	update_docfield(
		"Trip Steps",
		"fuel_consumption_qty",
		{
			"label": "Fuel Consumption Qty (Ltr)",
			"read_only": 1,
			"in_list_view": 1,
			"idx": 6,
		},
	)

	if frappe.db.table_exists("Trip Steps"):
		columns = set(frappe.db.get_table_columns("Trip Steps"))
		if "fuel_load_status" in columns:
			frappe.db.sql(
				"""
				UPDATE `tabTrip Steps`
				SET fuel_load_status = 'Loaded'
				WHERE COALESCE(fuel_load_status, '') = ''
				"""
			)

	frappe.clear_cache(doctype="Trip Steps")


def upsert_docfield(parent, field):
	if frappe.db.exists("DocField", {"parent": parent, "fieldname": field["fieldname"]}):
		update_docfield(parent, field["fieldname"], field)
		return

	docfield = frappe.get_doc(
		{
			"doctype": "DocField",
			"parent": parent,
			"parenttype": "DocType",
			"parentfield": "fields",
			**field,
		}
	)
	docfield.insert(ignore_permissions=True)


def update_docfield(parent, fieldname, values):
	name = frappe.db.get_value("DocField", {"parent": parent, "fieldname": fieldname})
	if not name:
		return

	frappe.db.set_value("DocField", name, values, update_modified=False)
