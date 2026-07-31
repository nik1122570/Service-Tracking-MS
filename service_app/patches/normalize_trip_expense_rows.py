import frappe

from service_app.service_tracking.expense_labels import canonical_expense_label, normalize_expense_name


def execute():
	normalize_child_expenses(
		"Fixed Expenses Table",
		"fixed_expenses",
		("currency", "amount"),
	)
	normalize_child_expenses(
		"Trip Simulation Table",
		"trip_expenses_outline",
		(
			"quantity",
			"rate",
			"amount",
			"previous_month_maintenance_cost",
			"description",
			"purchase_order",
		),
	)


def normalize_child_expenses(doctype, parentfield, merge_fields):
	rows = frappe.get_all(
		doctype,
		filters={"parentfield": parentfield},
		fields=["name", "parent", "parenttype", "parentfield", "idx", "expense", *merge_fields],
		order_by="parenttype, parent, idx",
	)
	seen = {}

	for row in rows:
		expense = canonical_expense_label(row.expense)
		expense_key = normalize_expense_name(expense)
		if not expense_key:
			continue

		key = (row.parenttype, row.parent, row.parentfield, expense_key)
		if key not in seen:
			seen[key] = row.name
			if row.expense != expense:
				frappe.db.set_value(doctype, row.name, "expense", expense, update_modified=False)
			continue

		target_name = seen[key]
		target = frappe.db.get_value(doctype, target_name, merge_fields, as_dict=True) or {}
		updates = {}
		for fieldname in merge_fields:
			if not target.get(fieldname) and row.get(fieldname):
				updates[fieldname] = row.get(fieldname)

		if updates:
			frappe.db.set_value(doctype, target_name, updates, update_modified=False)
		frappe.delete_doc(doctype, row.name, force=True, ignore_permissions=True)
