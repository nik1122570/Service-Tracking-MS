frappe.ui.form.on("Material Request", {
	refresh(frm) {
		add_trip_settlement_target_buttons(frm);
	},
});

function add_trip_settlement_target_buttons(frm) {
	if (frm.doc.docstatus !== 1) {
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.get_target_document_settlement_batches",
		args: {
			target_doctype: frm.doc.doctype,
			target_document: frm.doc.name,
		},
		callback(response) {
			const batches = response.message || [];
			if (!batches.length) {
				return;
			}

			frm.add_custom_button(
				__("Unlink Trip Settlement"),
				() => unlink_trip_settlement_target(frm, batches),
				__("Actions")
			);
		},
	});
}

function unlink_trip_settlement_target(frm, batches) {
	const batch_names = batches.map((batch) => batch.name).join(", ");
	frappe.confirm(
		__(
			"Unlink Trip Settlement Batches {0} from this {1}? You can cancel this document after unlinking.",
			[frappe.bold(batch_names), frm.doc.doctype]
		),
		() => {
			frappe.call({
				method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.unlink_target_document_settlement_batches",
				args: {
					target_doctype: frm.doc.doctype,
					target_document: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Unlinking trip settlement..."),
				callback(response) {
					const results = response.message || [];
					const relinked_rows = results.reduce((total, row) => total + cint(row.relinked_rows), 0);

					frappe.show_alert({
						message: __("{0} batches unlinked; {1} entitlement rows moved back to Batched.", [
							results.length,
							relinked_rows,
						]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}
	);
}
