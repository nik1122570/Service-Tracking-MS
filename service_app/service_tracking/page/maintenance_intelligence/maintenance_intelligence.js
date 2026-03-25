frappe.pages["maintenance-intelligence"].on_page_load = function (wrapper) {
	new service_app.MaintenanceIntelligencePage(wrapper);
};

frappe.provide("service_app");

service_app.MaintenanceIntelligencePage = class MaintenanceIntelligencePage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Maintenance Intelligence"),
			single_column: true,
		});
		this.chart_instances = {};
		this.currency = frappe.defaults.get_default("currency");
		this.make_filters();
		this.make_actions();
		this.make_layout();
		this.refresh();
		frappe.breadcrumbs.add("Service Tracking");
	}

	make_filters() {
		const defaultToDate = frappe.datetime.get_today();
		const defaultFromDate = frappe.datetime.month_start(
			frappe.datetime.add_months(defaultToDate, -11)
		);

		this.filters = {
			from_date: this.page.add_field({
				label: __("From Date"),
				fieldname: "from_date",
				fieldtype: "Date",
				default: defaultFromDate,
				change: () => this.refresh(),
			}),
			to_date: this.page.add_field({
				label: __("To Date"),
				fieldname: "to_date",
				fieldtype: "Date",
				default: defaultToDate,
				change: () => this.refresh(),
			}),
			supplier: this.page.add_field({
				label: __("Supplier"),
				fieldname: "supplier",
				fieldtype: "Link",
				options: "Supplier",
				change: () => this.refresh(),
			}),
			vehicle: this.page.add_field({
				label: __("Vehicle"),
				fieldname: "vehicle",
				fieldtype: "Link",
				options: "Vehicle",
				change: () => this.refresh(),
			}),
		};
	}

	make_actions() {
		this.page.set_primary_action(__("Refresh"), () => this.refresh());
		this.page.add_inner_button(__("Purchase Invoices"), () => {
			frappe.set_route("List", "Purchase Invoice", "List");
		});
	}

	make_layout() {
		this.page.body.empty();
		this.$layout = $(frappe.render_template("maintenance_intelligence")).appendTo(this.page.body);
		this.$generatedAt = this.$layout.find("[data-mi-generated-at]");
		this.$summaryCards = this.$layout.find("[data-mi-summary-cards]");
		this.$insights = this.$layout.find("[data-mi-insights]");
		this.$watchlist = this.$layout.find("[data-mi-watchlist]");
	}

	refresh() {
		if (!this.are_dates_valid()) {
			return;
		}

		frappe.call({
			method:
				"service_app.service_tracking.page.maintenance_intelligence.maintenance_intelligence.get_dashboard_data",
			args: {
				filters: this.get_filters(),
			},
			freeze: false,
			callback: (response) => {
				const data = response.message || {};
				this.currency = data.currency || this.currency;
				this.render(data);
			},
		});
	}

	are_dates_valid() {
		const fromDate = this.filters.from_date.get_value();
		const toDate = this.filters.to_date.get_value();
		if (!fromDate || !toDate) {
			return true;
		}
		if (frappe.datetime.str_to_obj(fromDate) <= frappe.datetime.str_to_obj(toDate)) {
			return true;
		}

		frappe.show_alert({
			message: __("From Date cannot be after To Date."),
			indicator: "red",
		});
		return false;
	}

	get_filters() {
		return {
			from_date: this.filters.from_date.get_value(),
			to_date: this.filters.to_date.get_value(),
			supplier: this.filters.supplier.get_value(),
			vehicle: this.filters.vehicle.get_value(),
		};
	}

	render(data) {
		this.$generatedAt.text(data.generated_at || __("Unknown"));
		this.render_summary_cards(data.summary_cards || []);
		this.render_insights(data.insights || []);
		this.render_watchlist(data.watchlist || []);
		this.render_charts(data.charts || {});
	}

	render_summary_cards(cards) {
		this.$summaryCards.empty();

		if (!cards.length) {
			this.$summaryCards.append(this.get_empty_state(__("No summary cards available.")));
			return;
		}

		cards.forEach((card) => {
			const clickableClass = card.route ? "is-clickable" : "";
			const $card = $(`
				<div class="mi-summary-card ${clickableClass}" data-tone="${card.tone || "neutral"}">
					<div class="mi-card-label">${frappe.utils.escape_html(card.label || "")}</div>
					<div class="mi-card-value">${this.format_value(card.value, card.fieldtype)}</div>
					<div class="mi-card-trend">${frappe.utils.escape_html(card.trend || "")}</div>
					<div class="mi-card-note">${frappe.utils.escape_html(card.note || "")}</div>
				</div>
			`);

			if (card.route) {
				$card.on("click", () => this.navigate(card.route, card.route_options));
			}

			this.$summaryCards.append($card);
		});
	}

	render_insights(insights) {
		this.$insights.empty();

		if (!insights.length) {
			this.$insights.append(this.get_empty_state(__("No insights available for the current filter selection.")));
			return;
		}

		insights.forEach((insight) => {
			this.$insights.append(`
				<div class="mi-insight-item" data-tone="${insight.tone || "neutral"}">
					<div class="mi-insight-title">${frappe.utils.escape_html(insight.title || "")}</div>
					<div class="mi-insight-body">${frappe.utils.escape_html(insight.body || "")}</div>
				</div>
			`);
		});
	}

	render_watchlist(rows) {
		this.$watchlist.empty();

		if (!rows.length) {
			this.$watchlist.append(
				this.get_empty_state(
					__("No vehicles currently fall into the due-soon or recently overdue window.")
				)
			);
			return;
		}

		rows.forEach((row) => {
			const $row = $(`
				<div class="mi-watchlist-row" data-tone="${row.tone || "neutral"}">
					<span class="mi-watchlist-tag">${frappe.utils.escape_html(row.status || "")}</span>
					<div class="mi-watchlist-title">${frappe.utils.escape_html(row.title || "")}</div>
					<div class="mi-watchlist-meta">${frappe.utils.escape_html(row.meta || "")}</div>
				</div>
			`);

			if (row.route) {
				$row.on("click", () => this.navigate(row.route, row.route_options));
			}

			this.$watchlist.append($row);
		});
	}

	render_charts(charts) {
		Object.entries(charts).forEach(([chartKey, chartConfig]) => {
			const $container = this.$layout.find(`[data-mi-chart="${chartKey}"]`);
			if (!$container.length) {
				return;
			}

			$container.empty();
			if (!this.chart_has_data(chartConfig)) {
				$container.append(this.get_empty_state(chartConfig.empty_message || __("No chart data available.")));
				return;
			}

			this.chart_instances[chartKey] = new frappe.Chart($container.get(0), {
				data: chartConfig.data,
				type: chartConfig.type || "line",
				colors: chartConfig.colors || undefined,
				height: 290,
				lineOptions: {
					regionFill: 1,
				},
				barOptions: {
					spaceRatio: 0.3,
				},
				tooltipOptions: {
					formatTooltipY: (value) => this.format_value(value, chartConfig.fieldtype),
				},
			});
		});
	}

	chart_has_data(chartConfig) {
		if (!chartConfig || !chartConfig.data || !chartConfig.data.datasets) {
			return false;
		}

		return chartConfig.data.datasets.some((dataset) =>
			(dataset.values || []).some((value) => Number(value || 0) !== 0)
		);
	}

	format_value(value, fieldtype) {
		if (fieldtype === "Currency") {
			return format_currency(value || 0, this.currency);
		}

		if (fieldtype === "Percent") {
			return `${Number(value || 0).toFixed(1)}%`;
		}

		if (fieldtype === "Int") {
			return frappe.format(value || 0, { fieldtype: "Int" });
		}

		return frappe.format(value || 0, { fieldtype: "Float" });
	}

	navigate(route, routeOptions) {
		if (routeOptions) {
			frappe.route_options = routeOptions;
		}
		frappe.set_route(...route);
	}

	get_empty_state(message) {
		return `<div class="mi-empty-state">${frappe.utils.escape_html(message)}</div>`;
	}
};
