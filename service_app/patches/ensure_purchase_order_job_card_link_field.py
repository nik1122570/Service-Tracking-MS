import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    meta = frappe.get_meta("Purchase Order")
    if meta.get_field("eah_job_card"):
        _backfill_eah_job_card_links()
        return

    create_custom_fields(
        {
            "Purchase Order": [
                {
                    "fieldname": "eah_job_card",
                    "label": "EAH Job Card",
                    "fieldtype": "Link",
                    "options": "EAH Job Card",
                    "insert_after": "supplier",
                    "read_only": 1,
                    "no_copy": 1,
                    "in_standard_filter": 1,
                }
            ]
        },
        update=True,
    )
    _backfill_eah_job_card_links()


def _backfill_eah_job_card_links():
    columns = set(frappe.db.get_table_columns("Purchase Order"))
    if "eah_job_card" not in columns:
        return

    if "job_card_link" in columns:
        frappe.db.sql(
            """
            UPDATE `tabPurchase Order`
            SET eah_job_card = job_card_link
            WHERE COALESCE(eah_job_card, '') = ''
              AND COALESCE(job_card_link, '') != ''
            """
        )

    if "custom_job_card_link" in columns:
        frappe.db.sql(
            """
            UPDATE `tabPurchase Order`
            SET eah_job_card = custom_job_card_link
            WHERE COALESCE(eah_job_card, '') = ''
              AND COALESCE(custom_job_card_link, '') != ''
            """
        )
