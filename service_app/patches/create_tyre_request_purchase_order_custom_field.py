from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Purchase Order": [
                {
                    "fieldname": "custom_tyre_request_link",
                    "label": "Tyre Request",
                    "fieldtype": "Link",
                    "options": "Tyre Request",
                    "insert_after": "custom_job_card_link",
                    "read_only": 1,
                    "no_copy": 1,
                    "print_hide": 1,
                    "search_index": 1,
                }
            ]
        },
        update=True,
    )
