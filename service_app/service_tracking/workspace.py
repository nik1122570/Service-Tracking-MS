import json
import os

import frappe


MAINTENANCE_CONTROL_CENTER = "Maintenance Control Center"
MAINTENANCE_INTELLIGENCE_PAGE = "maintenance-intelligence"
TYRE_INTELLIGENCE_PAGE = "tyre-intelligence"
WORKSPACE_MODULE = "Service Tracking"
DEFAULT_CURRENCY = lambda: frappe.db.get_single_value("Global Defaults", "default_currency")
MAINTENANCE_CONTROL_CENTER_ROLES = (
    "System Manager",
    "Workshop Manager",
    "Stock User",
    "Purchase Manager",
    "Purchase User",
)
MAINTENANCE_CONTROL_CENTER_NUMBER_CARDS = (
    {
        "label": "Total Maintenance Cost This Month",
        "method": "service_app.service_tracking.number_cards.get_total_maintenance_cost_this_month",
        "document_type": "Purchase Invoice",
        "currency": True,
    },
    {
        "label": "Total Maintenance Cost This Quarter",
        "method": "service_app.service_tracking.number_cards.get_total_maintenance_cost_this_quarter",
        "document_type": "Purchase Invoice",
        "currency": True,
    },
    {
        "label": "Total Number of Vehicles",
        "method": "service_app.service_tracking.number_cards.get_total_number_of_vehicles",
        "document_type": "Vehicle",
    },
    {
        "label": "Total Vehicles Serviced This Month",
        "method": "service_app.service_tracking.number_cards.get_total_vehicles_serviced_this_month_card",
        "document_type": "EAH Job Card",
    },
    {
        "label": "Most Appearing Vehicle",
        "method": "service_app.service_tracking.number_cards.get_most_appearing_vehicle",
        "document_type": "EAH Job Card",
    },
    {
        "label": "Total Spare Cost",
        "method": "service_app.service_tracking.number_cards.get_total_spare_cost",
        "document_type": "Purchase Invoice",
        "currency": True,
    },
    {
        "label": "Tyre Requests This Month",
        "method": "service_app.service_tracking.number_cards.get_tyre_requests_this_month",
        "document_type": "Tyre Request",
    },
    {
        "label": "Tyre Requests This Quarter",
        "method": "service_app.service_tracking.number_cards.get_tyre_requests_this_quarter",
        "document_type": "Tyre Request",
    },
    {
        "label": "Purchased Tyres",
        "method": "service_app.service_tracking.number_cards.get_total_purchased_tyres",
        "document_type": "Purchase Order",
    },
    {
        "label": "Received Tyres",
        "method": "service_app.service_tracking.number_cards.get_total_received_tyres",
        "document_type": "Tyre Receiving Note",
    },
    {
        "label": "Disposed Tyres",
        "method": "service_app.service_tracking.number_cards.get_total_disposed_tyres",
        "document_type": "Tyre Disposal Note",
    },
    {
        "label": "Outstanding Receiving Tyres",
        "method": "service_app.service_tracking.number_cards.get_total_outstanding_receiving_tyres",
        "document_type": "Tyre Request",
    },
    {
        "label": "Total Tyre Cost This Month",
        "method": "service_app.service_tracking.number_cards.get_total_tyre_cost_this_month",
        "document_type": "Purchase Invoice",
        "currency": True,
    },
    {
        "label": "Total Tyre Cost This Quarter",
        "method": "service_app.service_tracking.number_cards.get_total_tyre_cost_this_quarter",
        "document_type": "Purchase Invoice",
        "currency": True,
    },
)
MAINTENANCE_CONTROL_CENTER_CHARTS = (
    {
        "chart_name": "Monthly Spare Cost Trend",
        "label": "Monthly Spare Cost Trend",
        "chart_type": "Sum",
        "document_type": "EAH Job Card",
        "based_on": "service_date",
        "value_based_on": "spares_cost",
        "timeseries": 1,
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "type": "Line",
        "color": "#F59E0B",
        "currency": True,
        "filters_json": [["EAH Job Card", "docstatus", "=", 1]],
    },
    {
        "chart_name": "Monthly Tyre Cost Trend",
        "label": "Monthly Tyre Cost Trend",
        "chart_type": "Sum",
        "document_type": "Purchase Order",
        "based_on": "transaction_date",
        "value_based_on": "total",
        "timeseries": 1,
        "timespan": "Last Year",
        "time_interval": "Monthly",
        "type": "Bar",
        "color": "#B45309",
        "currency": True,
        "filters_json": [
            ["Purchase Order", "docstatus", "=", 1],
            ["Purchase Order", "custom_tyre_request_link", "!=", ""]
        ],
    },
)
MAINTENANCE_CONTROL_CENTER_SHORTCUTS = (
    {
        "label": "Open Maintenance Intelligence",
        "type": "Page",
        "link_to": MAINTENANCE_INTELLIGENCE_PAGE,
        "color": "#B45309",
        "icon": "es-line-chart",
    },
    {
        "label": "Open Tyre Intelligence",
        "type": "Page",
        "link_to": TYRE_INTELLIGENCE_PAGE,
        "color": "#0F766E",
        "icon": "es-pie-chart",
    },
)


def create_fleet_maintenance_dashboard():
    """Create or update the Fleet Maintenance Dashboard Workspace.

    This is intended to be run via `bench execute` after the app is installed or
    when the workspace JSON is updated.
    """

    app_path = frappe.get_app_path("service_app")
    dashboard_path = os.path.join(
        app_path,
        "service_tracking",
        "workspace",
        "fleet_maintenance_dashboard.json",
    )

    if not os.path.exists(dashboard_path):
        frappe.throw(f"Workspace JSON not found: {dashboard_path}")

    with open(dashboard_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    workspace_name = data.get("name") or data.get("label")
    if not workspace_name:
        frappe.throw("Workspace JSON must define a 'name' or 'label'.")

    workspace = frappe.get_doc("Workspace", workspace_name) if frappe.db.exists("Workspace", workspace_name) else frappe.new_doc("Workspace")

    workspace.update(data)
    workspace.flags.ignore_permissions = True
    workspace.save()
    frappe.db.commit()

    return f"Workspace {workspace_name} created/updated."


def _upsert_custom_number_card(config):
    label = config["label"]
    card = frappe.get_doc("Number Card", label) if frappe.db.exists("Number Card", label) else frappe.new_doc("Number Card")

    card.update(
        {
            "label": label,
            "type": "Custom",
            "document_type": config.get("document_type"),
            "method": config["method"],
            "is_public": 1,
            "show_full_number": 1,
            "show_percentage_stats": 0,
            "currency": DEFAULT_CURRENCY() if config.get("currency") else None,
        }
    )
    card.flags.ignore_permissions = True

    if card.is_new():
        card.insert(ignore_permissions=True)
    else:
        card.save(ignore_permissions=True)

    return card.name


def _ensure_workspace_number_card(workspace, number_card_name, label):
    existing_row = next(
        (
            row for row in workspace.number_cards
            if row.number_card_name == number_card_name or row.label == label
        ),
        None,
    )

    if existing_row:
        existing_row.number_card_name = number_card_name
        existing_row.label = label
        return

    workspace.append(
        "number_cards",
        {
            "number_card_name": number_card_name,
            "label": label,
        },
    )


def _upsert_dashboard_chart(config):
    chart_name = config["chart_name"]
    chart = frappe.get_doc("Dashboard Chart", chart_name) if frappe.db.exists("Dashboard Chart", chart_name) else frappe.new_doc("Dashboard Chart")

    chart.update(
        {
            "chart_name": chart_name,
            "chart_type": config["chart_type"],
            "document_type": config["document_type"],
            "based_on": config["based_on"],
            "value_based_on": config.get("value_based_on"),
            "timeseries": config.get("timeseries", 0),
            "timespan": config.get("timespan"),
            "time_interval": config.get("time_interval"),
            "type": config.get("type", "Line"),
            "is_public": 1,
            "color": config.get("color"),
            "currency": DEFAULT_CURRENCY() if config.get("currency") else None,
            "filters_json": json.dumps(config.get("filters_json", [])),
            "dynamic_filters_json": "[]",
        }
    )
    chart.flags.ignore_permissions = True

    if chart.is_new():
        chart.insert(ignore_permissions=True)
    else:
        chart.save(ignore_permissions=True)

    return chart.chart_name


def _ensure_workspace_chart(workspace, chart_name, label):
    existing_row = next(
        (
            row for row in workspace.charts
            if row.chart_name == chart_name or row.label == label
        ),
        None,
    )

    if existing_row:
        existing_row.chart_name = chart_name
        existing_row.label = label
        return

    workspace.append(
        "charts",
        {
            "chart_name": chart_name,
            "label": label,
        },
    )


def _ensure_workspace_shortcut(workspace, config):
    existing_row = next(
        (
            row for row in workspace.shortcuts
            if row.label == config["label"]
            or (row.type == config.get("type") and row.link_to == config.get("link_to"))
        ),
        None,
    )

    if existing_row:
        existing_row.label = config["label"]
        existing_row.type = config.get("type")
        existing_row.link_to = config.get("link_to")
        existing_row.color = config.get("color")
        existing_row.icon = config.get("icon")
        return

    workspace.append(
        "shortcuts",
        {
            "label": config["label"],
            "type": config.get("type"),
            "link_to": config.get("link_to"),
            "color": config.get("color"),
            "icon": config.get("icon"),
        },
    )


def _load_workspace_content(workspace):
    if not workspace.content:
        return []

    try:
        content = json.loads(workspace.content)
    except Exception:
        return []

    return content if isinstance(content, list) else []


def _save_workspace_content(workspace, content):
    workspace.content = json.dumps(content, separators=(",", ":"))
    workspace.flags.workspace_content_updated = True


def _ensure_workspace_content_header(workspace, text, col=12):
    content = _load_workspace_content(workspace)
    existing_block = next(
        (
            block for block in content
            if block.get("type") == "header"
            and str((block.get("data") or {}).get("text", "")) == text
        ),
        None,
    )
    if existing_block:
        existing_block.setdefault("data", {})
        existing_block["data"]["text"] = text
        existing_block["data"]["col"] = existing_block["data"].get("col") or col
        _save_workspace_content(workspace, content)
        return

    content.append(
        {
            "id": frappe.generate_hash(length=10),
            "type": "header",
            "data": {
                "text": text,
                "col": col,
            },
        }
    )
    _save_workspace_content(workspace, content)


def _ensure_workspace_content_number_card_block(workspace, number_card_name, col=4):
    content = _load_workspace_content(workspace)
    existing_block = next(
        (
            block for block in content
            if block.get("type") == "number_card"
            and (block.get("data") or {}).get("number_card_name") == number_card_name
        ),
        None,
    )
    if existing_block:
        existing_block.setdefault("data", {})
        existing_block["data"]["number_card_name"] = number_card_name
        existing_block["data"]["col"] = existing_block["data"].get("col") or col
        _save_workspace_content(workspace, content)
        return

    content.append(
        {
            "id": frappe.generate_hash(length=10),
            "type": "number_card",
            "data": {
                "number_card_name": number_card_name,
                "col": col,
            },
        }
    )
    _save_workspace_content(workspace, content)


def _ensure_workspace_content_chart_block(workspace, chart_name, col=6):
    content = _load_workspace_content(workspace)
    existing_block = next(
        (
            block for block in content
            if block.get("type") == "chart"
            and (block.get("data") or {}).get("chart_name") == chart_name
        ),
        None,
    )
    if existing_block:
        existing_block.setdefault("data", {})
        existing_block["data"]["chart_name"] = chart_name
        existing_block["data"]["col"] = existing_block["data"].get("col") or col
        _save_workspace_content(workspace, content)
        return

    content.append(
        {
            "id": frappe.generate_hash(length=10),
            "type": "chart",
            "data": {
                "chart_name": chart_name,
                "col": col,
            },
        }
    )
    _save_workspace_content(workspace, content)


def _ensure_workspace_content_shortcut_block(workspace, shortcut_label, col=4):
    content = _load_workspace_content(workspace)

    existing_block = next(
        (
            block for block in content
            if block.get("type") == "shortcut"
            and (block.get("data") or {}).get("shortcut_name") == shortcut_label
        ),
        None,
    )
    if existing_block:
        existing_block.setdefault("data", {})
        existing_block["data"]["shortcut_name"] = shortcut_label
        existing_block["data"]["col"] = existing_block["data"].get("col") or col
        _save_workspace_content(workspace, content)
        return

    shortcut_block = {
        "id": frappe.generate_hash(length=10),
        "type": "shortcut",
        "data": {
            "shortcut_name": shortcut_label,
            "col": col,
        },
    }

    content.append(shortcut_block)
    _save_workspace_content(workspace, content)


def _ensure_workspace_role(workspace, role):
    existing = next((row for row in (workspace.roles or []) if row.role == role), None)
    if existing:
        return

    workspace.append("roles", {"role": role})


def _ensure_maintenance_control_center_workspace(workspace_name=MAINTENANCE_CONTROL_CENTER):
    is_new = not frappe.db.exists("Workspace", workspace_name)
    workspace = frappe.new_doc("Workspace") if is_new else frappe.get_doc("Workspace", workspace_name)

    workspace.label = workspace_name
    if hasattr(workspace, "title"):
        workspace.title = workspace_name
    if hasattr(workspace, "module"):
        workspace.module = WORKSPACE_MODULE
    if hasattr(workspace, "public"):
        workspace.public = 1
    workspace.is_hidden = 0
    workspace.icon = workspace.icon or "es-line-chart"
    workspace.content = workspace.content or "[]"

    for role in MAINTENANCE_CONTROL_CENTER_ROLES:
        _ensure_workspace_role(workspace, role)

    workspace.flags.ignore_permissions = True
    if is_new:
        workspace.insert(ignore_permissions=True)
    else:
        workspace.save(ignore_permissions=True)

    return workspace


@frappe.whitelist()
def setup_maintenance_control_center_workspace(workspace_name=MAINTENANCE_CONTROL_CENTER):
    workspace = _ensure_maintenance_control_center_workspace(workspace_name)

    _ensure_workspace_content_header(
        workspace,
        '<span class="h4"><b>Command Metrics</b></span>',
    )

    for card_config in MAINTENANCE_CONTROL_CENTER_NUMBER_CARDS:
        card_name = _upsert_custom_number_card(card_config)
        _ensure_workspace_number_card(workspace, card_name, card_config["label"])
        _ensure_workspace_content_number_card_block(workspace, card_name)

    _ensure_workspace_content_header(
        workspace,
        '<span class="h4"><b>Visual Diagnostics</b></span>',
    )

    for chart_config in MAINTENANCE_CONTROL_CENTER_CHARTS:
        chart_name = _upsert_dashboard_chart(chart_config)
        _ensure_workspace_chart(workspace, chart_name, chart_config["label"])
        _ensure_workspace_content_chart_block(workspace, chart_name)

    _ensure_workspace_content_header(
        workspace,
        '<span class="h4"><b>Intelligence Shortcuts</b></span>',
    )

    for shortcut_config in MAINTENANCE_CONTROL_CENTER_SHORTCUTS:
        _ensure_workspace_shortcut(workspace, shortcut_config)
        _ensure_workspace_content_shortcut_block(workspace, shortcut_config["label"])

    workspace.flags.ignore_permissions = True
    workspace.save(ignore_permissions=True)
    if getattr(workspace.flags, "workspace_content_updated", False):
        frappe.db.set_value(
            "Workspace",
            workspace.name,
            "content",
            workspace.content,
            update_modified=False,
        )
    frappe.clear_cache()
    frappe.db.commit()

    return f"Workspace {workspace_name} updated with management number cards and charts."


@frappe.whitelist()
def bootstrap_service_tracking_dashboards():
    """
    Ensure core service dashboards and workspace assets exist on any site
    (fresh installs and already-running sites).
    """
    create_fleet_maintenance_dashboard()
    setup_maintenance_control_center_workspace()
    return "Service Tracking dashboards bootstrapped."
