import frappe


def validate_spare_part_part_category(doc, method=None):
	"""Compatibility hook kept intentionally empty after removing Item controls."""
	return


@frappe.whitelist()
def get_warranty_days_for_part_category(part_category=None):
	"""Compatibility endpoint kept intentionally empty after removing Part Category logic."""
	return {
		"days": None,
		"item_warranty_field": None,
	}
