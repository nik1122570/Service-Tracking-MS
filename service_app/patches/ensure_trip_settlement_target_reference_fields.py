import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


TARGET_DOCTYPES = ("Sales Order", "Material Request", "Purchase Order")


def execute():
	custom_fields = {
		doctype: [
			{
				"fieldname": "custom_trip_settlement_batch",
				"label": "Trip Settlement Batch",
				"fieldtype": "Link",
				"options": "Trip Settlement Batch",
				"insert_after": get_insert_after(doctype),
				"read_only": 1,
				"no_copy": 1,
				"allow_on_submit": 1,
			}
		]
		for doctype in TARGET_DOCTYPES
	}
	create_custom_fields(custom_fields, update=True)
	backfill_existing_target_documents()


def get_insert_after(doctype):
	return {
		"Sales Order": "project",
		"Material Request": "project",
		"Purchase Order": "project",
	}.get(doctype, "status")


def backfill_existing_target_documents():
	for batch in frappe.get_all(
		"Trip Settlement Batch",
		filters={
			"docstatus": 1,
			"target_doctype": ["in", TARGET_DOCTYPES],
			"target_document": ["!=", ""],
		},
		fields=["name", "target_doctype", "target_document"],
	):
		if not frappe.db.exists(batch.target_doctype, batch.target_document):
			continue

		if frappe.get_meta(batch.target_doctype).has_field("custom_trip_settlement_batch"):
			frappe.db.set_value(
				batch.target_doctype,
				batch.target_document,
				"custom_trip_settlement_batch",
				batch.name,
				update_modified=False,
			)
