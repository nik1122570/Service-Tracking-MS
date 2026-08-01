import frappe
from frappe.utils import flt


def execute():
	if not frappe.db.exists("DocType", "Fuel Card Ledger Entry"):
		return

	for fuel_card in frappe.get_all("Fuel Card", pluck="name"):
		running_litres = flt(frappe.db.get_value("Fuel Card", fuel_card, "opening_litres"))
		running_value = flt(frappe.db.get_value("Fuel Card", fuel_card, "opening_value"))
		entries = frappe.get_all(
			"Fuel Card Ledger Entry",
			filters={"fuel_card": fuel_card},
			fields=["name", "litres_in", "litres_out", "rate"],
			order_by="posting_date asc, creation asc, name asc",
		)

		for entry in entries:
			amount = (flt(entry.litres_in) or flt(entry.litres_out)) * flt(entry.rate)
			running_litres += flt(entry.litres_in) - flt(entry.litres_out)
			running_value += amount if flt(entry.litres_in) else -amount
			frappe.db.set_value(
				"Fuel Card Ledger Entry",
				entry.name,
				{
					"amount": amount,
					"balance_litres_after_transaction": running_litres,
					"balance_value_after_transaction": running_value,
				},
				update_modified=False,
			)

		frappe.db.set_value(
			"Fuel Card",
			fuel_card,
			{
				"current_balance_litres": running_litres,
				"current_balance_value": running_value,
			},
			update_modified=False,
		)
