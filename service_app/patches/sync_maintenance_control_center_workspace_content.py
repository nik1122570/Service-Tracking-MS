import frappe

from service_app.service_tracking.workspace import (
    MAINTENANCE_CONTROL_CENTER,
    setup_maintenance_control_center_workspace,
)


def execute():
    if frappe.db.exists("Workspace", MAINTENANCE_CONTROL_CENTER):
        setup_maintenance_control_center_workspace(MAINTENANCE_CONTROL_CENTER)
