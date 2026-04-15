import frappe

from service_app.service_tracking.workspace import (
    MAINTENANCE_CONTROL_CENTER,
    MAINTENANCE_CONTROL_CENTER_NUMBER_CARDS,
    _upsert_custom_number_card,
    setup_maintenance_control_center_workspace,
)


def execute():
    tyre_card_labels = {
        "Total Tyre Cost This Month",
        "Total Tyre Cost This Quarter",
    }

    for config in MAINTENANCE_CONTROL_CENTER_NUMBER_CARDS:
        if config["label"] in tyre_card_labels:
            _upsert_custom_number_card(config)

    if frappe.db.exists("Workspace", MAINTENANCE_CONTROL_CENTER):
        setup_maintenance_control_center_workspace(MAINTENANCE_CONTROL_CENTER)
