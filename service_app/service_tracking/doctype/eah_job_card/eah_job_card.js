frappe.ui.form.on("EAH Job Card", {
	refresh(frm) {
		if (!frm.doc.vehicle) {
			return;
		}

		// Purchase Order (only for submitted Job Cards)
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button("Purchase Order", () => {
				frappe.model.open_mapped_doc({
					method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.make_purchase_order",
					frm: frm
				});
			}, "Create");
		}

		// Only show history button once document exists
		if (!frm.is_new()) {
			frm.add_custom_button("Maintenance History", () => {
				frappe.call({
					method: "service_app.service_tracking.doctype.eah_job_card.eah_job_card.get_vehicle_maintenance_history",
					args: {
						vehicle: frm.doc.vehicle
					},
					callback: (r) => {
						const history = r.message || [];

						const dialog = new frappe.ui.Dialog({
							title: "Maintenance History",
							fields: [
								{
									fieldtype: "HTML",
									fieldname: "history_html"
								}
							],
							primary_action: () => dialog.hide()
						});

						let html = "";

						if (history.length) {
							html = `<div style="max-height:420px; overflow:auto;">`;

							history.forEach((h) => {
								const templates = (h.service_templates || []).length
									? (h.service_templates || []).join(", ")
									: "<i>(none)</i>";

								html += `
									<div style="margin-bottom:10px;padding:10px;border:1px solid #eee;border-radius:6px;">
										<div><strong>${h.name}</strong> — ${h.service_date || ""}</div>
										<div><b>Supplier:</b> ${h.supplier || "-"}</div>
										<div><b>Driver:</b> ${h.driver_name || "-"}</div>
										<div><b>Service Templates:</b> ${templates}</div>
									</div>
								`;
							});

							html += `</div>`;
						} else {
							html = `<p>No maintenance history found for this vehicle.</p>`;
						}

						dialog.set_value("history_html", html);
						dialog.show();
					}
				});
			});
		}
	}
});
