import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr, flt, getdate, today

from service_app.service_tracking.doctype.eah_job_card.eah_job_card import get_item_price_rate


TYRE_ITEM_GROUP = "Tyres"
REQUEST_TYPE_TYRE_MAINTENANCE = "Tyre Maintenance"


class TyreRequest(Document):

    def validate(self):
        self.ensure_request_fields()
        self.sync_vehicle_data()
        self.ensure_request_items()
        self.validate_outstanding_receipt_control()
        self.calculate_totals()

    def ensure_request_fields(self):
        required_fields = (
            ("vehicle", "Vehicle"),
            ("request_date", "Request Date"),
            ("supplier", "Supplier"),
            ("price_list", "Price List"),
            ("project", "Project"),
            ("cost_center", "Cost Center"),
            ("odometer_reading", "Odometer Reading"),
        )

        for fieldname, label in required_fields:
            if not self.meta.get_field(fieldname):
                continue
            if not getattr(self, fieldname, None):
                frappe.throw(f"{label} is required.")

    def sync_vehicle_data(self):
        if self.vehicle:
            self.license_plate = frappe.db.get_value("Vehicle", self.vehicle, "license_plate")

    def ensure_request_items(self):
        if self.is_tyre_maintenance_request():
            self.ensure_tyre_maintenance_items()
            return

        self.ensure_tyre_items()

    def ensure_tyre_items(self):
        if not self.tyre_items:
            frappe.throw("At least one tyre row is required.")

        for index, row in enumerate(self.tyre_items, start=1):
            if not row.item:
                frappe.throw(f"Row {index}: Item is required.")

            if not item_belongs_to_group(row.item, TYRE_ITEM_GROUP):
                frappe.throw(
                    f"Row {index}: Item {row.item} must belong to Item Group {TYRE_ITEM_GROUP}."
                )

            row.qty = flt(row.qty)
            if row.qty <= 0:
                frappe.throw(f"Row {index}: Qty must be greater than zero.")

            if not row.wheel_position:
                frappe.throw(f"Row {index}: Wheel Position is required.")

            if not row.worn_out_serial_no:
                frappe.throw(f"Row {index}: Worn Out Serial Number is required.")

            if not row.worn_out_brand:
                frappe.throw(f"Row {index}: Worn Out Brand is required.")

            row.price_list = self.price_list

            item_details = frappe.db.get_value(
                "Item",
                row.item,
                ["item_name", "stock_uom", "brand"],
                as_dict=True,
            )
            if not item_details:
                frappe.throw(f"Row {index}: Item {row.item} was not found.")

            row.item_name = item_details.item_name
            row.uom = row.uom or item_details.stock_uom
            row.tyre_brand = row.tyre_brand or item_details.brand

            approved_rate = get_item_price_rate(row.item, self.price_list, self.supplier)
            if approved_rate is None:
                frappe.throw(
                    f"Row {index}: Approved Item Price is required for item {row.item} in Price List {self.price_list}."
                )

            if not flt(row.rate):
                row.rate = approved_rate

            if flt(row.rate) > flt(approved_rate):
                frappe.throw(
                    f"Row {index}: Rate for {row.item_name or row.item} cannot be greater than the approved Item Price "
                    f"of {approved_rate} in {self.price_list}."
                )

    def ensure_tyre_maintenance_items(self):
        if not self.tyre_maintenance:
            frappe.throw("At least one Tyre Maintenance row is required.")

        if not self.tyre_maintenance_item:
            frappe.throw("Tyre Maintenance Item is required for Tyre Maintenance requests.")

        for index, row in enumerate(self.tyre_maintenance, start=1):
            if not row.tyre_position:
                frappe.throw(f"Row {index}: Tyre Position is required.")

            if not row.select_fpse:
                frappe.throw(f"Row {index}: Operation is required.")

            row.rate = flt(row.rate)
            if row.rate <= 0:
                frappe.throw(f"Row {index}: Rate must be greater than zero.")

    def validate_outstanding_receipt_control(self):
        if self.is_tyre_maintenance_request():
            return

        outstanding_request = get_outstanding_tyre_request_for_vehicle(
            self.vehicle,
            self.request_date,
            exclude_name=self.name,
        )
        if not outstanding_request:
            return

        if outstanding_request.receiving_note:
            receipt_message = (
                f"Tyre Receiving Note {outstanding_request.receiving_note} exists with status "
                f"{outstanding_request.receiving_status}."
            )
        else:
            receipt_message = "No Tyre Receiving Note has been created yet."

        vehicle_label = self.license_plate or self.vehicle
        frappe.throw(
            "Tyre Request blocked for vehicle "
            f"{vehicle_label}. Tyre Request {outstanding_request.name} dated "
            f"{outstanding_request.request_date} has outstanding worn-out tyres pending receipt. "
            f"{receipt_message} Complete the tyre receipt before creating a new request."
        )

    def calculate_totals(self):
        if self.is_tyre_maintenance_request():
            self.total_qty = len(self.tyre_maintenance or [])
            self.total_purchase_amount = sum(flt(row.rate) for row in self.tyre_maintenance)
            return

        self.total_qty = sum(flt(row.qty) for row in self.tyre_items)
        self.total_purchase_amount = sum(flt(row.qty) * flt(row.rate) for row in self.tyre_items)

    def is_tyre_maintenance_request(self):
        return cstr(getattr(self, "request_type", "")).strip() == REQUEST_TYPE_TYRE_MAINTENANCE


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):
    source = frappe.get_doc("Tyre Request", source_name)
    if source.docstatus != 1:
        frappe.throw("Only submitted Tyre Requests can create a Purchase Order.")

    existing_purchase_order = frappe.db.get_value(
        "Purchase Order",
        {
            "custom_tyre_request_link": source.name,
            "docstatus": ["<", 2],
        },
        "name",
    )
    if existing_purchase_order:
        frappe.throw(
            f"Purchase Order {existing_purchase_order} already exists for Tyre Request {source.name}."
        )

    if source.is_tyre_maintenance_request():
        return make_tyre_maintenance_purchase_order(source, target_doc)

    def set_missing_values(source_doc, target_doc):
        target_doc.supplier = source_doc.supplier
        target_doc.transaction_date = source_doc.request_date or today()
        target_doc.project = source_doc.project
        target_doc.cost_center = source_doc.cost_center
        target_doc.custom_tyre_request_link = source_doc.name

        source_rows = [row for row in source_doc.tyre_items if row.item]
        for source_row, target_row in zip(source_rows, target_doc.items):
            target_row.description = build_tyre_purchase_description(source_row)
            target_row.project = source_doc.project
            target_row.cost_center = source_doc.cost_center
            target_row.schedule_date = source_doc.request_date or today()

    return get_mapped_doc(
        "Tyre Request",
        source_name,
        {
            "Tyre Request": {
                "doctype": "Purchase Order",
            },
            "Tyre Request Item": {
                "doctype": "Purchase Order Item",
                "field_map": {
                    "item": "item_code",
                    "item_name": "item_name",
                    "qty": "qty",
                    "uom": "uom",
                    "rate": "rate",
                },
            },
        },
        target_doc,
        set_missing_values,
    )


def make_tyre_maintenance_purchase_order(source, target_doc=None):
    if not source.tyre_maintenance_item:
        frappe.throw(
            "Set Tyre Maintenance Item before creating a Purchase Order for Tyre Maintenance."
        )

    total_amount = flt(source.total_purchase_amount)
    if total_amount <= 0:
        frappe.throw("Total Purchase Amount must be greater than zero.")

    target = target_doc or frappe.new_doc("Purchase Order")
    target.supplier = source.supplier
    target.transaction_date = source.request_date or today()
    target.project = source.project
    target.cost_center = source.cost_center
    target.custom_tyre_request_link = source.name

    item_details = frappe.db.get_value(
        "Item",
        source.tyre_maintenance_item,
        ["item_name", "stock_uom"],
        as_dict=True,
    )
    if not item_details:
        frappe.throw(f"Tyre Maintenance Item {source.tyre_maintenance_item} was not found.")

    target.append(
        "items",
        {
            "item_code": source.tyre_maintenance_item,
            "item_name": item_details.item_name,
            "qty": 1,
            "uom": item_details.stock_uom,
            "rate": total_amount,
            "description": build_tyre_maintenance_purchase_description(source),
            "project": source.project,
            "cost_center": source.cost_center,
            "schedule_date": source.request_date or today(),
        },
    )

    return target


@frappe.whitelist()
def make_tyre_receiving_note(source_name, target_doc=None):
    source = frappe.get_doc("Tyre Request", source_name)
    if source.docstatus != 1:
        frappe.throw("Only submitted Tyre Requests can create a Tyre Receiving Note.")

    if source.is_tyre_maintenance_request():
        frappe.throw(
            "Tyre Receiving Note is only applicable for New Tyre Purchase requests."
        )

    existing_receiving_note = frappe.db.get_value(
        "Tyre Receiving Note",
        {
            "tyre_request": source.name,
            "docstatus": ["<", 2],
        },
        "name",
    )
    if existing_receiving_note:
        frappe.throw(
            f"Tyre Receiving Note {existing_receiving_note} already exists for Tyre Request {source.name}."
        )

    target = frappe.new_doc("Tyre Receiving Note")
    target.tyre_request = source.name
    target.vehicle = source.vehicle
    target.license_plate = source.license_plate
    target.request_date = source.request_date
    target.supplier = source.supplier
    target.received_by = frappe.session.user

    has_rows = False
    for row in source.tyre_items:
        qty_expected = flt(row.qty)
        if not row.item or qty_expected <= 0:
            continue

        has_rows = True
        target.append(
            "received_tyres",
            {
                "source_request_item": row.name,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "tyre_brand": row.tyre_brand,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty_expected": qty_expected,
                "qty_received": qty_expected,
                "uom": row.uom,
                "condition": "Scrap",
                "disposition": "Held in Scrap Store",
                "remarks": row.remarks,
            },
        )

    if not has_rows:
        frappe.throw(
            f"Tyre Request {source.name} has no tyre rows available to receive."
        )

    return target


def get_outstanding_tyre_request_for_vehicle(vehicle, reference_date, exclude_name=None):
    if not vehicle or not reference_date:
        return None

    filters = {
        "vehicle": vehicle,
        "docstatus": 1,
        "request_date": ["<=", getdate(reference_date)],
    }
    if exclude_name:
        filters["name"] = ["!=", exclude_name]

    requests = frappe.get_all(
        "Tyre Request",
        filters=filters,
        fields=["name", "request_date", "license_plate"],
        order_by="request_date desc, creation desc",
    )

    for request in requests:
        receiving_note = frappe.db.get_value(
            "Tyre Receiving Note",
            {
                "tyre_request": request.name,
                "docstatus": ["<", 2],
            },
            ["name", "status", "docstatus"],
            as_dict=True,
        )

        if not receiving_note:
            request.receiving_note = None
            request.receiving_status = "Not Created"
            return request

        if receiving_note.docstatus != 1 or receiving_note.status != "Fully Received":
            request.receiving_note = receiving_note.name
            request.receiving_status = receiving_note.status
            return request

    return None


def item_belongs_to_group(item_code, parent_group):
    item_group = frappe.db.get_value("Item", item_code, "item_group")
    if not item_group:
        return False

    if item_group == parent_group:
        return True

    parent_bounds = frappe.db.get_value("Item Group", parent_group, ["lft", "rgt"], as_dict=True)
    item_bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
    if not parent_bounds or not item_bounds:
        return False

    return (
        parent_bounds.lft <= item_bounds.lft
        and parent_bounds.rgt >= item_bounds.rgt
    )


def build_tyre_purchase_description(row):
    details = []
    if row.wheel_position:
        details.append(f"Wheel Position: {row.wheel_position}")
    if row.tyre_brand:
        details.append(f"Tyre Brand: {row.tyre_brand}")
    if row.worn_out_brand:
        details.append(f"Worn Out Brand: {row.worn_out_brand}")
    if row.worn_out_serial_no:
        details.append(f"Worn Out Serial No: {row.worn_out_serial_no}")
    if row.remarks:
        details.append(f"Remarks: {row.remarks}")

    return "\n".join(details)


def build_tyre_maintenance_purchase_description(tyre_request):
    details = ["Tyre Maintenance Charges"]
    for index, row in enumerate(tyre_request.tyre_maintenance or [], start=1):
        line_parts = []
        if row.tyre_position:
            line_parts.append(f"Position: {row.tyre_position}")
        if row.select_fpse:
            line_parts.append(f"Operation: {row.select_fpse}")
        if row.tyre_brand:
            line_parts.append(f"Brand: {row.tyre_brand}")
        if flt(row.rate):
            line_parts.append(f"Rate: {flt(row.rate):g}")

        line_text = " | ".join(line_parts) if line_parts else "Tyre maintenance operation"
        details.append(f"{index}. {line_text}")

    return "\n".join(details)


def _normalize_tyre_purchase_order_integrity_row(
    item_code,
    qty,
    rate,
    uom=None,
    description=None,
    project=None,
    cost_center=None,
    schedule_date=None,
):
    return (
        (item_code or "").strip(),
        flt(qty, 6),
        flt(rate, 6),
        (uom or "").strip(),
        " ".join((description or "").split()),
        (project or "").strip(),
        (cost_center or "").strip(),
        str(schedule_date or ""),
    )


def get_expected_tyre_request_purchase_order_rows(tyre_request):
    if tyre_request.is_tyre_maintenance_request():
        maintenance_item_code = cstr(getattr(tyre_request, "tyre_maintenance_item", "")).strip()
        if not maintenance_item_code:
            return []

        maintenance_item = frappe.db.get_value(
            "Item",
            maintenance_item_code,
            ["name", "stock_uom"],
            as_dict=True,
        )
        if not maintenance_item:
            return []

        return [
            _normalize_tyre_purchase_order_integrity_row(
                maintenance_item.name,
                1,
                tyre_request.total_purchase_amount,
                maintenance_item.stock_uom,
                build_tyre_maintenance_purchase_description(tyre_request),
                tyre_request.project,
                tyre_request.cost_center,
                tyre_request.request_date,
            )
        ]

    return sorted(
        _normalize_tyre_purchase_order_integrity_row(
            row.item,
            row.qty,
            row.rate,
            row.uom,
            build_tyre_purchase_description(row),
            tyre_request.project,
            tyre_request.cost_center,
            tyre_request.request_date,
        )
        for row in tyre_request.tyre_items
        if row.item
    )


def _get_tyre_request_purchase_order_integrity_rows(doc):
    return sorted(
        _normalize_tyre_purchase_order_integrity_row(
            row.item_code,
            row.qty,
            row.rate,
            row.uom,
            row.description,
            row.project,
            row.cost_center,
            row.schedule_date,
        )
        for row in doc.items
        if row.item_code
    )


def _format_tyre_request_purchase_order_integrity_rows(rows):
    return "<br>".join(
        f"{item_code} | Qty: {qty:g} | Rate: {rate:g} | UOM: {uom or 'N/A'} | Project: {project or 'N/A'} | Cost Center: {cost_center or 'N/A'}"
        for item_code, qty, rate, uom, _description, project, cost_center, _schedule_date in rows
    ) or "None"


def validate_purchase_order_tyre_request_integrity(doc, method=None):
    tyre_request_name = getattr(doc, "custom_tyre_request_link", None)
    if not tyre_request_name:
        return

    tyre_request = frappe.get_doc("Tyre Request", tyre_request_name)
    expected_rows = get_expected_tyre_request_purchase_order_rows(tyre_request)
    current_rows = _get_tyre_request_purchase_order_integrity_rows(doc)

    expected_parent_values = (
        (tyre_request.supplier or "").strip(),
        (tyre_request.project or "").strip(),
        (tyre_request.cost_center or "").strip(),
    )
    current_parent_values = (
        (doc.supplier or "").strip(),
        (doc.project or "").strip(),
        (doc.cost_center or "").strip(),
    )

    if expected_rows == current_rows and expected_parent_values == current_parent_values:
        return

    frappe.throw(
        "This Purchase Order was generated from "
        f"<b>Tyre Request {tyre_request.name}</b>. "
        "Mapped item rows and parent supplier, project, and cost center must remain identical to the Tyre Request. "
        "Update the Tyre Request and recreate the Purchase Order if changes are required."
        "<br><br><b>Expected Parent Values</b><br>"
        f"Supplier: {expected_parent_values[0] or 'None'}<br>"
        f"Project: {expected_parent_values[1] or 'None'}<br>"
        f"Cost Center: {expected_parent_values[2] or 'None'}"
        "<br><br><b>Current Parent Values</b><br>"
        f"Supplier: {current_parent_values[0] or 'None'}<br>"
        f"Project: {current_parent_values[1] or 'None'}<br>"
        f"Cost Center: {current_parent_values[2] or 'None'}"
        "<br><br><b>Expected Rows</b><br>"
        f"{_format_tyre_request_purchase_order_integrity_rows(expected_rows)}"
        "<br><br><b>Current Rows</b><br>"
        f"{_format_tyre_request_purchase_order_integrity_rows(current_rows)}",
        title="Tyre Request Integrity Error",
    )
