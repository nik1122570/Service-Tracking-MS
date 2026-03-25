frappe.ui.form.on("Trip Simulation", {
	sales_order(frm) {
		if (!frm.doc.sales_order) {
			frm.set_df_property("sales_order_revenue_allocation", "options", "");
			return;
		}

		maybe_refresh_trip_simulation_preview(frm);
	},
	trip_route(frm) {
		if (!frm.doc.trip_route || !frm.doc.sales_order) {
			return;
		}

		maybe_refresh_trip_simulation_preview(frm);
	},
	sales_order_revenue_allocation(frm) {
		if (!frm.doc.sales_order || !frm.doc.trip_route) {
			return;
		}

		refresh_trip_simulation_preview(frm);
	}
});

function maybe_refresh_trip_simulation_preview(frm) {
	if (frm.doc.estimated_costs?.length) {
		frappe.confirm(
			"Refresh the simulation from the selected Sales Order and Route? Existing estimated cost rows will be replaced.",
			() => refresh_trip_simulation_preview(frm),
			() => {}
		);
		return;
	}

	refresh_trip_simulation_preview(frm);
}

function refresh_trip_simulation_preview(frm) {
	if (!frm.doc.sales_order || !frm.doc.trip_route) {
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.doctype.trip_simulation.trip_simulation.get_trip_simulation_preview",
		args: {
			sales_order: frm.doc.sales_order,
			trip_route: frm.doc.trip_route,
			allocation_name: frm.doc.sales_order_revenue_allocation || "",
			simulation_name: frm.doc.name || ""
		},
		callback: ({ message }) => {
			if (!message) {
				return;
			}

			const allocationOptions = [""].concat(
				(message.allocation_options || []).map((option) => option.value)
			);
			frm.set_df_property(
				"sales_order_revenue_allocation",
				"options",
				allocationOptions.join("\n")
			);

			frm.set_value(
				"sales_order_revenue_allocation",
				message.sales_order_revenue_allocation || ""
			);

			frm.set_value("customer", message.customer || "");
			frm.set_value("cost_center", message.cost_center || "");
			frm.set_value("expected_revenue", message.expected_revenue || 0);
			frm.set_value("target_profit_margin", message.target_profit_margin || 0);
			frm.set_value("trip_days", message.trip_days || 0);
			frm.set_value("total_distance_km", message.total_distance_km || 0);
			frm.set_value("total_fuel_estimate_ltr", message.total_fuel_estimate_ltr || 0);
			frm.set_value("total_estimated_cost", message.total_estimated_cost || 0);
			frm.set_value("expected_gross_profit", message.expected_gross_profit || 0);
			frm.set_value("expected_profit_margin", message.expected_profit_margin || 0);
			frm.set_value("below_target_margin", message.below_target_margin ? 1 : 0);

			frm.clear_table("estimated_costs");
			(message.estimated_costs || []).forEach((row) => {
				const child = frm.add_child("estimated_costs");
				Object.assign(child, row);
			});
			frm.refresh_field("estimated_costs");
		}
	});
}
