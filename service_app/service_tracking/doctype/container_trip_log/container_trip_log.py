# Copyright (c) 2026, Nickson  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ContainerTripLog(Document):
	def validate(self):
		self.set_trip_totals()
		self.validate_container_rows()

	def on_submit(self):
		self.set_trip_totals()
		entitlement_log = self.create_trip_entitlement_log()
		frappe.db.set_value(
			self.doctype,
			self.name,
			"trip_entitlement_log",
			entitlement_log.name,
			update_modified=False,
		)
		if self.trip_status != "Cancelled":
			frappe.db.set_value(
				self.doctype,
				self.name,
				"trip_status",
				"Completed",
				update_modified=False,
			)

	def set_trip_totals(self):
		total_qty = len(self.get("container") or [])
		self.total_qty = total_qty
		self.total_expected_revenue = flt(self.expected_revenue) * total_qty
		self.expected_mileage_pay = flt(self.driver_mileage_per_trip) * total_qty

	def validate_container_rows(self):
		if not self.get("container"):
			frappe.throw(_("At least one container is required."))

		seen_containers = set()
		for row in self.container:
			if not row.container_id:
				frappe.throw(_("Container is required in row {0}.").format(row.idx))

			if row.container_id in seen_containers:
				frappe.throw(
					_("Container {0} has been entered more than once.").format(row.container_id)
				)
			seen_containers.add(row.container_id)

	def create_trip_entitlement_log(self):
		existing_log = self.get_existing_entitlement_log()
		if existing_log:
			return frappe.get_doc("Trip Entitlement Log", existing_log)

		entitlement_log = frappe.new_doc("Trip Entitlement Log")
		entitlement_log.container_trip_log = self.name
		entitlement_log.trip_date = self.trip_date
		entitlement_log.project = self.project
		entitlement_log.customer = self.customer
		entitlement_log.driver = self.driver
		entitlement_log.container_count = self.total_qty

		set_if_field_exists(entitlement_log, "container_numbers", self.get_container_numbers())
		set_if_field_exists(entitlement_log, "route", self.route)
		set_if_field_exists(entitlement_log, "vehicle", self.vehicle)
		set_if_field_exists(entitlement_log, "trailer_1", self.trailer_1)
		set_if_field_exists(entitlement_log, "trailer_2", self.trailer_2)
		set_if_field_exists(entitlement_log, "total_expected_revenue", self.total_expected_revenue)
		set_if_field_exists(entitlement_log, "expected_mileage_pay", self.expected_mileage_pay)
		set_if_field_exists(entitlement_log, "total_fuel_litres", self.get_total_fuel_litres())
		set_if_field_exists(entitlement_log, "status", "Pending")

		for entitlement_row in self.get_entitlement_rows():
			entitlement_log.append("entitlement_items", entitlement_row)

		entitlement_log.insert(ignore_permissions=True)
		if entitlement_log.meta.is_submittable:
			entitlement_log.submit()

		return entitlement_log

	def get_existing_entitlement_log(self):
		if self.trip_entitlement_log and frappe.db.exists("Trip Entitlement Log", self.trip_entitlement_log):
			return self.trip_entitlement_log

		return frappe.db.get_value(
			"Trip Entitlement Log",
			{"container_trip_log": self.name, "docstatus": ["!=", 2]},
			"name",
		)

	def get_entitlement_rows(self):
		return [
			{
				"entitlement_type": "Revenue",
				"item": get_project_item(self.project, "revenue"),
				"quantity": self.total_qty,
				"uom": get_existing_uom("Trip", "Nos"),
				"rate": flt(self.expected_revenue),
				"amount": flt(self.total_expected_revenue),
				"status": "Pending",
			},
			{
				"entitlement_type": "Fuel",
				"item": get_project_item(self.project, "fuel"),
				"quantity": self.get_total_fuel_litres(),
				"uom": get_existing_uom("Litre", "Liter", "Nos"),
				"rate": 0,
				"amount": 0,
				"status": "Pending",
			},
			{
				"entitlement_type": "Mileage",
				"item": get_project_item(self.project, "mileage"),
				"quantity": self.total_qty,
				"uom": get_existing_uom("Container", "Nos"),
				"rate": flt(self.driver_mileage_per_trip),
				"amount": flt(self.expected_mileage_pay),
				"status": "Pending",
			},
		]

	def get_total_fuel_litres(self):
		return flt(self.fuel_litres_entitled_per_trip) * flt(self.total_qty)

	def get_container_numbers(self):
		return ", ".join(row.container_id for row in self.get("container") or [] if row.container_id)


def set_if_field_exists(doc, fieldname, value):
	if doc.meta.get_field(fieldname):
		doc.set(fieldname, value)


def get_existing_uom(*uoms):
	for uom in uoms:
		if frappe.db.exists("UOM", uom):
			return uom
	return None


def get_project_item(project, entitlement_type):
	if not project:
		return None

	project_doc = frappe.get_cached_doc("Project", project)
	fieldnames_by_type = {
		"revenue": (
			"custom_revenue_item",
			"custom_trip_revenue_item",
			"custom_sales_item",
			"custom_transport_service_item",
		),
		"fuel": (
			"custom_fuel_item",
			"custom_fuel_reimbursement_item",
		),
		"mileage": (
			"custom_mileage_item",
			"custom_driver_mileage_item",
			"custom_driver_mileage_allowance_item",
		),
	}

	for fieldname in fieldnames_by_type.get(entitlement_type, ()):
		if project_doc.meta.get_field(fieldname) and project_doc.get(fieldname):
			return project_doc.get(fieldname)

	return None
