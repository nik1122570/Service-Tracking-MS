import frappe


def execute():
	if not frappe.db.exists("Workspace", "Trip Simulation Center"):
		return

	workspace = frappe.get_doc("Workspace", "Trip Simulation Center")
	changed = False

	for shortcut in workspace.shortcuts:
		if shortcut.label != "Trip Settings":
			continue

		shortcut.type = "URL"
		shortcut.link_to = ""
		shortcut.url = "/app/trip-settings"
		shortcut.doc_view = ""
		shortcut.stats_filter = ""
		changed = True

	if changed:
		workspace.flags.ignore_permissions = True
		workspace.save(ignore_permissions=True)
