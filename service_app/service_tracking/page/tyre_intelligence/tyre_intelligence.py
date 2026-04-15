from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import (
    add_days,
    add_months,
    date_diff,
    flt,
    fmt_money,
    get_first_day,
    getdate,
    now_datetime,
    nowdate,
)

from service_app.service_tracking.tyre_analytics import (
    get_default_currency,
    get_tyre_disposal_rows,
    get_tyre_history_rows,
    get_tyre_purchase_invoice_rows,
    get_tyre_receiving_rows,
    get_tyre_request_rows,
)


FORECAST_HISTORY_MONTHS = 6
FORECAST_HORIZON_MONTHS = 3
EARLY_REPLACEMENT_DAYS = 90
EARLY_REPLACEMENT_DISTANCE = 10000
LEDGER_WARNING_DAYS = 60
LEDGER_CRITICAL_DAYS = 90
LEDGER_REPORT_FROM_DATE = "2000-01-01"
BOARD_LIMIT = 6


@frappe.whitelist()
def get_dashboard_data(filters=None):
    filters = frappe._dict(frappe.parse_json(filters) or {}) if filters else frappe._dict()
    normalized_filters = _normalize_filters(filters)
    previous_filters = _get_previous_period_filters(normalized_filters)

    invoice_rows = get_tyre_purchase_invoice_rows(normalized_filters)
    previous_invoice_rows = get_tyre_purchase_invoice_rows(previous_filters)
    request_rows = get_tyre_request_rows(normalized_filters)
    history_rows = get_tyre_history_rows(normalized_filters)
    ledger_rows = _get_ledger_balance_rows(normalized_filters)

    summary = _get_summary(invoice_rows, request_rows, ledger_rows)
    previous_summary = _get_summary(previous_invoice_rows, [], [])
    brand_rows = _get_brand_performance_rows(history_rows, invoice_rows)
    project_rows = _get_project_pressure_rows(request_rows, invoice_rows, history_rows)
    forecast = _get_forecast_outlook(normalized_filters)
    best_brand = _get_best_brand_row(brand_rows)
    watch_brand = _get_watch_brand_row(brand_rows)
    top_project = project_rows[0] if project_rows else None

    return {
        "currency": get_default_currency(),
        "generated_at": now_datetime().strftime("%d %b %Y %H:%M"),
        "scope_label": _("Tyre invoices, tyre lifecycle history, and tyre ledger balances"),
        "focus_label": _get_focus_label(normalized_filters),
        "summary_cards": _build_summary_cards(
            normalized_filters,
            summary,
            previous_summary,
            best_brand,
            watch_brand,
            top_project,
            forecast,
        ),
        "charts": {
            "monthly_spend_trend": _get_monthly_spend_trend(normalized_filters, invoice_rows),
            "forecast_outlook": forecast["chart"],
            "brand_performance": _get_brand_performance_chart(brand_rows),
            "brand_spend_mix": _get_brand_spend_mix_chart(invoice_rows),
            "project_pressure": _get_project_pressure_chart(project_rows),
            "ledger_balance": _get_ledger_balance_chart(ledger_rows),
        },
        "insights": _build_insights(
            summary,
            previous_summary,
            best_brand,
            watch_brand,
            top_project,
            ledger_rows,
            forecast,
        ),
        "brand_board": _build_brand_board(brand_rows, normalized_filters),
        "project_board": _build_project_board(project_rows, normalized_filters),
        "ledger_board": _build_ledger_board(ledger_rows, normalized_filters),
    }


def _normalize_filters(filters):
    to_date = getdate(filters.get("to_date") or nowdate())
    from_date = getdate(filters.get("from_date") or get_first_day(add_months(to_date, -11)))

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    return frappe._dict(
        {
            "from_date": str(from_date),
            "to_date": str(to_date),
            "supplier": (filters.get("supplier") or "").strip(),
            "project": (filters.get("project") or "").strip(),
            "vehicle": (filters.get("vehicle") or "").strip(),
            "brand": (filters.get("brand") or "").strip(),
        }
    )


def _get_previous_period_filters(filters):
    period_days = max(date_diff(filters.to_date, filters.from_date) + 1, 1)
    previous_to_date = add_days(filters.from_date, -1)
    previous_from_date = add_days(previous_to_date, -(period_days - 1))

    return frappe._dict(
        {
            "from_date": str(previous_from_date),
            "to_date": str(previous_to_date),
            "supplier": filters.supplier,
            "project": filters.project,
            "vehicle": filters.vehicle,
            "brand": filters.brand,
        }
    )


def _get_focus_label(filters):
    parts = []
    if filters.project:
        parts.append(_("Project: {0}").format(filters.project))
    if filters.brand:
        parts.append(_("Brand: {0}").format(filters.brand))
    if filters.supplier:
        parts.append(_("Supplier: {0}").format(filters.supplier))
    if filters.vehicle:
        parts.append(_("Vehicle: {0}").format(filters.vehicle))

    return " | ".join(parts) if parts else _("Management Portfolio View")


def _get_summary(invoice_rows, request_rows, ledger_rows):
    invoices = {row.get("purchase_invoice") for row in invoice_rows if row.get("purchase_invoice")}
    requests = {row.get("tyre_request") for row in request_rows if row.get("tyre_request")}
    vehicles = {
        row.get("vehicle") for row in list(invoice_rows) + list(request_rows)
        if row.get("vehicle")
    }

    total_spend = sum(flt(row.get("amount")) for row in invoice_rows)
    billed_qty = sum(flt(row.get("qty")) for row in invoice_rows)
    ledger_balance_qty = sum(flt(row.get("balance_qty")) for row in ledger_rows)
    aged_balance_qty = sum(
        flt(row.get("balance_qty"))
        for row in ledger_rows
        if flt(row.get("age_days")) >= LEDGER_WARNING_DAYS
    )

    return frappe._dict(
        {
            "total_spend": flt(total_spend),
            "billed_qty": flt(billed_qty),
            "invoice_count": len(invoices),
            "request_count": len(requests),
            "vehicle_count": len(vehicles),
            "average_rate": (flt(total_spend) / flt(billed_qty)) if billed_qty else 0,
            "ledger_balance_qty": flt(ledger_balance_qty),
            "aged_balance_qty": flt(aged_balance_qty),
        }
    )


def _get_brand_performance_rows(history_rows, invoice_rows):
    grouped = defaultdict(
        lambda: {
            "vehicles": set(),
            "suppliers": set(),
            "fitted_qty": 0.0,
            "active_cycles": 0,
            "replaced_cycles": 0,
            "early_replacements": 0,
            "days_samples": [],
            "distance_samples": [],
            "total_spend": 0.0,
            "billed_qty": 0.0,
            "invoice_count": set(),
        }
    )

    for row in history_rows:
        brand = _get_brand_label(row.get("tyre_brand"))
        bucket = grouped[brand]
        bucket["fitted_qty"] += flt(row.get("qty"))
        if row.get("vehicle"):
            bucket["vehicles"].add(row.get("vehicle"))
        if row.get("supplier"):
            bucket["suppliers"].add(row.get("supplier"))
        if row.get("next_request_date"):
            bucket["replaced_cycles"] += 1
            if row.get("days_in_service") is not None:
                bucket["days_samples"].append(flt(row.get("days_in_service")))
            if row.get("distance_covered") is not None:
                bucket["distance_samples"].append(flt(row.get("distance_covered")))
            if _is_early_replacement(row):
                bucket["early_replacements"] += 1
        else:
            bucket["active_cycles"] += 1

    for row in invoice_rows:
        brand = _get_brand_label(row.get("tyre_brand"))
        bucket = grouped[brand]
        bucket["total_spend"] += flt(row.get("amount"))
        bucket["billed_qty"] += flt(row.get("qty"))
        if row.get("purchase_invoice"):
            bucket["invoice_count"].add(row.get("purchase_invoice"))

    weighted_distance_total = 0.0
    weighted_distance_count = 0
    weighted_days_total = 0.0
    weighted_days_count = 0
    for bucket in grouped.values():
        weighted_distance_total += sum(bucket["distance_samples"])
        weighted_distance_count += len(bucket["distance_samples"])
        weighted_days_total += sum(bucket["days_samples"])
        weighted_days_count += len(bucket["days_samples"])

    portfolio_distance = (weighted_distance_total / weighted_distance_count) if weighted_distance_count else 0
    portfolio_days = (weighted_days_total / weighted_days_count) if weighted_days_count else 0

    rows = []
    for brand, bucket in grouped.items():
        average_distance = (
            sum(bucket["distance_samples"]) / len(bucket["distance_samples"])
            if bucket["distance_samples"]
            else None
        )
        average_days = (
            sum(bucket["days_samples"]) / len(bucket["days_samples"])
            if bucket["days_samples"]
            else None
        )
        replaced_cycles = bucket["replaced_cycles"]
        early_rate = ((bucket["early_replacements"] / replaced_cycles) * 100) if replaced_cycles else None
        is_ranked = replaced_cycles >= 2 and average_distance is not None
        performance_score = _get_brand_performance_score(
            average_distance,
            average_days,
            early_rate,
            portfolio_distance,
            portfolio_days,
            is_ranked,
        )

        row = frappe._dict(
            {
                "brand": brand,
                "vehicles": len(bucket["vehicles"]),
                "suppliers": len(bucket["suppliers"]),
                "fitted_qty": flt(bucket["fitted_qty"]),
                "active_cycles": bucket["active_cycles"],
                "replaced_cycles": replaced_cycles,
                "early_replacements": bucket["early_replacements"],
                "early_replacement_rate": early_rate,
                "average_distance": average_distance,
                "average_days": average_days,
                "total_spend": flt(bucket["total_spend"]),
                "billed_qty": flt(bucket["billed_qty"]),
                "average_rate": (
                    flt(bucket["total_spend"]) / flt(bucket["billed_qty"])
                    if bucket["billed_qty"]
                    else 0
                ),
                "invoice_count": len(bucket["invoice_count"]),
                "performance_score": performance_score,
                "is_ranked": is_ranked,
                "confidence_label": _get_brand_confidence_label(replaced_cycles),
            }
        )
        row["tone"] = _get_brand_tone(row)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            0 if row.is_ranked else 1,
            -(row.performance_score or 0),
            -flt(row.replaced_cycles),
            -flt(row.total_spend),
            row.brand,
        )
    )

    ranked_rows = [row for row in rows if row.is_ranked]
    if ranked_rows:
        ranked_rows[0]["badge"] = _("Leader")
        if len(ranked_rows) > 1:
            ranked_rows[-1]["badge"] = _("Under Watch")

    for row in rows:
        if row.get("badge"):
            continue
        if not row.is_ranked:
            row["badge"] = _("Sample Building")
        elif (row.performance_score or 0) >= 105:
            row["badge"] = _("Strong")
        elif (row.performance_score or 0) < 95:
            row["badge"] = _("Soft")
        else:
            row["badge"] = _("Stable")

    return rows


def _get_brand_performance_score(
    average_distance,
    average_days,
    early_replacement_rate,
    portfolio_distance,
    portfolio_days,
    is_ranked,
):
    if not is_ranked:
        return None

    components = []
    if average_distance is not None and portfolio_distance:
        components.append((0.55, _relative_index(average_distance, portfolio_distance)))
    if average_days is not None and portfolio_days:
        components.append((0.20, _relative_index(average_days, portfolio_days)))
    if early_replacement_rate is not None:
        components.append((0.25, _clamp(100 - flt(early_replacement_rate), 25, 140)))

    if not components:
        return None

    weight_total = sum(weight for weight, _value in components)
    return sum(weight * value for weight, value in components) / weight_total


def _get_project_pressure_rows(request_rows, invoice_rows, history_rows):
    grouped = defaultdict(
        lambda: {
            "requests": set(),
            "request_lines": 0,
            "requested_qty": 0.0,
            "vehicles": set(),
            "brands": set(),
            "suppliers": set(),
            "invoices": set(),
            "billed_qty": 0.0,
            "total_spend": 0.0,
            "replaced_cycles": 0,
            "early_replacements": 0,
        }
    )

    for row in request_rows:
        project = _get_project_label(row.get("project"))
        bucket = grouped[project]
        if row.get("tyre_request"):
            bucket["requests"].add(row.get("tyre_request"))
        bucket["request_lines"] += 1
        bucket["requested_qty"] += flt(row.get("qty"))
        if row.get("vehicle"):
            bucket["vehicles"].add(row.get("vehicle"))
        if row.get("tyre_brand"):
            bucket["brands"].add(row.get("tyre_brand"))
        if row.get("supplier"):
            bucket["suppliers"].add(row.get("supplier"))

    for row in invoice_rows:
        project = _get_project_label(row.get("project"))
        bucket = grouped[project]
        if row.get("purchase_invoice"):
            bucket["invoices"].add(row.get("purchase_invoice"))
        bucket["billed_qty"] += flt(row.get("qty"))
        bucket["total_spend"] += flt(row.get("amount"))
        if row.get("vehicle"):
            bucket["vehicles"].add(row.get("vehicle"))
        if row.get("tyre_brand"):
            bucket["brands"].add(row.get("tyre_brand"))
        if row.get("supplier"):
            bucket["suppliers"].add(row.get("supplier"))

    for row in history_rows:
        project = _get_project_label(row.get("project"))
        bucket = grouped[project]
        if row.get("next_request_date"):
            bucket["replaced_cycles"] += 1
            if _is_early_replacement(row):
                bucket["early_replacements"] += 1

    total_spend = sum(flt(bucket["total_spend"]) for bucket in grouped.values())
    total_requested_qty = sum(flt(bucket["requested_qty"]) for bucket in grouped.values())

    changes_per_vehicle_values = []
    for bucket in grouped.values():
        vehicle_count = len(bucket["vehicles"])
        if vehicle_count:
            changes_per_vehicle_values.append(flt(bucket["requested_qty"]) / vehicle_count)

    portfolio_change_density = (
        sum(changes_per_vehicle_values) / len(changes_per_vehicle_values)
        if changes_per_vehicle_values
        else 0
    )

    rows = []
    for project, bucket in grouped.items():
        vehicle_count = len(bucket["vehicles"])
        requested_qty = flt(bucket["requested_qty"])
        total_project_spend = flt(bucket["total_spend"])
        early_rate = (
            (bucket["early_replacements"] / bucket["replaced_cycles"]) * 100
            if bucket["replaced_cycles"]
            else None
        )
        changes_per_vehicle = (requested_qty / vehicle_count) if vehicle_count else requested_qty
        spend_share = (total_project_spend / total_spend) * 100 if total_spend else 0
        qty_share = (requested_qty / total_requested_qty) * 100 if total_requested_qty else 0
        pressure_index = (
            spend_share * 0.50
            + qty_share * 0.25
            + min(changes_per_vehicle * 8, 20)
            + min(flt(early_rate or 0) * 0.20, 20)
        )

        row = frappe._dict(
            {
                "project": project,
                "request_count": len(bucket["requests"]),
                "request_lines": bucket["request_lines"],
                "requested_qty": requested_qty,
                "vehicle_count": vehicle_count,
                "brand_count": len(bucket["brands"]),
                "supplier_count": len(bucket["suppliers"]),
                "invoice_count": len(bucket["invoices"]),
                "billed_qty": flt(bucket["billed_qty"]),
                "total_spend": total_project_spend,
                "average_rate": (
                    total_project_spend / flt(bucket["billed_qty"])
                    if bucket["billed_qty"]
                    else 0
                ),
                "replaced_cycles": bucket["replaced_cycles"],
                "early_replacement_rate": early_rate,
                "changes_per_vehicle": changes_per_vehicle,
                "spend_share": spend_share,
                "qty_share": qty_share,
                "pressure_index": pressure_index,
            }
        )
        row["tone"] = _get_project_tone(row, portfolio_change_density)
        row["meaning"] = _get_project_meaning(row, portfolio_change_density)
        rows.append(row)

    rows.sort(
        key=lambda row: (
            -flt(row.pressure_index),
            -flt(row.total_spend),
            -flt(row.requested_qty),
            row.project,
        )
    )
    return rows


def _get_ledger_balance_rows(filters):
    ledger_filters = frappe._dict(
        {
            "from_date": LEDGER_REPORT_FROM_DATE,
            "to_date": filters.to_date,
            "supplier": filters.supplier,
            "project": filters.project,
            "vehicle": filters.vehicle,
            "brand": filters.brand,
        }
    )
    receipt_rows = get_tyre_receiving_rows(ledger_filters)
    disposal_rows = get_tyre_disposal_rows(ledger_filters)

    disposed_qty_by_receipt_item = defaultdict(float)
    for row in disposal_rows:
        if row.get("source_receiving_item"):
            disposed_qty_by_receipt_item[row.get("source_receiving_item")] += flt(row.get("qty_out"))

    snapshot_date = getdate(filters.to_date)
    rows = []
    for row in receipt_rows:
        received_date = getdate(row.get("received_date"))
        if received_date > snapshot_date:
            continue

        receipt_item_name = row.get("receiving_item_name")
        balance_qty = flt(row.get("qty_received")) - flt(disposed_qty_by_receipt_item.get(receipt_item_name))
        if balance_qty <= 0:
            continue

        age_days = max(date_diff(snapshot_date, received_date), 0)
        brand = _get_brand_label(row.get("worn_out_brand") or row.get("tyre_brand"))

        rows.append(
            frappe._dict(
                {
                    "title": _get_ledger_title(brand, row.get("worn_out_serial_no"), row.get("wheel_position")),
                    "brand": brand,
                    "tyre_receiving_note": row.get("tyre_receiving_note"),
                    "tyre_request": row.get("tyre_request"),
                    "vehicle": row.get("vehicle"),
                    "license_plate": row.get("license_plate"),
                    "supplier": row.get("supplier"),
                    "project": row.get("project"),
                    "wheel_position": row.get("wheel_position"),
                    "item": row.get("item"),
                    "item_name": row.get("item_name"),
                    "worn_out_serial_no": row.get("worn_out_serial_no"),
                    "received_date": received_date,
                    "balance_qty": balance_qty,
                    "age_days": age_days,
                    "aging_bucket": _get_aging_bucket(age_days),
                    "tone": _get_ledger_tone(age_days),
                    "remarks": row.get("remarks"),
                }
            )
        )

    return sorted(
        rows,
        key=lambda row: (-flt(row.age_days), -flt(row.balance_qty), row.received_date, row.title),
    )


def _get_monthly_spend_trend(filters, invoice_rows=None):
    invoice_rows = invoice_rows if invoice_rows is not None else get_tyre_purchase_invoice_rows(filters)
    month_starts = _get_month_sequence(filters.from_date, filters.to_date)
    totals_by_month = defaultdict(float)

    for row in invoice_rows:
        month_start = getdate(row.get("posting_date")).strftime("%Y-%m-01")
        totals_by_month[month_start] += flt(row.get("amount"))

    return {
        "type": "line",
        "fieldtype": "Currency",
        "colors": ["#D97706"],
        "data": {
            "labels": [getdate(month_start).strftime("%b %Y") for month_start in month_starts],
            "datasets": [
                {
                    "name": _("Spend"),
                    "values": [flt(totals_by_month.get(month_start, 0)) for month_start in month_starts],
                }
            ],
        },
        "empty_message": _("No billed tyre spend was found for the selected window."),
    }


def _get_forecast_outlook(filters):
    history_end = getdate(filters.to_date)
    history_start = get_first_day(add_months(history_end, -(FORECAST_HISTORY_MONTHS - 1)))
    history_filters = frappe._dict(
        {
            "from_date": str(history_start),
            "to_date": filters.to_date,
            "supplier": filters.supplier,
            "project": filters.project,
            "vehicle": filters.vehicle,
            "brand": filters.brand,
        }
    )

    history_rows = get_tyre_purchase_invoice_rows(history_filters)
    history_chart = _get_monthly_spend_trend(history_filters, history_rows)
    history_values = history_chart["data"]["datasets"][0]["values"]
    forecast_values = _forecast_values(history_values, FORECAST_HORIZON_MONTHS)
    history_labels = history_chart["data"]["labels"]
    forecast_labels = [
        add_months(get_first_day(history_end), step).strftime("%b %Y")
        for step in range(1, FORECAST_HORIZON_MONTHS + 1)
    ]
    baseline = history_values[-1] if history_values else 0

    return {
        "next_month_prediction": forecast_values[0] if forecast_values else 0,
        "history_months": len(history_values),
        "chart": {
            "type": "line",
            "fieldtype": "Currency",
            "colors": ["#0F766E"],
            "data": {
                "labels": ([history_labels[-1]] + forecast_labels) if history_labels else forecast_labels,
                "datasets": [
                    {
                        "name": _("Projected Spend"),
                        "values": ([baseline] + forecast_values) if history_labels else forecast_values,
                    }
                ],
            },
            "empty_message": _("Not enough billed tyre history exists yet to project the next months."),
        },
    }


def _forecast_values(values, horizon):
    cleaned_values = [flt(value) for value in values if value is not None]
    if not cleaned_values:
        return [0] * horizon

    moving_window = cleaned_values[-min(3, len(cleaned_values)) :]
    moving_average = sum(moving_window) / len(moving_window)

    if len(cleaned_values) == 1:
        return [flt(moving_average)] * horizon

    sample_size = len(cleaned_values)
    x_mean = sum(range(sample_size)) / sample_size
    y_mean = sum(cleaned_values) / sample_size
    denominator = sum((index - x_mean) ** 2 for index in range(sample_size))
    slope = (
        sum((index - x_mean) * (value - y_mean) for index, value in enumerate(cleaned_values)) / denominator
        if denominator
        else 0
    )
    intercept = y_mean - (slope * x_mean)

    projections = []
    for step in range(horizon):
        regression_value = intercept + slope * (sample_size + step)
        blended_value = max((regression_value + moving_average) / 2, 0)
        projections.append(flt(blended_value))

    return projections


def _get_brand_performance_chart(brand_rows):
    ranked_rows = [row for row in brand_rows if row.is_ranked]
    if len(ranked_rows) <= BOARD_LIMIT:
        selected_rows = ranked_rows
    else:
        selected_rows = ranked_rows[:3] + [row for row in reversed(ranked_rows[-3:]) if row not in ranked_rows[:3]]

    return {
        "type": "bar",
        "fieldtype": "Float",
        "colors": ["#0F766E"],
        "data": {
            "labels": [row.brand for row in selected_rows],
            "datasets": [
                {
                    "name": _("Lifecycle Score"),
                    "values": [flt(row.performance_score or 0) for row in selected_rows],
                }
            ],
        },
        "empty_message": _("At least two closed tyre lifecycles are needed before brand performance can be ranked."),
    }


def _get_brand_spend_mix_chart(invoice_rows):
    grouped = defaultdict(float)
    for row in invoice_rows:
        grouped[_get_brand_label(row.get("tyre_brand"))] += flt(row.get("amount"))

    rows = sorted(grouped.items(), key=lambda entry: (-entry[1], entry[0]))[:BOARD_LIMIT]
    return {
        "type": "bar",
        "fieldtype": "Currency",
        "colors": ["#C2410C"],
        "data": {
            "labels": [label for label, _value in rows],
            "datasets": [
                {
                    "name": _("Spend"),
                    "values": [flt(value) for _label, value in rows],
                }
            ],
        },
        "empty_message": _("No billed brand spend is available for the current filters."),
    }


def _get_project_pressure_chart(project_rows):
    selected_rows = project_rows[:BOARD_LIMIT]
    return {
        "type": "bar",
        "fieldtype": "Float",
        "colors": ["#7C3AED"],
        "data": {
            "labels": [row.project for row in selected_rows],
            "datasets": [
                {
                    "name": _("Pressure Index"),
                    "values": [flt(row.pressure_index) for row in selected_rows],
                }
            ],
        },
        "empty_message": _("No project-linked tyre activity was found for the selected filters."),
    }


def _get_ledger_balance_chart(ledger_rows):
    ordered_buckets = ["0-30 Days", "31-60 Days", "61-90 Days", "90+ Days"]
    totals_by_bucket = {bucket: 0.0 for bucket in ordered_buckets}

    for row in ledger_rows:
        totals_by_bucket[row.aging_bucket] += flt(row.balance_qty)

    return {
        "type": "bar",
        "fieldtype": "Float",
        "colors": ["#0F766E", "#D97706", "#EA580C", "#B42318"],
        "data": {
            "labels": ordered_buckets,
            "datasets": [
                {
                    "name": _("Balance Qty"),
                    "values": [flt(totals_by_bucket[bucket]) for bucket in ordered_buckets],
                }
            ],
        },
        "empty_message": _("No positive tyre ledger balances remain in the selected snapshot."),
    }


def _build_summary_cards(filters, summary, previous_summary, best_brand, watch_brand, top_project, forecast):
    cost_by_vehicle_report_options = _get_cost_by_vehicle_report_options(filters)
    cost_by_brand_report_options = _get_cost_by_brand_report_options(filters)
    lifecycle_report_options = _get_lifecycle_report_options(filters)
    repeat_report_options = _get_repeat_report_options(filters)
    budget_report_options = _get_budget_report_options(filters)
    ledger_report_options = _get_ledger_report_options(filters)

    return [
        {
            "label": _("Tyre Spend"),
            "value": summary.total_spend,
            "fieldtype": "Currency",
            "tone": _get_spend_tone(summary.total_spend, previous_summary.total_spend),
            "trend": _get_change_text(summary.total_spend, previous_summary.total_spend, fieldtype="Currency"),
            "note": _("{0} invoices across {1} tyre requests and {2} vehicles.").format(
                summary.invoice_count,
                summary.request_count,
                summary.vehicle_count,
            ),
            "route": ["query-report", "Tyre Cost by Vehicle Report"],
            "route_options": cost_by_vehicle_report_options,
        },
        {
            "label": _("Tyres Billed"),
            "value": summary.billed_qty,
            "fieldtype": "Float",
            "tone": _get_consumption_tone(summary.billed_qty, previous_summary.billed_qty),
            "trend": _get_change_text(summary.billed_qty, previous_summary.billed_qty, fieldtype="Float"),
            "note": _("Average invoice rate is {0}.").format(_format_metric(summary.average_rate, "Currency")),
            "route": ["query-report", "Tyre Cost by Brand Report"],
            "route_options": cost_by_brand_report_options,
        },
        {
            "label": _("Top Brand"),
            "value": best_brand.brand if best_brand else _("Sample Building"),
            "fieldtype": "Data",
            "tone": best_brand.tone if best_brand else "neutral",
            "trend": (
                _("Score {0} with {1} closed cycles").format(
                    f"{flt(best_brand.performance_score):.1f}",
                    best_brand.replaced_cycles,
                )
                if best_brand
                else _("Need at least two closed tyre lifecycles to rank brands.")
            ),
            "note": (
                _("{0} avg km, {1}% early replacements.").format(
                    _format_metric(best_brand.average_distance, "Float"),
                    f"{flt(best_brand.early_replacement_rate or 0):.1f}",
                )
                if best_brand
                else _("The lifecycle model will rank brands once more replacement history exists.")
            ),
            "route": ["query-report", "Tyre Lifespan Analysis Report"],
            "route_options": lifecycle_report_options,
        },
        {
            "label": _("Brand Under Watch"),
            "value": watch_brand.brand if watch_brand else _("No Watch Brand Yet"),
            "fieldtype": "Data",
            "tone": watch_brand.tone if watch_brand else "neutral",
            "trend": (
                _("Score {0} with {1}% early replacements").format(
                    f"{flt(watch_brand.performance_score):.1f}",
                    f"{flt(watch_brand.early_replacement_rate or 0):.1f}",
                )
                if watch_brand
                else _("Only one ranked brand exists, so no lagging brand is identified yet.")
            ),
            "note": (
                _("Average lifecycle is {0} km across {1} closed cycles.").format(
                    _format_metric(watch_brand.average_distance, "Float"),
                    watch_brand.replaced_cycles,
                )
                if watch_brand
                else _("More closed-lifecycle history is required before a weaker brand can be isolated.")
            ),
            "route": ["query-report", "Repeat Early Replacement Report"],
            "route_options": repeat_report_options,
        },
        {
            "label": _("Project Hotspot"),
            "value": top_project.project if top_project else _("No Project Pressure"),
            "fieldtype": "Data",
            "tone": top_project.tone if top_project else "neutral",
            "trend": (
                _("Pressure {0} | {1}% of spend").format(
                    f"{flt(top_project.pressure_index):.1f}",
                    f"{flt(top_project.spend_share):.1f}",
                )
                if top_project
                else _("No project-linked tyre activity in this window.")
            ),
            "note": top_project.meaning if top_project else _("Project pressure will appear as tyre requests and invoices accumulate."),
            "route": ["query-report", "Tyre Budget vs Actual Report"],
            "route_options": budget_report_options,
        },
        {
            "label": _("Tyre Ledger Balance"),
            "value": summary.ledger_balance_qty,
            "fieldtype": "Float",
            "tone": "critical" if summary.aged_balance_qty else "positive",
            "trend": _("{0} tyres aged beyond {1} days").format(
                _format_metric(summary.aged_balance_qty, "Float"),
                LEDGER_WARNING_DAYS,
            ),
            "note": _("Positive balance remaining in the tyre receiving-versus-disposal ledger snapshot."),
            "route": ["query-report", "Tyre Ledger Report"],
            "route_options": ledger_report_options,
        },
        {
            "label": _("Forecast Next Month"),
            "value": forecast["next_month_prediction"],
            "fieldtype": "Currency",
            "tone": "neutral",
            "trend": _("Projection built from the last {0} months of billed history").format(
                forecast["history_months"]
            ),
            "note": _("Trend blend: recent moving average plus direction of change."),
        },
    ]


def _build_insights(summary, previous_summary, best_brand, watch_brand, top_project, ledger_rows, forecast):
    if not summary.total_spend and not ledger_rows:
        return [
            {
                "title": _("No Tyre Intelligence Yet"),
                "tone": "neutral",
                "body": _("The selected filters do not match billed tyre activity or positive tyre ledger balances."),
            }
        ]

    insights = [
        {
            "title": _("Spend Momentum"),
            "tone": _get_spend_tone(summary.total_spend, previous_summary.total_spend),
            "body": _get_spend_momentum_text(summary.total_spend, previous_summary.total_spend),
        }
    ]

    if best_brand:
        insights.append(
            {
                "title": _("Brand Leader"),
                "tone": best_brand.tone,
                "body": _(
                    "{0} is leading the closed-lifecycle ranking with score {1}, average distance {2}, and early replacements at {3}%."
                ).format(
                    best_brand.brand,
                    f"{flt(best_brand.performance_score):.1f}",
                    _format_metric(best_brand.average_distance, "Float"),
                    f"{flt(best_brand.early_replacement_rate or 0):.1f}",
                ),
            }
        )

    if watch_brand:
        insights.append(
            {
                "title": _("Brand Under Watch"),
                "tone": watch_brand.tone,
                "body": _(
                    "{0} is the weakest ranked brand right now. Its lifecycle score is {1} with early replacements at {2}%."
                ).format(
                    watch_brand.brand,
                    f"{flt(watch_brand.performance_score):.1f}",
                    f"{flt(watch_brand.early_replacement_rate or 0):.1f}",
                ),
            }
        )

    if top_project:
        insights.append(
            {
                "title": _("Project Pressure"),
                "tone": top_project.tone,
                "body": _(
                    "{0} is driving {1}% of billed tyre spend and {2} tyre changes per vehicle. {3}"
                ).format(
                    top_project.project,
                    f"{flt(top_project.spend_share):.1f}",
                    f"{flt(top_project.changes_per_vehicle):.1f}",
                    top_project.meaning,
                ),
            }
        )

    if ledger_rows:
        oldest_balance = ledger_rows[0]
        insights.append(
            {
                "title": _("Ledger Retention Risk"),
                "tone": oldest_balance.tone,
                "body": _(
                    "{0} still has {1} tyres on hand after {2} days in the ledger snapshot. Review whether disposal or store clearance is stalled."
                ).format(
                    oldest_balance.title,
                    _format_metric(oldest_balance.balance_qty, "Float"),
                    _format_metric(oldest_balance.age_days, "Int"),
                ),
            }
        )

    insights.append(
        {
            "title": _("Forward View"),
            "tone": "neutral",
            "body": _(
                "Projected billed tyre spend for the next month is {0}, based on {1} months of recent invoice history."
            ).format(
                _format_metric(forecast["next_month_prediction"], "Currency"),
                forecast["history_months"],
            ),
        }
    )

    return insights[:5]


def _build_brand_board(brand_rows, filters):
    selected_rows = brand_rows[:4]
    watch_brand = _get_watch_brand_row(brand_rows)
    if watch_brand and watch_brand not in selected_rows:
        selected_rows.append(watch_brand)

    board = []
    for row in selected_rows[:BOARD_LIMIT]:
        board.append(
            {
                "title": row.brand,
                "headline": (
                    _("Score {0}").format(f"{flt(row.performance_score):.1f}")
                    if row.performance_score is not None
                    else _("Open lifecycle sample")
                ),
                "meta": _(
                    "{0} closed cycles | Avg distance {1} | Early replacements {2}% | Spend {3}"
                ).format(
                    row.replaced_cycles,
                    _format_metric(row.average_distance, "Float"),
                    f"{flt(row.early_replacement_rate or 0):.1f}" if row.early_replacement_rate is not None else "0.0",
                    _format_metric(row.total_spend, "Currency"),
                ),
                "note": _get_brand_board_note(row),
                "tone": row.tone,
                "badge": row.badge,
                "route": ["query-report", "Tyre Lifespan Analysis Report"],
                "route_options": _get_lifecycle_report_options(filters, row.brand),
            }
        )

    return board


def _build_project_board(project_rows, filters):
    return [
        {
            "title": row.project,
            "headline": _("{0} tyre changes across {1} vehicles").format(
                _format_metric(row.requested_qty, "Float"),
                row.vehicle_count,
            ),
            "meta": _("Spend {0} | Pressure {1} | {2} brands | {3}% early replacements").format(
                _format_metric(row.total_spend, "Currency"),
                f"{flt(row.pressure_index):.1f}",
                row.brand_count,
                f"{flt(row.early_replacement_rate or 0):.1f}",
            ),
            "note": row.meaning,
            "tone": row.tone,
            "badge": _("{0}% spend share").format(f"{flt(row.spend_share):.1f}"),
            "route": ["query-report", "Tyre Budget vs Actual Report"],
            "route_options": _get_budget_report_options(filters, row.project),
        }
        for row in project_rows[:BOARD_LIMIT]
    ]


def _build_ledger_board(ledger_rows, filters):
    return [
        {
            "title": row.title,
            "headline": _("{0} tyres still on hand").format(_format_metric(row.balance_qty, "Float")),
            "meta": _("{0} | Received {1} | {2} days | Vehicle {3}").format(
                row.aging_bucket,
                row.received_date.strftime("%d %b %Y"),
                _format_metric(row.age_days, "Int"),
                row.vehicle or _("Not Tagged"),
            ),
            "note": _(
                "Tyre Request {0}. Wheel {1}. Review disposal flow if this balance should have moved out already."
            ).format(
                row.tyre_request or _("Not Linked"),
                row.wheel_position or _("Not Set"),
            ),
            "tone": row.tone,
            "badge": row.brand,
            "route": ["query-report", "Tyre Ledger Report"],
            "route_options": _get_ledger_report_options(filters, row.brand, row.vehicle, row.worn_out_serial_no),
        }
        for row in ledger_rows[:BOARD_LIMIT]
    ]


def _get_best_brand_row(brand_rows):
    ranked_rows = [row for row in brand_rows if row.is_ranked]
    return ranked_rows[0] if ranked_rows else None


def _get_watch_brand_row(brand_rows):
    ranked_rows = [row for row in brand_rows if row.is_ranked]
    return ranked_rows[-1] if len(ranked_rows) > 1 else None


def _get_brand_board_note(row):
    if not row.is_ranked:
        return _("Closed-lifecycle history is still building for this brand, so the score is not final.")
    if (row.performance_score or 0) >= 105:
        return _("This brand is sustaining above-portfolio tyre life and is currently the strongest performer.")
    if (row.performance_score or 0) < 95:
        return _("This brand is trailing the portfolio and should be reviewed for fitment, route, and supply quality.")
    return _("This brand is broadly in line with the portfolio and should be monitored as more history closes.")


def _get_project_meaning(row, portfolio_change_density):
    if row.changes_per_vehicle >= max(portfolio_change_density * 1.5, 3):
        if flt(row.early_replacement_rate or 0) >= 25:
            return _(
                "Change density is materially above the portfolio average and early replacements are elevated, which points to harsh operating conditions or avoidable tyre-life loss."
            )
        return _(
            "This project is consuming tyre changes faster than the rest of the portfolio, suggesting a tougher duty cycle or heavier utilization."
        )

    if flt(row.early_replacement_rate or 0) >= 25:
        return _(
            "Change volume is not extreme, but early replacements are high. Check alignment, inflation control, load profile, and route conditions."
        )

    if flt(row.spend_share) >= 30:
        return _(
            "This is the main driver of current tyre budget consumption and should be treated as the priority project for management attention."
        )

    return _("Tyre activity is comparatively stable relative to the rest of the filtered portfolio.")


def _get_spend_momentum_text(current_value, previous_value):
    if previous_value <= 0 and current_value <= 0:
        return _("No billed tyre spend was recorded in either the current or previous comparison window.")

    if previous_value <= 0 < current_value:
        return _("This window contains billed tyre spend while the previous equal-length window had none.")

    change_amount = current_value - previous_value
    change_percentage = (change_amount / previous_value) * 100 if previous_value else 0
    direction = _("up") if change_amount > 0 else _("down") if change_amount < 0 else _("flat")

    return _("Billed tyre spend is {0} {1}% versus the previous equal-length window.").format(
        direction,
        f"{abs(change_percentage):.1f}",
    )


def _get_spend_tone(current_value, previous_value):
    if previous_value <= 0:
        return "neutral"
    if current_value > previous_value * 1.15:
        return "critical"
    if current_value < previous_value * 0.90:
        return "positive"
    return "neutral"


def _get_consumption_tone(current_value, previous_value):
    if previous_value <= 0:
        return "neutral"
    if current_value > previous_value * 1.15:
        return "warning"
    if current_value < previous_value * 0.90:
        return "positive"
    return "neutral"


def _get_brand_tone(row):
    if not row.is_ranked:
        return "neutral"
    if (row.performance_score or 0) < 95 or flt(row.early_replacement_rate or 0) >= 35:
        return "critical"
    if (row.performance_score or 0) >= 105 and flt(row.early_replacement_rate or 0) <= 15:
        return "positive"
    if flt(row.early_replacement_rate or 0) >= 20:
        return "warning"
    return "neutral"


def _get_project_tone(row, portfolio_change_density):
    if flt(row.early_replacement_rate or 0) >= 25 or row.changes_per_vehicle >= max(portfolio_change_density * 1.5, 3):
        return "critical"
    if flt(row.spend_share) >= 20 or row.changes_per_vehicle >= max(portfolio_change_density * 1.15, 2):
        return "warning"
    return "positive" if row.total_spend or row.requested_qty else "neutral"


def _get_ledger_tone(age_days):
    if age_days >= LEDGER_CRITICAL_DAYS:
        return "critical"
    if age_days >= LEDGER_WARNING_DAYS:
        return "warning"
    return "positive"


def _get_brand_confidence_label(replaced_cycles):
    if replaced_cycles >= 5:
        return _("High Confidence")
    if replaced_cycles >= 3:
        return _("Medium Confidence")
    if replaced_cycles >= 2:
        return _("Initial Read")
    if replaced_cycles == 1:
        return _("Early Read")
    return _("Open Lifecycles Only")


def _get_common_report_options(filters):
    options = {"from_date": filters.from_date, "to_date": filters.to_date}
    if filters.brand:
        options["brand"] = filters.brand
    if filters.supplier:
        options["supplier"] = filters.supplier
    if filters.project:
        options["project"] = filters.project
    return options


def _get_cost_by_vehicle_report_options(filters):
    options = {"from_date": filters.from_date, "to_date": filters.to_date}
    if filters.vehicle:
        options["vehicles"] = [filters.vehicle]
    if filters.supplier:
        options["supplier"] = filters.supplier
    if filters.project:
        options["project"] = filters.project
    return options


def _get_cost_by_brand_report_options(filters):
    return _get_common_report_options(filters)


def _get_repeat_report_options(filters):
    options = {"from_date": filters.from_date, "to_date": filters.to_date}
    if filters.vehicle:
        options["vehicles"] = [filters.vehicle]
    if filters.supplier:
        options["supplier"] = filters.supplier
    if filters.brand:
        options["brand"] = filters.brand
    return options


def _get_lifecycle_report_options(filters, brand=None):
    options = {"from_date": filters.from_date, "to_date": filters.to_date}
    if brand or filters.brand:
        options["brand"] = brand or filters.brand
    if filters.vehicle:
        options["vehicles"] = [filters.vehicle]
    return options


def _get_budget_report_options(filters, project=None):
    options = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
        "budget_dimension": "Project",
    }
    if filters.vehicle:
        options["vehicles"] = [filters.vehicle]
    if filters.supplier:
        options["supplier"] = filters.supplier
    if filters.brand:
        options["brand"] = filters.brand
    if project or filters.project:
        options["project"] = project or filters.project
    return options


def _get_ledger_report_options(filters, brand=None, vehicle=None, serial_no=None):
    options = {
        "from_date": LEDGER_REPORT_FROM_DATE,
        "to_date": filters.to_date,
    }
    if vehicle or filters.vehicle:
        options["vehicle"] = vehicle or filters.vehicle
    if brand or filters.brand:
        options["brand"] = brand or filters.brand
    if serial_no:
        options["serial_no"] = serial_no
    return options


def _get_month_sequence(from_date, to_date):
    month_starts = []
    cursor = get_first_day(getdate(from_date))
    end = get_first_day(getdate(to_date))

    while cursor <= end:
        month_starts.append(str(cursor))
        cursor = get_first_day(add_months(cursor, 1))

    return month_starts


def _get_brand_label(brand):
    return brand or _("Unspecified Brand")


def _get_project_label(project):
    return project or _("Unassigned Project")


def _get_ledger_title(brand, serial_no, wheel_position):
    if serial_no:
        return _("{0} / Serial {1}").format(brand, serial_no)
    if wheel_position:
        return _("{0} / Wheel {1}").format(brand, wheel_position)
    return brand


def _get_aging_bucket(age_days):
    if age_days <= 30:
        return "0-30 Days"
    if age_days <= 60:
        return "31-60 Days"
    if age_days <= 90:
        return "61-90 Days"
    return "90+ Days"


def _is_early_replacement(row):
    days_in_service = row.get("days_in_service")
    distance_covered = row.get("distance_covered")
    day_breach = days_in_service is not None and flt(days_in_service) < EARLY_REPLACEMENT_DAYS
    distance_breach = distance_covered is not None and flt(distance_covered) < EARLY_REPLACEMENT_DISTANCE
    return day_breach or distance_breach


def _relative_index(value, baseline):
    if not baseline:
        return 100
    return _clamp((flt(value) / flt(baseline)) * 100, 40, 160)


def _clamp(value, minimum, maximum):
    return max(minimum, min(flt(value), maximum))


def _get_change_text(current_value, previous_value, fieldtype="Currency"):
    if previous_value <= 0 and current_value <= 0:
        return _("Flat versus previous window")
    if previous_value <= 0 < current_value:
        return _("New activity versus a zero-base previous window")

    difference = current_value - previous_value
    percent_change = (difference / previous_value) * 100 if previous_value else 0
    direction = _("up") if difference > 0 else _("down") if difference < 0 else _("flat")
    return _("{0} {1}% versus previous window").format(direction, f"{abs(percent_change):.1f}")


def _format_metric(value, fieldtype="Float"):
    if value is None:
        return _("Not Available") if fieldtype == "Data" else "0"
    if fieldtype == "Currency":
        return fmt_money(flt(value), currency=get_default_currency())
    if fieldtype == "Percent":
        return f"{flt(value):.1f}"
    if fieldtype == "Int":
        return f"{int(round(flt(value))):,}"
    if fieldtype == "Data":
        return str(value)
    return f"{flt(value):,.1f}"
