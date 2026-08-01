# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class FuelCardLedgerEntry(Document):
	def validate(self):
		self.validate_litres()
		self.set_amount()

	def before_insert(self):
		self.set_balance_after_transaction()

	def after_insert(self):
		update_fuel_card_balance(self.fuel_card)

	def on_trash(self):
		frappe.throw(_("Fuel Card Ledger Entry cannot be deleted. Create a reversing entry instead."))

	def validate_litres(self):
		if flt(self.litres_in) and flt(self.litres_out):
			frappe.throw(_("Only one of Litres In or Litres Out can be set."))

		if not flt(self.litres_in) and not flt(self.litres_out):
			frappe.throw(_("Set either Litres In or Litres Out."))

	def set_amount(self):
		litres = flt(self.litres_in) or flt(self.litres_out)
		self.amount = litres * flt(self.rate)

	def set_balance_after_transaction(self):
		current_balance = get_fuel_card_balance(self.fuel_card)
		current_value = get_fuel_card_value(self.fuel_card)
		transaction_value = flt(self.amount) if flt(self.litres_in) else -flt(self.amount)
		self.balance_litres_after_transaction = current_balance + flt(self.litres_in) - flt(self.litres_out)
		self.balance_value_after_transaction = current_value + transaction_value
		if self.balance_litres_after_transaction < 0:
			frappe.throw(
				_("Fuel Card {0} does not have enough litres. Current balance is {1}.").format(
					frappe.bold(self.fuel_card),
					frappe.bold(flt(current_balance, 2)),
				)
			)
		if self.balance_value_after_transaction < 0:
			frappe.throw(
				_(
					"Fuel Card {0} does not have enough monetary value for this fuel request. "
					"Available value is {1}, requested value is {2}. Please refill the Fuel Card."
				).format(
					frappe.bold(self.fuel_card),
					frappe.bold(flt(current_value, 2)),
					frappe.bold(flt(self.amount, 2)),
				)
			)


def create_fuel_card_ledger_entry(
	fuel_card,
	transaction_type,
	litres_in=0,
	litres_out=0,
	rate=0,
	reference_doctype=None,
	reference_name=None,
	posting_date=None,
	vehicle=None,
	driver=None,
	remarks=None,
):
	ledger_entry = frappe.get_doc(
		{
			"doctype": "Fuel Card Ledger Entry",
			"fuel_card": fuel_card,
			"posting_date": posting_date or now_datetime(),
			"transaction_type": transaction_type,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"litres_in": flt(litres_in),
			"litres_out": flt(litres_out),
			"rate": flt(rate),
			"vehicle": vehicle,
			"driver": driver,
			"remarks": remarks,
		}
	)
	ledger_entry.insert(ignore_permissions=True)
	return ledger_entry


def get_fuel_card_balance(fuel_card):
	if not fuel_card:
		return 0

	opening_litres = flt(frappe.db.get_value("Fuel Card", fuel_card, "opening_litres"))
	ledger_balance = frappe.db.sql(
		"""
		SELECT COALESCE(SUM(litres_in - litres_out), 0)
		FROM `tabFuel Card Ledger Entry`
		WHERE fuel_card = %(fuel_card)s
		""",
		{"fuel_card": fuel_card},
	)[0][0]
	return opening_litres + flt(ledger_balance)


def get_fuel_card_value(fuel_card):
	opening_value = flt(frappe.db.get_value("Fuel Card", fuel_card, "opening_value"))
	value = frappe.db.sql(
		"""
		SELECT COALESCE(SUM((litres_in - litres_out) * rate), 0)
		FROM `tabFuel Card Ledger Entry`
		WHERE fuel_card = %(fuel_card)s
		""",
		{"fuel_card": fuel_card},
	)[0][0]
	return opening_value + flt(value)


def update_fuel_card_balance(fuel_card):
	if not fuel_card:
		return

	frappe.db.set_value(
		"Fuel Card",
		fuel_card,
		{
			"current_balance_litres": get_fuel_card_balance(fuel_card),
			"current_balance_value": get_fuel_card_value(fuel_card),
			"last_transaction_date": now_datetime(),
		},
		update_modified=False,
	)
