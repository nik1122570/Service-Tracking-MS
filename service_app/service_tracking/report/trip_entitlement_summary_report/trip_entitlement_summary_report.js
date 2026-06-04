frappe.query_reports["Trip Entitlement Summary Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.month_start(),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "invoice_as_at_date",
			label: __("Invoice As At Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
			description: __("Includes submitted Sales Invoices posted on or before this date."),
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "vehicle",
			label: __("Truck / Vehicle"),
			fieldtype: "Link",
			options: "Vehicle",
		},
		{
			fieldname: "driver",
			label: __("Driver"),
			fieldtype: "Link",
			options: "Drivers",
		},
		{
			fieldname: "entitlement_status",
			label: __("Entitlement Status"),
			fieldtype: "Select",
			options: "\nPending\nBatched\nProcessed\nCancelled",
		},
	],
};
