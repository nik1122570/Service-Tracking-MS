from collections import defaultdict
import json

import frappe
from frappe import _
from frappe.utils import add_months, date_diff, flt, getdate, today


def parse_multi_select_filter(values):
    if not values:
        return []

    if isinstance(values, list):
        return [value for value in values if value]

    if isinstance(values, str):
        try:
            parsed_values = json.loads(values)
        except Exception:
            parsed_values = [value.strip() for value in values.split(",") if value.strip()]

        if isinstance(parsed_values, str):
            return [parsed_values]

        return [value for value in parsed_values if value]

    return [values]


def set_default_date_filters(filters, months=12):
    if not filters.get("to_date"):
        filters.to_date = today()

    if not filters.get("from_date"):
        filters.from_date = add_months(getdate(filters.to_date), -months)


def validate_date_filters(filters, require_dates=True):
    if require_dates and (not filters.get("from_date") or not filters.get("to_date")):
        frappe.throw(_("From Date and To Date are required."))

    if filters.get("from_date") and filters.get("to_date"):
        if getdate(filters.from_date) > getdate(filters.to_date):
            frappe.throw(_("From Date cannot be greater than To Date."))


def get_default_currency():
    return frappe.db.get_single_value("Global Defaults", "default_currency")


def get_vehicle_details(vehicle_names):
    if not vehicle_names:
        return {}

    vehicles = frappe.get_all(
        "Vehicle",
        filters={"name": ["in", list(vehicle_names)]},
        fields=["name", "license_plate", "make", "model"],
    )

    return {vehicle.name: vehicle for vehicle in vehicles}


def get_tyre_request_rows(filters=None, ignore_date_filters=False):
    filters = frappe._dict(filters or {})
    vehicle_names = _get_vehicle_names(filters)
    conditions = ["request.docstatus = 1"]
    values = {}

    if not ignore_date_filters and filters.get("from_date") and filters.get("to_date"):
        conditions.append("request.request_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.from_date
        values["to_date"] = filters.to_date

    if vehicle_names:
        conditions.append("request.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicle_names)

    if filters.get("supplier"):
        conditions.append("request.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("project"):
        conditions.append("request.project = %(project)s")
        values["project"] = filters.project

    if filters.get("cost_center"):
        conditions.append("request.cost_center = %(cost_center)s")
        values["cost_center"] = filters.cost_center

    if filters.get("brand"):
        conditions.append("COALESCE(item.tyre_brand, '') = %(brand)s")
        values["brand"] = filters.brand

    if filters.get("item"):
        conditions.append("item.item = %(item)s")
        values["item"] = filters.item

    if filters.get("wheel_position"):
        conditions.append("item.wheel_position = %(wheel_position)s")
        values["wheel_position"] = filters.wheel_position

    if filters.get("serial_no"):
        conditions.append("COALESCE(item.worn_out_serial_no, '') = %(serial_no)s")
        values["serial_no"] = filters.serial_no

    return frappe.db.sql(
        f"""
        SELECT
            request.name AS tyre_request,
            request.request_date,
            request.vehicle,
            request.license_plate,
            request.odometer_reading,
            request.supplier,
            request.project,
            request.cost_center,
            request.total_qty,
            request.total_purchase_amount,
            request.price_list,
            item.name AS request_item_name,
            item.wheel_position,
            item.item,
            item.item_name,
            item.tyre_brand,
            item.qty,
            item.uom,
            item.rate,
            item.worn_out_serial_no,
            item.worn_out_brand,
            item.remarks
        FROM `tabTyre Request` request
        INNER JOIN `tabTyre Request Item` item
            ON item.parent = request.name
        WHERE {' AND '.join(conditions)}
        ORDER BY request.request_date ASC, request.name ASC, item.idx ASC
        """,
        values,
        as_dict=True,
    )


def get_tyre_purchase_rows(filters=None, ignore_date_filters=False):
    filters = frappe._dict(filters or {})
    vehicle_names = _get_vehicle_names(filters)
    conditions = [
        "po.docstatus = 1",
        "po.custom_tyre_request_link IS NOT NULL",
        "po.custom_tyre_request_link != ''",
    ]
    values = {}

    if not ignore_date_filters and filters.get("from_date") and filters.get("to_date"):
        conditions.append("po.transaction_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.from_date
        values["to_date"] = filters.to_date

    if vehicle_names:
        conditions.append("request.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicle_names)

    if filters.get("supplier"):
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("project"):
        conditions.append("po.project = %(project)s")
        values["project"] = filters.project

    if filters.get("cost_center"):
        conditions.append("po.cost_center = %(cost_center)s")
        values["cost_center"] = filters.cost_center

    if filters.get("brand"):
        conditions.append("COALESCE(item.brand, '') = %(brand)s")
        values["brand"] = filters.brand

    if filters.get("item"):
        conditions.append("poi.item_code = %(item)s")
        values["item"] = filters.item

    return frappe.db.sql(
        f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date,
            po.supplier,
            po.project,
            po.cost_center,
            po.custom_tyre_request_link AS tyre_request,
            request.vehicle,
            request.license_plate,
            poi.item_code AS item,
            poi.item_name,
            item.brand AS tyre_brand,
            poi.qty,
            poi.uom,
            poi.rate,
            (poi.qty * poi.rate) AS amount
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi
            ON poi.parent = po.name
        INNER JOIN `tabTyre Request` request
            ON request.name = po.custom_tyre_request_link
        LEFT JOIN `tabItem` item
            ON item.name = poi.item_code
        WHERE {' AND '.join(conditions)}
        ORDER BY po.transaction_date ASC, po.name ASC, poi.idx ASC
        """,
        values,
        as_dict=True,
    )


def get_tyre_receiving_rows(filters=None, ignore_date_filters=False):
    filters = frappe._dict(filters or {})
    vehicle_names = _get_vehicle_names(filters)
    conditions = ["receipt.docstatus = 1"]
    values = {}

    if not ignore_date_filters and filters.get("from_date") and filters.get("to_date"):
        conditions.append("receipt.received_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.from_date
        values["to_date"] = filters.to_date

    if vehicle_names:
        conditions.append("receipt.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicle_names)

    if filters.get("supplier"):
        conditions.append("receipt.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("project"):
        conditions.append("request.project = %(project)s")
        values["project"] = filters.project

    if filters.get("cost_center"):
        conditions.append("request.cost_center = %(cost_center)s")
        values["cost_center"] = filters.cost_center

    if filters.get("brand"):
        conditions.append(
            "COALESCE(receipt_item.worn_out_brand, receipt_item.tyre_brand, '') = %(brand)s"
        )
        values["brand"] = filters.brand

    if filters.get("item"):
        conditions.append("receipt_item.item = %(item)s")
        values["item"] = filters.item

    if filters.get("wheel_position"):
        conditions.append("receipt_item.wheel_position = %(wheel_position)s")
        values["wheel_position"] = filters.wheel_position

    if filters.get("serial_no"):
        conditions.append("COALESCE(receipt_item.worn_out_serial_no, '') = %(serial_no)s")
        values["serial_no"] = filters.serial_no

    return frappe.db.sql(
        f"""
        SELECT
            receipt.name AS tyre_receiving_note,
            receipt.tyre_request,
            receipt.received_date,
            receipt.received_by,
            receipt.status,
            receipt.vehicle,
            receipt.license_plate,
            receipt.supplier,
            request.project,
            request.cost_center,
            receipt_item.name AS receiving_item_name,
            receipt_item.wheel_position,
            receipt_item.item,
            receipt_item.item_name,
            receipt_item.tyre_brand,
            receipt_item.worn_out_brand,
            receipt_item.worn_out_serial_no,
            receipt_item.qty_expected,
            receipt_item.qty_received,
            receipt_item.uom,
            receipt_item.condition,
            receipt_item.disposition,
            receipt_item.remarks
        FROM `tabTyre Receiving Note` receipt
        INNER JOIN `tabTyre Receiving Note Item` receipt_item
            ON receipt_item.parent = receipt.name
        LEFT JOIN `tabTyre Request` request
            ON request.name = receipt.tyre_request
        WHERE {' AND '.join(conditions)}
        ORDER BY receipt.received_date ASC, receipt.name ASC, receipt_item.idx ASC
        """,
        values,
        as_dict=True,
    )


def get_tyre_disposal_rows(filters=None, ignore_date_filters=False):
    filters = frappe._dict(filters or {})
    vehicle_names = _get_vehicle_names(filters)
    conditions = ["disposal.docstatus = 1"]
    values = {}

    if not ignore_date_filters and filters.get("from_date") and filters.get("to_date"):
        conditions.append("disposal.posting_date BETWEEN %(from_date)s AND %(to_date)s")
        values["from_date"] = filters.from_date
        values["to_date"] = filters.to_date

    if vehicle_names:
        conditions.append("disposal.vehicle IN %(vehicles)s")
        values["vehicles"] = tuple(vehicle_names)

    if filters.get("supplier"):
        conditions.append("request.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("project"):
        conditions.append("request.project = %(project)s")
        values["project"] = filters.project

    if filters.get("cost_center"):
        conditions.append("request.cost_center = %(cost_center)s")
        values["cost_center"] = filters.cost_center

    if filters.get("brand"):
        conditions.append(
            "COALESCE(disposal_item.worn_out_brand, disposal_item.tyre_brand, '') = %(brand)s"
        )
        values["brand"] = filters.brand

    if filters.get("item"):
        conditions.append("disposal_item.item = %(item)s")
        values["item"] = filters.item

    if filters.get("wheel_position"):
        conditions.append("disposal_item.wheel_position = %(wheel_position)s")
        values["wheel_position"] = filters.wheel_position

    if filters.get("serial_no"):
        conditions.append("COALESCE(disposal_item.worn_out_serial_no, '') = %(serial_no)s")
        values["serial_no"] = filters.serial_no

    return frappe.db.sql(
        f"""
        SELECT
            disposal.name AS tyre_disposal_note,
            disposal.tyre_receiving_note,
            disposal.tyre_request,
            disposal.posting_date,
            disposal.disposed_by,
            disposal.disposal_method,
            disposal.status,
            disposal.vehicle,
            disposal.license_plate,
            request.supplier,
            request.project,
            request.cost_center,
            disposal_item.name AS disposal_item_name,
            disposal_item.source_receiving_item,
            disposal_item.wheel_position,
            disposal_item.item,
            disposal_item.item_name,
            disposal_item.tyre_brand,
            disposal_item.worn_out_brand,
            disposal_item.worn_out_serial_no,
            disposal_item.qty_available,
            disposal_item.qty_out,
            disposal_item.uom,
            disposal_item.condition,
            disposal_item.disposition,
            disposal_item.remarks
        FROM `tabTyre Disposal Note` disposal
        INNER JOIN `tabTyre Disposal Note Item` disposal_item
            ON disposal_item.parent = disposal.name
        LEFT JOIN `tabTyre Request` request
            ON request.name = disposal.tyre_request
        WHERE {' AND '.join(conditions)}
        ORDER BY disposal.posting_date ASC, disposal.name ASC, disposal_item.idx ASC
        """,
        values,
        as_dict=True,
    )


def get_tyre_history_rows(filters=None):
    filters = frappe._dict(filters or {})
    request_rows = get_tyre_request_rows(filters, ignore_date_filters=True)
    grouped_rows = defaultdict(list)

    for row in request_rows:
        grouped_rows[(row.vehicle, row.wheel_position)].append(frappe._dict(row))

    data = []
    for group_rows in grouped_rows.values():
        group_rows.sort(key=lambda row: (getdate(row.request_date), row.tyre_request, row.request_item_name))

        for index, row in enumerate(group_rows):
            next_row = group_rows[index + 1] if index + 1 < len(group_rows) else None
            request_date = getdate(row.request_date)
            next_request_date = getdate(next_row.request_date) if next_row else None
            start_odometer = flt(row.odometer_reading)
            end_odometer = flt(next_row.odometer_reading) if next_row else None
            distance_covered = None
            if next_row:
                distance_covered = flt(end_odometer) - flt(start_odometer)
                if distance_covered < 0:
                    distance_covered = None

            data.append(
                {
                    "tyre_request": row.tyre_request,
                    "request_item_name": row.request_item_name,
                    "request_date": request_date,
                    "vehicle": row.vehicle,
                    "license_plate": row.license_plate,
                    "supplier": row.supplier,
                    "project": row.project,
                    "cost_center": row.cost_center,
                    "wheel_position": row.wheel_position,
                    "item": row.item,
                    "item_name": row.item_name,
                    "tyre_brand": row.tyre_brand,
                    "qty": flt(row.qty),
                    "rate": flt(row.rate),
                    "amount": flt(row.qty) * flt(row.rate),
                    "worn_out_serial_no": row.worn_out_serial_no,
                    "worn_out_brand": row.worn_out_brand,
                    "start_odometer": start_odometer,
                    "next_tyre_request": next_row.tyre_request if next_row else None,
                    "next_request_date": next_request_date,
                    "end_odometer": end_odometer,
                    "distance_covered": distance_covered,
                    "days_in_service": date_diff(next_request_date, request_date) if next_row else None,
                    "replacement_brand": next_row.tyre_brand if next_row else None,
                    "current_status": "Replaced" if next_row else "Active",
                }
            )

    from_date = getdate(filters.from_date) if filters.get("from_date") else None
    to_date = getdate(filters.to_date) if filters.get("to_date") else None
    filtered_data = []
    for row in data:
        if from_date and row["request_date"] < from_date:
            continue
        if to_date and row["request_date"] > to_date:
            continue
        if filters.get("brand") and (row.get("tyre_brand") or "") != filters.brand:
            continue
        if filters.get("wheel_position") and row.get("wheel_position") != filters.wheel_position:
            continue
        filtered_data.append(row)

    return filtered_data


def get_outstanding_tyre_return_rows(filters=None):
    filters = frappe._dict(filters or {})
    request_rows = get_tyre_request_rows(filters)
    if not request_rows:
        return []

    request_map = {}
    for row in request_rows:
        bucket = request_map.setdefault(
            row.tyre_request,
            {
                "tyre_request": row.tyre_request,
                "request_date": row.request_date,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "project": row.project,
                "cost_center": row.cost_center,
                "requested_qty": 0.0,
                "requested_amount": 0.0,
            },
        )
        bucket["requested_qty"] += flt(row.qty)
        bucket["requested_amount"] += flt(row.qty) * flt(row.rate)

    receiving_rows = get_tyre_receiving_rows(filters, ignore_date_filters=True)
    receiving_map = defaultdict(lambda: {"received_qty": 0.0, "status": "Not Created", "tyre_receiving_note": None})
    for row in receiving_rows:
        bucket = receiving_map[row.tyre_request]
        bucket["received_qty"] += flt(row.qty_received)
        bucket["status"] = row.status
        bucket["tyre_receiving_note"] = row.tyre_receiving_note
        bucket["received_date"] = row.received_date

    outstanding_rows = []
    for request_name, request_data in request_map.items():
        receipt_data = receiving_map.get(request_name, {})
        received_qty = flt(receipt_data.get("received_qty"))
        requested_qty = flt(request_data["requested_qty"])
        outstanding_qty = requested_qty - received_qty
        status = receipt_data.get("status") or "Not Created"
        if outstanding_qty <= 0 and status == "Fully Received":
            continue

        row = dict(request_data)
        row["received_qty"] = received_qty
        row["outstanding_qty"] = max(outstanding_qty, 0)
        row["tyre_receiving_note"] = receipt_data.get("tyre_receiving_note")
        row["receiving_status"] = status
        row["days_outstanding"] = date_diff(today(), getdate(request_data["request_date"]))
        outstanding_rows.append(row)

    return sorted(
        outstanding_rows,
        key=lambda row: (getdate(row["request_date"]), row["tyre_request"]),
        reverse=True,
    )


def get_tyre_scrap_aging_rows(filters=None):
    filters = frappe._dict(filters or {})
    receipt_rows = get_tyre_receiving_rows(filters, ignore_date_filters=True)
    disposal_rows = get_tyre_disposal_rows(filters, ignore_date_filters=True)
    disposed_qty_by_receipt_item = defaultdict(float)
    from_date = getdate(filters.from_date) if filters.get("from_date") else None
    to_date = getdate(filters.to_date) if filters.get("to_date") else None

    for row in disposal_rows:
        if row.get("source_receiving_item"):
            disposed_qty_by_receipt_item[row.source_receiving_item] += flt(row.qty_out)

    data = []
    for row in receipt_rows:
        received_date = getdate(row.received_date)
        if from_date and received_date < from_date:
            continue
        if to_date and received_date > to_date:
            continue

        receipt_item_name = row.receiving_item_name
        balance_qty = flt(row.qty_received) - flt(disposed_qty_by_receipt_item.get(receipt_item_name))
        if balance_qty <= 0:
            continue

        age_days = max(date_diff(today(), received_date), 0)
        data.append(
            {
                "tyre_receiving_note": row.tyre_receiving_note,
                "tyre_request": row.tyre_request,
                "received_date": received_date,
                "vehicle": row.vehicle,
                "license_plate": row.license_plate,
                "supplier": row.supplier,
                "project": row.project,
                "cost_center": row.cost_center,
                "wheel_position": row.wheel_position,
                "item": row.item,
                "item_name": row.item_name,
                "worn_out_brand": row.worn_out_brand,
                "worn_out_serial_no": row.worn_out_serial_no,
                "qty_received": flt(row.qty_received),
                "qty_disposed": flt(disposed_qty_by_receipt_item.get(receipt_item_name)),
                "balance_qty": balance_qty,
                "age_days": age_days,
                "aging_bucket": get_aging_bucket(age_days),
                "received_by": row.received_by,
                "remarks": row.remarks,
            }
        )

    return sorted(data, key=lambda row: (row["age_days"], row["received_date"]), reverse=True)


def get_aging_bucket(age_days):
    if age_days <= 30:
        return "0-30 Days"
    if age_days <= 60:
        return "31-60 Days"
    if age_days <= 90:
        return "61-90 Days"
    return "90+ Days"


def get_budget_amount_by_dimension(dimension):
    if dimension not in {"cost_center", "project"}:
        return {}

    budget_against = "Cost Center" if dimension == "cost_center" else "Project"
    rows = frappe.db.sql(
        f"""
        SELECT
            budget.{dimension} AS dimension_value,
            COALESCE(SUM(account.budget_amount), 0) AS budget_amount
        FROM `tabBudget` budget
        INNER JOIN `tabBudget Account` account
            ON account.parent = budget.name
        WHERE budget.docstatus < 2
          AND budget.budget_against = %(budget_against)s
          AND COALESCE(budget.{dimension}, '') != ''
        GROUP BY budget.{dimension}
        """,
        {"budget_against": budget_against},
        as_dict=True,
    )

    return {
        row.dimension_value: flt(row.budget_amount)
        for row in rows
        if row.dimension_value
    }


def _get_vehicle_names(filters):
    vehicles = parse_multi_select_filter(filters.get("vehicles"))
    if filters.get("vehicle"):
        vehicles.append(filters.vehicle)
    return sorted(set(vehicle for vehicle in vehicles if vehicle))
