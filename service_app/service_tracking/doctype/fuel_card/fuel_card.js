// Copyright (c) 2026, Nickson and contributors
// For license information, please see license.txt

frappe.ui.form.on("Fuel Card", {
	refresh(frm) {
		if (frm.doc.name && !frm.is_new()) {
			frm.add_custom_button(__("Recharge Fuel"), () => {
				show_recharge_dialog(frm);
			});

			frm.add_custom_button(__("Issue Fuel"), () => {
				show_issue_dialog(frm);
			});

			frm.add_custom_button(__("View Ledger"), () => {
				frappe.set_route("query-report", "Fuel Card Movement Report", {
					fuel_card: frm.doc.name,
				});
			}, __("View"));

			frm.add_custom_button(__("Recharges"), () => {
				frappe.set_route("List", "Fuel Card Recharge", {
					fuel_card: frm.doc.name,
				});
			}, __("View"));

			frm.add_custom_button(__("Issues"), () => {
				frappe.set_route("List", "Fuel Card Issue", {
					fuel_card: frm.doc.name,
				});
			}, __("View"));
		}
	},
});

function show_recharge_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Recharge Fuel Card"),
		fields: [
			{
				fieldname: "posting_date",
				fieldtype: "Date",
				label: __("Posting Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "purchase_order",
				fieldtype: "Link",
				label: __("Purchase Order"),
				options: "Purchase Order",
			},
			{
				fieldname: "purchase_invoice",
				fieldtype: "Link",
				label: __("Purchase Invoice"),
				options: "Purchase Invoice",
			},
			{
				fieldname: "litres",
				fieldtype: "Float",
				label: __("Purchase Qty / Litres"),
				reqd: 1,
				onchange: () => update_dialog_amount(dialog),
			},
			{
				fieldname: "rate",
				fieldtype: "Currency",
				label: __("Rate per Litre"),
				reqd: 1,
				onchange: () => update_dialog_amount(dialog),
			},
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Monetary Value"),
				read_only: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Recharge"),
		primary_action(values) {
			frappe.call({
				method: "service_app.service_tracking.doctype.fuel_card.fuel_card.quick_recharge",
				args: Object.assign(values, {
					fuel_card: frm.doc.name,
				}),
				freeze: true,
				freeze_message: __("Recharging Fuel Card..."),
				callback(response) {
					dialog.hide();
					frappe.show_alert({
						message: __("Fuel Card recharged via {0}", [response.message.name]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

function show_issue_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Issue Fuel"),
		fields: [
			{
				fieldname: "posting_date",
				fieldtype: "Date",
				label: __("Posting Date"),
				default: frappe.datetime.get_today(),
				reqd: 1,
			},
			{
				fieldname: "issue_type",
				fieldtype: "Select",
				label: __("Issue Type"),
				options: "Office Car Usage\nAdjustment",
				default: "Office Car Usage",
				reqd: 1,
			},
			{
				fieldname: "vehicle",
				fieldtype: "Link",
				label: __("Vehicle"),
				options: "Vehicle",
			},
			{
				fieldname: "driver",
				fieldtype: "Link",
				label: __("Driver"),
				options: "Drivers",
			},
			{
				fieldname: "employee",
				fieldtype: "Link",
				label: __("Employee"),
				options: "Employee",
			},
			{
				fieldname: "purpose",
				fieldtype: "Data",
				label: __("Purpose"),
			},
			{
				fieldname: "litres",
				fieldtype: "Float",
				label: __("Issued Qty / Litres"),
				reqd: 1,
				onchange: () => update_dialog_amount(dialog),
			},
			{
				fieldname: "rate",
				fieldtype: "Currency",
				label: __("Rate per Litre"),
				reqd: 1,
				onchange: () => update_dialog_amount(dialog),
			},
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Monetary Value"),
				read_only: 1,
			},
			{
				fieldname: "remarks",
				fieldtype: "Small Text",
				label: __("Remarks"),
			},
		],
		primary_action_label: __("Issue Fuel"),
		primary_action(values) {
			frappe.call({
				method: "service_app.service_tracking.doctype.fuel_card.fuel_card.quick_issue",
				args: Object.assign(values, {
					fuel_card: frm.doc.name,
				}),
				freeze: true,
				freeze_message: __("Issuing Fuel..."),
				callback(response) {
					dialog.hide();
					frappe.show_alert({
						message: __("Fuel issued via {0}", [response.message.name]),
						indicator: "green",
					});
					frm.reload_doc();
				},
			});
		},
	});
	dialog.show();
}

function update_dialog_amount(dialog) {
	const litres = flt(dialog.get_value("litres"));
	const rate = flt(dialog.get_value("rate"));
	dialog.set_value("amount", litres * rate);
}
