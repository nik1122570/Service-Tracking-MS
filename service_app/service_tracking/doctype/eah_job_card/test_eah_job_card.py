# Copyright (c) 2026, Nickson  and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestEAHJobCard(FrappeTestCase):
    def test_supplied_parts_uom_links_to_uom_doctype(self):
        field = frappe.get_meta("Supplied Parts").get_field("uom")

        self.assertIsNotNone(field)
        self.assertEqual(field.options, "UOM")
