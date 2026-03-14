import frappe
from frappe.model.document import Document


class EAHJobCard(Document):

    def validate(self):
        self.ensure_required_fields()
        self.ensure_supplied_parts_data()

    def ensure_required_fields(self):

        if not self.vehicle:
            frappe.throw("Vehicle is required.")

        if not self.service_date:
            frappe.throw("Service Date is required.")

        if not self.supplier:
            frappe.throw("Supplier is required.")

        if not self.project:
            frappe.throw("Project is required.")

        if not self.driver_name:
            frappe.throw("Driver Name is required.")


    def ensure_supplied_parts_data(self):
        """
        Ensure supplied parts contain the required maintenance tracking data
        """

        for part in self.supplied_parts:

            if not part.item:
                frappe.throw("Item is required in Supplied Parts.")

            if not part.qty:
                frappe.throw(f"Quantity is required for item {part.item}")

            if not part.useful_life:
                frappe.throw(f"Useful Life must be defined for item {part.item}")

            if not part.has_warranty:
                frappe.throw(f"Warranty selection required for item {part.item}")

            if part.has_warranty == "Yes" and not part.warranty_period__in_months:
                frappe.throw(
                    f"Warranty period must be defined for item {part.item}"
                )

            # auto-fetch item name if missing
            if part.item and not part.item_name:
                part.item_name = frappe.db.get_value(
                    "Item", part.item, "item_name"
                )


    def on_submit(self):
        """
        Confirm that maintenance record including spare parts was stored
        """

        parts_summary = ""

        for part in self.supplied_parts:
            parts_summary += f"""
            • {part.item_name or part.item}
            | Useful Life: {part.useful_life}
            | Warranty: {part.has_warranty}
            """

        frappe.msgprint(
            f"""
            <b>Maintenance History Recorded Successfully</b><br><br>

            Vehicle: <b>{self.vehicle}</b><br>
            Service Date: {self.service_date}<br>
            Supplier: {self.supplier}<br>
            Driver: {self.driver_name}<br><br>

            <b>Supplied Parts Recorded:</b><br>
            {parts_summary}
            """,
            title="Maintenance Recorded",
            indicator="green"
        )
        
import frappe
from frappe.model.document import Document
from frappe.utils import add_months, today, getdate


class EAHJobCard(Document):

    def validate(self):
        warnings = []
        warnings += self.check_recent_vehicle_service()
        warnings += self.check_part_warranty()
        warnings += self.check_useful_life()

        if warnings:
            frappe.msgprint(
                "<br>".join(warnings),
                title="Maintenance Warning",
                indicator="orange"
            )


    def before_submit(self):

        errors = []
        errors += self.check_recent_vehicle_service()
        errors += self.check_part_warranty()
        errors += self.check_useful_life()

        # If there are control issues
        if errors:

            # If override NOT checked → block submission
            if not self.custom_override_controls:

                frappe.throw(
                    "<b>Submission Blocked.</b><br><br>"
                    "Maintenance controls detected the following issues:<br><br>"
                    + "<br>".join(errors) +
                    "<br><br>Please check <b>'Override Controls'</b> to allow submission.",
                    title="Maintenance Control"
                )

            # If override checked → allow but warn
            else:

                frappe.msgprint(
                    "<b>Controls Overridden by Management</b><br><br>"
                    + "<br>".join(errors),
                    title="Override Applied",
                    indicator="orange"
                )


    def check_recent_vehicle_service(self):
        warnings = []

        last_service = frappe.get_all(
            "EAH Job Card",
            filters={
                "vehicle": self.vehicle,
                "docstatus": 1,
                "name": ["!=", self.name]
            },
            fields=["service_date"],
            order_by="service_date desc",
            limit=1
        )

        if last_service:
            warnings.append(
                f"⚠ Vehicle was recently serviced on {last_service[0].service_date}"
            )

        return warnings


    def check_part_warranty(self):
        warnings = []

        for part in self.supplied_parts:

            previous_parts = frappe.get_all(
                "Supplied Parts",
                filters={
                    "item": part.item,
                    "parenttype": "EAH Job Card"
                },
                fields=["parent", "warranty_period__in_months"]
            )

            for prev in previous_parts:

                job_card = frappe.get_doc("EAH Job Card", prev.parent)

                if prev.warranty_period__in_months:

                    expiry = add_months(
                        job_card.service_date,
                        prev.warranty_period__in_months
                    )

                    if getdate(today()) <= getdate(expiry):

                        warnings.append(
                            f"⚠ Part {part.item} may still be under warranty until {expiry}"
                        )

        return warnings


    def check_useful_life(self):
        warnings = []

        for part in self.supplied_parts:

            previous_parts = frappe.get_all(
                "Supplied Parts",
                filters={
                    "item": part.item,
                    "parenttype": "EAH Job Card"
                },
                fields=["parent", "useful_life"]
            )

            for prev in previous_parts:

                job_card = frappe.get_doc("EAH Job Card", prev.parent)

                expiry = add_months(
                    job_card.service_date,
                    prev.useful_life
                )

                if getdate(today()) <= getdate(expiry):

                    warnings.append(
                        f"⚠ Part {part.item} may still be within useful life until {expiry}"
                    )

        return warnings


    def on_submit(self):
        frappe.msgprint(
            f"""
            <b>Maintenance Record Stored Successfully</b><br><br>
            Vehicle: {self.vehicle}<br>
            Service Date: {self.service_date}<br>
            Supplier: {self.supplier}
            """,
            title="Maintenance Recorded",
            indicator="green"
        )
        
@frappe.whitelist()
def get_vehicle_maintenance_history(vehicle):

    if not vehicle:
        return []

    job_cards = frappe.get_all(
        "EAH Job Card",
        filters={"vehicle": vehicle, "docstatus": 1},
        fields=[
            "name",
            "service_date",
            "supplier",
            "driver_name",
            "project",
            "odometer_reading"
        ],
        order_by="service_date desc"
    )

    history = []

    for jc in job_cards:

        parts = frappe.get_all(
            "Supplied Parts",
            filters={"parent": jc.name},
            fields=["item_name", "qty"]
        )

        parts_list = []
        for p in parts:
            parts_list.append(f"{p.item_name} (Qty: {p.qty})")

        jc["parts_used"] = ", ".join(parts_list)

        history.append(jc)

    return history