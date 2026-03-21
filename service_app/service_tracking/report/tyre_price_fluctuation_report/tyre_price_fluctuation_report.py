# Copyright (c) 2026, Nickson and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from service_app.service_tracking.report.item_price_fluctuation_report import (
    item_price_fluctuation_report as base_report,
)
from service_app.service_tracking.tyre_analytics import set_default_date_filters


def execute(filters=None):
    filters = frappe._dict(filters or {})
    set_default_date_filters(filters)
    base_report.validate_filters(filters)

    columns = get_columns()
    item_price_docs, brand_map = get_tyre_item_price_docs(filters)
    if not item_price_docs:
        return columns, [], _("No tyre Item Price records found for the selected filters."), None

    version_map = base_report.get_item_price_versions([doc.name for doc in item_price_docs])
    all_rows = base_report.build_history_rows(item_price_docs, version_map)

    data = []
    for row in all_rows:
        row["tyre_brand"] = brand_map.get(row.get("item_code"))
        if not base_report.row_matches_filters(row, filters):
            continue
        if filters.get("brand") and (row.get("tyre_brand") or "") != filters.brand:
            continue
        data.append(row)

    chart = base_report.get_chart_data(data, filters)
    message = get_message(filters, data)

    return columns, data, message, chart


def get_columns():
    columns = list(base_report.get_columns())
    columns.insert(
        6,
        {
            "label": _("Tyre Brand"),
            "fieldname": "tyre_brand",
            "fieldtype": "Data",
            "width": 130,
        },
    )
    return columns


def get_tyre_item_price_docs(filters):
    tyre_item_group = frappe.db.get_value("Item Group", "Tyres", ["lft", "rgt"], as_dict=True)
    if not tyre_item_group:
        frappe.throw(_("Item Group Tyres was not found."))

    conditions = [
        "item_group.lft >= %(lft)s",
        "item_group.rgt <= %(rgt)s",
    ]
    values = {"lft": tyre_item_group.lft, "rgt": tyre_item_group.rgt}

    if filters.get("item_code"):
        conditions.append("item_price.item_code = %(item_code)s")
        values["item_code"] = filters.item_code

    if filters.get("price_list"):
        conditions.append("item_price.price_list = %(price_list)s")
        values["price_list"] = filters.price_list

    if filters.get("supplier"):
        conditions.append("item_price.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("brand"):
        conditions.append("COALESCE(item.brand, '') = %(brand)s")
        values["brand"] = filters.brand

    docs = frappe.db.sql(
        f"""
        SELECT
            item_price.name,
            item_price.item_code,
            item_price.item_name,
            item_price.price_list,
            item_price.supplier,
            item_price.uom,
            item_price.currency,
            item_price.price_list_rate,
            item_price.valid_from,
            item_price.valid_upto,
            item_price.creation,
            item_price.owner,
            item.brand AS tyre_brand
        FROM `tabItem Price` item_price
        INNER JOIN `tabItem` item
            ON item.name = item_price.item_code
        INNER JOIN `tabItem Group` item_group
            ON item_group.name = item.item_group
        WHERE {' AND '.join(conditions)}
        ORDER BY item_price.item_code ASC, item_price.price_list ASC, item_price.supplier ASC, item_price.valid_from ASC, item_price.creation ASC
        """,
        values,
        as_dict=True,
    )

    brand_map = {doc.item_code: doc.tyre_brand for doc in docs if doc.item_code}
    return docs, brand_map


def get_message(filters, data):
    if not data:
        return _("No tyre Item Price fluctuation history found for the selected filters.")

    if not filters.get("item_code"):
        return _("Select an Item filter to display the tyre price trend chart.")

    return None
