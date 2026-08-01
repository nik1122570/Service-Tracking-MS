# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class FuelCard(Document):
	def validate(self):
		ledger = frappe.db.sql(
			"""
			SELECT
				COALESCE(SUM(litres_in - litres_out), 0) AS balance_litres,
				COALESCE(SUM((litres_in - litres_out) * rate), 0) AS balance_value
			FROM `tabFuel Card Ledger Entry`
			WHERE fuel_card = %(fuel_card)s
			""",
			{"fuel_card": self.name},
			as_dict=True,
		)[0]

		self.current_balance_litres = flt(self.opening_litres) + flt(ledger.balance_litres)
		self.current_balance_value = flt(self.opening_value) + flt(ledger.balance_value)


@frappe.whitelist()
def quick_recharge(
	fuel_card,
	posting_date,
	litres,
	rate,
	amount=None,
	purchase_order=None,
	purchase_invoice=None,
	remarks=None,
):
	if not fuel_card:
		frappe.throw(_("Fuel Card is required."))

	card = frappe.get_doc("Fuel Card", fuel_card)
	doc = frappe.get_doc(
		{
			"doctype": "Fuel Card Recharge",
			"posting_date": posting_date,
			"fuel_card": fuel_card,
			"supplier": card.supplier,
			"fuel_item": card.fuel_item,
			"purchase_order": purchase_order,
			"purchase_invoice": purchase_invoice,
			"litres": flt(litres),
			"rate": flt(rate),
			"remarks": remarks,
		}
	)
	doc.insert()
	doc.submit()
	return {
		"name": doc.name,
		"doctype": doc.doctype,
	}


@frappe.whitelist()
def quick_issue(
	fuel_card,
	posting_date,
	issue_type,
	litres,
	rate,
	amount=None,
	vehicle=None,
	driver=None,
	employee=None,
	purpose=None,
	remarks=None,
):
	if not fuel_card:
		frappe.throw(_("Fuel Card is required."))

	doc = frappe.get_doc(
		{
			"doctype": "Fuel Card Issue",
			"posting_date": posting_date,
			"fuel_card": fuel_card,
			"issue_type": issue_type,
			"vehicle": vehicle,
			"driver": driver,
			"employee": employee,
			"purpose": purpose,
			"litres": flt(litres),
			"rate": flt(rate),
			"remarks": remarks,
		}
	)
	doc.insert()
	doc.submit()
	return {
		"name": doc.name,
		"doctype": doc.doctype,
	}
