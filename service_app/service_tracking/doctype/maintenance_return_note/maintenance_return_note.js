frappe.ui.form.on("Maintenance Return Note", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Used Spare Parts Issue Note", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.maintenance_return_note.maintenance_return_note.make_used_spare_parts_issue_note",
					frm: frm,
				});
			}, "Create");
		}
	},
});
