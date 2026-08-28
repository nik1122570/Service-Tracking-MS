import frappe
from frappe.utils import flt


FUEL_SETTING_PAIRS = (
	("heavy_truck_litres_per_km", "heavy_truck_loaded_litres_per_km"),
	("heavy_truck_litres_per_km", "heavy_truck_empty_litres_per_km"),
	("light_truck_litres_per_km", "light_truck_loaded_litres_per_km"),
	("light_truck_litres_per_km", "light_truck_empty_litres_per_km"),
)


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return

	existing_trip_setting_fields = {
		row.fieldname
		for row in frappe.get_all(
			"DocField",
			filters={"parent": "Trip Settings"},
			fields=["fieldname"],
		)
	}
	for source_field, target_field in FUEL_SETTING_PAIRS:
		if source_field not in existing_trip_setting_fields or target_field not in existing_trip_setting_fields:
			continue

		target_value = frappe.db.get_single_value("Trip Settings", target_field)
		if flt(target_value):
			continue

		source_value = frappe.db.get_single_value("Trip Settings", source_field)
		if flt(source_value):
			frappe.db.set_single_value("Trip Settings", target_field, flt(source_value))

	if frappe.db.table_exists("Trip Steps"):
		columns = set(frappe.db.get_table_columns("Trip Steps"))
		if "fuel_load_status" in columns:
			frappe.db.sql(
				"""
				UPDATE `tabTrip Steps`
				SET fuel_load_status = 'Loaded'
				WHERE COALESCE(fuel_load_status, '') = ''
				"""
			)
