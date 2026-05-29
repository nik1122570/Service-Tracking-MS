import frappe
from frappe import _


def get_data():
	return {
		"fieldname": "name",
		"method": "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch_dashboard.get_open_count",
		"transactions": [
			{
				"label": _("Reference"),
				"items": ["Container Trip Log", "Sales Order", "Material Request", "Purchase Order"],
			}
		],
	}


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
	doc = frappe.get_doc("Trip Settlement Batch", name)
	doc.check_permission()
	links = []

	trip_logs = sorted({row.container_trip_log for row in doc.get("items") or [] if row.container_trip_log})
	if trip_logs:
		links.append(
			{
				"doctype": "Container Trip Log",
				"open_count": 0,
				"count": len(trip_logs),
				"names": trip_logs,
			}
		)

	if doc.target_doctype and doc.target_document:
		links.append(
			{
				"doctype": doc.target_doctype,
				"open_count": 0,
				"count": 1,
				"names": [doc.target_document],
			}
		)

	return {
		"count": {
			"internal_links_found": links,
			"external_links_found": [],
		}
	}
