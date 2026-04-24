import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, cint, date_diff, flt, getdate, today
from service_app.service_tracking.vehicle_make_controls import ensure_vehicle_make_enabled


# Warn when another submitted job card exists within the last 30 days.
RECENT_SERVICE_WARNING_DAYS = 30


class EAHJobCard(Document):

    def validate(self):
        self.ensure_required_fields()
        self.validate_job_card_make_enabled()
        self.ensure_supplied_parts_data()
        self.validate_labour_rates_template_scope()
        self.calculate_totals()
        self.validate_supplied_parts_rate_limit()
        warnings = []
        warnings += self.check_recent_vehicle_service()
        warnings += self.check_part_warranty()

        # Show warnings during draft validation, but keep submit flow quiet.
        if warnings and not getattr(self.flags, "in_submit", False):
            frappe.msgprint(
                "<br>".join(warnings),
                title="Maintenance Warning",
                indicator="orange"
            )

    def ensure_required_fields(self):

        if not self.vehicle:
            frappe.throw("Vehicle is required.")

        if not self.service_date:
            frappe.throw("Service Date is required.")

        if not self.supplier:
            frappe.throw("Supplier is required.")

        if not self.price_list:
            frappe.throw("Price List is required.")

        if not self.project:
            frappe.throw("Project is required.")

        if not self.driver_name:
            frappe.throw("Driver Name is required.")

    def ensure_supplied_parts_data(self):
        """
        Ensure supplied parts contain the required transactional data.
        """

        for part in self.supplied_parts:

            if not part.item:
                frappe.throw("Item is required in Supplied Parts.")

            if not part.qty:
                frappe.throw(f"Quantity is required for item {part.item}")

            # Auto-fetch item name if missing.
            if part.item and not part.item_name:
                part.item_name = frappe.db.get_value(
                    "Item", part.item, "item_name"
                )

            # Keep child row price list aligned with parent Job Card price list.
            if self.price_list and part.price_list != self.price_list:
                part.price_list = self.price_list

            # Auto-fetch supplier-specific price (fallback to generic Item Price)
            # when row rate is blank/zero.
            price_list = part.price_list or self.price_list
            if part.item and price_list and not flt(part.rate):
                approved_rate = get_item_price_rate(part.item, price_list, self.supplier)
                if approved_rate is not None:
                    part.rate = flt(approved_rate)

    def is_warranty_control_disabled(self):
        return bool(
            cint(
                frappe.db.get_single_value(
                    "Service App Settings",
                    "disable_warranty_control_in_job_card",
                )
                or 0
            )
        )

    def _get_first_present_value(self, source, fieldnames):
        for fieldname in fieldnames:
            value = getattr(source, fieldname, None)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    def _normalize_scope_value(self, value):
        return " ".join(str(value or "").strip().split()).lower()

    def get_job_card_make(self):
        make = self._get_first_present_value(
            self,
            ["make", "custom_make", "vehicle_make", "custom_vehicle_make"],
        )
        return make, "EAH Job Card"

    def validate_job_card_make_enabled(self):
        make, scope_source = self.get_job_card_make()
        ensure_vehicle_make_enabled(
            make,
            context_label=f"{scope_source} Make",
        )

    def validate_labour_rates_template_scope(self):
        labour_rows = list(getattr(self, "labour_rates", None) or [])
        if not labour_rows:
            return

        job_make, scope_source = self.get_job_card_make()
        if not job_make:
            frappe.throw(
                "Make must be populated on EAH Job Card before selecting Labour Rate templates.",
                title="Missing Job Card Scope",
            )
        normalized_job_make = self._normalize_scope_value(job_make)
        mismatch_errors = []

        for index, row in enumerate(labour_rows, start=1):
            operation = getattr(row, "operation_done", None) or getattr(row, "operation", None)
            if not operation:
                continue

            operation_scope = frappe.db.get_value(
                "Service Tempelate",
                operation,
                ["make"],
                as_dict=True,
            )
            if not operation_scope:
                mismatch_errors.append(f"Row {index}: Operation template {operation} was not found.")
                continue

            operation_make = (operation_scope.make or "").strip()
            normalized_operation_make = self._normalize_scope_value(operation_make)

            if (
                normalized_job_make
                and normalized_operation_make
                and normalized_job_make != normalized_operation_make
            ):
                mismatch_errors.append(
                    f"Row {index}: Operation {operation} is for make {operation_make}, "
                    f"but Job Card make is {job_make} (source: {scope_source})."
                )

        if mismatch_errors:
            frappe.throw("<br>".join(mismatch_errors), title="Labour Rate Template Mismatch")

    def calculate_totals(self):
        total_qty = sum(flt(part.qty) for part in self.supplied_parts)
        spares_cost = sum(flt(part.qty) * flt(part.rate) for part in self.supplied_parts)
        service_charges = get_job_card_labour_charge_total(self, update_row_totals=True)

        total_vat_exclusive = spares_cost + service_charges

        if self.meta.has_field("custom_total_qty"):
            self.custom_total_qty = total_qty

        self.spares_cost = spares_cost
        self.service_charges = service_charges
        self.total_vat_exclusive = total_vat_exclusive
    def validate_supplied_parts_rate_limit(self):
        errors = []

        for index, part in enumerate(self.supplied_parts, start=1):
            price_list = part.price_list or self.price_list
            approved_rate = get_item_price_rate(part.item, price_list, self.supplier)
            entered_rate = flt(part.rate)
            part_label = part.item_name or part.item or f"Row {index}"

            if approved_rate is None:
                if entered_rate > 0:
                    errors.append(
                        f"Row {index}: {part_label} has no approved Item Price in Price List {price_list}. "
                        "Raise a Price Change Request for Management Approval before entering a rate."
                    )
                continue

            if entered_rate > flt(approved_rate):
                errors.append(
                    f"Row {index}: Rate for {part_label} cannot be greater than the approved Item Price "
                    f"of {approved_rate} in {price_list}. Raise a Price Change Request for Management Approval."
                )

        if errors:
            frappe.throw(
                "<br>".join(errors),
                title="Rate Change Not Allowed"
            )
    def before_submit(self):

        errors = []
        errors += self.check_recent_vehicle_service()
        errors += self.check_part_warranty()

        # If there are control issues
        if errors:

            # If override NOT checked -> block submission
            if not self.custom_override_controls:

                frappe.throw(
                    "<b>Submission Blocked.</b><br><br>"
                    "Maintenance controls detected the following issues:<br><br>"
                    + "<br>".join(errors) +
                    "<br><br>Please check <b>'Override Controls'</b> to allow submission.",
                    title="Maintenance Control"
                )

            # If override checked -> allow but warn
            else:
                pass

    def check_recent_vehicle_service(self):
        warnings = []
        reference_date = getdate(self.service_date or today())
        filters = {
            "vehicle": self.vehicle,
            "docstatus": 1,
            "service_date": ["<=", reference_date]
        }

        if self.name:
            filters["name"] = ["!=", self.name]

        last_service = frappe.get_all(
            "EAH Job Card",
            filters=filters,
            fields=["name", "service_date"],
            order_by="service_date desc",
            limit=1
        )

        if last_service:
            last_service_date = getdate(last_service[0].service_date)
            days_since_last_service = date_diff(reference_date, last_service_date)

            if 0 <= days_since_last_service <= RECENT_SERVICE_WARNING_DAYS:
                warnings.append(
                    "Vehicle was last serviced on "
                    f"{last_service_date} ({days_since_last_service} days ago)."
                )

        return warnings

    def get_latest_previous_part_service_date(self, item_code):
        if not item_code or not self.vehicle or not self.service_date:
            return None

        if not hasattr(self, "_previous_part_service_date_by_item"):
            self._previous_part_service_date_by_item = {}

        if item_code in self._previous_part_service_date_by_item:
            return self._previous_part_service_date_by_item[item_code]

        conditions = [
            "sp.parenttype = 'EAH Job Card'",
            "sp.parentfield = 'supplied_parts'",
            "sp.item = %(item_code)s",
            "jc.vehicle = %(vehicle)s",
            "jc.docstatus = 1",
            "jc.service_date <= %(service_date)s"
        ]
        values = {
            "item_code": item_code,
            "vehicle": self.vehicle,
            "service_date": getdate(self.service_date)
        }

        if self.name:
            conditions.append("jc.name != %(current_name)s")
            values["current_name"] = self.name

        records = frappe.db.sql(
            f"""
            SELECT
                sp.parent,
                jc.service_date
            FROM `tabSupplied Parts` sp
            INNER JOIN `tabEAH Job Card` jc
                ON jc.name = sp.parent
            WHERE {" AND ".join(conditions)}
            ORDER BY jc.service_date DESC
            LIMIT 1
            """,
            values,
            as_dict=True,
        )
        service_date = getdate(records[0].service_date) if records else None
        self._previous_part_service_date_by_item[item_code] = service_date
        return service_date

    def get_item_warranty_days(self, item_code):
        if not item_code:
            return 0

        if not hasattr(self, "_item_warranty_days_by_item"):
            self._item_warranty_days_by_item = {}

        if item_code in self._item_warranty_days_by_item:
            return self._item_warranty_days_by_item[item_code]

        warranty_days = cint(flt(frappe.db.get_value("Item", item_code, "warranty_period") or 0))
        self._item_warranty_days_by_item[item_code] = warranty_days
        return warranty_days

    def check_part_warranty(self):
        if self.is_warranty_control_disabled():
            return []

        warnings = []
        reference_date = getdate(self.service_date or today())
        checked_items = set()

        for part in self.supplied_parts:
            if not part.item or part.item in checked_items:
                continue

            checked_items.add(part.item)
            part_label = part.item_name or part.item
            warranty_days = self.get_item_warranty_days(part.item)
            if warranty_days <= 0:
                continue

            previous_service_date = self.get_latest_previous_part_service_date(part.item)
            if not previous_service_date:
                continue

            expiry = getdate(add_days(previous_service_date, warranty_days))
            if reference_date <= expiry:
                days_remaining = max(date_diff(expiry, reference_date), 0)
                warnings.append(
                    f"Part {part_label} may still be under warranty until {expiry} "
                    f"({days_remaining} day(s) remaining)."
                )

        return warnings

    def on_submit(self):
        # Keep submit flow quiet by design.
        pass


@frappe.whitelist()
def make_maintenance_return_note(source_name, target_doc=None):
    source = frappe.get_doc("EAH Job Card", source_name)

    if source.docstatus != 1:
        frappe.throw("Only submitted EAH Job Cards can create a Maintenance Return Note.")

    existing_note = frappe.db.get_value(
        "Maintenance Return Note",
        {
            "eah_job_card": source.name,
            "docstatus": ["<", 2],
        },
        "name",
    )
    if existing_note:
        frappe.throw(
            f"Maintenance Return Note {existing_note} already exists for EAH Job Card {source.name}."
        )

    target = frappe.new_doc("Maintenance Return Note")
    target.source_type = "From EAH Job Card"
    target.eah_job_card = source.name
    target.vehicle = source.vehicle
    target.service_date = source.service_date
    target.supplier = source.supplier
    target.received_by = frappe.session.user

    has_rows = False
    for part in source.supplied_parts:
        qty_expected = flt(part.qty)
        if not part.item or qty_expected <= 0:
            continue

        has_rows = True
        target.append(
            "returned_parts",
            {
                "source_supplied_part_row": part.name,
                "item": part.item,
                "item_name": part.item_name,
                "qty_expected": qty_expected,
                "qty_received": qty_expected,
                "uom": getattr(part, "uom", None),
                "condition": "Repairable",
                "disposition": "Stored",
            },
        )

    if not has_rows:
        frappe.throw(
            f"EAH Job Card {source.name} has no supplied parts available to create a Maintenance Return Note."
        )

    return target


@frappe.whitelist()
def make_purchase_order(source_name, target_doc=None):

    def set_job_card_item_reference(source, target):
        item_meta = frappe.get_meta("Purchase Order Item")
        if not item_meta.get_field("job_card_item"):
            return

        for row in target.items or []:
            row.job_card_item = source.name

    def append_labour_charge_item(source, target):
        service_charges = get_job_card_labour_charge_total(source, update_row_totals=False)
        if service_charges <= 0:
            return

        labour_item = get_default_labour_item_for_job_card(source)
        if not labour_item:
            frappe.throw(
                "Default Labour Item is required to transfer labour charges into the Purchase Order. "
                "Please set it on the EAH Job Card or in Service App Settings."
            )

        item_details = frappe.db.get_value(
            "Item",
            labour_item,
            ["item_name", "description", "stock_uom"],
            as_dict=True,
        )
        if not item_details:
            frappe.throw(f"Default Labour Item {labour_item} was not found.")

        description = f"Labour Charges for EAH Job Card {source.name}"
        service_templates = []

        labour_rows = list(getattr(source, "labour_rates", None) or [])
        if labour_rows:
            service_templates = [
                (getattr(row, "operation_done", None) or getattr(row, "operation", None))
                for row in labour_rows
                if (getattr(row, "operation_done", None) or getattr(row, "operation", None))
            ]
        else:
            service_templates = [
                row.service_template
                for row in (getattr(source, "service_task_templates", None) or [])
                if getattr(row, "service_template", None)
            ]

        if service_templates:
            description += "\nService Templates: " + ", ".join(service_templates)

        if item_details.description:
            description += f"\n{item_details.description}"

        target.append(
            "items",
            {
                "item_code": labour_item,
                "item_name": item_details.item_name,
                "description": description,
                "schedule_date": source.service_date or today(),
                "qty": 1,
                "uom": item_details.stock_uom,
                "stock_uom": item_details.stock_uom,
                "conversion_factor": 1,
                "rate": service_charges,
            },
        )

    def set_missing_values(source, target):
        target.supplier = source.supplier
        # Link PO -> Job Card using whichever link field exists on Purchase Order.
        if hasattr(target, "custom_job_card_link"):
            target.custom_job_card_link = source.name
        elif hasattr(target, "job_card_link"):
            target.job_card_link = source.name
        elif hasattr(target, "eah_job_card"):
            target.eah_job_card = source.name
        target.cost_center = getattr(source, "custom_cost_center", None)
        if hasattr(target, "ignore_pricing_rule"):
            target.ignore_pricing_rule = 1
        append_labour_charge_item(source, target)
        set_job_card_item_reference(source, target)

    doc = get_mapped_doc(
        "EAH Job Card",
        source_name,
        {
            "EAH Job Card": {
                "doctype": "Purchase Order"
            },
            "Supplied Parts": {
                "doctype": "Purchase Order Item",
                "field_map": {
                    "item": "item_code",
                    "item_name": "item_name",
                    "qty": "qty",
                    "rate": "rate",
                    "uom": "uom"
                }
            },
        },
        target_doc,
        set_missing_values
    )

    return doc


def _normalize_purchase_order_integrity_row(item_code, qty, rate, uom=None):
    return (
        (item_code or "").strip(),
        flt(qty, 6),
        flt(rate, 6),
        (uom or "").strip(),
    )


def get_expected_job_card_purchase_order_rows(job_card):
    rows = [
        _normalize_purchase_order_integrity_row(part.item, part.qty, part.rate, part.uom)
        for part in job_card.supplied_parts
        if part.item
    ]

    service_charges = get_job_card_labour_charge_total(job_card, update_row_totals=False)
    if service_charges > 0:
        labour_item = get_default_labour_item_for_job_card(job_card)
        if not labour_item:
            frappe.throw(
                "Default Labour Item is required to transfer labour charges into the Purchase Order. "
                "Please set it on the EAH Job Card or in Service App Settings."
            )

        labour_uom = frappe.db.get_value("Item", labour_item, "stock_uom") or ""

        rows.append(
            _normalize_purchase_order_integrity_row(
                labour_item,
                1,
                service_charges,
                labour_uom,
            )
        )

    return sorted(rows)


def _get_purchase_order_integrity_rows(doc):
    return sorted(
        _normalize_purchase_order_integrity_row(item.item_code, item.qty, item.rate, item.uom)
        for item in doc.items
        if item.item_code
    )


def _format_purchase_order_integrity_rows(rows):
    return "<br>".join(
        f"{item_code} | Qty: {qty:g} | Rate: {rate:g} | UOM: {uom or 'N/A'}"
        for item_code, qty, rate, uom in rows
    ) or "None"


def get_purchase_order_job_card_link(doc):
    for fieldname in ("custom_job_card_link", "job_card_link", "eah_job_card"):
        value = (getattr(doc, fieldname, None) or "").strip()
        if value:
            return value
    return ""


def _get_single_doctype_value_if_field_exists(doctype, fieldnames):
    fieldname = _get_first_available_doctype_field(doctype, fieldnames)
    if not fieldname:
        return ""

    if frappe.get_meta(doctype).issingle:
        value = frappe.db.get_single_value(doctype, fieldname)
    else:
        value = frappe.db.get_value(doctype, doctype, fieldname)

    return (value or "").strip() if isinstance(value, str) else value


def get_default_labour_item_for_job_card(job_card):
    # Priority:
    # 1) Value on EAH Job Card (supports both v15/v16 fieldnames)
    # 2) Value in Service App Settings (supports both standard/custom-prefixed fieldnames)
    for fieldname in ("default_labour_item", "custom_default_labour_item"):
        value = getattr(job_card, fieldname, None)
        if isinstance(value, str):
            value = value.strip()
        if value:
            return value

    return _get_single_doctype_value_if_field_exists(
        "Service App Settings",
        ("default_labour_item", "custom_default_labour_item"),
    )


def _get_first_available_doctype_field(doctype, fieldnames):
    columns = set(frappe.db.get_table_columns(doctype))
    for fieldname in fieldnames:
        if fieldname in columns:
            return fieldname
    return None


def validate_purchase_order_job_card_integrity(doc, method=None):
    job_card_link = get_purchase_order_job_card_link(doc)
    if not job_card_link:
        return

    job_card = frappe.get_doc("EAH Job Card", job_card_link)
    expected_rows = get_expected_job_card_purchase_order_rows(job_card)
    current_rows = _get_purchase_order_integrity_rows(doc)
    expected_cost_center = (getattr(job_card, "custom_cost_center", None) or "").strip()
    current_cost_center = (getattr(doc, "cost_center", None) or "").strip()
    expected_labour_charge = get_job_card_labour_charge_total(job_card, update_row_totals=False)

    if current_rows == expected_rows and current_cost_center == expected_cost_center:
        return

    frappe.throw(
        "Please make sure the Labour Charge in this Purchase Order matches the Labour Charge in "
        f"<b>EAH Job Card {job_card.name}</b> "
        f"(<b>EAH Labour Charge: {expected_labour_charge:g}</b>). "
        "If any update is needed, kindly adjust the EAH Job Card and create a new Purchase Order.",
        title="Job Card Integrity Error",
    )


@frappe.whitelist()
def make_material_request(source_name, target_doc=None):
    doc = get_mapped_doc(
        "EAH Job Card",
        source_name,
        {
            "EAH Job Card": {
                "doctype": "Material Request",
                "field_map": {
                    "name": "eah_job_card"
                }
            },
            "Supplied Parts": {
                "doctype": "Material Request Item",
                "field_map": {
                    "item": "item_code",
                    "item_name": "item_name",
                    "qty": "qty"
                },
            },
        },
        target_doc
    )

    doc.material_request_type = "Purchase"

    return doc


@frappe.whitelist()
def get_vehicle_maintenance_history(vehicle):

    if not vehicle:
        return []

    fields = [
        "name",
        "service_date",
        "supplier",
        "driver_name",
        "project",
    ]
    odometer_field = _get_first_available_doctype_field(
        "EAH Job Card",
        ("odometer_reading", "vehicle_odometer", "odometer", "current_odometer"),
    )
    if odometer_field:
        fields.append(odometer_field)

    job_cards = frappe.get_all(
        "EAH Job Card",
        filters={"vehicle": vehicle, "docstatus": 1},
        fields=fields,
        order_by="service_date desc"
    )

    history = []

    for jc in job_cards:
        if "odometer_reading" not in jc:
            jc["odometer_reading"] = jc.get(odometer_field) if odometer_field else None

        templates = []
        labour_templates = frappe.get_all(
            "Maintainance Tempelate",
            filters={
                "parent": jc.name,
                "parentfield": "labour_rates"
            },
            pluck="operation_done"
        )

        if labour_templates:
            templates = labour_templates
        else:
            # Compatibility fallback for legacy child layouts storing operation directly.
            legacy_labour_templates = frappe.get_all(
                "Maintainance Tempelate",
                filters={
                    "parent": jc.name,
                    "parentfield": "labour_rates"
                },
                pluck="operation"
            )
            if legacy_labour_templates:
                templates = legacy_labour_templates
            else:
            # Backward compatibility for legacy rows.
                templates = frappe.get_all(
                    "Job Card Template",
                    filters={
                        "parent": jc.name,
                        "parentfield": "service_task_templates"
                    },
                    pluck="service_template"
                )

        parts = frappe.get_all(
            "Supplied Parts",
            filters={"parent": jc.name},
            fields=["item_name", "qty"]
        )

        parts_list = []
        for p in parts:
            parts_list.append(f"{p.item_name} (Qty: {p.qty})")

        jc["service_templates"] = templates
        jc["parts_used"] = ", ".join(parts_list)

        history.append(jc)

    return history


def get_item_price_rate(item_code, price_list, supplier=None):
    if not item_code or not price_list:
        return None

    filters = {
        "item_code": item_code,
        "price_list": price_list
    }

    if supplier:
        filters["supplier"] = supplier

    price = frappe.db.get_value("Item Price", filters, "price_list_rate")

    # If no supplier price found, fallback to the generic price list entry.
    if price is None and supplier:
        price = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "price_list": price_list
            },
            "price_list_rate"
        )

    return price


@frappe.whitelist()
def get_item_price(item_code, price_list, supplier=None):
    price = get_item_price_rate(item_code, price_list, supplier)
    return {"rate": price or 0}


def get_job_card_labour_charge_total(job_card, update_row_totals=False):
    labour_rows = list(getattr(job_card, "labour_rates", None) or [])
    if not labour_rows:
        # Backward compatibility for legacy Job Cards that still use service_task_templates.
        return sum(
            flt(task.rate) for task in (getattr(job_card, "service_task_templates", None) or [])
        )

    total = 0
    for row in labour_rows:
        maximum_hours = flt(getattr(row, "maximum_hours", 0), 6)
        flat_rate = flt(getattr(row, "flat_rate", 0), 6)
        row_total = flt(maximum_hours * flat_rate, 6)
        if update_row_totals:
            row.maximum_hours = maximum_hours
            row.flat_rate = flat_rate
            row.total_amount = row_total
        total += row_total

    return flt(total, 6)











