from frappe import _


def sales_order_dashboard(data):
	return add_trip_settlement_batch_reference(data, "Sales Order")


def material_request_dashboard(data):
	return add_trip_settlement_batch_reference(data, "Material Request")


def purchase_order_dashboard(data):
	return add_trip_settlement_batch_reference(data, "Purchase Order")


def add_trip_settlement_batch_reference(data, target_doctype):
	data.setdefault("non_standard_fieldnames", {})
	data.setdefault("dynamic_links", {})
	data.setdefault("transactions", [])

	data["non_standard_fieldnames"]["Trip Settlement Batch"] = "target_document"
	data["dynamic_links"]["target_document"] = [target_doctype, "target_doctype"]
	add_transaction_item(data, _("Reference"), "Trip Settlement Batch")

	return data


def add_transaction_item(data, label, item):
	for group in data.get("transactions") or []:
		if group.get("label") == label:
			if item not in group.get("items", []):
				group.setdefault("items", []).append(item)
			return

	data.setdefault("transactions", []).append({"label": label, "items": [item]})
