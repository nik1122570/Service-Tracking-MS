frappe.ui.form.on("Tyre Receiving Note", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Tyre Disposal Note", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.tyre_receiving_note.tyre_receiving_note.make_tyre_disposal_note",
					frm: frm
				});
			}, "Create");
		}
	}
});
