// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Trip Settlement Batch", {
	refresh(frm) {
		set_transaction_date(frm);
		set_target_doctype(frm);
		set_party_requirements(frm);
		calculate_totals(frm);

		frm.add_custom_button(__("View Summary"), () => view_summary(frm), __("Reports"));

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Entitlements"), () => get_entitlements(frm));
		}

		if (frm.doc.docstatus === 1 && !frm.doc.target_document && frm.doc.status !== "Unreconciled") {
			frm.add_custom_button(__("Create ERPNext Document"), () => create_erpnext_document(frm), __("Actions"));
			frm.add_custom_button(__("Unreconcile"), () => unreconcile_batch(frm), __("Actions"));
		}

		if (frm.doc.target_doctype && frm.doc.target_document) {
			frm.add_custom_button(
				__("Open {0}", [frm.doc.target_doctype]),
				() => frappe.set_route("Form", frm.doc.target_doctype, frm.doc.target_document),
				__("Actions")
			);

			if (frm.doc.docstatus === 1) {
				frm.add_custom_button(
					__("Unlink ERPNext Document"),
					() => unlink_target_document(frm),
					__("Actions")
				);
			}
		}
	},

	settlement_type(frm) {
		set_target_doctype(frm);
		set_party_requirements(frm);
	},

	validate(frm) {
		set_transaction_date(frm);
		set_target_doctype(frm);
		calculate_totals(frm);
	},

	items_add(frm) {
		calculate_totals(frm);
	},

	items_remove(frm) {
		calculate_totals(frm);
	},
});

function set_transaction_date(frm) {
	if (frappe.meta.has_field(frm.doctype, "transaction_date") && !frm.doc.transaction_date) {
		frm.set_value("transaction_date", frappe.datetime.get_today());
	}
}

function set_target_doctype(frm) {
	const target_doctype = {
		Revenue: "Sales Order",
		Fuel: "Material Request",
		Mileage: "Purchase Order",
	}[frm.doc.settlement_type] || "";

	if (frm.doc.target_doctype !== target_doctype) {
		frm.set_value("target_doctype", target_doctype);
	}
}

function set_party_requirements(frm) {
	frm.toggle_reqd("customer", frm.doc.settlement_type === "Revenue");
	frm.toggle_reqd("supplier", frm.doc.settlement_type === "Mileage");
}

function calculate_totals(frm) {
	const rows = frm.doc.items || [];
	const total_qty = rows.reduce((total, row) => total + flt(row.quantity), 0);
	const total_amount = rows.reduce((total, row) => total + flt(row.amount), 0);

	frm.set_value("total_qty", total_qty);
	frm.set_value("total_amount", total_amount);
}

function get_entitlements(frm) {
	const required_fields = ["settlement_type", "start_date", "end_date", "project"];
	const missing_fields = required_fields.filter((fieldname) => !frm.doc[fieldname]);

	if (missing_fields.length) {
		frappe.msgprint(__("Please set Settlement Type, Start Date, End Date, and Project first."));
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.get_pending_entitlements",
		args: {
			settlement_type: frm.doc.settlement_type,
			start_date: frm.doc.start_date,
			end_date: frm.doc.end_date,
			project: frm.doc.project,
			vehicle: frm.doc.vehicle,
		},
		callback(response) {
			const rows = response.message || [];
			frm.clear_table("items");

			rows.forEach((source_row) => {
				const row = frm.add_child("items");
				Object.assign(row, source_row);
			});

			frm.refresh_field("items");
			calculate_totals(frm);
			frappe.show_alert({
				message: __("{0} entitlement rows loaded.", [rows.length]),
				indicator: rows.length ? "green" : "orange",
			});
		},
	});
}

function view_summary(frm) {
	const required_fields = ["start_date", "end_date", "project"];
	const missing_fields = required_fields.filter((fieldname) => !frm.doc[fieldname]);

	if (missing_fields.length) {
		frappe.msgprint(__("Please set Start Date, End Date, and Project first."));
		return;
	}

	frappe.set_route("query-report", "Trip Entitlement Summary Report", {
		from_date: frm.doc.start_date,
		to_date: frm.doc.end_date,
		project: frm.doc.project,
		vehicle: frm.doc.vehicle || undefined,
	});
}

function unreconcile_batch(frm) {
	frappe.confirm(
		__(
			"Unreconcile this Trip Settlement Batch? This will release the linked trip entitlement rows so the batch and trip logs can be cancelled."
		),
		() => {
			frappe.call({
				method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.unreconcile_batch",
				args: {
					source_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Unreconciling Trip Settlement Batch..."),
				callback(response) {
					const result = response.message || {};
					frappe.show_alert({
						message: __("{0} entitlement rows released.", [result.released_rows || 0]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}
	);
}

function unlink_target_document(frm) {
	frappe.confirm(
		__(
			"Unlink {0} {1} from this Trip Settlement Batch? This will let you cancel the ERPNext document first, then unreconcile the batch.",
			[frm.doc.target_doctype, frm.doc.target_document]
		),
		() => {
			frappe.call({
				method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.unlink_target_document",
				args: {
					source_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Unlinking ERPNext document..."),
				callback(response) {
					const result = response.message || {};
					frappe.show_alert({
						message: __("{0} entitlement rows moved back to Batched.", [
							result.relinked_rows || 0,
						]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		}
	);
}

function create_erpnext_document(frm) {
	frappe.confirm(
		__("Create {0} from this Trip Settlement Batch?", [frm.doc.target_doctype || "ERPNext Document"]),
		() => {
			frappe.call({
				method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.create_erpnext_document",
				args: {
					source_name: frm.doc.name,
				},
				freeze: true,
				freeze_message: __("Creating ERPNext document..."),
				callback(response) {
					const target = response.message || {};
					if (!target.name) {
						return;
					}

					frappe.show_alert({
						message: __("{0} {1} created successfully.", [target.doctype, target.name]),
						indicator: "green",
					});
					frm.reload_doc().then(() => {
						frappe.set_route("Form", target.doctype, target.name);
					});
				},
			});
		}
	);
}
