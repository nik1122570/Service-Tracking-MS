frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		fetch_spare_part_rates(frm, { force: false });
	},

	onload_post_render(frm) {
		fetch_spare_part_rates(frm, { force: false });
	},

	refresh(frm) {
		fetch_spare_part_rates(frm, { force: false });
		add_trip_settlement_target_buttons(frm);
	},

	buying_price_list(frm) {
		fetch_spare_part_rates(frm, { force: true });
	},

	price_list(frm) {
		fetch_spare_part_rates(frm, { force: true });
	},

	supplier(frm) {
		fetch_spare_part_rates(frm, { force: true });
	}
});

frappe.ui.form.on("Purchase Order Item", {
	item_code(frm, cdt, cdn) {
		fetch_spare_part_rate_for_row(frm, cdt, cdn, { force: true });
	}
});

function get_purchase_order_price_list(frm) {
	return frm.doc.buying_price_list || frm.doc.price_list || "";
}

function fetch_spare_part_rates(frm, { force = false } = {}) {
	(frm.doc.items || []).forEach((row) => {
		if (row.item_code) {
			fetch_spare_part_rate_for_row(frm, row.doctype, row.name, { force });
		}
	});
}

function fetch_spare_part_rate_for_row(frm, cdt, cdn, { force = false } = {}) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) {
		return;
	}

	const price_list = get_purchase_order_price_list(frm);
	if (!price_list) {
		return;
	}

	if (!force && flt(row.rate)) {
		return;
	}

	const requestKey = [row.item_code, price_list, frm.doc.supplier || ""].join("::");
	row.__last_spare_part_rate_request = requestKey;

	frappe.call({
		method: "service_app.service_tracking.purchase_order.get_spare_part_item_price",
		args: {
			item_code: row.item_code,
			price_list,
			supplier: frm.doc.supplier
		},
		callback: (r) => {
			const currentRow = locals[cdt] && locals[cdt][cdn];
			if (!currentRow || currentRow.__last_spare_part_rate_request !== requestKey) {
				return;
			}

			const response = r.message || {};
			if (!response.is_spare_part) {
				return;
			}
			if (!response.has_item_price) {
				return;
			}

			const approvedRate = flt(response.rate);
			frappe.model.set_value(cdt, cdn, "rate", approvedRate);
		}
	});
}

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
