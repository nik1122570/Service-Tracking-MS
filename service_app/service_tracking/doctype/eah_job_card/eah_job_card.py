import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc


class EAHJobCard(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		# Helpers to ensure numeric calculations (fields may be passed as strings)
		def _num(value):
			try:
				return float(value) if value not in (None, "") else 0.0
			except Exception:
				return 0.0

		# Total quantity of supplied parts (custom field)
		custom_total_qty = sum([_num(row.qty) for row in (self.get("supplied_parts") or [])])

		# Calculate spares cost from Supplied Parts
		spares_cost = sum([
			_num(row.rate) * _num(row.qty)
			for row in (self.get("supplied_parts") or [])
		])

		# Calculate service charges from Service Task Templates (rate field)
		service_charges = sum([_num(row.rate) for row in (self.get("service_task_templates") or [])])

		# Set fields
		self.custom_total_qty = custom_total_qty
		self.spares_cost = spares_cost
		self.service_charges = service_charges
		self.total_vat_exclusive = spares_cost + service_charges


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):

	def set_missing_values(source, target):
		target.supplier = source.supplier
		target.custom_job_card_link = source.name  # Link PO → Job Card

	doc = get_mapped_doc(
		"EAH Job Card",
		source_name,
		{
			"EAH Job Card": {
				"doctype": "Purchase Order"
			},
			"Supplied Parts": {
				"doctype": "Purchase Order Item",
				"field_map": {
					"item": "item_code",
					"item_name": "item_name",
					"qty": "qty",
					"rate": "rate"
				}
			},
		},
		target_doc,
		set_missing_values
	)

	return doc


@frappe.whitelist()
def make_material_request(source_name, target_doc=None):
	doc = get_mapped_doc(
		"EAH Job Card",
		source_name,
		{
			"EAH Job Card": {
				"doctype": "Material Request",
				"field_map": {
					"name": "eah_job_card"
				}
			},
			"Supplied Parts": {
				"doctype": "Material Request Item",
				"field_map": {
					"item": "item_code",
					"item_name": "item_name",
					"qty": "qty"
				},
			},
		},
		target_doc
	)

	doc.material_request_type = "Purchase"

	return doc


@frappe.whitelist()
def get_vehicle_maintenance_history(vehicle):
	if not vehicle:
		return []

	# Fetch recent Job Cards for this vehicle
	job_cards = frappe.get_all(
		"EAH Job Card",
		filters={"vehicle": vehicle},
		fields=["name", "service_date", "supplier", "driver_name"],
		order_by="service_date desc"
	)

	# Include the selected service templates for each job card
	for jc in job_cards:
		templates = frappe.get_all(
			"Job Card Template",
			filters={
				"parent": jc.name,
				"parentfield": "service_task_templates"
			},
			pluck="service_template"
		)
		jc["service_templates"] = templates

	return job_cards

