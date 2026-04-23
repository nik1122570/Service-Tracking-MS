import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt
from service_app.service_tracking.vehicle_make_controls import ensure_vehicle_make_enabled

SPARE_PARTS_ITEM_GROUP = "Spare Parts"
VEHICLE_MAKE_DOCTYPE = "Vehicle Make"
ITEM_WARRANTY_FIELD_CANDIDATES = (
    "warranty_period",
    "warranty_period_in_days",
    "warranty_period__in_days",
)


def validate_spare_part_part_category(doc, method=None):
    _validate_item_make_enabled(doc)
    _validate_spare_part_make_requirement(doc)
    _apply_default_price_list_from_make(doc)

    if doc.meta.get_field("part_category"):
        item_group = cstr(getattr(doc, "item_group", "")).strip()
        part_category = cstr(getattr(doc, "part_category", "")).strip()

        if _is_spare_parts_item(item_group) and not part_category:
            frappe.throw(
                _("Part Category is required when Item Group is {0}.").format(
                    frappe.bold(SPARE_PARTS_ITEM_GROUP)
                ),
                title=_("Missing Part Category"),
            )

        _apply_warranty_period_from_part_category(doc)
        _enforce_warranty_period_read_only(doc)


@frappe.whitelist()
def get_warranty_days_for_part_category(part_category):
    return {
        "days": _get_warranty_days(part_category),
        "item_warranty_field": _get_item_warranty_fieldname(frappe.get_meta("Item")),
    }


@frappe.whitelist()
def get_make_default_price_list(make):
    return {
        "default_price_list": _get_make_default_price_list(make),
        "default_company": _get_default_company(),
    }


def _is_spare_parts_item(item_group):
    return cstr(item_group).strip().casefold() == SPARE_PARTS_ITEM_GROUP.casefold()


def _is_universal_item(doc):
    if not doc.meta.get_field("is_universal"):
        return False
    return bool(cint(getattr(doc, "is_universal", 0) or 0))


def _validate_spare_part_make_requirement(doc):
    if not _is_spare_parts_item(getattr(doc, "item_group", None)):
        return

    if not doc.meta.get_field("make"):
        return

    if _is_universal_item(doc):
        return

    make = cstr(getattr(doc, "make", "")).strip()
    if make:
        return

    frappe.throw(
        _("Make is required for {0} unless {1} is checked.").format(
            frappe.bold(SPARE_PARTS_ITEM_GROUP),
            frappe.bold("Is Universal"),
        ),
        title=_("Missing Make"),
    )


def _validate_item_make_enabled(doc):
    if not _is_spare_parts_item(getattr(doc, "item_group", None)):
        return

    if not doc.meta.get_field("make"):
        return

    ensure_vehicle_make_enabled(
        getattr(doc, "make", None),
        context_label="Item Make",
    )


def _apply_default_price_list_from_make(doc):
    if not _is_spare_parts_item(getattr(doc, "item_group", None)):
        return

    if _is_universal_item(doc):
        return

    if not doc.meta.get_field("make") or not doc.meta.get_field("item_defaults"):
        return

    make = cstr(getattr(doc, "make", "")).strip()
    if not make:
        return

    default_price_list = _get_make_default_price_list(make)
    if not default_price_list:
        frappe.throw(
            _("Please set Default Price List on Vehicle Make {0}.").format(
                frappe.bold(make)
            ),
            title=_("Missing Make Price List"),
        )

    _set_item_default_price_list(doc, default_price_list)


def _set_item_default_price_list(doc, default_price_list):
    rows = list(getattr(doc, "item_defaults", None) or [])
    if rows:
        for row in rows:
            row.default_price_list = default_price_list
        return

    default_company = _get_default_company()
    if not default_company:
        frappe.throw(
            _(
                "Cannot set Item Default Price List automatically because no default Company is configured."
            ),
            title=_("Missing Default Company"),
        )

    doc.append(
        "item_defaults",
        {
            "company": default_company,
            "default_price_list": default_price_list,
        },
    )


def _get_make_default_price_list(make):
    make = cstr(make).strip()
    if not make:
        return None

    ensure_vehicle_make_enabled(make, context_label="Item Make")

    value = frappe.db.get_value(VEHICLE_MAKE_DOCTYPE, make, "default_price_list")
    return cstr(value).strip() or None


def _get_default_company():
    company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )
    return cstr(company).strip() or None


def _apply_warranty_period_from_part_category(doc):
    if not cstr(getattr(doc, "part_category", "")).strip():
        return

    warranty_field = _get_item_warranty_fieldname(doc.meta)
    if not warranty_field:
        return

    warranty_days = _get_warranty_days(doc.part_category)
    if warranty_days is None:
        return

    doc.set(warranty_field, warranty_days)


def _get_warranty_days(part_category):
    settings_field = _resolve_settings_field_for_part_category(part_category)
    if not settings_field:
        return None

    raw_days = frappe.db.get_single_value("Service App Settings", settings_field)
    if raw_days in (None, ""):
        return None

    return flt(raw_days)


def _get_item_warranty_fieldname(meta):
    for fieldname in ITEM_WARRANTY_FIELD_CANDIDATES:
        if meta.get_field(fieldname):
            return fieldname
    return None


def _normalize_part_category(part_category):
    return re.sub(r"[^a-z0-9]+", " ", cstr(part_category).strip().casefold()).strip()


def _resolve_settings_field_for_part_category(part_category):
    normalized = _normalize_part_category(part_category)
    if not normalized:
        return None

    if "both" in normalized:
        return "warranty_period_for_both"

    if "electrical" in normalized or "electric" in normalized:
        return "warranty_period_for_electrical_part"

    second_hand_tokens = (
        "second hand",
        "2nd hand",
        "pirate",
        "alternative",
    )
    if any(token in normalized for token in second_hand_tokens):
        return "warranty_period_for_second_hand_part"

    if "original" in normalized:
        return "warranty_period_for_original_parts_in_days"

    return None


def _enforce_warranty_period_read_only(doc):
    warranty_field = _get_item_warranty_fieldname(doc.meta)
    if not warranty_field or doc.is_new():
        return

    if not doc.has_value_changed(warranty_field):
        return

    expected_days = _get_warranty_days(getattr(doc, "part_category", None))
    current_value = flt(getattr(doc, warranty_field, 0) or 0)

    if expected_days is not None and current_value == flt(expected_days):
        return

    frappe.throw(
        _(
            "Warranty Period is read-only. Please set Part Category and maintain its days in Service App Settings."
        ),
        title=_("Read-only Field"),
    )
