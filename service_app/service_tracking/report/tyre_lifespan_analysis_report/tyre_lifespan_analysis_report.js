frappe.query_reports["Tyre Lifespan Analysis Report"] = {
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
			fieldname: "vehicles",
			label: __("Vehicle"),
			fieldtype: "MultiSelectList",
			get_data(txt) {
				return frappe.db.get_link_options("Vehicle", txt);
			}
		},
		{
			fieldname: "brand",
			label: __("Tyre Brand"),
			fieldtype: "Data"
		},
		{
			fieldname: "wheel_position",
			label: __("Wheel Position"),
			fieldtype: "Link",
			options: "Tyre Position"
		}
	]
};
