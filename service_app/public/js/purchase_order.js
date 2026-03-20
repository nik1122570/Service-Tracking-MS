frappe.ui.form.on("Purchase Order", {
	setup(frm) {
		lock_job_card_items(frm);
	},

	onload_post_render(frm) {
		lock_job_card_items(frm);
	},

	refresh(frm) {
		lock_job_card_items(frm);
	},

	custom_job_card_link(frm) {
		lock_job_card_items(frm);
	},

	custom_tyre_request_link(frm) {
		lock_job_card_items(frm);
	}
});

function lock_job_card_items(frm) {
	const items_grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!items_grid) {
		return;
	}

	const is_job_card_purchase_order = Boolean(frm.doc.custom_job_card_link);
	const is_tyre_request_purchase_order = Boolean(frm.doc.custom_tyre_request_link);
	const is_locked_purchase_order = is_job_card_purchase_order || is_tyre_request_purchase_order;
	const read_only = is_locked_purchase_order ? 1 : 0;

	if (frm.fields_dict.cost_center) {
		frm.set_df_property("cost_center", "read_only", read_only);
	}
	if (frm.fields_dict.project) {
		frm.set_df_property("project", "read_only", read_only);
	}
	if (frm.fields_dict.supplier) {
		frm.set_df_property("supplier", "read_only", read_only);
	}
	const locked_fields = [
		"item_code",
		"item_name",
		"qty",
		"rate",
		"uom",
		"stock_uom",
		"conversion_factor",
		"schedule_date",
		"description",
		"project",
		"cost_center"
	];

	locked_fields.forEach((fieldname) => {
		items_grid.update_docfield_property(fieldname, "read_only", read_only);
	});

	items_grid.cannot_add_rows = is_locked_purchase_order;
	items_grid.cannot_delete_rows = is_locked_purchase_order;
	items_grid.cannot_delete_all_rows = is_locked_purchase_order;

	const gridWrapper = $(items_grid.wrapper);
	gridWrapper.find(".grid-add-row, .grid-remove-rows, .grid-remove-all-rows").toggle(!is_locked_purchase_order);

	frm.refresh_field("items");
}

