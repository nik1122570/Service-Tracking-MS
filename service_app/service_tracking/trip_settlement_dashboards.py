import json

import frappe
from frappe import _


def sales_order_dashboard(data):
	return add_trip_settlement_batch_reference(data, "Sales Order")


def material_request_dashboard(data):
	return add_trip_settlement_batch_reference(data, "Material Request")


def purchase_order_dashboard(data):
	data = add_trip_settlement_batch_reference(data, "Purchase Order")
	data = add_eah_job_card_reference(data)
	data = add_trip_simulation_reference(data)
	data["method"] = "service_app.service_tracking.trip_settlement_dashboards.get_purchase_order_open_count"
	return data


def quotation_dashboard(data):
	return add_trip_simulation_reference(data)


def add_trip_settlement_batch_reference(data, target_doctype):
	data.setdefault("non_standard_fieldnames", {})
	data.setdefault("dynamic_links", {})
	data.setdefault("transactions", [])

	data["non_standard_fieldnames"]["Trip Settlement Batch"] = "target_document"
	data["dynamic_links"]["target_document"] = [target_doctype, "target_doctype"]
	add_transaction_item(data, _("Reference"), "Trip Settlement Batch")

	return data


def add_eah_job_card_reference(data):
	data.setdefault("non_standard_fieldnames", {})
	data.setdefault("internal_and_external_links", {})
	data.setdefault("transactions", [])

	data["non_standard_fieldnames"]["EAH Job Card"] = "purchase_order"
	data["internal_and_external_links"]["EAH Job Card"] = "eah_job_card"
	add_transaction_item(data, _("Reference"), "EAH Job Card")

	return data


def add_trip_simulation_reference(data):
	data.setdefault("internal_and_external_links", {})
	data.setdefault("transactions", [])

	data["internal_and_external_links"]["Trip Simulation"] = "custom_trip_simulation"
	add_transaction_item(data, _("Reference"), "Trip Simulation")

	return data


def add_transaction_item(data, label, item):
	for group in data.get("transactions") or []:
		if group.get("label") == label:
			if item not in group.get("items", []):
				group.setdefault("items", []).append(item)
			return

	data.setdefault("transactions", []).append({"label": label, "items": [item]})


@frappe.whitelist()
def get_purchase_order_open_count(doctype, name, items=None):
	from frappe.desk.notifications import get_open_count as get_standard_open_count

	result = get_standard_open_count(doctype, name, items)
	if doctype != "Purchase Order":
		return result

	parsed_items = json.loads(items) if isinstance(items, str) else items
	if parsed_items and "EAH Job Card" not in parsed_items:
		return result

	purchase_order = frappe.get_doc("Purchase Order", name)
	purchase_order.check_permission()
	job_cards = get_linked_eah_job_cards_for_purchase_order(purchase_order)
	replace_connection_count(result, "EAH Job Card", job_cards)

	return result


def get_linked_eah_job_cards_for_purchase_order(purchase_order):
	job_cards = set()

	for fieldname in ("eah_job_card", "job_card_link", "custom_job_card_link"):
		if purchase_order.meta.get_field(fieldname):
			value = (purchase_order.get(fieldname) or "").strip()
			if value:
				job_cards.add(value)

	if frappe.db.has_column("EAH Job Card", "purchase_order"):
		job_cards.update(
			frappe.get_all(
				"EAH Job Card",
				filters={
					"purchase_order": purchase_order.name,
					"docstatus": ["<", 2],
				},
				pluck="name",
			)
			or []
		)

	return sorted(job_cards)


def replace_connection_count(result, linked_doctype, names):
	count = result.setdefault("count", {})
	internal_links = count.setdefault("internal_links_found", [])
	external_links = count.setdefault("external_links_found", [])

	internal_links[:] = [row for row in internal_links if row.get("doctype") != linked_doctype]
	external_links[:] = [row for row in external_links if row.get("doctype") != linked_doctype]

	if names:
		internal_links.append(
			{
				"doctype": linked_doctype,
				"open_count": 0,
				"count": len(names),
				"names": names,
			}
		)
	else:
		external_links.append(
			{
				"doctype": linked_doctype,
				"open_count": 0,
				"count": 0,
			}
		)
