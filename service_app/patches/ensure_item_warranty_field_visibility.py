import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


ITEM_WARRANTY_FIELD_CANDIDATES = (
    "warranty_period",
    "warranty_period_in_days",
    "warranty_period__in_days",
)


def execute():
    if not frappe.db.exists("DocType", "Item"):
        return

    meta = frappe.get_meta("Item")
    fieldname = next(
        (candidate for candidate in ITEM_WARRANTY_FIELD_CANDIDATES if meta.get_field(candidate)),
        None,
    )
    if not fieldname:
        return

    make_property_setter("Item", fieldname, "hidden", 0, "Check")
    make_property_setter("Item", fieldname, "read_only", 1, "Check")
    make_property_setter("Item", fieldname, "permlevel", 0, "Int")
    frappe.clear_cache(doctype="Item")
