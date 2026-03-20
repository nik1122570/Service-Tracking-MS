import frappe
from frappe.model.document import Document
from frappe.utils import flt, today

from service_app.service_tracking.doctype.maintenance_return_note.maintenance_return_note import (
    get_return_note_item_balances,
)


class UsedSparePartsIssueNote(Document):

    def validate(self):
        self.sync_from_return_note()
        self.set_default_issue_metadata()
        self.validate_issue_items()
        self.calculate_totals()
        self.status = "Draft"

    def before_submit(self):
        if flt(self.total_qty_out) <= 0:
            frappe.throw("You cannot submit a Used Spare Parts Issue Note without issued quantities.")

    def on_submit(self):
        self.db_set("status", "Submitted")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    def sync_from_return_note(self):
        if not self.maintenance_return_note:
            frappe.throw("Maintenance Return Note is required.")

        source = frappe.get_doc("Maintenance Return Note", self.maintenance_return_note)
        if source.docstatus != 1:
            frappe.throw("Only submitted Maintenance Return Notes can create a Used Spare Parts Issue Note.")

        self.eah_job_card = source.eah_job_card
        self.vehicle = source.vehicle

    def set_default_issue_metadata(self):
        if not self.posting_date:
            self.posting_date = today()

        if not self.issued_by:
            self.issued_by = frappe.session.user

        if not self.purpose:
            self.purpose = "Internal Reuse"

    def validate_issue_items(self):
        if not self.issue_items:
            frappe.throw("At least one issue row is required.")

        source_rows = {
            row.name: row
            for row in frappe.get_all(
                "Maintenance Return Note Item",
                filters={
                    "parent": self.maintenance_return_note,
                    "parenttype": "Maintenance Return Note",
                    "parentfield": "returned_parts",
                },
                fields=["name", "item", "item_name", "uom", "condition", "remarks"],
            )
        }
        balances = get_return_note_item_balances(self.maintenance_return_note, exclude_issue_note=self.name)

        for index, row in enumerate(self.issue_items, start=1):
            if not row.source_return_item:
                frappe.throw(f"Row {index}: Source return item is required.")

            source_row = source_rows.get(row.source_return_item)
            if not source_row:
                frappe.throw(
                    f"Row {index}: Source return item {row.source_return_item} does not belong to Maintenance Return Note {self.maintenance_return_note}."
                )

            row.item = source_row.item
            row.item_name = source_row.item_name
            row.uom = source_row.uom
            row.condition = source_row.condition
            if not row.remarks:
                row.remarks = source_row.remarks

            available_qty = flt(balances.get(row.source_return_item))
            row.qty_available = available_qty
            row.qty_out = flt(row.qty_out)

            if row.qty_out <= 0:
                frappe.throw(f"Row {index}: Qty Out must be greater than zero for item {row.item}.")

            if row.qty_out > available_qty:
                frappe.throw(
                    f"Row {index}: Qty Out cannot be greater than available quantity ({available_qty}) for item {row.item}."
                )

            if not row.disposition:
                row.disposition = self.purpose

    def calculate_totals(self):
        self.total_qty_out = sum(flt(row.qty_out) for row in self.issue_items)