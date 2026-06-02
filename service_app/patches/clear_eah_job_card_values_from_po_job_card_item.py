import frappe


def execute():
	if not frappe.db.has_column("Purchase Order Item", "job_card_item"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabPurchase Order Item`
		SET job_card_item = NULL
		WHERE job_card_item LIKE 'JOB CARD-%'
		"""
	)
