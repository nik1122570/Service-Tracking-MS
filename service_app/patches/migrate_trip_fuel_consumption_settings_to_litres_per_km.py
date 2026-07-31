import frappe


def execute():
	if not frappe.db.exists("DocType", "Trip Settings"):
		return

	field_renames = {
		"heavy_truck_km_per_litre": "heavy_truck_litres_per_km",
		"light_truck_km_per_litre": "light_truck_litres_per_km",
	}

	for old_fieldname, new_fieldname in field_renames.items():
		old_value = get_single_raw_value(old_fieldname)
		new_value = frappe.db.get_single_value("Trip Settings", new_fieldname)
		if old_value not in (None, "") and new_value in (None, ""):
			frappe.db.set_single_value("Trip Settings", new_fieldname, old_value)

		delete_single_raw_value(old_fieldname)


def get_single_raw_value(fieldname):
	value = frappe.db.sql(
		"""
		SELECT value
		FROM `tabSingles`
		WHERE doctype = 'Trip Settings'
		  AND field = %(fieldname)s
		LIMIT 1
		""",
		{"fieldname": fieldname},
	)
	return value[0][0] if value else None


def delete_single_raw_value(fieldname):
	frappe.db.sql(
		"""
		DELETE FROM `tabSingles`
		WHERE doctype = 'Trip Settings'
		  AND field = %(fieldname)s
		""",
		{"fieldname": fieldname},
	)
