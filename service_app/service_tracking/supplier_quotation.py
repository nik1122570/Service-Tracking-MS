import frappe
from frappe.utils import cstr, flt
from service_app.service_tracking.vehicle_make_controls import ensure_vehicle_make_enabled


def validate_supplier_quotation_duplicate_item_prices(doc, method=None):
    if getattr(doc, "meta", None) and doc.meta.get_field("make"):
        ensure_vehicle_make_enabled(
            getattr(doc, "make", None),
            context_label="Supplier Quotation Make",
        )

    items = list(getattr(doc, "items", None) or [])
    if not items:
        return

    item_price_meta = frappe.get_meta("Item Price")
    include_make = bool(item_price_meta.get_field("make"))
    seen_keys = {}
    errors = []
    current_reference = cstr(getattr(doc, "name", "")).strip()

    for index, row in enumerate(items, start=1):
        if hasattr(row, "make"):
            ensure_vehicle_make_enabled(
                getattr(row, "make", None),
                context_label=f"Supplier Quotation Item Row {index} Make",
            )

        payload = _build_duplicate_check_payload(doc, row, include_make)
        if not payload:
            continue

        payload_key = _build_payload_key(payload, include_make)
        if payload_key in seen_keys:
            first_row = seen_keys[payload_key]
            errors.append(
                f"Row {index}: Item {frappe.bold(payload['item_code'])} duplicates Row {first_row} "
                "in this Supplier Quotation."
            )
            continue
        seen_keys[payload_key] = index

        existing = _get_existing_item_price(payload, include_make)
        if not existing:
            continue

        existing_reference = cstr(getattr(existing, "reference", "")).strip()
        if current_reference and existing_reference and existing_reference == current_reference:
            continue

        errors.append(
            f"Row {index}: Item {frappe.bold(payload['item_code'])} already exists in Item Price as "
            f"{frappe.bold(existing.name)}."
        )

    if errors:
        frappe.throw("<br>".join(errors), title="Duplicate Item Price Not Allowed")


def sync_item_prices_from_supplier_quotation(doc, method=None):
    if not _is_ready_for_price_publish(doc, method):
        return

    items = list(getattr(doc, "items", None) or [])
    if not items:
        return

    item_price_meta = frappe.get_meta("Item Price")
    include_make = bool(item_price_meta.get_field("make"))
    errors = []
    created_count = 0
    updated_count = 0
    duplicate_messages = []
    seen_payload_keys = set()

    for index, row in enumerate(items, start=1):
        payload = _build_item_price_payload(doc, row, index, errors, include_make)
        if not payload:
            continue

        payload_key = _build_payload_key(payload, include_make)
        if payload_key in seen_payload_keys:
            duplicate_messages.append(
                f"Row {index}: Item {frappe.bold(payload['item_code'])} is duplicated in this Supplier Quotation."
            )
            continue
        seen_payload_keys.add(payload_key)

        sync_result, existing_name = _create_item_price_if_missing(payload, include_make)
        if sync_result == "created":
            created_count += 1
        elif sync_result == "updated":
            updated_count += 1
        elif sync_result == "duplicate":
            duplicate_messages.append(
                f"Row {index}: Item {frappe.bold(payload['item_code'])} is already in Item Price "
                f"as {frappe.bold(existing_name)}."
            )

    if errors:
        frappe.throw("<br>".join(errors), title="Item Price Sync Failed")

    if created_count or updated_count:
        frappe.msgprint(
            f"Item Price uploaded. Created: {created_count}, Updated: {updated_count}.",
            title="Item Price Uploaded",
            indicator="green",
        )

    if duplicate_messages:
        frappe.msgprint(
            "Some rows were skipped because they already exist in Item Price:<br><br>"
            + "<br>".join(duplicate_messages),
            title="Duplicate Item Prices Skipped",
            indicator="orange",
        )


def _is_ready_for_price_publish(doc, method):
    if getattr(doc, "docstatus", 0) == 2:
        return False

    if method == "on_submit":
        return True

    workflow_state = cstr(getattr(doc, "workflow_state", "")).strip()
    status = cstr(getattr(doc, "status", "")).strip()
    return _state_means_approved(workflow_state) or _state_means_approved(status)


def _state_means_approved(state_value):
    normalized = cstr(state_value).strip().casefold()
    if not normalized:
        return False

    if normalized.startswith("not approved"):
        return False

    if normalized in ("approved", "approve"):
        return True

    return normalized.startswith("approved ")


def _first_present_value(source, fieldnames):
    for fieldname in fieldnames:
        value = getattr(source, fieldname, None)
        if value not in (None, ""):
            return value
    return None


def _build_item_price_payload(doc, row, index, errors, include_make):
    item_code = cstr(_first_present_value(row, ("item_code", "item")) or "").strip()
    price_list = cstr(
        _first_present_value(row, ("price_list", "custom_price_list", "buying_price_list"))
        or _first_present_value(doc, ("price_list", "buying_price_list", "custom_price_list"))
        or ""
    ).strip()
    supplier = cstr(
        _first_present_value(row, ("supplier", "custom_supplier"))
        or _first_present_value(doc, ("supplier", "custom_supplier"))
        or ""
    ).strip()
    rate = flt(
        _first_present_value(row, ("rate", "price_list_rate", "custom_rate", "base_rate")) or 0
    )
    uom = cstr(_first_present_value(row, ("uom", "stock_uom")) or "").strip()
    make = ""
    if include_make:
        make = cstr(
            _first_present_value(row, ("make", "custom_make"))
            or _first_present_value(doc, ("make", "custom_make"))
            or ""
        ).strip()

    if item_code and not uom:
        uom = cstr(frappe.db.get_value("Item", item_code, "stock_uom") or "").strip()

    if not item_code:
        errors.append(f"Row {index}: Item Code is required.")
    if not price_list:
        errors.append(f"Row {index}: Price List is required.")
    if rate <= 0:
        errors.append(f"Row {index}: Rate must be greater than 0.")
    if not uom:
        errors.append(f"Row {index}: UOM is required.")

    if errors:
        row_prefix = f"Row {index}:"
        if any(message.startswith(row_prefix) for message in errors):
            return None

    return {
        "item_code": item_code,
        "price_list": price_list,
        "supplier": supplier,
        "uom": uom,
        "make": make,
        "price_list_rate": rate,
        "valid_from": _first_present_value(row, ("valid_from", "custom_valid_from")),
        "valid_upto": _first_present_value(row, ("valid_upto", "custom_valid_upto")),
        "reference": cstr(doc.name).strip(),
    }


def _build_duplicate_check_payload(doc, row, include_make):
    item_code = cstr(_first_present_value(row, ("item_code", "item")) or "").strip()
    price_list = cstr(
        _first_present_value(row, ("price_list", "custom_price_list", "buying_price_list"))
        or _first_present_value(doc, ("price_list", "buying_price_list", "custom_price_list"))
        or ""
    ).strip()
    supplier = cstr(
        _first_present_value(row, ("supplier", "custom_supplier"))
        or _first_present_value(doc, ("supplier", "custom_supplier"))
        or ""
    ).strip()
    uom = cstr(_first_present_value(row, ("uom", "stock_uom")) or "").strip()
    make = ""
    if include_make:
        make = cstr(
            _first_present_value(row, ("make", "custom_make"))
            or _first_present_value(doc, ("make", "custom_make"))
            or ""
        ).strip()

    if item_code and not uom:
        uom = cstr(frappe.db.get_value("Item", item_code, "stock_uom") or "").strip()

    if not item_code or not price_list or not uom:
        return None

    return {
        "item_code": item_code,
        "price_list": price_list,
        "supplier": supplier,
        "uom": uom,
        "make": make,
        "reference": cstr(getattr(doc, "name", "")).strip(),
    }


def _get_item_price_filters(payload, include_make):
    filters = {
        "item_code": payload["item_code"],
        "price_list": payload["price_list"],
        "supplier": payload["supplier"] or "",
        "uom": payload["uom"],
        "buying": 1,
    }
    if include_make:
        filters["make"] = payload["make"] or ""
    return filters


def _get_existing_item_price(payload, include_make):
    filters = _get_item_price_filters(payload, include_make)
    return frappe.db.get_value("Item Price", filters, ["name", "reference"], as_dict=True)


def _build_payload_key(payload, include_make):
    key = (
        payload["item_code"] or "",
        payload["price_list"] or "",
        payload["supplier"] or "",
        payload["uom"] or "",
        1,
    )
    if include_make:
        key = key + (payload["make"] or "",)
    return key


def _create_item_price_if_missing(payload, include_make):
    existing = _get_existing_item_price(payload, include_make)
    if existing:
        existing_reference = cstr(getattr(existing, "reference", "")).strip()
        current_reference = cstr(payload.get("reference") or "").strip()
        if current_reference and existing_reference and existing_reference == current_reference:
            item_price = frappe.get_doc("Item Price", existing.name)
            _apply_item_price_values(item_price, payload, include_make)
            item_price.save(ignore_permissions=True)
            return "updated", existing.name
        return "duplicate", existing.name

    item_price = frappe.new_doc("Item Price")
    _apply_item_price_values(item_price, payload, include_make)
    item_price.insert(ignore_permissions=True)
    return "created", item_price.name


def _apply_item_price_values(item_price, payload, include_make):
    item_price.item_code = payload["item_code"]
    item_price.price_list = payload["price_list"]
    item_price.price_list_rate = flt(payload["price_list_rate"])
    item_price.uom = payload["uom"]
    item_price.supplier = payload["supplier"] or ""
    item_price.buying = 1
    item_price.selling = 0
    item_price.valid_from = payload["valid_from"] or None
    item_price.valid_upto = payload["valid_upto"] or None
    item_price.reference = payload["reference"]

    if include_make and item_price.meta.get_field("make"):
        item_price.make = payload["make"] or ""
