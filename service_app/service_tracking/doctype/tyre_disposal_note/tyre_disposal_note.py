import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from service_app.service_tracking.doctype.tyre_receiving_note.tyre_receiving_note import (
    get_tyre_receiving_item_balances,
)


class TyreDisposalNote(Document):

    def validate(self):
        self.sync_from_receiving_note()
        self.set_default_disposal_metadata()
        self.validate_disposal_items()
        self.calculate_totals()
        self.status = "Draft"

    def before_submit(self):
        if flt(self.total_qty_out) <= 0:
            frappe.throw("You cannot submit a Tyre Disposal Note without disposal quantities.")

    def on_submit(self):
        self.db_set("status", "Submitted")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    def sync_from_receiving_note(self):
        if not self.tyre_receiving_note:
            frappe.throw("Tyre Receiving Note is required.")

        source = frappe.get_doc("Tyre Receiving Note", self.tyre_receiving_note)
        if source.docstatus != 1:
            frappe.throw("Only submitted Tyre Receiving Notes can create a Tyre Disposal Note.")

        self.tyre_request = source.tyre_request
        self.vehicle = source.vehicle
        self.license_plate = source.license_plate

    def set_default_disposal_metadata(self):
        if not self.posting_date:
            self.posting_date = today()

        if not self.disposed_by:
            self.disposed_by = frappe.session.user

        if not self.disposal_method:
            self.disposal_method = "Destroyed"

    def validate_disposal_items(self):
        if not self.disposal_items:
            frappe.throw("At least one disposal row is required.")

        source_rows = {
            row.name: row
            for row in frappe.get_all(
                "Tyre Receiving Note Item",
                filters={
                    "parent": self.tyre_receiving_note,
                    "parenttype": "Tyre Receiving Note",
                    "parentfield": "received_tyres",
                },
                fields=[
                    "name",
                    "wheel_position",
                    "item",
                    "item_name",
                    "tyre_brand",
                    "worn_out_brand",
                    "worn_out_serial_no",
                    "uom",
                    "condition",
                    "remarks",
                ],
            )
        }
        balances = get_tyre_receiving_item_balances(self.tyre_receiving_note, exclude_disposal_note=self.name)

        for index, row in enumerate(self.disposal_items, start=1):
            if not row.source_receiving_item:
                frappe.throw(f"Row {index}: Source receiving row is required.")

            source_row = source_rows.get(row.source_receiving_item)
            if not source_row:
                frappe.throw(
                    f"Row {index}: Source receiving row {row.source_receiving_item} does not belong to Tyre Receiving Note {self.tyre_receiving_note}."
                )

            row.wheel_position = source_row.wheel_position
            row.item = source_row.item
            row.item_name = source_row.item_name
            row.tyre_brand = source_row.tyre_brand
            row.worn_out_brand = source_row.worn_out_brand
            row.worn_out_serial_no = source_row.worn_out_serial_no
            row.uom = source_row.uom
            row.condition = source_row.condition
            if not row.remarks:
                row.remarks = source_row.remarks

            available_qty = flt(balances.get(row.source_receiving_item))
            row.qty_available = available_qty
            row.qty_out = flt(row.qty_out)

            if row.qty_out <= 0:
                frappe.throw(f"Row {index}: Qty Out must be greater than zero for item {row.item}.")

            if row.qty_out > available_qty:
                frappe.throw(
                    f"Row {index}: Qty Out cannot be greater than available quantity ({available_qty}) for item {row.item}."
                )

            if not row.disposition:
                row.disposition = "Disposed"

    def calculate_totals(self):
        self.total_qty_out = sum(flt(row.qty_out) for row in self.disposal_items)
