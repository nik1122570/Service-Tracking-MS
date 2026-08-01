# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from service_app.service_tracking.doctype.fuel_card_ledger_entry.fuel_card_ledger_entry import (
	create_fuel_card_ledger_entry,
)


class FuelCardRecharge(Document):
	def validate(self):
		if flt(self.litres) <= 0:
			frappe.throw(_("Litres must be greater than zero."))

		self.amount = flt(self.litres) * flt(self.rate)

	def on_submit(self):
		ledger_entry = create_fuel_card_ledger_entry(
			fuel_card=self.fuel_card,
			transaction_type="Recharge",
			litres_in=self.litres,
			rate=self.rate,
			reference_doctype=self.doctype,
			reference_name=self.name,
			posting_date=self.posting_date,
			remarks=self.remarks,
		)
		self.db_set("ledger_entry", ledger_entry.name, update_modified=False)

	def on_cancel(self):
		create_fuel_card_ledger_entry(
			fuel_card=self.fuel_card,
			transaction_type="Cancellation",
			litres_out=self.litres,
			rate=self.rate,
			reference_doctype=self.doctype,
			reference_name=self.name,
			posting_date=self.posting_date,
			remarks=_("Cancellation of Fuel Card Recharge {0}").format(self.name),
		)
