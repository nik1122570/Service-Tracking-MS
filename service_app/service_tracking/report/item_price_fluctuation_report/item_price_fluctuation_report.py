# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import json
import re
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate

TRACKED_FIELDS = {
    "item_code",
    "item_name",
    "price_list",
    "supplier",
    "price_list_rate",
    "currency",
    "valid_from",
    "valid_upto",
    "uom",
}
DATE_FIELDS = {"valid_from", "valid_upto"}
NUMERIC_FIELDS = {"price_list_rate"}


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    columns = get_columns()
    item_price_docs = get_item_price_docs(filters)
    if not item_price_docs:
        return columns, [], _("No Item Price records found for the selected filters."), None

    version_map = get_item_price_versions([doc.name for doc in item_price_docs])
    all_rows = build_history_rows(item_price_docs, version_map)
    data = [row for row in all_rows if row_matches_filters(row, filters)]
    chart = get_chart_data(data, filters)
    message = get_message(filters, data)

    return columns, data, message, chart


def validate_filters(filters):
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("From Date and To Date are required."))

    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be greater than To Date."))


def get_columns():
    return [
        {
            "label": _("Changed On"),
            "fieldname": "changed_on",
            "fieldtype": "Datetime",
            "width": 155,
        },
        {
            "label": _("Event Type"),
            "fieldname": "event_type",
            "fieldtype": "Data",
            "width": 130,
        },
        {
            "label": _("Direction"),
            "fieldname": "change_direction",
            "fieldtype": "Data",
            "width": 110,
        },
        {
            "label": _("Item Price"),
            "fieldname": "item_price",
            "fieldtype": "Link",
            "options": "Item Price",
            "width": 150,
        },
        {
            "label": _("Item"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 140,
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 170,
        },
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 140,
        },
        {
            "label": _("Price List"),
            "fieldname": "price_list",
            "fieldtype": "Link",
            "options": "Price List",
            "width": 140,
        },
        {
            "label": _("UOM"),
            "fieldname": "uom",
            "fieldtype": "Link",
            "options": "UOM",
            "width": 90,
        },
        {
            "label": _("Previous Rate"),
            "fieldname": "previous_rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 125,
        },
        {
            "label": _("New Rate"),
            "fieldname": "new_rate",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 125,
        },
        {
            "label": _("Change Amount"),
            "fieldname": "change_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 125,
        },
        {
            "label": _("Change %"),
            "fieldname": "change_percentage",
            "fieldtype": "Percent",
            "width": 100,
        },
        {
            "label": _("Valid From"),
            "fieldname": "valid_from",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Valid Upto"),
            "fieldname": "valid_upto",
            "fieldtype": "Date",
            "width": 105,
        },
        {
            "label": _("Changed By"),
            "fieldname": "changed_by",
            "fieldtype": "Data",
            "width": 140,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "hidden": 1,
        },
    ]


def get_item_price_docs(filters):
    doc_filters = {}
    for fieldname in ("item_code", "price_list", "supplier"):
        if filters.get(fieldname):
            doc_filters[fieldname] = filters.get(fieldname)

    return frappe.get_all(
        "Item Price",
        filters=doc_filters,
        fields=[
            "name",
            "item_code",
            "item_name",
            "price_list",
            "supplier",
            "uom",
            "currency",
            "price_list_rate",
            "valid_from",
            "valid_upto",
            "creation",
            "owner",
        ],
        order_by="item_code asc, price_list asc, supplier asc, valid_from asc, creation asc",
    )


def get_item_price_versions(docnames):
    version_map = defaultdict(list)
    if not docnames:
        return version_map

    versions = frappe.get_all(
        "Version",
        filters={
            "ref_doctype": "Item Price",
            "docname": ["in", docnames],
        },
        fields=["name", "docname", "creation", "owner", "data"],
        order_by="docname asc, creation asc",
    )

    for version in versions:
        version_map[version.docname].append(version)

    return version_map


def build_history_rows(item_price_docs, version_map):
    rows = []

    for doc in item_price_docs:
        rows.extend(build_rows_for_item_price(doc, version_map.get(doc.name, [])))

    return sorted(
        rows,
        key=lambda row: (
            get_report_datetime(row.get("changed_on")),
            row.get("item_code") or "",
            row.get("price_list") or "",
            row.get("supplier") or "",
        ),
        reverse=True,
    )


def build_rows_for_item_price(doc, versions):
    current_state = get_current_state(doc)
    parsed_versions = []

    for version in versions:
        changes = extract_relevant_changes(version.data)
        if not changes:
            continue

        parsed_versions.append(
            frappe._dict(
                name=version.name,
                creation=get_datetime(version.creation),
                owner=version.owner,
                changes=changes,
            )
        )

    initial_state = current_state.copy()
    for version in reversed(parsed_versions):
        for fieldname, change in version.changes.items():
            initial_state[fieldname] = change["old"]

    rows = []
    baseline_date = initial_state.get("valid_from") or get_datetime(doc.creation)
    rows.append(
        make_row(
            doc=doc,
            state=initial_state,
            changed_on=baseline_date,
            changed_by=doc.owner,
            event_type="Initial Price",
            previous_rate=None,
            new_rate=flt(initial_state.get("price_list_rate")),
        )
    )

    state = initial_state.copy()
    for version in parsed_versions:
        previous_rate = flt(state.get("price_list_rate"))

        for fieldname, change in version.changes.items():
            state[fieldname] = change["new"]

        if "price_list_rate" not in version.changes:
            continue

        new_rate = flt(state.get("price_list_rate"))
        rows.append(
            make_row(
                doc=doc,
                state=state,
                changed_on=version.creation,
                changed_by=version.owner,
                event_type="Price Change",
                previous_rate=previous_rate,
                new_rate=new_rate,
            )
        )

    return rows


def make_row(doc, state, changed_on, changed_by, event_type, previous_rate, new_rate):
    change_amount = None
    change_percentage = None

    if previous_rate is not None:
        change_amount = flt(new_rate) - flt(previous_rate)
        if flt(previous_rate):
            change_percentage = (change_amount / flt(previous_rate)) * 100

    return {
        "changed_on": get_report_datetime(changed_on),
        "event_type": event_type,
        "change_direction": get_change_direction(previous_rate, new_rate, event_type),
        "item_price": doc.name,
        "item_code": state.get("item_code"),
        "item_name": state.get("item_name"),
        "supplier": state.get("supplier"),
        "price_list": state.get("price_list"),
        "uom": state.get("uom"),
        "previous_rate": previous_rate,
        "new_rate": flt(new_rate),
        "change_amount": change_amount,
        "change_percentage": change_percentage,
        "valid_from": state.get("valid_from"),
        "valid_upto": state.get("valid_upto"),
        "changed_by": changed_by,
        "currency": state.get("currency"),
    }


def get_report_datetime(value):
    return get_datetime(value or "1900-01-01 00:00:00")


def get_current_state(doc):
    state = {}
    for fieldname in TRACKED_FIELDS:
        state[fieldname] = normalize_field_value(fieldname, doc.get(fieldname))
    return state


def extract_relevant_changes(version_data):
    if not version_data:
        return {}

    try:
        payload = json.loads(version_data)
    except Exception:
        return {}

    changes = {}
    for change in payload.get("changed", []):
        if len(change) < 3:
            continue

        fieldname = change[0]
        if fieldname not in TRACKED_FIELDS:
            continue

        changes[fieldname] = {
            "old": normalize_field_value(fieldname, change[1]),
            "new": normalize_field_value(fieldname, change[2]),
        }

    return changes


def normalize_field_value(fieldname, value):
    if value in (None, ""):
        return None if fieldname in DATE_FIELDS else (0.0 if fieldname in NUMERIC_FIELDS else None)

    if fieldname in NUMERIC_FIELDS:
        return parse_numeric_value(value)

    if fieldname in DATE_FIELDS:
        return getdate(value)

    return value


def parse_numeric_value(value):
    if value in (None, ""):
        return 0.0

    if isinstance(value, (int, float)):
        return flt(value)

    cleaned_value = re.sub(r"[^0-9,.-]", "", str(value))
    if cleaned_value.count(",") and cleaned_value.count("."):
        cleaned_value = cleaned_value.replace(",", "")
    elif cleaned_value.count(",") and not cleaned_value.count("."):
        cleaned_value = cleaned_value.replace(",", "")

    return flt(cleaned_value)


def row_matches_filters(row, filters):
    changed_on = row.get("changed_on")
    if not changed_on:
        return False

    row_date = getdate(changed_on)
    if row_date < getdate(filters.from_date) or row_date > getdate(filters.to_date):
        return False

    if filters.get("item_code") and row.get("item_code") != filters.item_code:
        return False

    if filters.get("price_list") and row.get("price_list") != filters.price_list:
        return False

    if filters.get("supplier") and row.get("supplier") != filters.supplier:
        return False

    return True


def get_change_direction(previous_rate, new_rate, event_type):
    if event_type == "Initial Price":
        return "Initial"

    if previous_rate is None:
        return "Updated"

    if flt(new_rate) > flt(previous_rate):
        return "Increase"

    if flt(new_rate) < flt(previous_rate):
        return "Decrease"

    return "No Change"


def get_chart_data(data, filters):
    if not filters.get("item_code"):
        return None

    chart_rows = sorted(
        [row for row in data if row.get("item_code") == filters.item_code],
        key=lambda row: row.get("changed_on") or get_datetime("1900-01-01 00:00:00"),
    )

    if not chart_rows:
        return None

    labels = []
    label_index = {}
    dataset_points = defaultdict(dict)

    for row in chart_rows:
        label = get_datetime(row.get("changed_on")).strftime("%Y-%m-%d %H:%M")
        dataset_key = row.get("price_list") or _("No Price List")
        if row.get("supplier"):
            dataset_key = f"{dataset_key} / {row.get('supplier')}"

        if label not in label_index:
            label_index[label] = len(labels)
            labels.append(label)

        dataset_points[dataset_key][label] = flt(row.get("new_rate"))

    datasets = []
    for dataset_key, points in dataset_points.items():
        datasets.append(
            {
                "name": dataset_key,
                "values": [points.get(label) for label in labels],
            }
        )

    return {
        "data": {
            "labels": labels,
            "datasets": datasets,
        },
        "type": "line",
        "fieldtype": "Currency",
    }


def get_message(filters, data):
    if not data:
        return _("No Item Price fluctuation history found for the selected filters.")

    if not filters.get("item_code"):
        return _("Select an Item filter to display the Item Price trend chart.")

    return None

