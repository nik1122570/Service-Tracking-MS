frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Spare Parts Consumption by Item"] = {
	method: "service_app.service_tracking.charts.get_spare_parts_consumption",
	filters: [],
};
