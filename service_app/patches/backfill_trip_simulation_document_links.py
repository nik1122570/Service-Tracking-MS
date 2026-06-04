import frappe


def execute():
	backfill_quotation_links()
	backfill_purchase_order_links()


def backfill_quotation_links():
	if not frappe.db.has_column("Quotation", "custom_trip_simulation"):
		return

	for trip in frappe.get_all(
		"Trip Simulation",
		filters={"quotation": ["!=", ""]},
		fields=["name", "quotation"],
	):
		set_trip_simulation_link("Quotation", trip.quotation, trip.name)


def backfill_purchase_order_links():
	if not frappe.db.has_column("Purchase Order", "custom_trip_simulation"):
		return

	for trip in frappe.get_all(
		"Trip Simulation",
		filters={"fuel_purchase_order": ["!=", ""]},
		fields=["name", "fuel_purchase_order"],
	):
		set_trip_simulation_link("Purchase Order", trip.fuel_purchase_order, trip.name)

	for row in frappe.get_all(
		"Trip Simulation Table",
		filters={"purchase_order": ["!=", ""]},
		fields=["parent", "purchase_order"],
	):
		set_trip_simulation_link("Purchase Order", row.purchase_order, row.parent)


def set_trip_simulation_link(doctype, document_name, trip_simulation):
	if not document_name or not frappe.db.exists(doctype, document_name):
		return

	existing_link = frappe.db.get_value(doctype, document_name, "custom_trip_simulation")
	if existing_link:
		return

	frappe.db.set_value(
		doctype,
		document_name,
		"custom_trip_simulation",
		trip_simulation,
		update_modified=False,
	)
