import frappe
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate, nowdate

from service_app.service_tracking.tyre_analytics import get_outstanding_tyre_return_rows


@frappe.whitelist()
def get_total_vehicles_serviced_this_month():
    today = nowdate()
    first_day = get_first_day(today)
    last_day = get_last_day(today)

    count = frappe.db.sql("""
        SELECT COUNT(DISTINCT vehicle)
        FROM `tabEAH Job Card`
        WHERE docstatus = 1
          AND service_date BETWEEN %s AND %s
    """, (first_day, last_day))[0][0]

    return count


@frappe.whitelist()
def get_total_maintenance_cost():
    total = frappe.db.sql("""
        SELECT SUM(total_vat_exclusive)
        FROM `tabEAH Job Card`
    """)[0][0] or 0

    return total


@frappe.whitelist()
def get_total_spare_parts_used():
    count = frappe.db.sql("""
        SELECT COUNT(*)
        FROM `tabSupplied Parts`
    """)[0][0]

    return count


@frappe.whitelist()
def get_total_job_cards_this_month():
    today = nowdate()
    first_day = get_first_day(today)
    last_day = get_last_day(today)

    count = frappe.db.count('EAH Job Card', {'creation': ['between', [first_day, last_day]]})

    return count


def _get_current_month_date_range():
    today = nowdate()
    return get_first_day(today), get_last_day(today)


def _get_current_quarter_date_range(reference_date=None):
    reference = getdate(reference_date or nowdate())
    quarter_start_month = ((reference.month - 1) // 3) * 3 + 1
    quarter_start = getdate(f"{reference.year}-{quarter_start_month:02d}-01")
    quarter_end = get_last_day(add_months(quarter_start, 2))
    return quarter_start, quarter_end


def _get_default_currency():
    return frappe.db.get_single_value("Global Defaults", "default_currency")


def _get_submitted_maintenance_cost(from_date=None, to_date=None, fieldname="total_vat_exclusive"):
    conditions = ["docstatus = 1"]
    values = []

    if from_date and to_date:
        conditions.append("service_date BETWEEN %s AND %s")
        values.extend([from_date, to_date])

    total = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM({fieldname}), 0)
        FROM `tabEAH Job Card`
        WHERE {' AND '.join(conditions)}
        """,
        values,
    )[0][0] or 0

    return flt(total)


def _get_submitted_purchase_invoice_maintenance_cost(from_date=None, to_date=None):
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

    total = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(pii.base_net_amount), 0)
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        WHERE {' AND '.join(conditions)}
        """,
        values,
    )[0][0] or 0

    return flt(total)


def _get_submitted_purchase_invoice_spare_cost():
    total = frappe.db.sql(
        """
        SELECT COALESCE(SUM(pii.base_net_amount), 0)
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pii.purchase_order
        INNER JOIN `tabEAH Job Card` jc
            ON jc.name = po.custom_job_card_link
        WHERE pi.docstatus = 1
          AND pii.parenttype = 'Purchase Invoice'
          AND COALESCE(pii.purchase_order, '') != ''
          AND COALESCE(po.custom_job_card_link, '') != ''
          AND (
                COALESCE(jc.custom_default_labour_item, '') = ''
                OR pii.item_code != jc.custom_default_labour_item
          )
        """
    )[0][0] or 0

    return flt(total)


def _build_number_card_response(value, fieldtype="Int", options=None):
    response = {
        "value": value,
        "fieldtype": fieldtype,
    }

    if options:
        response["options"] = options

    return response


def _build_currency_number_card_response(value):
    return _build_number_card_response(flt(value), "Currency", _get_default_currency())


@frappe.whitelist()
def get_total_maintenance_cost_this_month(filters=None):
    from_date, to_date = _get_current_month_date_range()
    return _build_currency_number_card_response(
        _get_submitted_purchase_invoice_maintenance_cost(from_date, to_date)
    )


@frappe.whitelist()
def get_total_maintenance_cost_this_quarter(filters=None):
    from_date, to_date = _get_current_quarter_date_range()
    return _build_currency_number_card_response(
        _get_submitted_purchase_invoice_maintenance_cost(from_date, to_date)
    )


@frappe.whitelist()
def get_total_number_of_vehicles(filters=None):
    return _build_number_card_response(frappe.db.count("Vehicle"))


@frappe.whitelist()
def get_total_vehicles_serviced_this_month_card(filters=None):
    return _build_number_card_response(get_total_vehicles_serviced_this_month())


@frappe.whitelist()
def get_most_appearing_vehicle(filters=None):
    result = frappe.db.sql(
        """
        SELECT vehicle, COUNT(*) AS appearances
        FROM `tabEAH Job Card`
        WHERE docstatus = 1
          AND vehicle IS NOT NULL
          AND vehicle != ''
        GROUP BY vehicle
        ORDER BY appearances DESC, vehicle ASC
        LIMIT 1
        """,
        as_dict=True,
    )

    if not result:
        return "No serviced vehicle yet"

    top_vehicle = result[0]
    return f"{top_vehicle.vehicle} ({int(top_vehicle.appearances)})"


@frappe.whitelist()
def get_total_spare_cost(filters=None):
    return _build_currency_number_card_response(
        _get_submitted_purchase_invoice_spare_cost()
    )


def _get_current_quarter_date_range_for_filters():
    return _get_current_quarter_date_range()


def _get_submitted_tyre_request_count(from_date=None, to_date=None):
    filters = {"docstatus": 1}
    if from_date and to_date:
        filters["request_date"] = ["between", [from_date, to_date]]

    return frappe.db.count("Tyre Request", filters)


def _get_total_quantity_from_child_table(parent_doctype, child_doctype, parent_fieldname, quantity_fieldname):
    result = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM(child.{quantity_fieldname}), 0)
        FROM `tab{child_doctype}` child
        INNER JOIN `tab{parent_doctype}` parent
            ON parent.name = child.parent
        WHERE parent.docstatus = 1
          AND child.parenttype = %(parent_doctype)s
          AND child.parentfield = %(parent_fieldname)s
        """,
        {
            "parent_doctype": parent_doctype,
            "parent_fieldname": parent_fieldname,
        },
    )[0][0] or 0

    return flt(result)


def _get_total_purchased_tyre_qty():
    result = frappe.db.sql(
        """
        SELECT COALESCE(SUM(poi.qty), 0)
        FROM `tabPurchase Order Item` poi
        INNER JOIN `tabPurchase Order` po
            ON po.name = poi.parent
        WHERE po.docstatus = 1
          AND COALESCE(po.custom_tyre_request_link, '') != ''
        """
    )[0][0] or 0

    return flt(result)


def _get_submitted_tyre_cost(from_date=None, to_date=None, fieldname="total"):
    conditions = [
        "docstatus = 1",
        "COALESCE(custom_tyre_request_link, '') != ''",
    ]
    values = []

    if from_date and to_date:
        conditions.append("transaction_date BETWEEN %s AND %s")
        values.extend([from_date, to_date])

    total = frappe.db.sql(
        f"""
        SELECT COALESCE(SUM({fieldname}), 0)
        FROM `tabPurchase Order`
        WHERE {' AND '.join(conditions)}
        """,
        values,
    )[0][0] or 0

    return flt(total)


@frappe.whitelist()
def get_tyre_requests_this_month(filters=None):
    from_date, to_date = _get_current_month_date_range()
    return _build_number_card_response(int(_get_submitted_tyre_request_count(from_date, to_date)))


@frappe.whitelist()
def get_tyre_requests_this_quarter(filters=None):
    from_date, to_date = _get_current_quarter_date_range_for_filters()
    return _build_number_card_response(int(_get_submitted_tyre_request_count(from_date, to_date)))


@frappe.whitelist()
def get_total_purchased_tyres(filters=None):
    return _build_number_card_response(int(_get_total_purchased_tyre_qty()))


@frappe.whitelist()
def get_total_received_tyres(filters=None):
    return _build_number_card_response(
        int(
            _get_total_quantity_from_child_table(
                "Tyre Receiving Note",
                "Tyre Receiving Note Item",
                "received_tyres",
                "qty_received",
            )
        )
    )


@frappe.whitelist()
def get_total_disposed_tyres(filters=None):
    return _build_number_card_response(
        int(
            _get_total_quantity_from_child_table(
                "Tyre Disposal Note",
                "Tyre Disposal Note Item",
                "disposal_items",
                "qty_out",
            )
        )
    )


@frappe.whitelist()
def get_total_outstanding_receiving_tyres(filters=None):
    outstanding_qty = sum(flt(row.get("outstanding_qty")) for row in get_outstanding_tyre_return_rows({}))
    return _build_number_card_response(int(outstanding_qty))


@frappe.whitelist()
def get_total_tyre_cost_this_month(filters=None):
    from_date, to_date = _get_current_month_date_range()
    return _build_currency_number_card_response(_get_submitted_tyre_cost(from_date, to_date))


@frappe.whitelist()
def get_total_tyre_cost_this_quarter(filters=None):
    from_date, to_date = _get_current_quarter_date_range_for_filters()
    return _build_currency_number_card_response(_get_submitted_tyre_cost(from_date, to_date))
