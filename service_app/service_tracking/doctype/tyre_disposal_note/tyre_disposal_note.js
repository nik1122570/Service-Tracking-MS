frappe.ui.form.on("Tyre Disposal Note", {
	disposal_method(frm) {
		(frm.doc.disposal_items || []).forEach((row) => {
			if (!row.disposition) {
				frappe.model.set_value(row.doctype, row.name, "disposition", "Disposed");
			}
		});
	}
});
