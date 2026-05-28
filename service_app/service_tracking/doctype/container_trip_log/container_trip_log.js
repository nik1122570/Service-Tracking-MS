// Copyright (c) 2026, Nickson  and contributors
// For license information, please see license.txt

frappe.ui.form.on("Container Trip Log", {
	refresh(frm) {
		set_trip_totals(frm);

		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Unreconcile"), () => unreconcile_linked_batches(frm), __("Actions"));
		}
	},

	validate(frm) {
		set_trip_totals(frm);
	},

	expected_revenue(frm) {
		set_trip_totals(frm);
	},

	driver_mileage_per_trip(frm) {
		set_trip_totals(frm);
	},

	container_add(frm) {
		set_trip_totals(frm);
	},

	container_remove(frm) {
		set_trip_totals(frm);
	},
});

frappe.ui.form.on("Container Holder", {
	container_id(frm, cdt, cdn) {
		clear_duplicate_container_in_current_trip(frm, cdt, cdn);
	},
});

function set_trip_totals(frm) {
	const total_qty = (frm.doc.container || []).length;
	const expected_revenue = flt(frm.doc.expected_revenue);
	const driver_mileage_per_trip = flt(frm.doc.driver_mileage_per_trip);

	frm.set_value("total_qty", total_qty);
	frm.set_value("total_expected_revenue", expected_revenue * total_qty);
	frm.set_value("expected_mileage_pay", driver_mileage_per_trip * total_qty);
}

function clear_duplicate_container_in_current_trip(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row.container_id) {
		return;
	}

	const duplicate = (frm.doc.container || []).some((container_row) => {
		return container_row.name !== row.name && container_row.container_id === row.container_id;
	});

	if (!duplicate) {
		return;
	}

	frappe.msgprint({
		title: __("Duplicate Container"),
		message: __("Container {0} has already been selected in this Trip Log.", [frappe.bold(row.container_id)]),
		indicator: "orange",
	});
	frappe.model.set_value(cdt, cdn, "container_id", "");
}

function unreconcile_linked_batches(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.get_linked_settlement_batches",
		args: {
			trip_log: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Checking linked settlement batches..."),
		callback(response) {
			const batches = response.message || [];
			if (!batches.length) {
				frappe.msgprint({
					title: __("No Settlement Batches"),
					message: __("No submitted Trip Settlement Batches are linked to this Container Trip Log."),
					indicator: "blue",
				});
				return;
			}

			const blocked_batches = batches.filter((batch) => batch.target_document);
			if (blocked_batches.length) {
				const batch_list = blocked_batches
					.map((batch) => `${batch.name} (${batch.target_doctype} ${batch.target_document})`)
					.join("<br>");

				frappe.msgprint({
					title: __("Cannot Unreconcile"),
					message: __(
						"Cancel or reverse the ERPNext documents created by these batches first:<br>{0}",
						[batch_list]
					),
					indicator: "red",
				});
				return;
			}

			const batch_names = batches.map((batch) => batch.name).join(", ");
			frappe.confirm(
				__(
					"Unreconcile linked Trip Settlement Batches {0}? This will release their trip entitlement rows so they can be cancelled.",
					[frappe.bold(batch_names)]
				),
				() => run_unreconcile_linked_batches(frm)
			);
		},
	});
}

function run_unreconcile_linked_batches(frm) {
	frappe.call({
		method: "service_app.service_tracking.doctype.trip_settlement_batch.trip_settlement_batch.unreconcile_linked_batches",
		args: {
			trip_log: frm.doc.name,
		},
		freeze: true,
		freeze_message: __("Unreconciling linked settlement batches..."),
		callback(response) {
			const results = response.message || [];
			const released_rows = results.reduce((total, row) => total + cint(row.released_rows), 0);

			frappe.show_alert({
				message: __("{0} batches unreconciled; {1} entitlement rows released.", [
					results.length,
					released_rows,
				]),
				indicator: "green",
			});
			frm.reload_doc();
		},
	});
}
