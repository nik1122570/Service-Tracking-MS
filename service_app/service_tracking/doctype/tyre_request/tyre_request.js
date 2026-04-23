frappe.ui.form.on("Tyre Request", {
	setup(frm) {
		set_tyre_item_queries(frm);
		set_tyre_request_field_state(frm);
		calculate_tyre_request_totals(frm);
	},

	refresh(frm) {
		set_tyre_item_queries(frm);
		set_tyre_request_field_state(frm);
		if (is_new_tyre_purchase_request(frm)) {
			sync_tyre_item_price_list(frm, {
				fetch_rates: true,
				only_if_rate_missing: true,
				clear_rates: !frm.doc.price_list
			});
		}
		calculate_tyre_request_totals(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Purchase Order", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.tyre_request.tyre_request.make_purchase_order",
					frm: frm
				});
			}, "Create");

			if (is_new_tyre_purchase_request(frm)) {
				frm.add_custom_button("Tyre Receiving Note", () => {
					frappe.model.open_mapped_doc({
						method: "service_app.service_tracking.doctype.tyre_request.tyre_request.make_tyre_receiving_note",
						frm: frm
					});
				}, "Create");
			}
		}
	},

	request_type(frm) {
		set_tyre_request_field_state(frm);
		calculate_tyre_request_totals(frm);
		if (is_new_tyre_purchase_request(frm)) {
			sync_tyre_item_price_list(frm, {
				fetch_rates: true,
				only_if_rate_missing: true,
				clear_rates: !frm.doc.price_list
			});
		}
	},

	price_list(frm) {
		if (!is_new_tyre_purchase_request(frm)) {
			return;
		}
		sync_tyre_item_price_list(frm, {
			fetch_rates: true,
			clear_rates: !frm.doc.price_list
		});
		calculate_tyre_request_totals(frm);
	},

	supplier(frm) {
		if (!is_new_tyre_purchase_request(frm)) {
			return;
		}
		refresh_tyre_item_rates(frm, { force: true });
	},

	tyre_maintenance_add(frm) {
		calculate_tyre_request_totals(frm);
	},

	tyre_maintenance_remove(frm) {
		calculate_tyre_request_totals(frm);
	}
});

frappe.ui.form.on("Tyre Request Item", {
	tyre_items_add(frm, cdt, cdn) {
		sync_tyre_row_price_list(frm, cdt, cdn);
		calculate_tyre_request_totals(frm);
		fetch_tyre_item_price(frm, cdt, cdn, { only_if_rate_missing: true });
	},

	tyre_items_remove(frm) {
		calculate_tyre_request_totals(frm);
	},

	item(frm, cdt, cdn) {
		sync_tyre_row_price_list(frm, cdt, cdn);
		calculate_tyre_request_totals(frm);
		fetch_tyre_item_price(frm, cdt, cdn, { force: true });
	},

	qty(frm, cdt, cdn) {
		calculate_tyre_request_totals(frm);
		fetch_tyre_item_price(frm, cdt, cdn, { only_if_rate_missing: true });
	},

	rate(frm, cdt, cdn) {
		validate_tyre_rate_limit(frm, cdt, cdn);
		calculate_tyre_request_totals(frm);
	}
});

frappe.ui.form.on("Tyre Maintenance Item", {
	rate(frm) {
		calculate_tyre_request_totals(frm);
	}
});

function set_tyre_item_queries(frm) {
	if (!frm.fields_dict.tyre_items || !frm.fields_dict.tyre_items.grid) {
		return;
	}

	frm.fields_dict.tyre_items.grid.get_field("item").get_query = () => ({
		filters: {
			item_group: "Tyres"
		}
	});
}

function set_tyre_request_field_state(frm) {
	const isMaintenance = is_tyre_maintenance_request(frm);

	frm.toggle_display("tyre_maintenance", isMaintenance);
	frm.toggle_display("tyre_maintenance_item", isMaintenance);
	frm.toggle_display("tyre_items", !isMaintenance);

	frm.set_df_property("tyre_maintenance", "reqd", isMaintenance ? 1 : 0);
	frm.set_df_property("tyre_items", "reqd", isMaintenance ? 0 : 1);

	if (frm.fields_dict.tyre_items && frm.fields_dict.tyre_items.grid) {
		frm.fields_dict.tyre_items.grid.update_docfield_property("price_list", "read_only", 1);
	}
}

function calculate_tyre_request_totals(frm) {
	if (is_tyre_maintenance_request(frm)) {
		const total_operations = (frm.doc.tyre_maintenance || []).length;
		const total_maintenance_amount = (frm.doc.tyre_maintenance || []).reduce(
			(total, row) => total + flt(row.rate),
			0
		);

		set_tyre_request_total_field_value(frm, "total_qty", total_operations);
		set_tyre_request_total_field_value(frm, "total_purchase_amount", total_maintenance_amount);
		return;
	}

	const total_qty = (frm.doc.tyre_items || []).reduce(
		(total, row) => total + flt(row.qty),
		0
	);
	const total_purchase_amount = (frm.doc.tyre_items || []).reduce(
		(total, row) => total + (flt(row.qty) * flt(row.rate)),
		0
	);

	set_tyre_request_total_field_value(frm, "total_qty", total_qty);
	set_tyre_request_total_field_value(frm, "total_purchase_amount", total_purchase_amount);
}

function set_tyre_request_total_field_value(frm, fieldname, value) {
	frm.doc[fieldname] = value;
	if (frm.fields_dict[fieldname]) {
		frm.refresh_field(fieldname);
	}
}

function sync_tyre_item_price_list(
	frm,
	{ fetch_rates = false, only_if_rate_missing = false, clear_rates = false } = {}
) {
	const parent_price_list = frm.doc.price_list || null;

	(frm.doc.tyre_items || []).forEach((row) => {
		const price_list_changed = row.price_list !== parent_price_list;

		if (price_list_changed) {
			frappe.model.set_value(row.doctype, row.name, "price_list", parent_price_list);
		}

		if (clear_rates) {
			frappe.model.set_value(row.doctype, row.name, "rate", 0);
			return;
		}

		if ((fetch_rates || price_list_changed) && row.item && parent_price_list) {
			fetch_tyre_item_price(frm, row.doctype, row.name, { only_if_rate_missing });
		}
	});
}

function sync_tyre_row_price_list(frm, cdt, cdn) {
	if (!frm.doc.price_list) {
		return;
	}

	const row = locals[cdt][cdn];
	if (row && row.price_list !== frm.doc.price_list) {
		frappe.model.set_value(cdt, cdn, "price_list", frm.doc.price_list);
	}
}

function refresh_tyre_item_rates(frm, { force = false } = {}) {
	(frm.doc.tyre_items || []).forEach((row) => {
		if (row.item) {
			fetch_tyre_item_price(frm, row.doctype, row.name, { force });
		}
	});
}

function fetch_tyre_item_price(frm, cdt, cdn, { force = false, only_if_rate_missing = false } = {}) {
	const row = locals[cdt][cdn];
	if (!row || !row.item) {
		return;
	}

	const price_list = row.price_list || frm.doc.price_list;
	if (!price_list) {
		frappe.model.set_value(cdt, cdn, "rate", 0);
		return;
	}

	if (!force && only_if_rate_missing && flt(row.rate)) {
		return;
	}

	const request_key = [row.item, price_list, frm.doc.supplier || ""].join("::");
	row.__last_price_request = request_key;

	frappe.call({
		method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.get_item_price",
		args: {
			item_code: row.item,
			price_list,
			supplier: frm.doc.supplier
		},
		callback: (r) => {
			const current_row = locals[cdt] && locals[cdt][cdn];
			if (!current_row || current_row.__last_price_request !== request_key) {
				return;
			}

			const rate = flt(r.message && r.message.rate ? r.message.rate : 0);
			current_row.__skip_rate_limit_check = true;
			frappe.model.set_value(cdt, cdn, "rate", rate);
			calculate_tyre_request_totals(frm);
		}
	});
}

function validate_tyre_rate_limit(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row) {
		return;
	}

	if (row.__skip_rate_limit_check) {
		row.__skip_rate_limit_check = false;
		return;
	}

	if (!row.item) {
		return;
	}

	const price_list = row.price_list || frm.doc.price_list;
	const entered_rate = flt(row.rate);
	if (!price_list || !entered_rate) {
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.get_item_price",
		args: {
			item_code: row.item,
			price_list,
			supplier: frm.doc.supplier
		},
		callback: (r) => {
			const current_row = locals[cdt] && locals[cdt][cdn];
			if (!current_row) {
				return;
			}

			const approved_rate = flt(r.message && r.message.rate ? r.message.rate : 0);
			const tyreLabel = current_row.item_name || current_row.item;

			if (!approved_rate) {
				frappe.msgprint({
					title: "Item Price Required",
					indicator: "orange",
					message:
						`${tyreLabel} has no approved Item Price in ${price_list}. ` +
						"Create the Item Price first before saving this Tyre Request."
				});
				return;
			}

			if (flt(current_row.rate) > approved_rate) {
				frappe.msgprint({
					title: "Rate Not Allowed",
					indicator: "orange",
					message:
						`The maximum allowed rate for ${tyreLabel} is ${approved_rate}. ` +
						"Update Item Price first before saving a higher rate."
				});
			}
		}
	});
}

function is_tyre_maintenance_request(frm) {
	return (frm.doc.request_type || "").trim() === "Tyre Maintenance";
}

function is_new_tyre_purchase_request(frm) {
	return (frm.doc.request_type || "").trim() !== "Tyre Maintenance";
}
