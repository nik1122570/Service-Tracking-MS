frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		fetch_spare_part_rates(frm, { force: false });
	},

	onload_post_render(frm) {
		fetch_spare_part_rates(frm, { force: false });
	},

	refresh(frm) {
		fetch_spare_part_rates(frm, { force: false });
	},

	buying_price_list(frm) {
		fetch_spare_part_rates(frm, { force: true });
	},

	price_list(frm) {
		fetch_spare_part_rates(frm, { force: true });
	},

	supplier(frm) {
		fetch_spare_part_rates(frm, { force: true });
	}
});

frappe.ui.form.on("Purchase Order Item", {
	item_code(frm, cdt, cdn) {
		fetch_spare_part_rate_for_row(frm, cdt, cdn, { force: true });
	}
});

function get_purchase_order_price_list(frm) {
	return frm.doc.buying_price_list || frm.doc.price_list || "";
}

function fetch_spare_part_rates(frm, { force = false } = {}) {
	(frm.doc.items || []).forEach((row) => {
		if (row.item_code) {
			fetch_spare_part_rate_for_row(frm, row.doctype, row.name, { force });
		}
	});
}

function fetch_spare_part_rate_for_row(frm, cdt, cdn, { force = false } = {}) {
	const row = locals[cdt] && locals[cdt][cdn];
	if (!row || !row.item_code) {
		return;
	}

	const price_list = get_purchase_order_price_list(frm);
	if (!price_list) {
		return;
	}

	if (!force && flt(row.rate)) {
		return;
	}

	const requestKey = [row.item_code, price_list, frm.doc.supplier || ""].join("::");
	row.__last_spare_part_rate_request = requestKey;

	frappe.call({
		method: "service_app.service_tracking.purchase_order.get_spare_part_item_price",
		args: {
			item_code: row.item_code,
			price_list,
			supplier: frm.doc.supplier
		},
		callback: (r) => {
			const currentRow = locals[cdt] && locals[cdt][cdn];
			if (!currentRow || currentRow.__last_spare_part_rate_request !== requestKey) {
				return;
			}

			const response = r.message || {};
			if (!response.is_spare_part) {
				return;
			}
			if (!response.has_item_price) {
				return;
			}

			const approvedRate = flt(response.rate);
			frappe.model.set_value(cdt, cdn, "rate", approvedRate);
		}
	});
}

