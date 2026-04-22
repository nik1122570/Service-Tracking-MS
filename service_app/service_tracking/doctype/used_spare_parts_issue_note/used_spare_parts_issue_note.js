frappe.ui.form.on("Used Spare Parts Issue Note", {
	setup(frm) {
		frm.set_query("maintenance_return_note", () => ({
			filters: {
				docstatus: 1
			}
		}));
		apply_source_type_mode(frm);
	},

	onload(frm) {
		apply_source_type_mode(frm);
	},

	refresh(frm) {
		apply_source_type_mode(frm);
	},

	source_type(frm) {
		apply_source_type_mode(frm);

		if (frm.doc.source_type === "Manual") {
			frm.set_value("maintenance_return_note", "");
			return;
		}

		frm.set_value("manual_reason", "");
		if (frm.doc.maintenance_return_note) {
			populate_header_from_return_note(frm);
		}
	},

	maintenance_return_note(frm) {
		if (frm.doc.source_type !== "From Maintenance Return Note" || !frm.doc.maintenance_return_note) {
			return;
		}

		populate_header_from_return_note(frm);
	},

	purpose(frm) {
		(frm.doc.issue_items || []).forEach((row) => {
			if (!row.disposition) {
				frappe.model.set_value(row.doctype, row.name, "disposition", frm.doc.purpose);
			}
		});
	}
});

frappe.ui.form.on("Used Spare Parts Issue Note Item", {
	item(frm, cdt, cdn) {
		if (frm.doc.source_type !== "Manual") {
			return;
		}

		const row = locals[cdt] && locals[cdt][cdn];
		if (!row || !row.item) {
			return;
		}

		frappe.db.get_value("Item", row.item, ["item_name", "stock_uom"]).then((r) => {
			const data = (r && r.message) || {};
			frappe.model.set_value(cdt, cdn, "item_name", data.item_name || row.item_name || "");
			if (!row.uom) {
				frappe.model.set_value(cdt, cdn, "uom", data.stock_uom || "");
			}
			if (!row.condition) {
				frappe.model.set_value(cdt, cdn, "condition", "Reusable");
			}
			if (!row.disposition && frm.doc.purpose) {
				frappe.model.set_value(cdt, cdn, "disposition", frm.doc.purpose);
			}
		});
	}
});

function apply_source_type_mode(frm) {
	const is_from_return_note = frm.doc.source_type !== "Manual";

	frm.toggle_reqd("maintenance_return_note", is_from_return_note);
	frm.toggle_reqd("manual_reason", !is_from_return_note);

	frm.set_df_property("eah_job_card", "read_only", is_from_return_note ? 1 : 0);
	frm.set_df_property("vehicle", "read_only", is_from_return_note ? 1 : 0);

	const grid = frm.fields_dict.issue_items && frm.fields_dict.issue_items.grid;
	if (grid) {
		grid.update_docfield_property("item", "read_only", is_from_return_note ? 1 : 0);
		grid.update_docfield_property("uom", "read_only", is_from_return_note ? 1 : 0);
		grid.update_docfield_property("condition", "read_only", is_from_return_note ? 1 : 0);
		grid.update_docfield_property("qty_available", "read_only", is_from_return_note ? 1 : 0);
		grid.update_docfield_property("source_return_item", "hidden", is_from_return_note ? 0 : 1);
	}

	frm.refresh_fields([
		"maintenance_return_note",
		"manual_reason",
		"eah_job_card",
		"vehicle",
		"issue_items"
	]);
}

function populate_header_from_return_note(frm) {
	frappe.db
		.get_value("Maintenance Return Note", frm.doc.maintenance_return_note, ["eah_job_card", "vehicle"])
		.then((r) => {
			if (!r || !r.message) {
				return;
			}

			frm.set_value({
				eah_job_card: r.message.eah_job_card || "",
				vehicle: r.message.vehicle || ""
			});
		});
}
