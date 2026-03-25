import frappe


REPORT_NAME = "Vehicle Maintenance History Report"


def execute():
    if not frappe.db.exists("Report", REPORT_NAME):
        return

    frappe.db.set_value(
        "Report",
        REPORT_NAME,
        {
            "report_type": "Script Report",
            "query": "",
        },
        update_modified=False,
    )

    frappe.db.commit()
    frappe.clear_cache()
