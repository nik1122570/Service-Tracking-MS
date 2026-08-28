import frappe
from frappe.utils import flt


def execute():
	if frappe.db.table_exists("Trip Steps"):
		default_trip_step_fuel_fields()
		backfill_trip_simulation_fuel_ratios()


def default_trip_step_fuel_fields():
	columns = set(frappe.db.get_table_columns("Trip Steps"))
	if "fuel_load_status" in columns:
		frappe.db.sql(
			"""
			UPDATE `tabTrip Steps`
			SET fuel_load_status = 'Loaded'
			WHERE COALESCE(fuel_load_status, '') = ''
			"""
		)


def backfill_trip_simulation_fuel_ratios():
	trip_step_columns = set(frappe.db.get_table_columns("Trip Steps"))
	if "fuel_consumption_ratio" not in trip_step_columns:
		return
	if not frappe.db.table_exists("Trip Simulation") or not frappe.db.table_exists("Vehicle"):
		return

	trip_simulation_columns = set(frappe.db.get_table_columns("Trip Simulation"))
	vehicle_columns = set(frappe.db.get_table_columns("Vehicle"))
	if "vehicle" not in trip_simulation_columns or "truck_type" not in vehicle_columns:
		return

	settings = get_fuel_ratio_fallbacks()
	for truck_type, ratio in settings.items():
		if not flt(ratio):
			continue

		frappe.db.sql(
			"""
			UPDATE `tabTrip Steps` step
			INNER JOIN `tabTrip Simulation` sim
				ON sim.name = step.parent
			   AND step.parenttype = 'Trip Simulation'
			INNER JOIN `tabVehicle` vehicle
				ON vehicle.name = sim.vehicle
			SET step.fuel_consumption_ratio = %(ratio)s,
				step.fuel_consumption_qty = step.distance * %(ratio)s
			WHERE COALESCE(step.fuel_consumption_ratio, 0) = 0
			  AND LOWER(vehicle.truck_type) = %(truck_type)s
			""",
			{
				"ratio": flt(ratio),
				"truck_type": truck_type,
			},
		)


def get_fuel_ratio_fallbacks():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return {}

	return {
		"heavy truck": frappe.db.get_single_value("Trip Settings", "heavy_truck_litres_per_km"),
		"light truck": frappe.db.get_single_value("Trip Settings", "light_truck_litres_per_km"),
	}
