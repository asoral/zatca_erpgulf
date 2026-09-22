# Copyright (c) 2025, ERPGulf and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestZATCAERPGulfEventLog(FrappeTestCase):
    def test_event_log_fields(self):
        doc = frappe.get_doc({
            "doctype": "ZATCA ERPGulf Event Log",
            "title": "Test ZATCA Event",
            "invoice_number": "TEST-INV",
            "time": "2026-09-22 10:00:00",
            "api_response": "test response",
            "status": "success",
            "custom_uuid": "test-uuid",
        })
        doc.insert(ignore_permissions=True)
        self.assertEqual(doc.status, "success")
        self.assertEqual(doc.custom_uuid, "test-uuid")
        doc.delete(ignore_permissions=True)
