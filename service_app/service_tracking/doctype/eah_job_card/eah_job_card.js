frappe.ui.form.on("EAH Job Card", {
	setup(frm) {
		set_supplied_parts_field_state(frm);
		calculate_totals(frm);
	},

	refresh(frm) {
		set_supplied_parts_field_state(frm);
		sync_supplied_parts_price_list(frm, {
			fetch_rates: true,
			only_if_rate_missing: true,
			clear_rates: !frm.doc.price_list
		});
		calculate_totals(frm);

		if (!frm.is_new()) {
			frm.add_custom_button("Price Insight", () => {
				show_price_history_insight(frm);
			}, "View");
		}

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

function set_supplied_parts_field_state(frm) {
	if (frm.fields_dict.supplied_parts && frm.fields_dict.supplied_parts.grid) {
		frm.fields_dict.supplied_parts.grid.update_docfield_property("price_list", "read_only", 1);
	}
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

function show_price_history_insight(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.get_price_history_insight",
		args: {
			job_card: frm.doc.name
		},
		freeze: true,
		freeze_message: __("Checking purchase price history..."),
		callback: (r) => {
			const insight = r.message || {};
			const dialog = new frappe.ui.Dialog({
				title: __("Price Insight for {0}", [frm.doc.name]),
				size: "extra-large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "price_insight_html"
					}
				],
				primary_action_label: __("Close"),
				primary_action: () => dialog.hide()
			});

			dialog.set_value("price_insight_html", build_price_history_html(insight));
			dialog.show();
		}
	});
}

function build_price_history_html(insight) {
	const summary = insight.summary || {};
	const rows = insight.rows || [];
	const currency = insight.currency || "TZS";

	if (!rows.length) {
		return `<p class="text-muted">${__("No supplied parts found for price insight.")}</p>`;
	}

	const summary_html = `
		<div class="eah-price-summary">
			${build_price_summary_card(__("Items Checked"), summary.total || 0, "neutral")}
			${build_price_summary_card(__("Normal"), summary.normal || 0, "normal")}
			${build_price_summary_card(__("Review"), summary.review || 0, "review")}
			${build_price_summary_card(__("High Risk"), summary.high_risk || 0, "high-risk")}
			${build_price_summary_card(__("No History"), summary.no_history || 0, "no-history")}
		</div>
	`;

	const table_rows = rows.map((row) => {
		const status_class = `status-${row.status || "normal"}`;
		const change = format_percent(row.change_percent);
		const last_po = row.last_purchase_order
			? `<a href="/app/purchase-order/${encodeURIComponent(row.last_purchase_order)}">${escape_html(row.last_purchase_order)}</a>`
			: "-";

		return `
			<tr>
				<td>
					<div><strong>${escape_html(row.item_name || row.item || "")}</strong></div>
					<div class="text-muted small">${escape_html(row.item || "")}</div>
				</td>
				<td class="text-right">${format_number(row.qty)}</td>
				<td class="text-right">${format_currency(row.current_rate, currency)}</td>
				<td class="text-right">${format_currency(row.last_purchase_rate, currency)}</td>
				<td class="text-right ${get_change_class(row.change_percent)}">${change}</td>
				<td class="text-right">${format_currency(row.lowest_90_days, currency)}</td>
				<td class="text-right">${format_currency(row.highest_90_days, currency)}</td>
				<td>${escape_html(row.last_supplier || "-")}</td>
				<td>${last_po}</td>
				<td>${escape_html(row.last_purchase_date || "-")}</td>
				<td><span class="eah-price-status ${status_class}">${escape_html(row.status_label || "")}</span></td>
			</tr>
		`;
	}).join("");

	return `
		<style>
			.eah-price-summary {
				display: grid;
				grid-template-columns: repeat(5, minmax(110px, 1fr));
				gap: 8px;
				margin-bottom: 14px;
			}
			.eah-price-card {
				border: 1px solid var(--border-color);
				border-radius: 8px;
				padding: 10px;
				background: var(--fg-color);
			}
			.eah-price-card .label {
				color: var(--text-muted);
				font-size: 12px;
			}
			.eah-price-card .value {
				font-size: 20px;
				font-weight: 700;
				line-height: 1.2;
			}
			.eah-price-card.normal .value { color: #1f8f4d; }
			.eah-price-card.review .value { color: #b7791f; }
			.eah-price-card.high-risk .value { color: #c53030; }
			.eah-price-card.no-history .value { color: #5a67d8; }
			.eah-price-table-wrap {
				max-height: 430px;
				overflow: auto;
				border: 1px solid var(--border-color);
				border-radius: 8px;
			}
			.eah-price-table {
				margin: 0;
				white-space: nowrap;
			}
			.eah-price-table thead th {
				position: sticky;
				top: 0;
				background: var(--fg-color);
				z-index: 1;
			}
			.eah-price-status {
				border-radius: 999px;
				padding: 3px 8px;
				font-size: 12px;
				font-weight: 600;
			}
			.eah-price-status.status-normal {
				background: #e6f4ea;
				color: #1f8f4d;
			}
			.eah-price-status.status-review {
				background: #fff4de;
				color: #9a5b00;
			}
			.eah-price-status.status-high_risk {
				background: #fde8e8;
				color: #b42318;
			}
			.eah-price-status.status-no_history {
				background: #eef2ff;
				color: #4c51bf;
			}
			.eah-price-positive { color: #c53030; font-weight: 600; }
			.eah-price-negative { color: #1f8f4d; font-weight: 600; }
		</style>
		<div>
			<div class="text-muted" style="margin-bottom: 10px;">
				${__("Supplier")}: <strong>${escape_html(insight.supplier || "-")}</strong>
				&nbsp; | &nbsp;
				${__("Price List")}: <strong>${escape_html(insight.price_list || "-")}</strong>
			</div>
			${summary_html}
			<div class="eah-price-table-wrap">
				<table class="table table-bordered eah-price-table">
					<thead>
						<tr>
							<th>${__("Item")}</th>
							<th class="text-right">${__("Qty")}</th>
							<th class="text-right">${__("Current Rate")}</th>
							<th class="text-right">${__("Last PO Rate")}</th>
							<th class="text-right">${__("Change")}</th>
							<th class="text-right">${__("Lowest 90 Days")}</th>
							<th class="text-right">${__("Highest 90 Days")}</th>
							<th>${__("Last Supplier")}</th>
							<th>${__("Last PO")}</th>
							<th>${__("Last Date")}</th>
							<th>${__("Status")}</th>
						</tr>
					</thead>
					<tbody>${table_rows}</tbody>
				</table>
			</div>
		</div>
	`;
}

function build_price_summary_card(label, value, status) {
	return `
		<div class="eah-price-card ${status}">
			<div class="label">${escape_html(label)}</div>
			<div class="value">${cint(value)}</div>
		</div>
	`;
}

function format_currency(value, currency) {
	if (value === null || value === undefined || value === "") {
		return "-";
	}

	return frappe.format(flt(value), {
		fieldtype: "Currency",
		options: currency
	});
}

function format_number(value) {
	if (value === null || value === undefined || value === "") {
		return "-";
	}

	return format_number_with_precision(flt(value), 3);
}

function format_number_with_precision(value, precision) {
	return frappe.format(value, {
		fieldtype: "Float",
		precision
	});
}

function format_percent(value) {
	if (value === null || value === undefined) {
		return "-";
	}

	const formatted = frappe.format(flt(value), {
		fieldtype: "Percent",
		precision: 1
	});
	return flt(value) > 0 ? `+${formatted}` : formatted;
}

function get_change_class(value) {
	if (value === null || value === undefined) {
		return "";
	}

	return flt(value) > 0 ? "eah-price-positive" : "eah-price-negative";
}

function escape_html(value) {
	return frappe.utils.escape_html(String(value || ""));
}
