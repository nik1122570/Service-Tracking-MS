frappe.query_reports["Tyre Request to Purchase Lead Time Report"] = {
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
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier"
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "Link",
			options: "Project"
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center"
		},
		{
			fieldname: "brand",
			label: __("Tyre Brand"),
			fieldtype: "Data"
		}
	]
};
