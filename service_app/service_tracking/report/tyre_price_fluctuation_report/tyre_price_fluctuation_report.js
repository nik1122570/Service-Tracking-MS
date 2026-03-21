frappe.query_reports["Tyre Price Fluctuation Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -12)
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "item_code",
			label: __("Item"),
			fieldtype: "Link",
			options: "Item"
		},
		{
			fieldname: "brand",
			label: __("Tyre Brand"),
			fieldtype: "Data"
		},
		{
			fieldname: "price_list",
			label: __("Price List"),
			fieldtype: "Link",
			options: "Price List"
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier"
		}
	]
};
