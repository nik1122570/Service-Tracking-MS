import frappe
from frappe import _


def get_data():
	return {
		"fieldname": "name",
		"method": "service_app.service_tracking.doctype.container_trip_log.container_trip_log_dashboard.get_open_count",
		"transactions": [
			{
				"label": _("Settlement"),
				"items": ["Trip Settlement Batch"],
			}
		],
	}


@frappe.whitelist()
def get_open_count(doctype, name, items=None):
	frappe.get_doc("Container Trip Log", name).check_permission()
	batch_names = get_linked_settlement_batches(name)

	return {
		"count": {
			"internal_links_found": [
				{
					"doctype": "Trip Settlement Batch",
					"open_count": 0,
					"count": len(batch_names),
					"names": batch_names,
				}
			]
			if batch_names
			else [],
			"external_links_found": [],
		}
	}


def get_linked_settlement_batches(trip_log):
	batch_names = set(
		frappe.get_all(
			"Trip Settlement Batch Item",
			filters={"container_trip_log": trip_log},
			pluck="parent",
		)
	)

	batch_names.update(
		frappe.get_all(
			"Container Trip Entitlement Item",
			filters={
				"parent": trip_log,
				"parenttype": "Container Trip Log",
				"parentfield": "entitlement_items",
				"trip_settlement_batch": ["!=", ""],
			},
			pluck="trip_settlement_batch",
		)
	)

	parent_batch = frappe.db.get_value("Container Trip Log", trip_log, "trip_settlement_batch")
	if parent_batch:
		batch_names.add(parent_batch)

	return sorted(batch_names)
