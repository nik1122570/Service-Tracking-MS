frappe.query_reports["Fuel Card Movement Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "fuel_card",
			label: __("Fuel Card"),
			fieldtype: "Link",
			options: "Fuel Card",
		},
		{
			fieldname: "transaction_type",
			label: __("Transaction Type"),
			fieldtype: "Select",
			options: "\nRecharge\nTrip Usage\nOffice Car Usage\nAdjustment\nCancellation",
		},
		{
			fieldname: "vehicle",
			label: __("Vehicle"),
			fieldtype: "Link",
			options: "Vehicle",
		},
		{
			fieldname: "reference_doctype",
			label: __("Reference Doctype"),
			fieldtype: "Link",
			options: "DocType",
		},
	],
};
