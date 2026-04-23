frappe.ui.form.on("Item", {
	setup(frm) {
		set_make_query(frm);
		set_warranty_field_read_only(frm);
		toggle_part_category_required(frm);
		toggle_make_field_state(frm);
		sync_default_price_list_from_make(frm, { force: false });
		sync_warranty_from_part_category(frm, { force: false });
	},

	refresh(frm) {
		set_make_query(frm);
		set_warranty_field_read_only(frm);
		toggle_part_category_required(frm);
		toggle_make_field_state(frm);
		sync_default_price_list_from_make(frm, { force: false });
		sync_warranty_from_part_category(frm, { force: false });
	},

	item_group(frm) {
		toggle_part_category_required(frm);
		toggle_make_field_state(frm);
		sync_default_price_list_from_make(frm, { force: true });
	},

	part_category(frm) {
		sync_warranty_from_part_category(frm, { force: true });
	},

	make(frm) {
		sync_default_price_list_from_make(frm, { force: true });
	},

	is_universal(frm) {
		toggle_make_field_state(frm);
		sync_default_price_list_from_make(frm, { force: true });
	}
});

function toggle_part_category_required(frm) {
	if (!frm.fields_dict || !frm.fields_dict.part_category) {
		return;
	}

	const itemGroup = (frm.doc.item_group || "").trim().toLowerCase();
	const isSpareParts = itemGroup === "spare parts";
	frm.toggle_reqd("part_category", isSpareParts);
}

function set_make_query(frm) {
	if (!frm.fields_dict || !frm.fields_dict.make) {
		return;
	}

	frm.set_query("make", () => ({
		filters: {
			enabled: 1
		}
	}));
}

function is_spare_parts_item(frm) {
	return ((frm.doc.item_group || "").trim().toLowerCase() === "spare parts");
}

function is_universal_item(frm) {
	return cint(frm.doc.is_universal || 0) === 1;
}

function toggle_make_field_state(frm) {
	if (!frm.fields_dict || !frm.fields_dict.make) {
		return;
	}

	const isSpareParts = is_spare_parts_item(frm);
	frm.toggle_display("make", isSpareParts);

	const required = is_spare_parts_item(frm) && !is_universal_item(frm);
	frm.toggle_reqd("make", required);
}

function set_warranty_field_read_only(frm) {
	const candidates = ["warranty_period", "warranty_period_in_days", "warranty_period__in_days"];
	candidates.forEach((fieldname) => {
		if (frm.fields_dict && frm.fields_dict[fieldname]) {
			frm.set_df_property(fieldname, "read_only", 1);
		}
	});
}

function sync_default_price_list_from_make(frm, { force = false } = {}) {
	if (!is_spare_parts_item(frm)) {
		return;
	}

	if (is_universal_item(frm)) {
		return;
	}

	if (!frm.doc.make || !frm.fields_dict || !frm.fields_dict.item_defaults) {
		return;
	}

	const requestKey = [frm.doc.make, frm.doc.item_group || ""].join("::");
	frm.__last_make_price_list_request = requestKey;

	frappe.call({
		method: "service_app.service_tracking.item.get_make_default_price_list",
		args: {
			make: frm.doc.make
		},
		callback: (r) => {
			if (frm.__last_make_price_list_request !== requestKey) {
				return;
			}

			const data = r.message || {};
			const defaultPriceList = data.default_price_list;
			if (!defaultPriceList) {
				return;
			}

			apply_default_price_list_to_item_defaults(
				frm,
				defaultPriceList,
				data.default_company,
				{ force }
			);
		}
	});
}

function apply_default_price_list_to_item_defaults(
	frm,
	defaultPriceList,
	defaultCompany,
	{ force = false } = {}
) {
	const rows = frm.doc.item_defaults || [];

	if (!rows.length) {
		if (!defaultCompany) {
			return;
		}

		const row = frm.add_child("item_defaults", {
			company: defaultCompany,
			default_price_list: defaultPriceList
		});
		if (row) {
			frm.refresh_field("item_defaults");
		}
		return;
	}

	rows.forEach((row) => {
		if (!row.name) {
			row.default_price_list = defaultPriceList;
			return;
		}

		if (!force && row.default_price_list === defaultPriceList) {
			return;
		}

		frappe.model.set_value(row.doctype, row.name, "default_price_list", defaultPriceList);
	});
}

function sync_warranty_from_part_category(frm, { force = false } = {}) {
	if (!frm.doc.part_category) {
		return;
	}

	frappe.call({
		method: "service_app.service_tracking.item.get_warranty_days_for_part_category",
		args: {
			part_category: frm.doc.part_category
		},
		callback: (r) => {
			const data = r.message || {};
			const days = flt(data.days);
			if (!days) {
				return;
			}

			const warrantyField = get_warranty_fieldname(frm, data.item_warranty_field);
			if (!warrantyField) {
				return;
			}

			const currentValue = flt(frm.doc[warrantyField]);
			if (!force && currentValue) {
				return;
			}

			frm.set_value(warrantyField, days);
		}
	});
}

function get_warranty_fieldname(frm, serverFieldname) {
	if (serverFieldname && frm.fields_dict && frm.fields_dict[serverFieldname]) {
		return serverFieldname;
	}

	const candidates = ["warranty_period", "warranty_period_in_days", "warranty_period__in_days"];
	return candidates.find((fieldname) => frm.fields_dict && frm.fields_dict[fieldname]) || null;
}
