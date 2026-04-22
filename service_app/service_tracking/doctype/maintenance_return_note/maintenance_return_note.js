frappe.ui.form.on("Maintenance Return Note", {
	setup(frm) {
		frm.set_query("eah_job_card", () => ({
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
		frm.add_custom_button("Spare Parts Ledger", () => {
			open_spare_parts_ledger_dialog(frm);
		}, "View");

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Used Spare Parts Issue Note", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.maintenance_return_note.maintenance_return_note.make_used_spare_parts_issue_note",
					frm: frm,
				});
			}, "Create");
		}
	},

	source_type(frm) {
		apply_source_type_mode(frm);

		if (frm.doc.source_type === "Manual") {
			frm.set_value("eah_job_card", "");
			return;
		}

		frm.set_value("manual_reason", "");
		if (frm.doc.eah_job_card) {
			populate_header_from_job_card(frm);
		}
	},

	eah_job_card(frm) {
		if (frm.doc.source_type !== "From EAH Job Card" || !frm.doc.eah_job_card) {
			return;
		}

		populate_header_from_job_card(frm);
	}
});

function apply_source_type_mode(frm) {
	const is_from_job_card = frm.doc.source_type !== "Manual";

	frm.toggle_reqd("eah_job_card", is_from_job_card);
	frm.toggle_reqd("manual_reason", !is_from_job_card);

	frm.set_df_property("vehicle", "read_only", is_from_job_card ? 1 : 0);
	frm.set_df_property("service_date", "read_only", is_from_job_card ? 1 : 0);
	frm.set_df_property("supplier", "read_only", is_from_job_card ? 1 : 0);

	frm.refresh_fields([
		"eah_job_card",
		"manual_reason",
		"vehicle",
		"service_date",
		"supplier"
	]);
}

function populate_header_from_job_card(frm) {
	frappe.db
		.get_value("EAH Job Card", frm.doc.eah_job_card, ["vehicle", "service_date", "supplier"])
		.then((r) => {
			if (!r || !r.message) {
				return;
			}

			frm.set_value({
				vehicle: r.message.vehicle || "",
				service_date: r.message.service_date || "",
				supplier: r.message.supplier || ""
			});
		});
}

function open_spare_parts_ledger_dialog(frm) {
	const itemOptions = get_return_note_item_options(frm);
	if (!itemOptions.length) {
		frappe.msgprint(__("Add at least one returned part item to view Spare Parts Ledger records."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Spare Parts Ledger View"),
		fields: [
			{
				fieldtype: "Select",
				fieldname: "item",
				label: __("Item"),
				options: itemOptions.join("\n"),
				reqd: 1
			},
			{
				fieldtype: "Int",
				fieldname: "limit",
				label: __("Rows to Show"),
				default: 30,
				reqd: 1
			},
			{
				fieldtype: "HTML",
				fieldname: "ledger_html"
			}
		],
		primary_action_label: __("Refresh"),
		primary_action(values) {
			load_spare_parts_ledger(frm, dialog, values.item, values.limit);
		}
	});

	dialog.show();
	dialog.set_value("item", itemOptions[0]);
	load_spare_parts_ledger(frm, dialog, itemOptions[0], 30);

	dialog.get_field("item").$input.on("change", () => {
		const values = dialog.get_values() || {};
		if (values.item) {
			load_spare_parts_ledger(frm, dialog, values.item, values.limit || 30);
		}
	});
}

function get_return_note_item_options(frm) {
	const seen = new Set();
	const options = [];

	(frm.doc.returned_parts || []).forEach((row) => {
		if (!row.item || seen.has(row.item)) {
			return;
		}

		seen.add(row.item);
		options.push(row.item);
	});

	return options;
}

function load_spare_parts_ledger(frm, dialog, item, limit) {
	dialog.fields_dict.ledger_html.$wrapper.html(
		`<div class="text-muted">${__("Loading ledger records...")}</div>`
	);

	frappe.call({
		method: "service_app.service_tracking.doctype.maintenance_return_note.maintenance_return_note.get_spare_parts_ledger_snapshot",
		args: {
			item,
			vehicle: frm.doc.vehicle || "",
			eah_job_card: frm.doc.eah_job_card || "",
			limit: limit || 30
		},
		callback: (r) => {
			const payload = r.message || {};
			const rows = payload.rows || [];
			const summary = payload.summary || {};
			dialog.fields_dict.ledger_html.$wrapper.html(render_spare_parts_ledger_html(item, rows, summary));
		},
		error: () => {
			dialog.fields_dict.ledger_html.$wrapper.html(
				`<div class="text-danger">${__("Unable to load Spare Parts Ledger data right now.")}</div>`
			);
		}
	});
}

function render_spare_parts_ledger_html(item, rows, summary) {
	const safe = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

	const summaryHtml = `
		<div style="margin-bottom: 10px;">
			<b>${__("Item")}:</b> ${safe(item)} |
			<b>${__("Period")}:</b> ${safe(summary.from_date || "")} ${__("to")} ${safe(summary.to_date || "")} |
			<b>${__("Movements")}:</b> ${safe(summary.movement_count || 0)} |
			<b>${__("In")}:</b> ${format_number(summary.total_in_qty)} |
			<b>${__("Out")}:</b> ${format_number(summary.total_out_qty)} |
			<b>${__("Balance")}:</b> ${format_number(summary.balance_qty)}
		</div>
	`;

	if (!rows.length) {
		return (
			summaryHtml +
			`<div class="text-muted">${__("No ledger movements found for this item in the current scope.")}</div>`
		);
	}

	const rowHtml = rows
		.map((row) => `
			<tr>
				<td>${safe(row.posting_date)}</td>
				<td>${safe(row.movement_type)}</td>
				<td>${safe(row.source_doctype)}</td>
				<td>${safe(row.source_document)}</td>
				<td style="text-align:right;">${format_number(row.in_qty)}</td>
				<td style="text-align:right;">${format_number(row.out_qty)}</td>
				<td style="text-align:right;"><b>${format_number(row.balance_qty)}</b></td>
				<td>${safe(row.condition)}</td>
				<td>${safe(row.disposition)}</td>
				<td>${safe(row.remarks)}</td>
			</tr>
		`)
		.join("");

	return `
		${summaryHtml}
		<div style="max-height: 360px; overflow: auto; border: 1px solid #d1d8dd; border-radius: 6px;">
			<table class="table table-bordered" style="margin: 0;">
				<thead>
					<tr>
						<th>${__("Posting Date")}</th>
						<th>${__("Movement Type")}</th>
						<th>${__("Source Type")}</th>
						<th>${__("Source Document")}</th>
						<th style="text-align:right;">${__("In Qty")}</th>
						<th style="text-align:right;">${__("Out Qty")}</th>
						<th style="text-align:right;">${__("Balance Qty")}</th>
						<th>${__("Condition")}</th>
						<th>${__("Disposition")}</th>
						<th>${__("Remarks")}</th>
					</tr>
				</thead>
				<tbody>${rowHtml}</tbody>
			</table>
		</div>
	`;
}

function format_number(value) {
	return frappe.format(value || 0, { fieldtype: "Float", precision: 2 });
}
