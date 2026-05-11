import frappe
from frappe.utils import flt

from service_app.service_tracking.doctype.container_trip_log.container_trip_log import (
	get_existing_uom,
	get_project_item,
)


def execute():
	if not (
		frappe.db.table_exists("Container Trip Log")
		and frappe.db.table_exists("Container Trip Entitlement Item")
	):
		return

	for trip in frappe.get_all(
		"Container Trip Log",
		fields=[
			"name",
			"docstatus",
			"project",
			"expected_revenue",
			"total_expected_revenue",
			"fuel_litres_entitled_per_trip",
			"driver_mileage_per_trip",
			"expected_mileage_pay",
			"total_qty",
		],
	):
		if has_container_trip_entitlements(trip.name):
			continue

		rows = get_old_entitlement_rows(trip.name) or get_generated_entitlement_rows(trip)
		insert_container_trip_entitlements(trip.name, rows)


def has_container_trip_entitlements(trip_log):
	return frappe.db.exists(
		"Container Trip Entitlement Item",
		{
			"parent": trip_log,
			"parenttype": "Container Trip Log",
			"parentfield": "entitlement_items",
		},
	)


def get_old_entitlement_rows(trip_log):
	if not frappe.db.table_exists("Trip Entitlement Table"):
		return []

	rows = get_old_direct_child_rows(trip_log)
	if rows:
		return rows

	if not frappe.db.table_exists("Trip Entitlement Log"):
		return []

	old_log = get_old_entitlement_log(trip_log)
	if not old_log:
		return []

	return frappe.db.sql(
		"""
		select
			entitlement_type,
			item,
			quantity,
			uom,
			rate,
			amount,
			status,
			trip_settlement_batch,
			target_doctype,
			target_document
		from `tabTrip Entitlement Table`
		where parent = %s
		order by idx asc
		""",
		old_log,
		as_dict=True,
	)


def get_old_direct_child_rows(trip_log):
	return frappe.db.sql(
		"""
		select
			entitlement_type,
			item,
			quantity,
			uom,
			rate,
			amount,
			status,
			trip_settlement_batch,
			target_doctype,
			target_document
		from `tabTrip Entitlement Table`
		where parent = %s
			and parenttype = 'Container Trip Log'
			and parentfield = 'entitlement_items'
		order by idx asc
		""",
		trip_log,
		as_dict=True,
	)


def get_old_entitlement_log(trip_log):
	rows = frappe.db.sql(
		"""
		select name
		from `tabTrip Entitlement Log`
		where container_trip_log = %s
			and docstatus != 2
		order by modified desc
		limit 1
		""",
		trip_log,
		as_dict=True,
	)
	return rows[0].name if rows else None


def get_generated_entitlement_rows(trip):
	total_qty = flt(trip.total_qty) or get_container_count(trip.name)
	total_expected_revenue = flt(trip.total_expected_revenue) or flt(trip.expected_revenue) * total_qty
	expected_mileage_pay = flt(trip.expected_mileage_pay) or flt(trip.driver_mileage_per_trip) * total_qty

	return [
		{
			"entitlement_type": "Revenue",
			"item": get_project_item(trip.project, "revenue"),
			"quantity": total_qty,
			"uom": get_existing_uom("Trip", "Nos"),
			"rate": flt(trip.expected_revenue),
			"amount": total_expected_revenue,
			"status": "Pending",
		},
		{
			"entitlement_type": "Fuel",
			"item": get_project_item(trip.project, "fuel"),
			"quantity": flt(trip.fuel_litres_entitled_per_trip) * total_qty,
			"uom": get_existing_uom("Litre", "Liter", "Nos"),
			"rate": 0,
			"amount": 0,
			"status": "Pending",
		},
		{
			"entitlement_type": "Mileage",
			"item": get_project_item(trip.project, "mileage"),
			"quantity": total_qty,
			"uom": get_existing_uom("Container", "Nos"),
			"rate": flt(trip.driver_mileage_per_trip),
			"amount": expected_mileage_pay,
			"status": "Pending",
		},
	]


def get_container_count(trip_log):
	return frappe.db.count(
		"Container Holder",
		{
			"parent": trip_log,
			"parenttype": "Container Trip Log",
			"parentfield": "container",
		},
	)


def insert_container_trip_entitlements(trip_log, rows):
	for idx, row in enumerate(rows, start=1):
		doc = frappe.get_doc(
			{
				"doctype": "Container Trip Entitlement Item",
				"parent": trip_log,
				"parenttype": "Container Trip Log",
				"parentfield": "entitlement_items",
				"idx": idx,
				"entitlement_type": row.get("entitlement_type"),
				"item": row.get("item"),
				"quantity": row.get("quantity"),
				"uom": row.get("uom"),
				"rate": row.get("rate"),
				"amount": row.get("amount"),
				"status": row.get("status") or "Pending",
				"trip_settlement_batch": row.get("trip_settlement_batch"),
				"target_doctype": row.get("target_doctype"),
				"target_document": row.get("target_document"),
			}
		)
		doc.insert(ignore_permissions=True)
