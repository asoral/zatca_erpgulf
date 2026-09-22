# Copyright (c) 2025, ERPGulf and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from zatca_erpgulf.zatca_erpgulf.zatca_context import validate_buyer_identifier


class TestZATCAContext(FrappeTestCase):
    def test_b2c_empty_buyer_id_omits_bt46(self):
        customer = frappe._dict(
            {
                "name": "SAL004",
                "custom_b2c": 1,
                "custom_buyer_id_type": "IQA",
                "custom_buyer_id": "",
            }
        )
        self.assertIsNone(validate_buyer_identifier(customer, is_b2c=True))

    def test_b2c_valid_iqa(self):
        customer = frappe._dict(
            {
                "name": "TEST-B2C-IQA",
                "custom_b2c": 1,
                "custom_buyer_id_type": "IQA",
                "custom_buyer_id": "2123456789",
            }
        )
        self.assertEqual(
            validate_buyer_identifier(customer, is_b2c=True),
            {"scheme": "IQA", "id": "2123456789"},
        )

    def test_b2b_valid_tin(self):
        customer = frappe._dict(
            {
                "name": "TEST-B2B-TIN",
                "custom_b2c": 0,
                "custom_buyer_id_type": "TIN",
                "custom_buyer_id": "312345678901233",
            }
        )
        self.assertEqual(
            validate_buyer_identifier(customer, is_b2c=False),
            {"scheme": "TIN", "id": "312345678901233"},
        )

    def test_invalid_tin_is_rejected(self):
        customer = frappe._dict(
            {
                "name": "TEST-INVALID-TIN",
                "custom_b2c": 0,
                "custom_buyer_id_type": "TIN",
                "custom_buyer_id": "1234567890",
            }
        )
        with self.assertRaises(frappe.ValidationError):
            validate_buyer_identifier(customer, is_b2c=False)
