import frappe


def execute():
	for doctype in ("Sales Order Item", "Material Request Item", "Purchase Order Item"):
		ensure_vehicle_field(doctype)


def ensure_vehicle_field(doctype):
	if frappe.db.exists("Custom Field", f"{doctype}-custom_vehicle"):
		return

	if frappe.get_meta(doctype).get_field("vehicle") or frappe.get_meta(doctype).get_field("custom_vehicle"):
		return

	insert_after = get_insert_after_field(doctype)
	custom_field = frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": doctype,
			"fieldname": "custom_vehicle",
			"label": "Vehicle",
			"fieldtype": "Link",
			"options": "Vehicle",
			"insert_after": insert_after,
			"read_only": 1,
		}
	)
	custom_field.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=doctype)


def get_insert_after_field(doctype):
	for fieldname in ("project", "description", "item_name", "item_code"):
		if frappe.get_meta(doctype).get_field(fieldname):
			return fieldname
	return None
