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
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"description": self.get_item_description(item),
					"qty": item.quantity,
					"uom": item.uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"rate": item.rate,
					"base_rate": item.rate,
					"amount": item.quantity * item.rate,
					"base_amount": item.quantity * item.rate,
					"delivery_date": self.end_date or today(),
					"project": self.project,
				},
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
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"description": self.get_item_description(item),
					"qty": item.quantity,
					"uom": item.uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"schedule_date": self.end_date or today(),
					"project": self.project,
				},
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
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"description": self.get_item_description(item),
					"qty": item.quantity,
					"uom": item.uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"rate": item.rate,
					"base_rate": item.rate,
					"amount": item.quantity * item.rate,
					"base_amount": item.quantity * item.rate,
					"schedule_date": self.end_date or today(),
					"project": self.project,
				},
			)

		return doc

	def get_grouped_items(self, include_rate=True):
		project_item = get_project_settlement_item(self.project, self.settlement_type)
		item_details = get_item_details(project_item)
		grouped_items = {}

		for row in self.items:
			uom = row.uom or item_details.stock_uom
			rate = flt(row.rate) if include_rate else 0
			key = (project_item, uom, rate)
			bucket = grouped_items.setdefault(
				key,
				frappe._dict(
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
			"{0} settlement for Trip Settlement Batch {1}. Period: {2} to {3}. Trips: {4}."
		).format(
			self.settlement_type,
			self.name,
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
				"Trip Entitlement Table",
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
			update_entitlement_log_status(row.trip_entitlement_log)

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

			source_log = get_entitlement_log(source_row.parent)
			if not source_log:
				frappe.throw(_("Trip Entitlement Log {0} no longer exists.").format(source_row.parent))

			if source_log.docstatus != 1:
				frappe.throw(_("Trip Entitlement Log {0} must be submitted.").format(source_log.name))

			self.validate_item_matches_filters(row, source_row, source_log)

	def validate_item_matches_filters(self, row, source_row, source_log):
		if source_log.project != self.project:
			frappe.throw(_("Row {0}: Source project does not match this batch.").format(row.idx))

		if self.vehicle and source_log.vehicle != self.vehicle:
			frappe.throw(_("Row {0}: Source vehicle does not match this batch.").format(row.idx))

		if getdate(source_log.trip_date) < getdate(self.start_date) or getdate(source_log.trip_date) > getdate(self.end_date):
			frappe.throw(_("Row {0}: Source trip date is outside this batch period.").format(row.idx))

		if row.trip_entitlement_log != source_log.name:
			frappe.throw(_("Row {0}: Trip Entitlement Log reference is incorrect.").format(row.idx))

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
				"Trip Entitlement Table",
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
			update_entitlement_log_status(row.trip_entitlement_log)

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
				"Trip Entitlement Table",
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
			update_entitlement_log_status(row.trip_entitlement_log)


@frappe.whitelist()
def get_pending_entitlements(settlement_type, start_date, end_date, project, vehicle=None):
	if not settlement_type or not start_date or not end_date or not project:
		frappe.throw(_("Settlement Type, Start Date, End Date, and Project are required."))

	if getdate(start_date) > getdate(end_date):
		frappe.throw(_("Start Date cannot be greater than End Date."))

	conditions = [
		"log.docstatus = 1",
		"log.project = %(project)s",
		"log.trip_date BETWEEN %(start_date)s AND %(end_date)s",
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
		conditions.append("log.vehicle = %(vehicle)s")
		values["vehicle"] = vehicle

	return frappe.db.sql(
		f"""
		SELECT
			log.name AS trip_entitlement_log,
			item.name AS trip_entitlement_row,
			log.container_trip_log,
			log.trip_date,
			log.project,
			log.vehicle,
			log.driver,
			log.container_numbers,
			item.entitlement_type,
			item.item,
			item.quantity,
			item.uom,
			item.rate,
			item.amount,
			item.status AS source_status
		FROM `tabTrip Entitlement Table` item
		INNER JOIN `tabTrip Entitlement Log` log
			ON log.name = item.parent
		WHERE {' AND '.join(conditions)}
		ORDER BY log.trip_date ASC, log.name ASC, item.idx ASC
		""",
		values,
		as_dict=True,
	)


def get_entitlement_child_row(row_name):
	return frappe.db.get_value(
		"Trip Entitlement Table",
		row_name,
		[
			"name",
			"parent",
			"entitlement_type",
			"item",
			"quantity",
			"uom",
			"rate",
			"amount",
			"status",
			"trip_settlement_batch",
		],
		as_dict=True,
	)


def get_entitlement_log(log_name):
	return frappe.db.get_value(
		"Trip Entitlement Log",
		log_name,
		[
			"name",
			"docstatus",
			"container_trip_log",
			"trip_date",
			"project",
			"vehicle",
		],
		as_dict=True,
	)


def update_entitlement_log_status(log_name):
	statuses = [
		row.status
		for row in frappe.get_all(
			"Trip Entitlement Table",
			filters={"parent": log_name},
			fields=["status"],
		)
	]

	if not statuses:
		return

	if all(status == "Pending" for status in statuses):
		status = "Pending"
	elif all(status == "Processed" for status in statuses):
		status = "Processed"
	else:
		status = "Partially Processed"

	frappe.db.set_value("Trip Entitlement Log", log_name, "status", status, update_modified=False)


@frappe.whitelist()
def create_erpnext_document(source_name):
	doc = frappe.get_doc("Trip Settlement Batch", source_name)
	target_doc = doc.create_erpnext_document()

	return {
		"doctype": target_doc.doctype,
		"name": target_doc.name,
	}


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
