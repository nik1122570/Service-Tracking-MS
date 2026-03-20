import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class MaintenanceReturnNote(Document):

    def validate(self):
        self.sync_from_job_card()
        self.ensure_single_active_return_note()
        self.set_default_receipt_metadata()
        self.validate_returned_parts()
        self.calculate_totals()
        self.status = self.get_receipt_status()

    def before_submit(self):
        if flt(self.total_received_qty) <= 0:
            frappe.throw("You cannot submit a Maintenance Return Note without received quantities.")

    def on_cancel(self):
        self.status = "Cancelled"

    def sync_from_job_card(self):
        if not self.eah_job_card:
            return

        job_card = frappe.get_doc("EAH Job Card", self.eah_job_card)
        self.vehicle = job_card.vehicle
        self.service_date = job_card.service_date
        self.supplier = job_card.supplier

    def ensure_single_active_return_note(self):
        if not self.eah_job_card:
            return

        existing_filters = {
            "eah_job_card": self.eah_job_card,
            "docstatus": ["<", 2],
        }
        if self.name:
            existing_filters["name"] = ["!=", self.name]

        existing_note = frappe.db.get_value(
            "Maintenance Return Note",
            existing_filters,
            "name",
        )
        if existing_note:
            frappe.throw(
                f"Maintenance Return Note {existing_note} already exists for EAH Job Card {self.eah_job_card}."
            )

    def set_default_receipt_metadata(self):
        if not self.received_date:
            self.received_date = today()

        if not self.received_by:
            self.received_by = frappe.session.user

    def validate_returned_parts(self):
        if not self.returned_parts:
            frappe.throw("At least one returned part is required.")

        for index, row in enumerate(self.returned_parts, start=1):
            if not row.item:
                frappe.throw(f"Row {index}: Item is required.")

            row.qty_expected = flt(row.qty_expected)
            if row.qty_expected <= 0:
                frappe.throw(f"Row {index}: Qty Expected must be greater than zero.")

            if row.qty_received in (None, ""):
                row.qty_received = row.qty_expected

            row.qty_received = flt(row.qty_received)
            if row.qty_received < 0:
                frappe.throw(f"Row {index}: Qty Received cannot be negative.")

            if row.qty_received > row.qty_expected:
                frappe.throw(
                    f"Row {index}: Qty Received cannot be greater than Qty Expected for item {row.item}."
                )

            if not row.uom:
                row.uom = frappe.db.get_value("Item", row.item, "stock_uom")

            if row.qty_received > 0:
                if not row.condition:
                    row.condition = "Repairable"
                if not row.disposition:
                    row.disposition = "Stored"
            elif not row.condition:
                row.condition = "Missing"

    def calculate_totals(self):
        self.total_expected_qty = sum(flt(row.qty_expected) for row in self.returned_parts)
        self.total_received_qty = sum(flt(row.qty_received) for row in self.returned_parts)

    def get_receipt_status(self):
        total_expected_qty = flt(self.total_expected_qty)
        total_received_qty = flt(self.total_received_qty)

        if self.docstatus == 2:
            return "Cancelled"

        if total_received_qty <= 0:
            return "Draft"

        if total_received_qty < total_expected_qty:
            return "Partially Received"

        return "Fully Received"


@frappe.whitelist()
def make_used_spare_parts_issue_note(source_name, target_doc=None):
    source = frappe.get_doc("Maintenance Return Note", source_name)

    if source.docstatus != 1:
        frappe.throw("Only submitted Maintenance Return Notes can create a Used Spare Parts Issue Note.")

    balances = get_return_note_item_balances(source.name)
    target = frappe.new_doc("Used Spare Parts Issue Note")
    target.maintenance_return_note = source.name
    target.eah_job_card = source.eah_job_card
    target.vehicle = source.vehicle
    target.issued_by = frappe.session.user
    target.remarks = source.remarks

    has_rows = False
    for row in source.returned_parts:
        qty_available = flt(balances.get(row.name))
        if qty_available <= 0:
            continue

        has_rows = True
        target.append(
            "issue_items",
            {
                "source_return_item": row.name,
                "item": row.item,
                "item_name": row.item_name,
                "qty_available": qty_available,
                "qty_out": qty_available,
                "uom": row.uom,
                "condition": row.condition,
                "disposition": "Internal Reuse",
                "remarks": row.remarks,
            },
        )

    if not has_rows:
        frappe.throw(
            f"Maintenance Return Note {source.name} has no remaining quantities available for issue."
        )

    return target


def get_return_note_item_balances(maintenance_return_note, exclude_issue_note=None):
    received_rows = frappe.get_all(
        "Maintenance Return Note Item",
        filters={
            "parent": maintenance_return_note,
            "parenttype": "Maintenance Return Note",
            "parentfield": "returned_parts",
        },
        fields=["name", "qty_received"],
    )

    issued_filters = {
        "maintenance_return_note": maintenance_return_note,
        "docstatus": 1,
    }
    if exclude_issue_note:
        issued_filters["name"] = ["!=", exclude_issue_note]

    issued_rows = frappe.db.sql(
        """
        SELECT
            issue_item.source_return_item,
            COALESCE(SUM(issue_item.qty_out), 0) AS qty_issued
        FROM `tabUsed Spare Parts Issue Note Item` issue_item
        INNER JOIN `tabUsed Spare Parts Issue Note` issue_note
            ON issue_note.name = issue_item.parent
        WHERE issue_note.maintenance_return_note = %(maintenance_return_note)s
          AND issue_note.docstatus = 1
          {exclude_condition}
        GROUP BY issue_item.source_return_item
        """.format(
            exclude_condition="AND issue_note.name != %(exclude_issue_note)s" if exclude_issue_note else ""
        ),
        {
            "maintenance_return_note": maintenance_return_note,
            "exclude_issue_note": exclude_issue_note,
        },
        as_dict=True,
    )

    issued_map = {row.source_return_item: flt(row.qty_issued) for row in issued_rows}
    balances = {}

    for row in received_rows:
        balances[row.name] = max(flt(row.qty_received) - flt(issued_map.get(row.name)), 0)

    return balances
