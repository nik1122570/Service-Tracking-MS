from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, flt, get_first_day, getdate, now_datetime, nowdate


FORECAST_HISTORY_MONTHS = 6
FORECAST_HORIZON_MONTHS = 3
DUE_SOON_DAYS = 30
OVERDUE_LOOKBACK_DAYS = 30
SERVICE_HISTORY_MONTHS = 18


@frappe.whitelist()
def get_dashboard_data(filters=None):
    filters = frappe._dict(frappe.parse_json(filters) or {}) if filters else frappe._dict()
    normalized_filters = _normalize_filters(filters)

    summary = _get_period_summary(normalized_filters)
    previous_filters = _get_previous_period_filters(normalized_filters)
    previous_summary = _get_period_summary(previous_filters)
    repeat_service_count = _get_repeat_service_vehicle_count(normalized_filters)
    vehicle_breakdown = _get_top_vehicle_costs(normalized_filters)
    supplier_breakdown = _get_top_supplier_costs(normalized_filters)
    monthly_trend = _get_monthly_spend_trend(normalized_filters)
    forecast = _get_forecast_outlook(normalized_filters)
    due_soon_watchlist = _get_due_soon_vehicles(normalized_filters)

    return {
        "currency": frappe.db.get_single_value("Global Defaults", "default_currency"),
        "generated_at": now_datetime().strftime("%d %b %Y %H:%M"),
        "filters": normalized_filters,
        "summary_cards": _build_summary_cards(
            normalized_filters,
            summary,
            previous_summary,
            forecast,
            due_soon_watchlist,
            repeat_service_count,
        ),
        "charts": {
            "monthly_spend_trend": monthly_trend,
            "forecast_outlook": forecast["chart"],
            "vehicle_spend": vehicle_breakdown["chart"],
            "supplier_spend": supplier_breakdown["chart"],
        },
        "insights": _build_insights(
            summary,
            previous_summary,
            supplier_breakdown["rows"],
            vehicle_breakdown["rows"],
            forecast,
            due_soon_watchlist,
            repeat_service_count,
        ),
        "watchlist": due_soon_watchlist,
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
            "vehicle": (filters.get("vehicle") or "").strip(),
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
            "vehicle": filters.vehicle,
        }
    )


def _get_invoice_conditions(filters, from_date=None, to_date=None):
    conditions = [
        "pi.docstatus = 1",
        "pii.parenttype = 'Purchase Invoice'",
        "COALESCE(pii.purchase_order, '') != ''",
        "COALESCE(po.custom_job_card_link, '') != ''",
    ]
    values = {}

    if from_date and to_date:
        conditions.append("pi.posting_date BETWEEN %(from_date)s AND %(to_date)s")
        values.update({"from_date": from_date, "to_date": to_date})

    if filters.get("supplier"):
        conditions.append("pi.supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("vehicle"):
        conditions.append("jc.vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    return conditions, values


def _get_period_summary(filters):
    conditions, values = _get_invoice_conditions(filters, filters.from_date, filters.to_date)
    result = frappe.db.sql(
        f"""
        SELECT
            COALESCE(SUM(pii.base_net_amount), 0) AS total_spend,
            COALESCE(
                SUM(
                    CASE
                        WHEN COALESCE(jc.custom_default_labour_item, '') != ''
                         AND pii.item_code = jc.custom_default_labour_item
                        THEN pii.base_net_amount
                        ELSE 0
                    END
                ),
                0
            ) AS labour_spend,
            COUNT(DISTINCT pi.name) AS invoice_count,
            COUNT(DISTINCT jc.vehicle) AS vehicle_count
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = po.custom_job_card_link
        WHERE {' AND '.join(conditions)}
        """,
        values,
        as_dict=True,
    )[0]

    total_spend = flt(result.total_spend)
    labour_spend = flt(result.labour_spend)
    spare_spend = max(total_spend - labour_spend, 0)
    invoice_count = int(result.invoice_count or 0)

    return frappe._dict(
        {
            "total_spend": total_spend,
            "labour_spend": labour_spend,
            "spare_spend": spare_spend,
            "invoice_count": invoice_count,
            "vehicle_count": int(result.vehicle_count or 0),
            "average_invoice_value": (total_spend / invoice_count) if invoice_count else 0,
        }
    )


def _get_repeat_service_vehicle_count(filters):
    conditions = [
        "docstatus = 1",
        "COALESCE(vehicle, '') != ''",
        "service_date BETWEEN %(from_date)s AND %(to_date)s",
    ]
    values = {
        "from_date": filters.from_date,
        "to_date": filters.to_date,
    }

    if filters.get("supplier"):
        conditions.append("supplier = %(supplier)s")
        values["supplier"] = filters.supplier

    if filters.get("vehicle"):
        conditions.append("vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    return int(
        frappe.db.sql(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT vehicle
                FROM `tabEAH Job Card`
                WHERE {' AND '.join(conditions)}
                GROUP BY vehicle
                HAVING COUNT(*) >= 2
            ) repeat_vehicle_rows
            """,
            values,
        )[0][0]
        or 0
    )


def _get_top_vehicle_costs(filters, limit=8):
    conditions, values = _get_invoice_conditions(filters, filters.from_date, filters.to_date)
    conditions.append("COALESCE(jc.vehicle, '') != ''")

    rows = frappe.db.sql(
        f"""
        SELECT
            jc.vehicle AS label,
            COALESCE(SUM(pii.base_net_amount), 0) AS value
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = po.custom_job_card_link
        WHERE {' AND '.join(conditions)}
        GROUP BY jc.vehicle
        ORDER BY value DESC, jc.vehicle ASC
        LIMIT {limit}
        """,
        values,
        as_dict=True,
    )

    chart = _build_bar_chart(_("Vehicle Spend"), rows, "#C46A0A")
    return {"rows": rows, "chart": chart}


def _get_top_supplier_costs(filters, limit=8):
    conditions, values = _get_invoice_conditions(filters, filters.from_date, filters.to_date)
    conditions.append("COALESCE(pi.supplier, '') != ''")

    rows = frappe.db.sql(
        f"""
        SELECT
            pi.supplier AS label,
            COALESCE(SUM(pii.base_net_amount), 0) AS value
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = po.custom_job_card_link
        WHERE {' AND '.join(conditions)}
        GROUP BY pi.supplier
        ORDER BY value DESC, pi.supplier ASC
        LIMIT {limit}
        """,
        values,
        as_dict=True,
    )

    chart = _build_bar_chart(_("Supplier Spend"), rows, "#8B5E34")
    return {"rows": rows, "chart": chart}


def _get_monthly_spend_trend(filters):
    month_starts = _get_month_sequence(filters.from_date, filters.to_date)
    conditions, values = _get_invoice_conditions(filters, filters.from_date, filters.to_date)

    rows = frappe.db.sql(
        f"""
        SELECT
            DATE_FORMAT(pi.posting_date, '%%Y-%%m-01') AS month_start,
            COALESCE(SUM(pii.base_net_amount), 0) AS total_spend
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = po.custom_job_card_link
        WHERE {' AND '.join(conditions)}
        GROUP BY YEAR(pi.posting_date), MONTH(pi.posting_date)
        ORDER BY YEAR(pi.posting_date), MONTH(pi.posting_date)
        """,
        values,
        as_dict=True,
    )

    totals_by_month = {str(getdate(row.month_start)): flt(row.total_spend) for row in rows}
    labels = [getdate(month_start).strftime("%b %Y") for month_start in month_starts]
    values = [flt(totals_by_month.get(month_start, 0)) for month_start in month_starts]

    return {
        "type": "line",
        "fieldtype": "Currency",
        "colors": ["#B45309"],
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "name": _("Spend"),
                    "values": values,
                }
            ],
        },
        "empty_message": _("No billed maintenance spend found for the selected window."),
    }


def _get_forecast_outlook(filters):
    history_end = getdate(filters.to_date)
    history_start = get_first_day(add_months(history_end, -(FORECAST_HISTORY_MONTHS - 1)))
    history_filters = frappe._dict(
        {
            "from_date": str(history_start),
            "to_date": filters.to_date,
            "supplier": filters.supplier,
            "vehicle": filters.vehicle,
        }
    )

    history_chart = _get_monthly_spend_trend(history_filters)
    history_values = history_chart["data"]["datasets"][0]["values"]
    forecast_values = _forecast_values(history_values, FORECAST_HORIZON_MONTHS)
    history_labels = history_chart["data"]["labels"]
    forecast_labels = [
        add_months(get_first_day(history_end), offset).strftime("%b %Y")
        for offset in range(1, FORECAST_HORIZON_MONTHS + 1)
    ]
    baseline_value = history_values[-1] if history_values else 0
    projection_values = [baseline_value] + forecast_values

    return {
        "next_month_prediction": forecast_values[0] if forecast_values else 0,
        "history_months": len(history_values),
        "chart": {
            "type": "line",
            "fieldtype": "Currency",
            "colors": ["#0F766E"],
            "data": {
                "labels": [history_labels[-1]] + forecast_labels if history_labels else forecast_labels,
                "datasets": [
                    {
                        "name": _("Projected Spend"),
                        "values": projection_values if history_labels else forecast_values,
                    }
                ],
            },
            "empty_message": _("Not enough history yet to project future maintenance spend."),
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


def _get_due_soon_vehicles(filters):
    history_start = add_months(nowdate(), -SERVICE_HISTORY_MONTHS)
    conditions = [
        "docstatus = 1",
        "COALESCE(vehicle, '') != ''",
        "service_date >= %(history_start)s",
    ]
    values = {"history_start": history_start}

    if filters.get("vehicle"):
        conditions.append("vehicle = %(vehicle)s")
        values["vehicle"] = filters.vehicle

    rows = frappe.db.sql(
        f"""
        SELECT vehicle, service_date
        FROM `tabEAH Job Card`
        WHERE {' AND '.join(conditions)}
        ORDER BY vehicle ASC, service_date ASC
        """,
        values,
        as_dict=True,
    )

    service_dates_by_vehicle = defaultdict(list)
    for row in rows:
        service_dates_by_vehicle[row.vehicle].append(getdate(row.service_date))

    vehicle_details = _get_vehicle_details(service_dates_by_vehicle.keys())
    today = getdate(nowdate())
    watchlist = []

    for vehicle, service_dates in service_dates_by_vehicle.items():
        unique_dates = sorted(set(service_dates))
        if len(unique_dates) < 2:
            continue

        intervals = [
            date_diff(unique_dates[index + 1], unique_dates[index])
            for index in range(len(unique_dates) - 1)
            if date_diff(unique_dates[index + 1], unique_dates[index]) > 0
        ]
        if not intervals:
            continue

        average_interval_days = round(sum(intervals) / len(intervals))
        next_service_date = getdate(add_days(unique_dates[-1], average_interval_days))
        days_until_due = date_diff(next_service_date, today)

        if not (-OVERDUE_LOOKBACK_DAYS <= days_until_due <= DUE_SOON_DAYS):
            continue

        recent_services = sum(1 for service_date in unique_dates if date_diff(today, service_date) <= 180)
        tone = "critical" if days_until_due < 0 else "warning"
        status = _("Overdue") if days_until_due < 0 else _("Due Soon")
        plate = vehicle_details.get(vehicle, {}).get("license_plate")
        title = vehicle if not plate else f"{vehicle} · {plate}"

        watchlist.append(
            {
                "title": title,
                "vehicle": vehicle,
                "status": status,
                "tone": tone,
                "meta": _(
                    "Last serviced on {0}. Predicted next service on {1}. Average interval: {2} days. Recent services in 180 days: {3}."
                ).format(
                    unique_dates[-1].strftime("%d %b %Y"),
                    next_service_date.strftime("%d %b %Y"),
                    average_interval_days,
                    recent_services,
                ),
                "route": ["List", "EAH Job Card", "List"],
                "route_options": {"vehicle": vehicle},
                "days_until_due": days_until_due,
            }
        )

    return sorted(watchlist, key=lambda row: (row["days_until_due"], row["vehicle"]))[:8]


def _get_vehicle_details(vehicle_names):
    vehicle_names = [vehicle for vehicle in vehicle_names if vehicle]
    if not vehicle_names:
        return {}

    vehicle_rows = frappe.get_all(
        "Vehicle",
        filters={"name": ["in", vehicle_names]},
        fields=["name", "license_plate"],
    )

    return {row.name: row for row in vehicle_rows}


def _build_bar_chart(dataset_name, rows, color):
    return {
        "type": "bar",
        "fieldtype": "Currency",
        "colors": [color],
        "data": {
            "labels": [row.label for row in rows],
            "datasets": [
                {
                    "name": dataset_name,
                    "values": [flt(row.value) for row in rows],
                }
            ],
        },
        "empty_message": _("No matching rows for the selected filters."),
    }


def _build_summary_cards(filters, summary, previous_summary, forecast, due_soon_watchlist, repeat_service_count):
    purchase_invoice_route = ["List", "Purchase Invoice", "List"]
    purchase_invoice_route_options = _get_purchase_invoice_route_options(filters)
    job_card_route = ["List", "EAH Job Card", "List"]
    job_card_route_options = _get_job_card_route_options(filters)

    return [
        {
            "label": _("Maintenance Spend"),
            "value": summary.total_spend,
            "fieldtype": "Currency",
            "tone": _get_spend_tone(summary.total_spend, previous_summary.total_spend),
            "trend": _get_change_text(summary.total_spend, previous_summary.total_spend),
            "note": _("{0} submitted invoices across {1} serviced vehicles.").format(
                summary.invoice_count,
                summary.vehicle_count,
            ),
            "route": purchase_invoice_route,
            "route_options": purchase_invoice_route_options,
        },
        {
            "label": _("Spare Spend"),
            "value": summary.spare_spend,
            "fieldtype": "Currency",
            "tone": "warning",
            "trend": _get_share_text(summary.spare_spend, summary.total_spend, _("of billed maintenance spend")),
            "note": _("Purchase invoice rows mapped to spare items after labour exclusion."),
            "route": purchase_invoice_route,
            "route_options": purchase_invoice_route_options,
        },
        {
            "label": _("Labour Spend"),
            "value": summary.labour_spend,
            "fieldtype": "Currency",
            "tone": "neutral",
            "trend": _get_share_text(summary.labour_spend, summary.total_spend, _("of billed maintenance spend")),
            "note": _("Mapped from the default labour item on linked job cards."),
            "route": purchase_invoice_route,
            "route_options": purchase_invoice_route_options,
        },
        {
            "label": _("Average Invoice"),
            "value": summary.average_invoice_value,
            "fieldtype": "Currency",
            "tone": "positive" if summary.invoice_count else "neutral",
            "trend": _("{0} invoices in this window").format(summary.invoice_count),
            "note": _("Useful for spotting unusually dense or fragmented billing."),
            "route": purchase_invoice_route,
            "route_options": purchase_invoice_route_options,
        },
        {
            "label": _("Forecast Next Month"),
            "value": forecast["next_month_prediction"],
            "fieldtype": "Currency",
            "tone": "neutral",
            "trend": _("Projection built from the last {0} months of billed history").format(
                forecast["history_months"]
            ),
            "note": _("Trend blend: linear direction plus recent rolling average."),
        },
        {
            "label": _("Vehicles Due Soon"),
            "value": len(due_soon_watchlist),
            "fieldtype": "Int",
            "tone": "critical" if due_soon_watchlist else "positive",
            "trend": _("{0} repeat-service vehicles in the selected window").format(repeat_service_count),
            "note": _("Predicted using each vehicle's average service interval."),
            "route": job_card_route,
            "route_options": job_card_route_options,
        },
    ]


def _build_insights(summary, previous_summary, supplier_rows, vehicle_rows, forecast, due_soon_watchlist, repeat_service_count):
    insights = [
        {
            "title": _("Spend Momentum"),
            "tone": _get_spend_tone(summary.total_spend, previous_summary.total_spend),
            "body": _get_spend_momentum_text(summary.total_spend, previous_summary.total_spend),
        }
    ]

    if supplier_rows and summary.total_spend:
        top_supplier = supplier_rows[0]
        top_supplier_share = (flt(top_supplier.value) / summary.total_spend) * 100
        insights.append(
            {
                "title": _("Supplier Concentration"),
                "tone": "warning" if top_supplier_share >= 45 else "neutral",
                "body": _("{0} is driving {1}% of billed maintenance spend in the current filter window.").format(
                    top_supplier.label,
                    f"{top_supplier_share:.1f}",
                ),
            }
        )

    if vehicle_rows and summary.total_spend:
        top_vehicle = vehicle_rows[0]
        top_vehicle_share = (flt(top_vehicle.value) / summary.total_spend) * 100
        insights.append(
            {
                "title": _("Vehicle Cost Pressure"),
                "tone": "critical" if top_vehicle_share >= 30 else "neutral",
                "body": _("{0} accounts for {1}% of billed maintenance spend in the selected window.").format(
                    top_vehicle.label,
                    f"{top_vehicle_share:.1f}",
                ),
            }
        )

    insights.append(
        {
            "title": _("Forward View"),
            "tone": "neutral",
            "body": _(
                "Projected billed maintenance for the next month is {0}, based on the last {1} months of invoice history."
            ).format(
                frappe.utils.fmt_money(forecast["next_month_prediction"]),
                forecast["history_months"],
            ),
        }
    )

    if due_soon_watchlist:
        next_vehicle = due_soon_watchlist[0]
        insights.append(
            {
                "title": _("Service Timing Risk"),
                "tone": next_vehicle["tone"],
                "body": _("{0} appears highest on the watchlist. {1}").format(
                    next_vehicle["title"],
                    next_vehicle["meta"],
                ),
            }
        )
    elif repeat_service_count:
        insights.append(
            {
                "title": _("Repeat Maintenance"),
                "tone": "warning",
                "body": _("{0} vehicles were serviced more than once in the selected window.").format(
                    repeat_service_count
                ),
            }
        )

    if not summary.total_spend:
        return [
            {
                "title": _("No Billed Maintenance Found"),
                "tone": "neutral",
                "body": _("The current filters do not match any submitted purchase invoices linked to job cards."),
            }
        ]

    return insights[:5]


def _get_spend_momentum_text(current_value, previous_value):
    if previous_value <= 0 and current_value <= 0:
        return _("No billed maintenance spend in either the current or previous comparison window.")

    if previous_value <= 0 < current_value:
        return _("This window contains billed maintenance spend while the previous equal-length window had none.")

    change_amount = current_value - previous_value
    change_percentage = (change_amount / previous_value) * 100 if previous_value else 0
    direction = _("up") if change_amount > 0 else _("down") if change_amount < 0 else _("flat")

    return _("Billed maintenance spend is {0} {1}% versus the previous equal-length window.").format(
        direction,
        f"{abs(change_percentage):.1f}",
    )


def _get_spend_tone(current_value, previous_value):
    if previous_value <= 0:
        return "neutral"

    if current_value > previous_value * 1.15:
        return "critical"

    if current_value < previous_value * 0.9:
        return "positive"

    return "neutral"


def _get_change_text(current_value, previous_value):
    if previous_value <= 0 and current_value <= 0:
        return _("No movement versus previous window")

    if previous_value <= 0 < current_value:
        return _("New spend recorded versus an empty previous window")

    change_percentage = ((current_value - previous_value) / previous_value) * 100 if previous_value else 0
    direction = "+" if change_percentage > 0 else ""
    return _("{0}{1}% vs previous window").format(direction, f"{change_percentage:.1f}")


def _get_share_text(value, total, suffix):
    if total <= 0:
        return _("No billed spend share available")

    return _("{0}% {1}").format(f"{(flt(value) / total) * 100:.1f}", suffix)


def _get_purchase_invoice_route_options(filters):
    route_options = {
        "posting_date": ["between", [filters.from_date, filters.to_date]],
    }
    if filters.get("supplier"):
        route_options["supplier"] = filters.supplier
    return route_options


def _get_job_card_route_options(filters):
    route_options = {
        "service_date": ["between", [filters.from_date, filters.to_date]],
    }
    if filters.get("supplier"):
        route_options["supplier"] = filters.supplier
    if filters.get("vehicle"):
        route_options["vehicle"] = filters.vehicle
    return route_options


def _get_month_sequence(from_date, to_date):
    month_starts = []
    current_month = get_first_day(from_date)
    last_month = get_first_day(to_date)

    while getdate(current_month) <= getdate(last_month):
        month_starts.append(str(getdate(current_month)))
        current_month = get_first_day(add_months(current_month, 1))

    return month_starts
