frappe.ui.form.on("EAH Job Card", {
	setup(frm) {
		set_supplied_parts_item_queries(frm);
		set_supplied_parts_field_state(frm);
		set_labour_rates_operation_query(frm);
		calculate_totals(frm);
	},

	refresh(frm) {
		set_supplied_parts_item_queries(frm);
		set_supplied_parts_field_state(frm);
		set_labour_rates_operation_query(frm);
		sync_supplied_parts_price_list(frm, {
			fetch_rates: true,
			only_if_rate_missing: true,
			clear_rates: !frm.doc.price_list
		});
		calculate_totals(frm);

		if (!frm.doc.vehicle) {
			return;
		}

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Maintenance Return Note", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.make_maintenance_return_note",
					frm: frm
				});
			}, "Create");

			frm.add_custom_button("Purchase Order", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.make_purchase_order",
					frm: frm
				});
			}, "Create");
		}

		if (!frm.is_new()) {
			frm.add_custom_button("Maintenance History", () => {
				frappe.call({
					method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.get_vehicle_maintenance_history",
					args: {
						vehicle: frm.doc.vehicle
					},
					callback: (r) => {
						const history = r.message || [];

						const dialog = new frappe.ui.Dialog({
							title: "Maintenance History",
							fields: [
								{
									fieldtype: "HTML",
									fieldname: "history_html"
								}
							],
							primary_action: () => dialog.hide()
						});

						let html = "";

						if (history.length) {
							html = `<div style="max-height:420px; overflow:auto;">`;

							history.forEach((h) => {
								const templates = (h.service_templates || []).length
									? (h.service_templates || []).join(", ")
									: "<i>(none)</i>";

								html += `
									<div style="margin-bottom:10px;padding:10px;border:1px solid #eee;border-radius:6px;">
										<div><strong>${h.name}</strong> - ${h.service_date || ""}</div>
										<div><b>Supplier:</b> ${h.supplier || "-"}</div>
										<div><b>Driver:</b> ${h.driver_name || "-"}</div>
										<div><b>Service Templates:</b> ${templates}</div>
									</div>
								`;
							});

							html += `</div>`;
						} else {
							html = `<p>No maintenance history found for this vehicle.</p>`;
						}

						dialog.set_value("history_html", html);
						dialog.show();
					}
				});
			});
		}
	},

	price_list(frm) {
		sync_supplied_parts_price_list(frm, {
			fetch_rates: true,
			clear_rates: !frm.doc.price_list
		});
		calculate_totals(frm);
	},

	supplier(frm) {
		sync_supplied_parts_price_list(frm, {
			fetch_rates: true,
			only_if_rate_missing: false,
			clear_rates: !frm.doc.price_list
		});
		calculate_totals(frm);
	},

	vehicle(frm) {
		set_labour_rates_operation_query(frm);
	},

	make(frm) {
		set_labour_rates_operation_query(frm);
	},

	weight_class(frm) {
		set_labour_rates_operation_query(frm);
	},

	custom_make(frm) {
		set_labour_rates_operation_query(frm);
	},

	custom_weight_class(frm) {
		set_labour_rates_operation_query(frm);
	}
});

frappe.ui.form.on("Supplied Parts", {
	supplied_parts_add(frm, cdt, cdn) {
		sync_row_price_list(frm, cdt, cdn);
		calculate_totals(frm);
		fetch_item_price(frm, cdt, cdn, { only_if_rate_missing: true });
	},

	supplied_parts_remove(frm) {
		calculate_totals(frm);
	},

	item(frm, cdt, cdn) {
		sync_row_price_list(frm, cdt, cdn);
		calculate_totals(frm);
		fetch_item_price(frm, cdt, cdn, { force: true });
	},

	qty(frm, cdt, cdn) {
		calculate_totals(frm);
		fetch_item_price(frm, cdt, cdn, { force: true });
	},

	rate(frm, cdt, cdn) {
		validate_rate_limit(frm, cdt, cdn);
		calculate_totals(frm);
	}
});

frappe.ui.form.on("Maintainance Tempelate", {
	labour_rates_add(frm) {
		calculate_totals(frm);
	},

	labour_rates_remove(frm) {
		calculate_totals(frm);
	},

	operation_done(frm, cdt, cdn) {
		set_labour_row_total(cdt, cdn);
		calculate_totals(frm);
	},

	// Backward compatibility for any legacy row layout still using operation directly.
	operation(frm, cdt, cdn) {
		set_labour_row_total(cdt, cdn);
		calculate_totals(frm);
	},

	maximum_hours(frm, cdt, cdn) {
		set_labour_row_total(cdt, cdn);
		calculate_totals(frm);
	},

	flat_rate(frm, cdt, cdn) {
		set_labour_row_total(cdt, cdn);
		calculate_totals(frm);
	},

	total_amount(frm, cdt, cdn) {
		set_labour_row_total(cdt, cdn);
		calculate_totals(frm);
	}
});

function set_supplied_parts_item_queries(frm) {
	if (!frm.fields_dict.supplied_parts || !frm.fields_dict.supplied_parts.grid) {
		return;
	}

	frm.fields_dict.supplied_parts.grid.get_field("item").get_query = () => ({
		filters: [
			["Item", "item_group", "=", "Spare Parts"],
			["Item", "docstatus", "=", 1]
		]
	});
}

function set_supplied_parts_field_state(frm) {
	if (frm.fields_dict.supplied_parts && frm.fields_dict.supplied_parts.grid) {
		frm.fields_dict.supplied_parts.grid.update_docfield_property("price_list", "read_only", 1);
	}
}

function set_labour_rates_operation_query(frm) {
	if (!frm.fields_dict.labour_rates || !frm.fields_dict.labour_rates.grid) {
		return;
	}

	const grid = frm.fields_dict.labour_rates.grid;
	const operation_field =
		(grid.get_field("operation_done") && "operation_done")
		|| (grid.get_field("operation") && "operation")
		|| null;
	if (!operation_field) {
		return;
	}

	grid.get_field(operation_field).get_query = () => {
		const make = get_job_card_make(frm);
		if (!make) {
			return {
				filters: {
					name: "__NO_MATCHING_TEMPLATE__"
				}
			};
		}

		const filters = {
			docstatus: 1,
			make
		};

		return { filters };
	};
}

function get_job_card_make(frm) {
	return (
		frm.doc.make
		|| frm.doc.custom_make
		|| ""
	);
}

function get_job_card_weight_class(frm) {
	return (
		frm.doc.weight_class
		|| frm.doc.custom_weight_class
		|| ""
	);
}

function calculate_totals(frm) {
	const custom_total_qty = (frm.doc.supplied_parts || []).reduce(
		(total, row) => total + flt(row.qty),
		0
	);
	const spares_cost = (frm.doc.supplied_parts || []).reduce(
		(total, row) => total + (flt(row.qty) * flt(row.rate)),
		0
	);
	const service_charges = calculate_labour_totals(frm);
	const total_vat_exclusive = spares_cost + service_charges;

	set_total_field_value(frm, "custom_total_qty", custom_total_qty);
	set_total_field_value(frm, "spares_cost", spares_cost);
	set_total_field_value(frm, "service_charges", service_charges);
	set_total_field_value(frm, "total_vat_exclusive", total_vat_exclusive);
	if (frm.fields_dict.labour_rates) {
		frm.refresh_field("labour_rates");
	}
}

function set_labour_row_total(cdt, cdn) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row) {
		return;
	}

	row.total_amount = flt(row.maximum_hours) * flt(row.flat_rate);
}

function calculate_labour_totals(frm) {
	return (frm.doc.labour_rates || []).reduce((total, row) => {
		const row_total = flt(row.maximum_hours) * flt(row.flat_rate);
		row.total_amount = row_total;
		return total + row_total;
	}, 0);
}

function set_total_field_value(frm, fieldname, value) {
	frm.doc[fieldname] = value;
	if (frm.fields_dict[fieldname]) {
		frm.refresh_field(fieldname);
	}
}

function sync_supplied_parts_price_list(
	frm,
	{ fetch_rates = false, only_if_rate_missing = false, clear_rates = false } = {}
) {
	const parent_price_list = frm.doc.price_list || null;

	(frm.doc.supplied_parts || []).forEach((row) => {
		const price_list_changed = row.price_list !== parent_price_list;

		if (price_list_changed) {
			frappe.model.set_value(row.doctype, row.name, "price_list", parent_price_list);
		}

		if (clear_rates) {
			frappe.model.set_value(row.doctype, row.name, "rate", 0);
			return;
		}

		if ((fetch_rates || price_list_changed) && row.item && parent_price_list) {
			fetch_item_price(frm, row.doctype, row.name, { only_if_rate_missing });
		}
	});
}

function sync_row_price_list(frm, cdt, cdn) {
	if (!frm.doc.price_list) {
		return;
	}

	const row = locals[cdt][cdn];
	if (row && row.price_list !== frm.doc.price_list) {
		frappe.model.set_value(cdt, cdn, "price_list", frm.doc.price_list);
	}
}

function refresh_supplied_parts_rates(frm, { force = false } = {}) {
	(frm.doc.supplied_parts || []).forEach((row) => {
		if (row.item) {
			fetch_item_price(frm, row.doctype, row.name, { force });
		}
	});
}

function fetch_item_price(frm, cdt, cdn, { force = false, only_if_rate_missing = false } = {}) {
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
			calculate_totals(frm);
		}
	});
}

function validate_rate_limit(frm, cdt, cdn) {
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
			const part_label = current_row.item_name || current_row.item;

			if (!approved_rate) {
				frappe.msgprint({
					title: "Price Change Request Required",
					indicator: "orange",
					message:
						`${part_label} has no approved Item Price in ${price_list}. ` +
						"Raise a Price Change Request for Management Approval before entering a rate."
				});
				return;
			}

			if (flt(current_row.rate) > approved_rate) {
				frappe.msgprint({
					title: "Price Change Request Required",
					indicator: "orange",
					message:
						`The maximum allowed rate for ${part_label} is ${approved_rate}. ` +
						"Raise a Price Change Request for Management Approval before saving a higher rate."
				});
			}
		}
	});
}
