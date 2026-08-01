import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return
	if not frappe.db.exists(
		"DocField",
		{"parent": "Trip Settings", "fieldname": "driver_mileage_per_day"},
	):
		return

	value = frappe.db.get_single_value("Trip Settings", "driver_mileage_per_day")
	if flt(value):
		return

	driver_mileage = frappe.db.get_value("Fixed Expenses", "Driver Mileage", "fixed_value")
	if flt(driver_mileage):
		frappe.db.set_single_value(
			"Trip Settings",
			"driver_mileage_per_day",
			flt(driver_mileage),
		)
