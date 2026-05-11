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
		self.sync_entitlement_items()

	def on_submit(self):
		self.set_trip_totals()
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

		self.validate_containers_not_already_carried(seen_containers)

	def validate_containers_not_already_carried(self, container_ids):
		carried_containers = get_carried_containers(container_ids, self.name)
		if not carried_containers:
			return

		messages = []
		for row in self.container:
			carried_trip = carried_containers.get(row.container_id)
			if not carried_trip:
				continue

			messages.append(
				_(
					"Row {0}: Container {1} was already carried in Trip Log {2} on {3}."
				).format(
					row.idx,
					frappe.bold(row.container_id),
					frappe.bold(carried_trip.trip_log),
					frappe.bold(carried_trip.trip_date or ""),
				)
			)

		if messages:
			frappe.throw("<br>".join(messages), title=_("Container Already Carried"))

	def sync_entitlement_items(self):
		if self.docstatus != 0:
			return

		self.set("entitlement_items", [])
		for entitlement_row in self.get_entitlement_rows():
			self.append("entitlement_items", entitlement_row)

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


def get_carried_containers(container_ids, current_trip_log=None):
	container_ids = [container_id for container_id in (container_ids or []) if container_id]
	if not container_ids:
		return {}

	placeholders = ", ".join(["%s"] * len(container_ids))
	values = list(container_ids)
	current_trip_condition = ""

	if current_trip_log:
		current_trip_condition = "and trip.name != %s"
		values.append(current_trip_log)

	rows = frappe.db.sql(
		f"""
		select
			container.container_id,
			container.parent as trip_log,
			trip.trip_date,
			trip.vehicle
		from `tabContainer Holder` container
		inner join `tabContainer Trip Log` trip
			on trip.name = container.parent
		where container.parenttype = 'Container Trip Log'
			and container.parentfield = 'container'
			and container.container_id in ({placeholders})
			and trip.docstatus = 1
			and ifnull(trip.trip_status, '') != 'Cancelled'
			{current_trip_condition}
		order by trip.trip_date desc, trip.modified desc
		""",
		values,
		as_dict=True,
	)

	return {row.container_id: row for row in rows}


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_available_containers(doctype, txt, searchfield, start, page_len, filters):
	current_trip_log = (filters or {}).get("current_trip_log")

	return frappe.db.sql(
		"""
		select
			container.name,
			container.container_number
		from `tabAllocated Container` container
		where (container.name like %(txt)s or container.container_number like %(txt)s)
			and not exists (
				select 1
				from `tabContainer Holder` child
				inner join `tabContainer Trip Log` trip
					on trip.name = child.parent
				where child.parenttype = 'Container Trip Log'
					and child.parentfield = 'container'
					and child.container_id = container.name
					and trip.docstatus = 1
					and ifnull(trip.trip_status, '') != 'Cancelled'
					and (%(current_trip_log)s = '' or trip.name != %(current_trip_log)s)
			)
		order by container.modified desc
		limit %(start)s, %(page_len)s
		""",
		{
			"txt": f"%{txt}%",
			"current_trip_log": current_trip_log or "",
			"start": start,
			"page_len": page_len,
		},
	)
