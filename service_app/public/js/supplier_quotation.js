frappe.ui.form.on("Supplier Quotation", {
	setup(frm) {
		set_supplier_quotation_make_query(frm);
	},

	refresh(frm) {
		set_supplier_quotation_make_query(frm);
	}
});

function set_supplier_quotation_make_query(frm) {
	if (!frm.fields_dict || !frm.fields_dict.items || !frm.fields_dict.items.grid) {
		return;
	}

	const makeField = frm.fields_dict.items.grid.get_field("make");
	if (!makeField) {
		return;
	}

	makeField.get_query = () => ({
		filters: {
			enabled: 1
		}
	});
}
