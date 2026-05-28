import frappe


def execute():
    custom_field_name = "Item-make"

    if frappe.db.exists("Custom Field", custom_field_name):
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            "reqd",
            0,
            update_modified=True,
        )

    for property_setter in frappe.get_all(
        "Property Setter",
        filters={
            "doc_type": "Item",
            "field_name": "make",
            "property": "reqd",
        },
        pluck="name",
    ):
        frappe.delete_doc(
            "Property Setter",
            property_setter,
            ignore_permissions=True,
            force=True,
        )

    frappe.clear_cache(doctype="Item")
