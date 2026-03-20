frappe.ui.form.on("Used Spare Parts Issue Note", {
	purpose(frm) {
		(frm.doc.issue_items || []).forEach((row) => {
			if (!row.disposition) {
				frappe.model.set_value(row.doctype, row.name, "disposition", frm.doc.purpose);
			}
		});
	}
});