import os

import frappe
from frappe import _
from frappe.modules import scrub
from frappe.utils import cstr


APP_NAME = "service_app"
MODULE_NAME = "service_tracking"
MODULE_DEF_NAME = "Service Tracking"


def ensure_required_link_target_doctypes():
    """Reload service_app DocTypes that old Custom Fields commonly link to."""
    ensure_service_tracking_module_def()

    for doctype in _get_local_doctype_names():
        frappe.reload_doc(MODULE_NAME, "doctype", scrub(doctype), force=True)


def ensure_service_tracking_module_def():
    if frappe.db.exists("Module Def", MODULE_DEF_NAME):
        frappe.db.set_value(
            "Module Def",
            MODULE_DEF_NAME,
            {
                "app_name": APP_NAME,
                "custom": 0,
            },
            update_modified=False,
        )
        return

    frappe.get_doc(
        {
            "doctype": "Module Def",
            "module_name": MODULE_DEF_NAME,
            "app_name": APP_NAME,
            "custom": 0,
        }
    ).insert(ignore_permissions=True)


@frappe.whitelist()
def get_broken_custom_link_fields():
    broken_fields = []

    for field in _get_custom_link_fields():
        options = cstr(field.options).strip()
        if not options or options == "[Select]":
            continue

        if frappe.db.exists("DocType", options):
            continue

        local_doctype_folder = _get_local_doctype_folder(options)
        if local_doctype_folder:
            frappe.reload_doc(MODULE_NAME, "doctype", local_doctype_folder, force=True)
            if frappe.db.exists("DocType", options):
                continue

        broken_fields.append(
            {
                "name": field.name,
                "dt": field.dt,
                "fieldname": field.fieldname,
                "label": field.label,
                "options": options,
            }
        )

    return broken_fields


@frappe.whitelist()
def neutralize_broken_custom_link_fields(dry_run=True):
    """Convert broken custom Link fields to Data so desk forms can load again.

    This is intentionally limited to Custom Field records. It preserves the
    database column and records the old Link target in the field description.
    """
    dry_run = cstr(dry_run).strip().casefold() not in ("0", "false", "no")
    broken_fields = get_broken_custom_link_fields()

    if dry_run:
        return {"dry_run": True, "changed": [], "broken_fields": broken_fields}

    changed = []
    for row in broken_fields:
        original_options, original_description = frappe.db.get_value(
            "Custom Field", row["name"], ["options", "description"]
        )
        original_options = cstr(original_options).strip()
        original_description = cstr(original_description).strip()
        note = _("Original broken Link target: {0}").format(original_options)

        description = (
            f"{original_description}\n{note}".strip()
            if original_description and note not in original_description
            else note
        )
        frappe.db.set_value(
            "Custom Field",
            row["name"],
            {
                "fieldtype": "Data",
                "options": None,
                "description": description,
            },
            update_modified=True,
        )
        changed.append(row)

    if changed:
        frappe.clear_cache()

    return {"dry_run": False, "changed": changed, "broken_fields": changed}


@frappe.whitelist()
def neutralize_broken_custom_link_fields_now():
    return neutralize_broken_custom_link_fields(dry_run=False)


@frappe.whitelist()
def restore_neutralized_custom_link_fields():
    restored = []
    marker = "Original broken Link target:"

    fields = frappe.get_all(
        "Custom Field",
        filters={"fieldtype": "Data", "description": ["like", f"%{marker}%"]},
        fields=["name", "dt", "fieldname", "description"],
        order_by="dt asc, fieldname asc",
    )

    for field in fields:
        original_target = _extract_original_link_target(field.description, marker)
        if not original_target or not frappe.db.exists("DocType", original_target):
            continue

        frappe.db.set_value(
            "Custom Field",
            field.name,
            {
                "fieldtype": "Link",
                "options": original_target,
                "description": _remove_original_link_target_note(field.description, marker),
            },
            update_modified=True,
        )
        restored.append(
            {
                "name": field.name,
                "dt": field.dt,
                "fieldname": field.fieldname,
                "options": original_target,
            }
        )

    if restored:
        frappe.clear_cache()

    return restored


def _get_custom_link_fields():
    return frappe.get_all(
        "Custom Field",
        filters={"fieldtype": "Link"},
        fields=["name", "dt", "fieldname", "label", "options"],
        order_by="dt asc, fieldname asc",
    )


def _get_local_doctype_names():
    doctype_root = frappe.get_app_path(APP_NAME, MODULE_NAME, "doctype")
    names = []

    for folder_name in os.listdir(doctype_root):
        doctype_json = os.path.join(doctype_root, folder_name, f"{folder_name}.json")
        if not os.path.isfile(doctype_json):
            continue
        names.append(folder_name.replace("_", " ").title())

    return names


def _get_local_doctype_folder(doctype):
    folder_name = scrub(doctype)
    doctype_json = frappe.get_app_path(
        APP_NAME, MODULE_NAME, "doctype", folder_name, f"{folder_name}.json"
    )
    return folder_name if os.path.isfile(doctype_json) else None


def _extract_original_link_target(description, marker):
    for line in cstr(description).splitlines():
        if marker not in line:
            continue
        return line.split(marker, 1)[1].strip()
    return None


def _remove_original_link_target_note(description, marker):
    lines = [line for line in cstr(description).splitlines() if marker not in line]
    return "\n".join(lines).strip() or None
