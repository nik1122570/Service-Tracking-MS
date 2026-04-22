import frappe
from frappe import _
from frappe.utils import cint, cstr

VEHICLE_MAKE_DOCTYPE = "Vehicle Make"


def validate_doc_make_enabled(doc, method=None):
    if not getattr(doc, "meta", None):
        return

    if not doc.meta.get_field("make"):
        return

    ensure_vehicle_make_enabled(
        getattr(doc, "make", None),
        context_label=f"{doc.doctype} Make",
    )


def ensure_vehicle_make_enabled(make, context_label="Vehicle Make"):
    make = cstr(make).strip()
    if not make:
        return

    if not frappe.db.exists(VEHICLE_MAKE_DOCTYPE, make):
        # Link validations will handle non-existing values.
        return

    if not _has_enabled_field():
        return

    enabled = cint(frappe.db.get_value(VEHICLE_MAKE_DOCTYPE, make, "enabled") or 0)
    if enabled:
        return

    frappe.throw(
        _("{0}: Vehicle Make {1} is disabled. Please select an enabled make.").format(
            context_label,
            frappe.bold(make),
        ),
        title=_("Disabled Vehicle Make"),
    )


def _has_enabled_field():
    try:
        meta = frappe.get_meta(VEHICLE_MAKE_DOCTYPE)
    except Exception:
        return False
    return bool(meta.get_field("enabled"))
