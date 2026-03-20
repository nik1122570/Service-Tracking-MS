frappe.query_reports["Tyre Ledger Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12),
			reqd: 1
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "vehicle",
			label: __("Vehicle"),
			fieldtype: "Link",
			options: "Vehicle"
		},
		{
			fieldname: "brand",
			label: __("Brand"),
			fieldtype: "Data"
		},
		{
			fieldname: "serial_no",
			label: __("Serial Number"),
			fieldtype: "Data"
		}
	]
};
