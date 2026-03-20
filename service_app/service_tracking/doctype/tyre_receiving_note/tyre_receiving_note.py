import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class TyreReceivingNote(Document):

    def validate(self):
        self.sync_from_request()
        self.ensure_single_active_receiving_note()
        self.set_default_receipt_metadata()
        self.validate_received_tyres()
        self.calculate_totals()
        self.status = self.get_receipt_status()

    def before_submit(self):
        if flt(self.total_received_qty) <= 0:
            frappe.throw("You cannot submit a Tyre Receiving Note without received quantities.")

    def on_cancel(self):
        self.status = "Cancelled"

    def sync_from_request(self):
        if not self.tyre_request:
            return

        source = frappe.get_doc("Tyre Request", self.tyre_request)
        self.vehicle = source.vehicle
        self.license_plate = source.license_plate
        self.request_date = source.request_date
        self.supplier = source.supplier

    def ensure_single_active_receiving_note(self):
        if not self.tyre_request:
            return

        existing_filters = {
            "tyre_request": self.tyre_request,
            "docstatus": ["<", 2],
        }
        if self.name:
            existing_filters["name"] = ["!=", self.name]

        existing_note = frappe.db.get_value(
            "Tyre Receiving Note",
            existing_filters,
            "name",
        )
        if existing_note:
            frappe.throw(
                f"Tyre Receiving Note {existing_note} already exists for Tyre Request {self.tyre_request}."
            )

    def set_default_receipt_metadata(self):
        if not self.received_date:
            self.received_date = today()

        if not self.received_by:
            self.received_by = frappe.session.user

    def validate_received_tyres(self):
        if not self.received_tyres:
            frappe.throw("At least one received tyre row is required.")

        source_rows = {
            row.name: row
            for row in frappe.get_all(
                "Tyre Request Item",
                filters={
                    "parent": self.tyre_request,
                    "parenttype": "Tyre Request",
                    "parentfield": "tyre_items",
                },
                fields=[
                    "name",
                    "wheel_position",
                    "item",
                    "item_name",
                    "tyre_brand",
                    "worn_out_brand",
                    "worn_out_serial_no",
                    "qty",
                    "uom",
                    "remarks",
                ],
            )
        }

        for index, row in enumerate(self.received_tyres, start=1):
            if not row.source_request_item:
                frappe.throw(f"Row {index}: Source request row is required.")

            source_row = source_rows.get(row.source_request_item)
            if not source_row:
                frappe.throw(
                    f"Row {index}: Source request row {row.source_request_item} does not belong to Tyre Request {self.tyre_request}."
                )

            row.wheel_position = source_row.wheel_position
            row.item = source_row.item
            row.item_name = source_row.item_name
            row.tyre_brand = source_row.tyre_brand
            row.worn_out_brand = source_row.worn_out_brand
            row.worn_out_serial_no = source_row.worn_out_serial_no
            row.qty_expected = flt(source_row.qty)
            row.uom = source_row.uom
            if not row.remarks:
                row.remarks = source_row.remarks

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

            if row.qty_received > 0:
                if not row.condition:
                    row.condition = "Scrap"
                if not row.disposition:
                    row.disposition = "Held in Scrap Store"
            elif not row.condition:
                row.condition = "Missing"

    def calculate_totals(self):
        self.total_expected_qty = sum(flt(row.qty_expected) for row in self.received_tyres)
        self.total_received_qty = sum(flt(row.qty_received) for row in self.received_tyres)

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
def make_tyre_disposal_note(source_name, target_doc=None):
    source = frappe.get_doc("Tyre Receiving Note", source_name)
    if source.docstatus != 1:
        frappe.throw("Only submitted Tyre Receiving Notes can create a Tyre Disposal Note.")

    balances = get_tyre_receiving_item_balances(source.name)
    target = frappe.new_doc("Tyre Disposal Note")
    target.tyre_receiving_note = source.name
    target.tyre_request = source.tyre_request
    target.vehicle = source.vehicle
    target.license_plate = source.license_plate
    target.disposed_by = frappe.session.user
    target.remarks = source.remarks

    has_rows = False
    for row in source.received_tyres:
        qty_available = flt(balances.get(row.name))
        if qty_available <= 0:
            continue

        has_rows = True
        target.append(
            "disposal_items",
            {
                "source_receiving_item": row.name,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "tyre_brand": row.tyre_brand,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty_available": qty_available,
                "qty_out": qty_available,
                "uom": row.uom,
                "condition": row.condition,
                "disposition": "Disposed",
                "remarks": row.remarks,
            },
        )

    if not has_rows:
        frappe.throw(
            f"Tyre Receiving Note {source.name} has no remaining quantities available for disposal."
        )

    return target


def get_tyre_receiving_item_balances(tyre_receiving_note, exclude_disposal_note=None):
    received_rows = frappe.get_all(
        "Tyre Receiving Note Item",
        filters={
            "parent": tyre_receiving_note,
            "parenttype": "Tyre Receiving Note",
            "parentfield": "received_tyres",
        },
        fields=["name", "qty_received"],
    )

    issued_rows = frappe.db.sql(
        """
        SELECT
            disposal_item.source_receiving_item,
            COALESCE(SUM(disposal_item.qty_out), 0) AS qty_out
        FROM `tabTyre Disposal Note Item` disposal_item
        INNER JOIN `tabTyre Disposal Note` disposal_note
            ON disposal_note.name = disposal_item.parent
        WHERE disposal_note.tyre_receiving_note = %(tyre_receiving_note)s
          AND disposal_note.docstatus = 1
          {exclude_condition}
        GROUP BY disposal_item.source_receiving_item
        """.format(
            exclude_condition="AND disposal_note.name != %(exclude_disposal_note)s"
            if exclude_disposal_note
            else ""
        ),
        {
            "tyre_receiving_note": tyre_receiving_note,
            "exclude_disposal_note": exclude_disposal_note,
        },
        as_dict=True,
    )

    issued_map = {row.source_receiving_item: flt(row.qty_out) for row in issued_rows}
    balances = {}

    for row in received_rows:
        balances[row.name] = max(flt(row.qty_received) - flt(issued_map.get(row.name)), 0)

    return balances
