# Copyright (c) 2026, Nickson  and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today


PROJECT_ITEM_FIELDS_BY_SETTLEMENT_TYPE = {
	"Revenue": "custom_sales_item",
	"Fuel": "custom_fuel_item",
	"Mileage": "custom_mileage_item",
}


class TripSettlementBatch(Document):
	def validate(self):
		self.validate_date_range()
		self.set_target_doctype()
		self.validate_party_fields()
		self.warn_overlapping_batches()
		self.calculate_totals()
		self.validate_items_against_source()

	def before_submit(self):
		if not self.get("items"):
			frappe.throw(_("Please get entitlement records before submitting this batch."))

		self.validate_items_against_source(require_pending=True)

	def on_submit(self):
		self.update_source_entitlements("Batched")
		self.db_set("status", "Submitted", update_modified=False)

	def before_cancel(self):
		if self.target_document:
			frappe.throw(
				_(
					"This batch has already created {0} {1}. Cancel or reverse that document before cancelling this batch."
				).format(self.target_doctype, self.target_document)
			)

	def on_cancel(self):
		self.release_source_entitlements()
		self.db_set("status", "Cancelled", update_modified=False)

	def unreconcile(self):
		self.validate_can_unreconcile()

		linked_trip_logs = set()
		released_rows = 0

		for row in self.get("items") or []:
			if row.container_trip_log:
				linked_trip_logs.add(row.container_trip_log)

			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row or source_row.trip_settlement_batch != self.name:
				continue

			frappe.db.set_value(
				"Container Trip Entitlement Item",
				row.trip_entitlement_row,
				{
					"status": "Pending",
					"trip_settlement_batch": None,
					"target_doctype": None,
					"target_document": None,
				},
				update_modified=False,
			)
			released_rows += 1

		for row in self.get("items") or []:
			frappe.db.set_value(
				"Trip Settlement Batch Item",
				row.name,
				{
					"container_trip_log": None,
					"source_status": "Pending",
				},
				update_modified=False,
			)

		for trip_log in linked_trip_logs:
			if frappe.db.get_value("Container Trip Log", trip_log, "trip_settlement_batch") == self.name:
				frappe.db.set_value(
					"Container Trip Log",
					trip_log,
					"trip_settlement_batch",
					None,
					update_modified=False,
				)
			update_container_trip_log_status(trip_log)

		self.db_set("status", "Unreconciled", update_modified=False)
		self.status = "Unreconciled"

		return {
			"released_rows": released_rows,
			"trip_logs": sorted(linked_trip_logs),
		}

	def unlink_target_document(self):
		self.validate_can_unlink_target_document()

		target = {
			"doctype": self.target_doctype,
			"name": self.target_document,
		}
		relinked_rows = 0

		for row in self.get("items") or []:
			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row or source_row.trip_settlement_batch != self.name:
				continue

			if (
				source_row.target_doctype
				and source_row.target_document
				and (
					source_row.target_doctype != self.target_doctype
					or source_row.target_document != self.target_document
				)
			):
				frappe.throw(
					_("Trip Entitlement Row {0} is linked to another target document {1} {2}.").format(
						row.trip_entitlement_row,
						source_row.target_doctype,
						source_row.target_document,
					)
				)

			frappe.db.set_value(
				"Container Trip Entitlement Item",
				row.trip_entitlement_row,
				{
					"status": "Batched",
					"target_doctype": None,
					"target_document": None,
				},
				update_modified=False,
			)
			frappe.db.set_value(
				"Trip Settlement Batch Item",
				row.name,
				"source_status",
				"Batched",
				update_modified=False,
			)
			update_container_trip_log_status(row.container_trip_log)
			relinked_rows += 1

		frappe.db.set_value(
			self.doctype,
			self.name,
			{
				"target_document": None,
				"status": "Submitted",
			},
			update_modified=False,
		)

		self.target_document = None
		self.status = "Submitted"

		return {
			"target": target,
			"relinked_rows": relinked_rows,
		}

	def validate_can_unlink_target_document(self):
		if self.docstatus != 1:
			frappe.throw(_("Only submitted Trip Settlement Batches can unlink ERPNext documents."))

		if not self.target_document:
			frappe.throw(_("This Trip Settlement Batch is not linked to an ERPNext document."))

		for row in self.get("items") or []:
			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row or source_row.trip_settlement_batch != self.name:
				continue

			if source_row.status != "Processed":
				frappe.throw(
					_("Trip Entitlement Row {0} must be Processed before unlinking the ERPNext document.").format(
						row.trip_entitlement_row
					)
				)

	def validate_can_unreconcile(self):
		if self.docstatus != 1:
			frappe.throw(_("Only submitted Trip Settlement Batches can be unreconciled."))

		if self.target_document:
			frappe.throw(
				_(
					"This batch has already created {0} {1}. Cancel or reverse that document before unreconciling this batch."
				).format(self.target_doctype, self.target_document)
			)

		for row in self.get("items") or []:
			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row or source_row.trip_settlement_batch != self.name:
				continue

			if source_row.status == "Processed" or source_row.target_document:
				frappe.throw(
					_("Trip Entitlement Row {0} is already Processed and cannot be unreconciled.").format(
						row.trip_entitlement_row
					)
				)

	def create_erpnext_document(self):
		self.validate_can_create_erpnext_document()

		if self.settlement_type == "Revenue":
			target_doc = self.create_sales_order()
		elif self.settlement_type == "Fuel":
			target_doc = self.create_material_request()
		elif self.settlement_type == "Mileage":
			target_doc = self.create_purchase_order()
		else:
			frappe.throw(_("Unsupported Settlement Type {0}.").format(self.settlement_type))

		target_doc.insert(ignore_permissions=True)
		self.mark_as_processed(target_doc.doctype, target_doc.name)

		return target_doc

	def validate_can_create_erpnext_document(self):
		if self.docstatus != 1:
			frappe.throw(_("Submit the Trip Settlement Batch before creating an ERPNext document."))

		if self.target_document:
			frappe.throw(
				_("{0} {1} has already been created for this batch.").format(
					self.target_doctype, self.target_document
				)
			)

		if not self.get("items"):
			frappe.throw(_("Please get entitlement records before creating an ERPNext document."))

		self.set_target_doctype()
		self.validate_party_fields()
		self.validate_project_item()
		self.validate_items_against_source()

		for row in self.items:
			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row:
				frappe.throw(_("Trip Entitlement Row {0} no longer exists.").format(row.trip_entitlement_row))

			if source_row.status != "Batched" or source_row.trip_settlement_batch != self.name:
				frappe.throw(
					_("Row {0}: Source entitlement must be Batched in this Trip Settlement Batch.").format(row.idx)
				)

	def validate_project_item(self):
		get_project_settlement_item(self.project, self.settlement_type)

	def create_sales_order(self):
		customer = self.customer
		if not customer:
			frappe.throw(_("Customer is required for Revenue settlement."))

		doc = frappe.new_doc("Sales Order")
		doc.customer = customer
		doc.order_type = "Sales"
		doc.transaction_date = today()
		doc.delivery_date = self.end_date or today()
		doc.project = self.project
		set_default_company(doc)
		set_currency_defaults(doc)
		set_selling_price_list_defaults(doc)
		set_compatible_field(doc, ("trip_settlement_batch", "custom_trip_settlement_batch"), self.name)
		set_compatible_field(doc, ("ignore_pricing_rule",), 1)

		for item in self.get_grouped_items():
			doc.append(
				"items",
				get_target_item_row(
					item,
					"Sales Order Item",
					self.get_item_description(item),
					{
						"rate": item.rate,
						"base_rate": item.rate,
						"amount": item.quantity * item.rate,
						"base_amount": item.quantity * item.rate,
						"delivery_date": self.end_date or today(),
					},
				),
			)

		return doc

	def create_material_request(self):
		doc = frappe.new_doc("Material Request")
		doc.material_request_type = "Purchase"
		doc.transaction_date = today()
		doc.schedule_date = self.end_date or today()
		doc.project = self.project
		set_default_company(doc)
		set_compatible_field(doc, ("trip_settlement_batch", "custom_trip_settlement_batch"), self.name)

		for item in self.get_grouped_items(include_rate=False):
			doc.append(
				"items",
				get_target_item_row(
					item,
					"Material Request Item",
					self.get_item_description(item),
					{"schedule_date": self.end_date or today()},
				),
			)

		return doc

	def create_purchase_order(self):
		if not self.supplier:
			frappe.throw(_("Supplier is required for Mileage settlement."))

		doc = frappe.new_doc("Purchase Order")
		doc.supplier = self.supplier
		doc.title = self.supplier
		doc.transaction_date = today()
		doc.schedule_date = self.end_date or today()
		doc.project = self.project
		set_default_company(doc)
		set_currency_defaults(doc)
		set_compatible_field(doc, ("trip_settlement_batch", "custom_trip_settlement_batch"), self.name)
		set_compatible_field(doc, ("ignore_pricing_rule",), 1)

		for item in self.get_grouped_items():
			doc.append(
				"items",
				get_target_item_row(
					item,
					"Purchase Order Item",
					self.get_item_description(item),
					{
						"rate": item.rate,
						"base_rate": item.rate,
						"amount": item.quantity * item.rate,
						"base_amount": item.quantity * item.rate,
						"schedule_date": self.end_date or today(),
					},
				),
			)

		return doc

	def get_grouped_items(self, include_rate=True):
		project_item = get_project_settlement_item(self.project, self.settlement_type)
		item_details = get_item_details(project_item)
		grouped_items = {}

		for row in self.items:
			uom = row.uom or item_details.stock_uom
			rate = flt(row.rate) if include_rate else 0
			key = (row.vehicle, project_item, uom, rate)
			bucket = grouped_items.setdefault(
				key,
				frappe._dict(
					vehicle=row.vehicle,
					project=self.project,
					item_code=project_item,
					item_name=item_details.item_name,
					stock_uom=item_details.stock_uom,
					uom=uom,
					rate=rate,
					quantity=0,
					amount=0,
					container_trip_logs=set(),
					entitlement_rows=[],
				),
			)
			bucket.quantity += flt(row.quantity)
			bucket.amount += flt(row.amount)
			if row.container_trip_log:
				bucket.container_trip_logs.add(row.container_trip_log)
			if row.trip_entitlement_row:
				bucket.entitlement_rows.append(row.trip_entitlement_row)

		if not grouped_items:
			frappe.throw(_("No settlement items found."))

		return list(grouped_items.values())

	def get_item_description(self, item):
		return _(
			"{0} settlement for Trip Settlement Batch {1}. Vehicle: {2}. Period: {3} to {4}. Trips: {5}."
		).format(
			self.settlement_type,
			self.name,
			item.vehicle or "-",
			frappe.format(self.start_date, {"fieldtype": "Date"}),
			frappe.format(self.end_date, {"fieldtype": "Date"}),
			", ".join(sorted(item.container_trip_logs)) or "-",
		)

	def mark_as_processed(self, target_doctype, target_document):
		frappe.db.set_value(
			self.doctype,
			self.name,
			{
				"target_doctype": target_doctype,
				"target_document": target_document,
				"status": "Processed",
			},
			update_modified=False,
		)

		for row in self.items:
			frappe.db.set_value(
				"Container Trip Entitlement Item",
				row.trip_entitlement_row,
				{
					"status": "Processed",
					"trip_settlement_batch": self.name,
					"target_doctype": target_doctype,
					"target_document": target_document,
				},
				update_modified=False,
			)
			frappe.db.set_value(
				"Trip Settlement Batch Item",
				row.name,
				"source_status",
				"Processed",
				update_modified=False,
			)
			update_container_trip_log_status(row.container_trip_log)

		self.target_doctype = target_doctype
		self.target_document = target_document
		self.status = "Processed"

	def validate_date_range(self):
		if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
			frappe.throw(_("Start Date cannot be greater than End Date."))

	def set_target_doctype(self):
		target_doctype = {
			"Revenue": "Sales Order",
			"Fuel": "Material Request",
			"Mileage": "Purchase Order",
		}.get(self.settlement_type)

		self.target_doctype = target_doctype

	def validate_party_fields(self):
		if self.settlement_type == "Revenue" and not self.customer:
			frappe.throw(_("Customer is required for Revenue settlement."))

		if self.settlement_type == "Mileage" and not self.supplier:
			frappe.throw(_("Supplier is required for Mileage settlement because it creates a Purchase Order."))

	def warn_overlapping_batches(self):
		if not (self.settlement_type and self.project and self.start_date and self.end_date):
			return

		overlapping_batches = frappe.get_all(
			"Trip Settlement Batch",
			filters=[
				["Trip Settlement Batch", "name", "!=", self.name],
				["Trip Settlement Batch", "docstatus", "!=", 2],
				["Trip Settlement Batch", "settlement_type", "=", self.settlement_type],
				["Trip Settlement Batch", "project", "=", self.project],
				["Trip Settlement Batch", "start_date", "<=", self.end_date],
				["Trip Settlement Batch", "end_date", ">=", self.start_date],
			],
			fields=["name", "start_date", "end_date", "vehicle", "status"],
			order_by="start_date asc",
		)

		for batch in overlapping_batches:
			if self.vehicle and batch.vehicle and batch.vehicle != self.vehicle:
				continue

			frappe.msgprint(
				_(
					"Overlapping {0} batch found: {1} ({2} to {3}). Only pending, unsettled rows will be included."
				).format(
					self.settlement_type,
					batch.name,
					frappe.format(batch.start_date, {"fieldtype": "Date"}),
					frappe.format(batch.end_date, {"fieldtype": "Date"}),
				),
				title=_("Overlapping Settlement Period"),
				indicator="orange",
			)
			return

	def calculate_totals(self):
		self.total_qty = sum(flt(row.quantity) for row in self.get("items") or [])
		self.total_amount = sum(flt(row.amount) for row in self.get("items") or [])

	def validate_items_against_source(self, require_pending=False):
		seen_rows = set()

		for row in self.get("items") or []:
			if not row.trip_entitlement_row:
				frappe.throw(_("Trip Entitlement Row is missing in settlement item row {0}.").format(row.idx))

			if row.trip_entitlement_row in seen_rows:
				frappe.throw(_("Trip Entitlement Row {0} is duplicated in this batch.").format(row.trip_entitlement_row))
			seen_rows.add(row.trip_entitlement_row)

			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row:
				frappe.throw(_("Trip Entitlement Row {0} no longer exists.").format(row.trip_entitlement_row))

			if source_row.parenttype != "Container Trip Log" or source_row.parentfield != "entitlement_items":
				frappe.throw(
					_("Row {0}: Source entitlement must belong to a Container Trip Log.").format(row.idx)
				)

			if source_row.entitlement_type != self.settlement_type:
				frappe.throw(
					_("Row {0}: Source entitlement type must be {1}.").format(row.idx, self.settlement_type)
				)

			if require_pending and source_row.status != "Pending":
				frappe.throw(
					_("Row {0}: Source entitlement is already {1}.").format(row.idx, source_row.status)
				)

			if source_row.trip_settlement_batch and source_row.trip_settlement_batch != self.name:
				frappe.throw(
					_("Row {0}: Source entitlement is already linked to batch {1}.").format(
						row.idx, source_row.trip_settlement_batch
					)
				)

			source_trip = get_container_trip_log(source_row.parent)
			if not source_trip:
				frappe.throw(_("Container Trip Log {0} no longer exists.").format(source_row.parent))

			if source_trip.docstatus != 1:
				frappe.throw(_("Container Trip Log {0} must be submitted.").format(source_trip.name))

			self.validate_item_matches_filters(row, source_row, source_trip)

	def validate_item_matches_filters(self, row, source_row, source_trip):
		if source_trip.project != self.project:
			frappe.throw(_("Row {0}: Source project does not match this batch.").format(row.idx))

		if self.vehicle and source_trip.vehicle != self.vehicle:
			frappe.throw(_("Row {0}: Source vehicle does not match this batch.").format(row.idx))

		if getdate(source_trip.trip_date) < getdate(self.start_date) or getdate(source_trip.trip_date) > getdate(self.end_date):
			frappe.throw(_("Row {0}: Source trip date is outside this batch period.").format(row.idx))

		if row.container_trip_log != source_trip.name:
			frappe.throw(_("Row {0}: Container Trip Log reference is incorrect.").format(row.idx))

		if row.entitlement_type != source_row.entitlement_type:
			frappe.throw(_("Row {0}: Entitlement Type does not match the source row.").format(row.idx))

		if row.item != source_row.item:
			frappe.throw(_("Row {0}: Item does not match the source row.").format(row.idx))

		if flt(row.quantity) != flt(source_row.quantity):
			frappe.throw(_("Row {0}: Quantity does not match the source row.").format(row.idx))

		if flt(row.rate) != flt(source_row.rate):
			frappe.throw(_("Row {0}: Rate does not match the source row.").format(row.idx))

		if flt(row.amount) != flt(source_row.amount):
			frappe.throw(_("Row {0}: Amount does not match the source row.").format(row.idx))

	def update_source_entitlements(self, status):
		for row in self.get("items") or []:
			frappe.db.set_value(
				"Container Trip Entitlement Item",
				row.trip_entitlement_row,
				{
					"status": status,
					"trip_settlement_batch": self.name,
				},
				update_modified=False,
			)
			frappe.db.set_value(
				"Trip Settlement Batch Item",
				row.name,
				"source_status",
				status,
				update_modified=False,
			)
			update_container_trip_log_status(row.container_trip_log)

	def release_source_entitlements(self):
		for row in self.get("items") or []:
			source_row = get_entitlement_child_row(row.trip_entitlement_row)
			if not source_row or source_row.trip_settlement_batch != self.name:
				continue

			if source_row.status == "Processed":
				frappe.throw(
					_("Trip Entitlement Row {0} is already Processed and cannot be released.").format(
						row.trip_entitlement_row
					)
				)

			frappe.db.set_value(
				"Container Trip Entitlement Item",
				row.trip_entitlement_row,
				{
					"status": "Pending",
					"trip_settlement_batch": None,
					"target_doctype": None,
					"target_document": None,
				},
				update_modified=False,
			)
			frappe.db.set_value(
				"Trip Settlement Batch Item",
				row.name,
				"source_status",
				"Pending",
				update_modified=False,
			)
			update_container_trip_log_status(row.container_trip_log)


@frappe.whitelist()
def get_pending_entitlements(settlement_type, start_date, end_date, project, vehicle=None):
	if not settlement_type or not start_date or not end_date or not project:
		frappe.throw(_("Settlement Type, Start Date, End Date, and Project are required."))

	if getdate(start_date) > getdate(end_date):
		frappe.throw(_("Start Date cannot be greater than End Date."))

	conditions = [
		"trip.docstatus = 1",
		"trip.project = %(project)s",
		"trip.trip_date BETWEEN %(start_date)s AND %(end_date)s",
		"item.parenttype = 'Container Trip Log'",
		"item.parentfield = 'entitlement_items'",
		"item.entitlement_type = %(settlement_type)s",
		"item.status = 'Pending'",
		"COALESCE(item.trip_settlement_batch, '') = ''",
	]
	values = {
		"settlement_type": settlement_type,
		"start_date": start_date,
		"end_date": end_date,
		"project": project,
	}

	if vehicle:
		conditions.append("trip.vehicle = %(vehicle)s")
		values["vehicle"] = vehicle

	return frappe.db.sql(
		f"""
		SELECT
			item.name AS trip_entitlement_row,
			trip.name AS container_trip_log,
			trip.trip_date,
			trip.project,
			trip.vehicle,
			trip.driver,
			(
				SELECT GROUP_CONCAT(container.container_id ORDER BY container.idx SEPARATOR ', ')
				FROM `tabContainer Holder` container
				WHERE container.parent = trip.name
					AND container.parenttype = 'Container Trip Log'
					AND container.parentfield = 'container'
			) AS container_numbers,
			item.entitlement_type,
			item.item,
			item.quantity,
			item.uom,
			item.rate,
			item.amount,
			item.status AS source_status
		FROM `tabContainer Trip Entitlement Item` item
		INNER JOIN `tabContainer Trip Log` trip
			ON trip.name = item.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY trip.trip_date ASC, trip.name ASC, item.idx ASC
		""",
		values,
		as_dict=True,
	)


def get_entitlement_child_row(row_name):
	return frappe.db.get_value(
		"Container Trip Entitlement Item",
		row_name,
		[
			"name",
			"parent",
			"parenttype",
			"parentfield",
			"entitlement_type",
			"item",
			"quantity",
			"uom",
			"rate",
			"amount",
			"status",
			"trip_settlement_batch",
			"target_doctype",
			"target_document",
		],
		as_dict=True,
	)


def get_container_trip_log(trip_log):
	return frappe.db.get_value(
		"Container Trip Log",
		trip_log,
		[
			"name",
			"docstatus",
			"trip_date",
			"project",
			"vehicle",
		],
		as_dict=True,
	)


def update_container_trip_log_status(trip_log):
	if not trip_log:
		return

	rows = frappe.get_all(
		"Container Trip Entitlement Item",
		filters={
			"parent": trip_log,
			"parenttype": "Container Trip Log",
			"parentfield": "entitlement_items",
		},
		fields=["entitlement_type", "status", "trip_settlement_batch"],
	)
	if not rows:
		return

	rows_by_type = {}
	for row in rows:
		rows_by_type.setdefault(row.entitlement_type, []).append(row)

	updates = {}
	if all(row.status == "Processed" for row in rows_by_type.get("Revenue", [])):
		updates["billing_status"] = "Billed"
	elif rows_by_type.get("Revenue"):
		updates["billing_status"] = "Not Billed"

	if all(row.status == "Processed" for row in rows_by_type.get("Fuel", [])):
		updates["fuel_reimbursement_status"] = "Reimbursed"
	elif rows_by_type.get("Fuel"):
		updates["fuel_reimbursement_status"] = "Not reimbursed"

	if all(row.status == "Processed" for row in rows_by_type.get("Mileage", [])):
		updates["mileage_status"] = "Paid"
	elif rows_by_type.get("Mileage"):
		updates["mileage_status"] = "Not Paid"

	if updates:
		frappe.db.set_value("Container Trip Log", trip_log, updates, update_modified=False)


@frappe.whitelist()
def create_erpnext_document(source_name):
	doc = frappe.get_doc("Trip Settlement Batch", source_name)
	target_doc = doc.create_erpnext_document()

	return {
		"doctype": target_doc.doctype,
		"name": target_doc.name,
	}


@frappe.whitelist()
def unreconcile_batch(source_name):
	doc = frappe.get_doc("Trip Settlement Batch", source_name)
	doc.check_permission("cancel")
	result = doc.unreconcile()

	return result


@frappe.whitelist()
def unlink_target_document(source_name):
	doc = frappe.get_doc("Trip Settlement Batch", source_name)
	doc.check_permission("cancel")
	result = doc.unlink_target_document()

	return result


@frappe.whitelist()
def get_target_document_settlement_batches(target_doctype, target_document):
	if not target_doctype or not target_document:
		frappe.throw(_("Target document is required."))

	if target_doctype not in ("Sales Order", "Material Request", "Purchase Order"):
		frappe.throw(_("Unsupported target document type {0}.").format(target_doctype))

	if not frappe.db.exists(target_doctype, target_document):
		frappe.throw(_("{0} {1} was not found.").format(target_doctype, target_document))

	frappe.get_doc(target_doctype, target_document).check_permission("read")

	return frappe.get_all(
		"Trip Settlement Batch",
		filters={
			"docstatus": 1,
			"target_doctype": target_doctype,
			"target_document": target_document,
		},
		fields=["name", "settlement_type", "status"],
		order_by="modified desc",
	)


@frappe.whitelist()
def unlink_target_document_settlement_batches(target_doctype, target_document):
	if not target_doctype or not target_document:
		frappe.throw(_("Target document is required."))

	if target_doctype not in ("Sales Order", "Material Request", "Purchase Order"):
		frappe.throw(_("Unsupported target document type {0}.").format(target_doctype))

	frappe.get_doc(target_doctype, target_document).check_permission("cancel")
	batches = get_target_document_settlement_batches(target_doctype, target_document)
	results = []

	for batch in batches:
		doc = frappe.get_doc("Trip Settlement Batch", batch.name)
		doc.check_permission("cancel")
		result = doc.unlink_target_document()
		results.append(
			{
				"name": batch.name,
				"relinked_rows": result.get("relinked_rows", 0),
			}
		)

	return results


@frappe.whitelist()
def get_linked_settlement_batches(trip_log):
	if not trip_log:
		frappe.throw(_("Container Trip Log is required."))

	if not frappe.db.exists("Container Trip Log", trip_log):
		frappe.throw(_("Container Trip Log {0} was not found.").format(trip_log))

	frappe.get_doc("Container Trip Log", trip_log).check_permission("read")

	batch_names = set(
		frappe.get_all(
			"Container Trip Entitlement Item",
			filters={
				"parent": trip_log,
				"parenttype": "Container Trip Log",
				"parentfield": "entitlement_items",
				"trip_settlement_batch": ["!=", ""],
			},
			pluck="trip_settlement_batch",
		)
	)

	parent_batch = frappe.db.get_value("Container Trip Log", trip_log, "trip_settlement_batch")
	if parent_batch:
		batch_names.add(parent_batch)

	batch_names.update(
		frappe.get_all(
			"Trip Settlement Batch Item",
			filters={"container_trip_log": trip_log},
			pluck="parent",
		)
	)

	if not batch_names:
		return []

	return frappe.get_all(
		"Trip Settlement Batch",
		filters={"name": ["in", sorted(batch_names)], "docstatus": 1},
		fields=["name", "settlement_type", "status", "target_doctype", "target_document"],
		order_by="modified desc",
	)


@frappe.whitelist()
def unreconcile_linked_batches(trip_log):
	frappe.get_doc("Container Trip Log", trip_log).check_permission("cancel")
	batches = get_linked_settlement_batches(trip_log)
	results = []

	for batch in batches:
		doc = frappe.get_doc("Trip Settlement Batch", batch.name)
		doc.check_permission("cancel")
		result = doc.unreconcile()
		results.append(
			{
				"name": batch.name,
				"released_rows": result.get("released_rows", 0),
			}
		)

	return results


def get_project_settlement_item(project, settlement_type):
	if not project:
		frappe.throw(_("Project is required."))

	fieldname = PROJECT_ITEM_FIELDS_BY_SETTLEMENT_TYPE.get(settlement_type)
	if not fieldname:
		frappe.throw(_("Unsupported Settlement Type {0}.").format(settlement_type))

	project_doc = frappe.get_cached_doc("Project", project)
	if not project_doc.meta.get_field(fieldname):
		frappe.throw(
			_("Project field {0} is missing. Please add it before creating settlement documents.").format(
				fieldname
			)
		)

	item_code = project_doc.get(fieldname)
	if not item_code:
		frappe.throw(
			_("Please set {0} on Project {1} before creating the {2} document.").format(
				frappe.unscrub(fieldname), project, settlement_type
			)
		)

	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} set on Project {1} was not found.").format(item_code, project))

	return item_code


def get_item_details(item_code):
	item_details = frappe.db.get_value(
		"Item",
		item_code,
		["item_name", "stock_uom"],
		as_dict=True,
	)
	if not item_details:
		frappe.throw(_("Item {0} was not found.").format(item_code))

	if not item_details.stock_uom:
		frappe.throw(_("Item {0} must have a Stock UOM.").format(item_code))

	return item_details


def get_target_item_row(item, child_doctype, description, extra_values=None):
	row = {
		"item_code": item.item_code,
		"item_name": item.item_name,
		"description": description,
		"qty": item.quantity,
		"uom": item.uom,
		"stock_uom": item.stock_uom,
		"conversion_factor": 1,
		"project": item.project,
	}
	row.update(extra_values or {})

	set_vehicle_on_target_item_row(row, item.vehicle, child_doctype)

	return row


def set_vehicle_on_target_item_row(row, vehicle, child_doctype):
	if not vehicle:
		return

	meta = frappe.get_meta(child_doctype)
	for fieldname in ("vehicle", "custom_vehicle", "truck", "custom_truck"):
		if meta.get_field(fieldname):
			row[fieldname] = vehicle
			return


def set_default_company(doc):
	if not doc.meta.get_field("company"):
		return

	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or frappe.db.get_value("Company", {}, "name")
	)
	if company:
		doc.company = company


def set_currency_defaults(doc):
	if not doc.meta.get_field("currency"):
		return

	company_currency = None
	if getattr(doc, "company", None):
		company_currency = frappe.db.get_value("Company", doc.company, "default_currency")

	currency = company_currency or frappe.db.get_single_value("Global Defaults", "default_currency")
	if currency:
		doc.currency = currency
		set_compatible_field(doc, ("conversion_rate",), 1)


def set_selling_price_list_defaults(doc):
	if not doc.meta.get_field("selling_price_list"):
		return

	price_list = (
		frappe.db.get_single_value("Selling Settings", "selling_price_list")
		or frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
	)
	if not price_list:
		return

	doc.selling_price_list = price_list
	price_list_currency = frappe.db.get_value("Price List", price_list, "currency") or doc.currency
	if price_list_currency:
		doc.price_list_currency = price_list_currency
		set_compatible_field(doc, ("plc_conversion_rate",), 1)


def set_compatible_field(doc, fieldnames, value):
	for fieldname in fieldnames:
		if doc.meta.get_field(fieldname):
			doc.set(fieldname, value)

