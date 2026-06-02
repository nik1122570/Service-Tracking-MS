import frappe
from frappe import _

from service_app.service_tracking.doctype.eah_job_card.eah_job_card import (
	get_active_purchase_orders_for_job_card,
)


def get_data():
	return {
		"fieldname": "eah_job_card",
		"method": "service_app.service_tracking.doctype.eah_job_card.eah_job_card_dashboard.get_open_count",
		"internal_and_external_links": {
			"Purchase Order": "purchase_order",
		},
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["Purchase Order"],
			}
		],
	}


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
	frappe.get_doc("EAH Job Card", name).check_permission()
	purchase_orders = get_active_purchase_orders_for_job_card(name)

	return {
		"count": {
			"internal_links_found": [
				{
					"doctype": "Purchase Order",
					"open_count": 0,
					"count": len(purchase_orders),
					"names": purchase_orders,
				}
			]
			if purchase_orders
			else [],
			"external_links_found": [],
		}
	}
