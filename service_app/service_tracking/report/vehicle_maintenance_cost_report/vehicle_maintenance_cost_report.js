frappe.query_reports["Vehicle Maintenance Cost Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "vehicles",
			label: __("Vehicle"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return frappe.db.get_link_options("Vehicle", txt);
			},
		},
	],
};
