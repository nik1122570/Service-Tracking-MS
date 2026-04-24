import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


FIELD_MAP = {
    "Item": [
        {
            "fieldname": "make",
            "label": "Make",
            "fieldtype": "Link",
            "options": "Vehicle Make",
            "insert_after": "item_group",
        },
        {
            "fieldname": "is_universal",
            "label": "Is Universal",
            "fieldtype": "Check",
            "default": "0",
            "insert_after": "make",
            "description": "Check if this spare part can be used across all vehicle makes.",
        },
        {
            "fieldname": "part_category",
            "label": "Part Category",
            "fieldtype": "Link",
            "options": "Part Category",
            "insert_after": "is_universal",
        },
    ],
    "Item Price": [
        {
            "fieldname": "make",
            "label": "Make",
            "fieldtype": "Link",
            "options": "Vehicle Make",
            "insert_after": "supplier",
        }
    ],
    "Supplier Quotation Item": [
        {
            "fieldname": "supplier",
            "label": "Supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "insert_after": "item_name",
        },
        {
            "fieldname": "make",
            "label": "Make",
            "fieldtype": "Link",
            "options": "Vehicle Make",
            "insert_after": "supplier",
        },
        {
            "fieldname": "price_list",
            "label": "Price List",
            "fieldtype": "Link",
            "options": "Price List",
            "insert_after": "make",
        },
        {
            "fieldname": "part_category",
            "label": "Part Category",
            "fieldtype": "Link",
            "options": "Part Category",
            "fetch_from": "item_code.part_category",
            "insert_after": "price_list",
        },
    ],
    "Purchase Order Item": [
        {
            "fieldname": "job_card_item",
            "label": "Job Card",
            "fieldtype": "Link",
            "options": "EAH Job Card",
            "insert_after": "item_code",
            "read_only": 1,
            "no_copy": 1,
        }
    ],
}


def execute():
    missing_field_map = {}
    for doctype, fields in FIELD_MAP.items():
        meta = frappe.get_meta(doctype)
        missing_fields = []
        for df in fields:
            if meta.get_field(df["fieldname"]):
                continue
            missing_fields.append(df)

        if missing_fields:
            missing_field_map[doctype] = missing_fields

    if not missing_field_map:
        return

    create_custom_fields(missing_field_map, update=True)
