import frappe
from frappe.utils import flt

from service_app.service_tracking.doctype.eah_job_card.eah_job_card import (
    get_active_purchase_orders_for_job_card,
    get_item_price_rate,
    get_purchase_order_job_card_link,
)
from service_app.service_tracking.doctype.tyre_request.tyre_request import (
    validate_purchase_order_tyre_request_integrity,
)

SPARE_PARTS_ITEM_GROUP = "Spare Parts"


def validate_purchase_order_source_integrity(doc, method=None):
    validate_duplicate_eah_job_card_purchase_order(doc)
    validate_purchase_order_spare_parts_rate_limit(doc, method)
    validate_purchase_order_tyre_request_integrity(doc, method)


def validate_duplicate_eah_job_card_purchase_order(doc):
    job_card_link = get_purchase_order_job_card_link(doc)
    if not job_card_link:
        return

    existing_purchase_orders = [
        purchase_order
        for purchase_order in get_active_purchase_orders_for_job_card(job_card_link)
        if purchase_order != doc.name
    ]
    if not existing_purchase_orders:
        return

    frappe.throw(
        "Purchase Order already exists for EAH Job Card "
        f"{frappe.bold(job_card_link)}: {', '.join(existing_purchase_orders)}. "
        "Please use the existing Purchase Order to avoid duplicate payments.",
        title="Duplicate EAH Job Card Purchase Order",
    )


def sync_job_card_purchase_order_link(doc, method=None):
    job_card_link = get_purchase_order_job_card_link(doc)
    if not job_card_link or not doc.name:
        return

    if not frappe.db.exists("EAH Job Card", job_card_link):
        return

    for fieldname in ("purchase_order", "custom_purchase_order"):
        if frappe.db.has_column("EAH Job Card", fieldname):
            frappe.db.set_value(
                "EAH Job Card",
                job_card_link,
                fieldname,
                doc.name,
                update_modified=False,
            )


def clear_job_card_purchase_order_link(doc, method=None):
    doc = get_purchase_order_doc(doc)

    for job_card_link in get_job_cards_linked_to_purchase_order(doc):
        if not frappe.db.exists("EAH Job Card", job_card_link):
            continue

        for fieldname in ("purchase_order", "custom_purchase_order"):
            if not frappe.db.has_column("EAH Job Card", fieldname):
                continue

            linked_purchase_order = frappe.db.get_value("EAH Job Card", job_card_link, fieldname)
            if linked_purchase_order == doc.name:
                frappe.db.set_value(
                    "EAH Job Card",
                    job_card_link,
                    fieldname,
                    None,
                    update_modified=False,
                )


def get_purchase_order_doc(doc):
    if isinstance(doc, str):
        return frappe.get_doc("Purchase Order", doc)
    return doc


def get_job_cards_linked_to_purchase_order(doc):
    job_cards = set()
    job_card_link = get_purchase_order_job_card_link(doc)
    if job_card_link:
        job_cards.add(job_card_link)

    for fieldname in ("purchase_order", "custom_purchase_order"):
        if not frappe.db.has_column("EAH Job Card", fieldname):
            continue

        job_cards.update(
            frappe.get_all(
                "EAH Job Card",
                filters={fieldname: doc.name},
                pluck="name",
            )
            or []
        )

    return sorted(job_cards)


def validate_purchase_order_spare_parts_rate_limit(doc, method=None):
    price_list = get_purchase_order_price_list(doc)
    errors = []
    for index, row in enumerate(doc.items or [], start=1):
        if not row.item_code:
            continue

        if not item_belongs_to_group(row.item_code, SPARE_PARTS_ITEM_GROUP):
            continue

        if not price_list:
            errors.append(
                f"Row {index}: Set Buying Price List before adding Spare Parts rates."
            )
            continue

        approved_rate = get_item_price_rate(row.item_code, price_list, doc.supplier)
        entered_rate = flt(row.rate)
        item_label = row.item_name or row.item_code or f"Row {index}"

        if approved_rate is None:
            errors.append(
                f"Row {index}: {item_label} has no approved Item Price in Price List {price_list}."
            )
            continue

        # Ensure default rate is fetched from Item Price for spare parts when row rate is blank/zero.
        if not entered_rate:
            row.rate = flt(approved_rate)
            entered_rate = flt(row.rate)

        if entered_rate > flt(approved_rate):
            errors.append(
                f"Row {index}: Rate for {item_label} cannot be greater than the approved Item Price "
                f"of {approved_rate} in {price_list}."
            )

    if errors:
        frappe.throw("<br>".join(errors), title="Spare Part Rate Not Allowed")


def get_purchase_order_price_list(doc):
    return (
        getattr(doc, "buying_price_list", None)
        or getattr(doc, "price_list", None)
        or ""
    )


def item_belongs_to_group(item_code, parent_group):
    item_group = frappe.db.get_value("Item", item_code, "item_group")
    if not item_group:
        return False

    if item_group == parent_group:
        return True

    parent_bounds = frappe.db.get_value("Item Group", parent_group, ["lft", "rgt"], as_dict=True)
    item_bounds = frappe.db.get_value("Item Group", item_group, ["lft", "rgt"], as_dict=True)
    if not parent_bounds or not item_bounds:
        return False

    return (
        parent_bounds.lft <= item_bounds.lft
        and parent_bounds.rgt >= item_bounds.rgt
    )


@frappe.whitelist()
def get_spare_part_item_price(item_code, price_list, supplier=None):
    if not item_code:
        return {"is_spare_part": False, "has_item_price": False, "rate": None}

    is_spare_part = item_belongs_to_group(item_code, SPARE_PARTS_ITEM_GROUP)
    if not is_spare_part:
        return {"is_spare_part": False, "has_item_price": False, "rate": None}

    approved_rate = get_item_price_rate(item_code, price_list, supplier)
    return {
        "is_spare_part": True,
        "has_item_price": approved_rate is not None,
        "rate": flt(approved_rate) if approved_rate is not None else None,
    }
