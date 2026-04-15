frappe.pages["tyre-intelligence"].on_page_load = function (wrapper) {
	new service_app.TyreIntelligencePage(wrapper);
};

frappe.provide("service_app");

service_app.TyreIntelligencePage = class TyreIntelligencePage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Tyre Intelligence"),
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
			project: this.page.add_field({
				label: __("Project"),
				fieldname: "project",
				fieldtype: "Link",
				options: "Project",
				change: () => this.refresh(),
			}),
			vehicle: this.page.add_field({
				label: __("Vehicle"),
				fieldname: "vehicle",
				fieldtype: "Link",
				options: "Vehicle",
				change: () => this.refresh(),
			}),
			brand: this.page.add_field({
				label: __("Tyre Brand"),
				fieldname: "brand",
				fieldtype: "Data",
				change: () => this.refresh(),
			}),
		};
	}

	make_actions() {
		this.page.set_primary_action(__("Refresh"), () => this.refresh());
		this.page.add_inner_button(__("Tyre Ledger Report"), () => {
			frappe.route_options = {
				from_date: "2000-01-01",
				to_date: this.filters.to_date.get_value(),
				vehicle: this.filters.vehicle.get_value(),
				brand: this.filters.brand.get_value(),
			};
			frappe.set_route("query-report", "Tyre Ledger Report");
		});
		this.page.add_inner_button(__("Tyre Lifespan Report"), () => {
			frappe.route_options = this.get_lifecycle_report_options();
			frappe.set_route("query-report", "Tyre Lifespan Analysis Report");
		});
		this.page.add_inner_button(__("Vehicle Tyre History"), () => {
			frappe.route_options = this.get_lifecycle_report_options();
			frappe.set_route("query-report", "Vehicle Tyre History Report");
		});
	}

	make_layout() {
		this.page.body.empty();
		this.$layout = $(frappe.render_template("tyre_intelligence")).appendTo(this.page.body);
		this.$generatedAt = this.$layout.find("[data-ti-generated-at]");
		this.$scope = this.$layout.find("[data-ti-scope]");
		this.$focus = this.$layout.find("[data-ti-focus]");
		this.$summaryCards = this.$layout.find("[data-ti-summary-cards]");
		this.$insights = this.$layout.find("[data-ti-insights]");
		this.$brandBoard = this.$layout.find('[data-ti-board="brand"]');
		this.$projectBoard = this.$layout.find('[data-ti-board="project"]');
		this.$ledgerBoard = this.$layout.find('[data-ti-board="ledger"]');
	}

	refresh() {
		if (!this.are_dates_valid()) {
			return;
		}

		frappe.call({
			method: "service_app.service_tracking.page.tyre_intelligence.tyre_intelligence.get_dashboard_data",
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
			project: this.filters.project.get_value(),
			vehicle: this.filters.vehicle.get_value(),
			brand: this.filters.brand.get_value(),
		};
	}

	get_lifecycle_report_options() {
		const options = {
			from_date: this.filters.from_date.get_value(),
			to_date: this.filters.to_date.get_value(),
			brand: this.filters.brand.get_value(),
		};
		if (this.filters.vehicle.get_value()) {
			options.vehicles = [this.filters.vehicle.get_value()];
		}
		return options;
	}

	render(data) {
		this.$generatedAt.text(data.generated_at || __("Unknown"));
		this.$scope.text(data.scope_label || __("Tyre intelligence scope"));
		this.$focus.text(data.focus_label || __("Management Portfolio View"));
		this.render_summary_cards(data.summary_cards || []);
		this.render_insights(data.insights || []);
		this.render_board(this.$brandBoard, data.brand_board || [], __("No brand ranking is available yet."));
		this.render_board(this.$projectBoard, data.project_board || [], __("No project tyre pressure is available for these filters."));
		this.render_board(this.$ledgerBoard, data.ledger_board || [], __("No positive tyre ledger balances remain in this snapshot."));
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
				<div class="ti-summary-card ${clickableClass}" data-tone="${card.tone || "neutral"}">
					<div class="ti-card-label">${frappe.utils.escape_html(card.label || "")}</div>
					<div class="ti-card-value">${this.format_value(card.value, card.fieldtype)}</div>
					<div class="ti-card-trend">${frappe.utils.escape_html(card.trend || "")}</div>
					<div class="ti-card-note">${frappe.utils.escape_html(card.note || "")}</div>
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
				<div class="ti-insight-item" data-tone="${insight.tone || "neutral"}">
					<div class="ti-insight-title">${frappe.utils.escape_html(insight.title || "")}</div>
					<div class="ti-insight-body">${frappe.utils.escape_html(insight.body || "")}</div>
				</div>
			`);
		});
	}

	render_board($container, rows, emptyMessage) {
		$container.empty();
		if (!rows.length) {
			$container.append(this.get_empty_state(emptyMessage));
			return;
		}

		rows.forEach((row) => {
			const clickableClass = row.route ? "is-clickable" : "";
			const badgeHtml = row.badge
				? `<span class="ti-board-badge">${frappe.utils.escape_html(row.badge)}</span>`
				: "";
			const $row = $(`
				<div class="ti-board-item ${clickableClass}" data-tone="${row.tone || "neutral"}">
					<div class="ti-board-top">
						<div class="ti-board-title">${frappe.utils.escape_html(row.title || "")}</div>
						${badgeHtml}
					</div>
					<div class="ti-board-headline">${frappe.utils.escape_html(row.headline || "")}</div>
					<div class="ti-board-meta">${frappe.utils.escape_html(row.meta || "")}</div>
					<div class="ti-board-note">${frappe.utils.escape_html(row.note || "")}</div>
				</div>
			`);

			if (row.route) {
				$row.on("click", () => this.navigate(row.route, row.route_options));
			}

			$container.append($row);
		});
	}

	render_charts(charts) {
		Object.entries(charts).forEach(([chartKey, chartConfig]) => {
			const $container = this.$layout.find(`[data-ti-chart="${chartKey}"]`);
			if (!$container.length) {
				return;
			}

			if (this.chart_instances[chartKey] && this.chart_instances[chartKey].destroy) {
				this.chart_instances[chartKey].destroy();
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
				height: 300,
				lineOptions: {
					regionFill: 1,
				},
				barOptions: {
					spaceRatio: 0.28,
				},
				tooltipOptions: {
					formatTooltipY: (value) => this.format_value(value, chartConfig.fieldtype, false),
				},
			});
		});
	}

	chart_has_data(chartConfig) {
		if (!chartConfig?.data?.labels?.length || !chartConfig?.data?.datasets?.length) {
			return false;
		}

		return chartConfig.data.datasets.some((dataset) => (dataset.values || []).length);
	}

	format_value(value, fieldtype, escape = true) {
		if (fieldtype === "Data" || typeof value === "string") {
			const text = value || __("Not Available");
			return escape ? frappe.utils.escape_html(text) : text;
		}
		if (fieldtype === "Currency") {
			return format_currency(value || 0, this.currency);
		}
		if (fieldtype === "Percent") {
			return `${Number(value || 0).toFixed(1)}%`;
		}
		if (fieldtype === "Int") {
			return frappe.format(value || 0, { fieldtype: "Int" });
		}
		return frappe.format(value || 0, { fieldtype: "Float", precision: 1 });
	}

	navigate(route, routeOptions) {
		if (routeOptions) {
			frappe.route_options = routeOptions;
		}
		frappe.set_route(...route);
	}

	get_empty_state(message) {
		return `<div class="ti-empty-state">${frappe.utils.escape_html(message)}</div>`;
	}
};
