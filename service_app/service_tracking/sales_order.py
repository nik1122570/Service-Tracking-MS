import frappe
from frappe import _
from frappe.utils import flt


def validate_sales_order_trip_revenue_allocations(doc, method=None):
    allocations = list(getattr(doc, "custom_trip_revenue_allocations", None) or [])
    total_allocated = 0

    for row in allocations:
        if not row.allocation_label:
            frappe.throw("Trip Revenue Allocation rows require an Allocation Label.")

        row.allocated_amount = flt(row.allocated_amount)
        if row.allocated_amount <= 0:
            frappe.throw(
                _("Trip Revenue Allocation row {0}: Allocated Amount must be greater than zero.").format(row.idx)
            )

        row.allocation_status = "Allocated" if row.linked_trip_simulation else "Available"
        total_allocated += row.allocated_amount

    if total_allocated > flt(doc.total):
        frappe.throw(
            _(
                "Total Trip Revenue Allocation {0} cannot exceed Sales Order Total {1}."
            ).format(
                frappe.format_value(total_allocated, {"fieldtype": "Currency"}),
                frappe.format_value(doc.total, {"fieldtype": "Currency"}),
            ),
            title="Trip Revenue Allocation Error",
        )

    doc.custom_total_allocated_trip_revenue = total_allocated
    doc.custom_remaining_trip_revenue = flt(doc.total) - total_allocated


def get_sales_order_trip_context(
    sales_order,
    allocation_name=None,
    simulation_name=None,
    require_allocation=True,
):
    doc = frappe.get_doc("Sales Order", sales_order)
    allocations = list(getattr(doc, "custom_trip_revenue_allocations", None) or [])
    uses_allocations = bool(allocations)
    selected_allocation = allocation_name or ""
    expected_revenue = flt(doc.total)

    allocation_options = [
        {
            "value": build_allocation_option_value(row),
            "label": build_allocation_option_label(row),
            "allocated_amount": flt(row.allocated_amount),
            "linked_trip_simulation": row.linked_trip_simulation,
        }
        for row in allocations
        if not row.linked_trip_simulation or row.linked_trip_simulation == simulation_name
    ]

    if uses_allocations:
        allocation_row_name = extract_allocation_name(selected_allocation)
        if not selected_allocation and len(allocation_options) == 1:
            selected_allocation = allocation_options[0]["value"]
            allocation_row_name = extract_allocation_name(selected_allocation)

        if not allocation_row_name and require_allocation:
            frappe.throw(
                _("Sales Order {0} requires a Trip Revenue Allocation selection.").format(frappe.bold(doc.name)),
                title="Trip Revenue Allocation Required",
            )

        selected_row = next((row for row in allocations if row.name == allocation_row_name), None)
        if not selected_row and not require_allocation:
            selected_row = None

        if not selected_row:
            if require_allocation:
                frappe.throw(
                    _("Trip Revenue Allocation {0} was not found on Sales Order {1}.").format(
                        allocation_row_name,
                        frappe.bold(doc.name),
                    )
                )
            else:
                selected_allocation = ""
                expected_revenue = 0
        else:
            if selected_row.linked_trip_simulation and selected_row.linked_trip_simulation != simulation_name:
                frappe.throw(
                    _(
                        "Trip Revenue Allocation {0} is already linked to Trip Simulation {1}."
                    ).format(
                        frappe.bold(selected_row.allocation_label or selected_row.idx),
                        frappe.bold(selected_row.linked_trip_simulation),
                    ),
                    title="Trip Revenue Allocation In Use",
                )

            expected_revenue = flt(selected_row.allocated_amount)

    customer = doc.customer
    cost_center = get_sales_order_cost_center(doc)
    target_profit_margin = flt(frappe.db.get_value("Customer", customer, "custom_target_profit_margin"))

    return frappe._dict(
        customer=customer,
        cost_center=cost_center,
        expected_revenue=expected_revenue,
        target_profit_margin=target_profit_margin,
        uses_allocations=uses_allocations,
        selected_allocation=selected_allocation,
        allocation_options=allocation_options,
    )


def build_allocation_option_label(row):
    route_label = f" | {row.trip_route}" if row.trip_route else ""
    return f"{row.name} | {row.allocation_label}{route_label} | {flt(row.allocated_amount):,.2f}"


def build_allocation_option_value(row):
    return f"{row.name} | {row.allocation_label} | {flt(row.allocated_amount):,.2f}"


def extract_allocation_name(value):
    return (value or "").split(" | ", 1)[0].strip()


def get_sales_order_cost_center(doc):
    explicit_cost_center = getattr(doc, "custom_trip_cost_center", None)
    if explicit_cost_center:
        return explicit_cost_center

    for item in doc.items:
        if item.cost_center:
            return item.cost_center

    return None


def reserve_sales_order_trip_allocation(sales_order, allocation_name, simulation_name):
    if not sales_order or not allocation_name:
        return

    doc = frappe.get_doc("Sales Order", sales_order)
    allocation_row_name = extract_allocation_name(allocation_name)
    row = next((row for row in doc.custom_trip_revenue_allocations if row.name == allocation_row_name), None)
    if not row:
        frappe.throw(
            _("Trip Revenue Allocation {0} was not found on Sales Order {1}.").format(
                allocation_name,
                frappe.bold(doc.name),
            )
        )

    if row.linked_trip_simulation and row.linked_trip_simulation != simulation_name:
        frappe.throw(
            _("Trip Revenue Allocation {0} is already linked to Trip Simulation {1}.").format(
                frappe.bold(row.allocation_label or row.idx),
                frappe.bold(row.linked_trip_simulation),
            )
        )

    row.linked_trip_simulation = simulation_name
    row.allocation_status = "Allocated"
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()


def release_sales_order_trip_allocation(sales_order, allocation_name, simulation_name):
    if not sales_order or not allocation_name:
        return

    doc = frappe.get_doc("Sales Order", sales_order)
    allocation_row_name = extract_allocation_name(allocation_name)
    row = next((row for row in doc.custom_trip_revenue_allocations if row.name == allocation_row_name), None)
    if not row or row.linked_trip_simulation != simulation_name:
        return

    row.linked_trip_simulation = None
    row.allocation_status = "Available"
    doc.flags.ignore_validate_update_after_submit = True
    doc.save()
