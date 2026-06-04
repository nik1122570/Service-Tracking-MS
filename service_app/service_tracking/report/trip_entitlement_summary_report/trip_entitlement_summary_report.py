# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, today


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	columns = get_columns()
	data = get_data(filters)
	message = None if data else _("No trip entitlement records found for the selected filters.")
	report_summary = get_report_summary(data)

	return columns, data, message, None, report_summary


def validate_filters(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are required."))

	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be greater than To Date."))

def get_columns():
	return [
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 160},
		{"label": _("Truck / Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
		{"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 130},
		{"label": _("Drivers Used"), "fieldname": "drivers_used", "fieldtype": "Small Text", "width": 170},
		{"label": _("Trailer 1 Used"), "fieldname": "trailer_1_used", "fieldtype": "Small Text", "width": 140},
		{"label": _("Trailer 2 Used"), "fieldname": "trailer_2_used", "fieldtype": "Small Text", "width": 140},
		{"label": _("Trip Count"), "fieldname": "trip_count", "fieldtype": "Int", "width": 100},
		{"label": _("Container Count"), "fieldname": "container_count", "fieldtype": "Float", "width": 125},
		{
			"label": _("Expected Revenue"),
			"fieldname": "expected_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{
			"label": _("Actual Billed Revenue"),
			"fieldname": "actual_billed_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 165,
		},
		{
			"label": _("Unbilled Revenue"),
			"fieldname": "unbilled_revenue",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{
			"label": _("Billing Variance"),
			"fieldname": "billing_variance",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 140,
		},
		{
			"label": _("Billing Completion %"),
			"fieldname": "billing_completion_percentage",
			"fieldtype": "Percent",
			"width": 155,
		},
		{"label": _("Sales Invoices"), "fieldname": "sales_invoices", "fieldtype": "Small Text", "width": 190},
		{"label": _("Fuel Litres To Reimburse"), "fieldname": "fuel_litres", "fieldtype": "Float", "width": 165},
		{
			"label": _("Mileage Demanded"),
			"fieldname": "mileage_demanded",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 145,
		},
		{"label": _("Revenue Status"), "fieldname": "revenue_status", "fieldtype": "Data", "width": 120},
		{"label": _("Fuel Status"), "fieldname": "fuel_status", "fieldtype": "Data", "width": 120},
		{"label": _("Mileage Status"), "fieldname": "mileage_status", "fieldtype": "Data", "width": 120},
		{"label": _("Settlement Batches"), "fieldname": "settlement_batches", "fieldtype": "Small Text", "width": 180},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = [
		"trip.docstatus = 1",
		"trip.trip_date BETWEEN %(from_date)s AND %(to_date)s",
		"item.parenttype = 'Container Trip Log'",
		"item.parentfield = 'entitlement_items'",
	]
	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("project"):
		conditions.append("trip.project = %(project)s")
		values["project"] = filters.project

	if filters.get("vehicle"):
		conditions.append("trip.vehicle = %(vehicle)s")
		values["vehicle"] = filters.vehicle

	if filters.get("driver"):
		conditions.append("trip.driver = %(driver)s")
		values["driver"] = filters.driver

	if filters.get("entitlement_status"):
		conditions.append("item.status = %(entitlement_status)s")
		values["entitlement_status"] = filters.entitlement_status

	currency = frappe.db.get_single_value("Global Defaults", "default_currency")

	rows = frappe.db.sql(
		f"""
		SELECT
			trip.project,
			trip.vehicle,
			vehicle.license_plate,
			GROUP_CONCAT(DISTINCT NULLIF(trip.driver, '') ORDER BY trip.driver SEPARATOR ', ') AS drivers_used,
			GROUP_CONCAT(DISTINCT NULLIF(trip.trailer_1, '') ORDER BY trip.trailer_1 SEPARATOR ', ') AS trailer_1_used,
			GROUP_CONCAT(DISTINCT NULLIF(trip.trailer_2, '') ORDER BY trip.trailer_2 SEPARATOR ', ') AS trailer_2_used,
			COUNT(DISTINCT trip.name) AS trip_count,
			SUM(CASE WHEN item.entitlement_type = 'Revenue' THEN item.quantity ELSE 0 END) AS container_count,
			SUM(CASE WHEN item.entitlement_type = 'Revenue' THEN item.amount ELSE 0 END) AS expected_revenue,
			SUM(CASE WHEN item.entitlement_type = 'Fuel' THEN item.quantity ELSE 0 END) AS fuel_litres,
			SUM(CASE WHEN item.entitlement_type = 'Mileage' THEN item.amount ELSE 0 END) AS mileage_demanded,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Revenue' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS revenue_status,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Fuel' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS fuel_status,
			GROUP_CONCAT(DISTINCT CASE WHEN item.entitlement_type = 'Mileage' THEN item.status END ORDER BY item.status SEPARATOR ', ') AS mileage_status,
			GROUP_CONCAT(DISTINCT NULLIF(item.trip_settlement_batch, '') ORDER BY item.trip_settlement_batch SEPARATOR ', ') AS settlement_batches
		FROM `tabContainer Trip Log` trip
		INNER JOIN `tabContainer Trip Entitlement Item` item
			ON item.parent = trip.name
		LEFT JOIN `tabVehicle` vehicle
			ON vehicle.name = trip.vehicle
		WHERE {' AND '.join(conditions)}
		GROUP BY trip.project, trip.vehicle, vehicle.license_plate
		ORDER BY trip.project ASC, trip.vehicle ASC
		""",
		values,
		as_dict=True,
	)

	actual_billed_by_project_vehicle = get_actual_billed_revenue(filters)

	for row in rows:
		row.currency = currency
		row.trip_count = int(row.trip_count or 0)
		row.container_count = flt(row.container_count)
		row.expected_revenue = flt(row.expected_revenue)
		actual_billed = actual_billed_by_project_vehicle.get((row.project or "", row.vehicle or ""), {})
		row.actual_billed_revenue = flt(actual_billed.get("actual_billed_revenue"))
		row.unbilled_revenue = row.expected_revenue - row.actual_billed_revenue
		row.billing_variance = row.actual_billed_revenue - row.expected_revenue
		row.billing_completion_percentage = (
			(row.actual_billed_revenue / row.expected_revenue) * 100 if row.expected_revenue else 0
		)
		row.sales_invoices = actual_billed.get("sales_invoices")
		row.fuel_litres = flt(row.fuel_litres)
		row.mileage_demanded = flt(row.mileage_demanded)

	return rows


def get_actual_billed_revenue(filters):
	vehicle_field = get_sales_order_item_vehicle_field()
	if not vehicle_field:
		return {}

	if filters.get("entitlement_status") and filters.entitlement_status != "Processed":
		return {}

	selected_entitlements = get_selected_revenue_batch_amounts(filters)
	if not selected_entitlements:
		return {}

	total_batch_amounts = get_total_revenue_batch_amounts(selected_entitlements)
	billed_amounts = get_submitted_invoice_amounts(filters, selected_entitlements, vehicle_field)
	actual_by_project_vehicle = {}

	for key, selected in selected_entitlements.items():
		total_batch_amount = flt(total_batch_amounts.get(key))
		billed = billed_amounts.get(key, {})
		if not total_batch_amount:
			continue

		actual_billed_revenue = flt(billed.get("actual_billed_revenue")) * (
			flt(selected.amount) / total_batch_amount
		)
		project_vehicle_key = (selected.project or "", selected.vehicle or "")
		bucket = actual_by_project_vehicle.setdefault(
			project_vehicle_key,
			{
				"actual_billed_revenue": 0,
				"sales_invoices": set(),
			},
		)
		bucket["actual_billed_revenue"] += actual_billed_revenue
		bucket["sales_invoices"].update(billed.get("sales_invoices") or [])

	return {
		key: {
			"actual_billed_revenue": flt(value["actual_billed_revenue"]),
			"sales_invoices": ", ".join(sorted(value["sales_invoices"])) or None,
		}
		for key, value in actual_by_project_vehicle.items()
	}


def get_selected_revenue_batch_amounts(filters):
	conditions = [
		"batch.docstatus = 1",
		"batch.settlement_type = 'Revenue'",
		"batch.target_doctype = 'Sales Order'",
		"COALESCE(batch.target_document, '') != ''",
		"item.entitlement_type = 'Revenue'",
		"item.trip_date BETWEEN %(from_date)s AND %(to_date)s",
	]
	values = {
		"from_date": filters.from_date,
		"to_date": filters.to_date,
	}

	if filters.get("project"):
		conditions.append("item.project = %(project)s")
		values["project"] = filters.project

	if filters.get("vehicle"):
		conditions.append("item.vehicle = %(vehicle)s")
		values["vehicle"] = filters.vehicle

	if filters.get("driver"):
		conditions.append("item.driver = %(driver)s")
		values["driver"] = filters.driver

	if filters.get("entitlement_status"):
		conditions.append("item.source_status = %(entitlement_status)s")
		values["entitlement_status"] = filters.entitlement_status

	rows = frappe.db.sql(
		f"""
		SELECT
			batch.name AS batch,
			item.project,
			COALESCE(item.vehicle, '') AS vehicle,
			SUM(item.amount) AS amount
		FROM `tabTrip Settlement Batch` batch
		INNER JOIN `tabTrip Settlement Batch Item` item
			ON item.parent = batch.name
			AND item.parenttype = 'Trip Settlement Batch'
		WHERE {' AND '.join(conditions)}
		GROUP BY batch.name, item.project, item.vehicle
		""",
		values,
		as_dict=True,
	)

	return {(row.batch, row.vehicle or ""): row for row in rows}


def get_total_revenue_batch_amounts(selected_entitlements):
	batch_names = sorted({key[0] for key in selected_entitlements})
	if not batch_names:
		return {}

	rows = frappe.get_all(
		"Trip Settlement Batch Item",
		filters={
			"parent": ["in", batch_names],
			"parenttype": "Trip Settlement Batch",
			"entitlement_type": "Revenue",
		},
		fields=["parent", "vehicle", "amount"],
	)
	totals = {}
	for row in rows:
		key = (row.parent, row.vehicle or "")
		totals[key] = totals.get(key, 0) + flt(row.amount)

	return totals


def get_submitted_invoice_amounts(filters, selected_entitlements, vehicle_field):
	vehicle_expression = f"COALESCE(NULLIF(order_item.`{vehicle_field}`, ''), NULLIF(batch.vehicle, ''), '')"
	batch_names = sorted({key[0] for key in selected_entitlements})
	conditions = [
		"batch.docstatus = 1",
		"batch.settlement_type = 'Revenue'",
		"batch.target_doctype = 'Sales Order'",
		"COALESCE(batch.target_document, '') != ''",
		"batch.name IN %(batch_names)s",
		"invoice.docstatus = 1",
		"invoice.posting_date <= %(invoice_as_at_date)s",
	]
	values = {
		"batch_names": tuple(batch_names),
		"invoice_as_at_date": filters.get("invoice_as_at_date") or today(),
	}

	rows = frappe.db.sql(
		f"""
		SELECT
			batch.name AS batch,
			{vehicle_expression} AS vehicle,
			SUM(invoice_item.base_net_amount) AS actual_billed_revenue,
			GROUP_CONCAT(
				DISTINCT invoice.name
				ORDER BY invoice.posting_date, invoice.name
				SEPARATOR ', '
			) AS sales_invoices
		FROM `tabTrip Settlement Batch` batch
		INNER JOIN `tabSales Order` sales_order
			ON sales_order.name = batch.target_document
			AND sales_order.docstatus != 2
		INNER JOIN `tabSales Order Item` order_item
			ON order_item.parent = sales_order.name
			AND order_item.parenttype = 'Sales Order'
		INNER JOIN `tabSales Invoice Item` invoice_item
			ON invoice_item.sales_order = sales_order.name
			AND invoice_item.so_detail = order_item.name
			AND invoice_item.parenttype = 'Sales Invoice'
		INNER JOIN `tabSales Invoice` invoice
			ON invoice.name = invoice_item.parent
		WHERE {' AND '.join(conditions)}
		GROUP BY batch.name, {vehicle_expression}
		""",
		values,
		as_dict=True,
	)

	return {
		(row.batch, row.vehicle or ""): {
			"actual_billed_revenue": flt(row.actual_billed_revenue),
			"sales_invoices": set((row.sales_invoices or "").split(", ")) if row.sales_invoices else set(),
		}
		for row in rows
	}


def get_sales_order_item_vehicle_field():
	for fieldname in ("custom_vehicle", "vehicle"):
		if frappe.db.has_column("Sales Order Item", fieldname):
			return fieldname
	return None


def get_report_summary(data):
	currency = frappe.db.get_single_value("Global Defaults", "default_currency")
	expected_revenue = sum(flt(row.get("expected_revenue")) for row in data)
	billed_revenue = sum(flt(row.get("actual_billed_revenue")) for row in data)
	pending_billing_amount = max(expected_revenue - billed_revenue, 0)

	return [
		{
			"value": expected_revenue,
			"label": _("Expected Revenue"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Blue",
		},
		{
			"value": billed_revenue,
			"label": _("Billed Revenue"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green",
		},
		{
			"value": pending_billing_amount,
			"label": _("Pending Billing Amount"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Orange" if pending_billing_amount else "Green",
		},
	]

