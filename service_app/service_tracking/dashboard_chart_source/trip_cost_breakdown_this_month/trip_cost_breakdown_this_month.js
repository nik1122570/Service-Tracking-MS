frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Trip Cost Breakdown This Month"] = {
	method: "service_app.service_tracking.charts.get_trip_cost_breakdown",
	filters: [],
};
