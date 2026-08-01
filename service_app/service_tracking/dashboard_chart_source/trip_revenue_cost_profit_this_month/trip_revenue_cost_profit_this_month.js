frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Trip Revenue Cost Profit This Month"] = {
	method: "service_app.service_tracking.charts.get_trip_revenue_cost_profit",
	filters: [],
};
