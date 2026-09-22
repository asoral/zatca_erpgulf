from frappe.utils import now_datetime
import frappe


def log_zatca_event(invoice_number, response_text, status, uuid=None, title=None):
    """Log ZATCA event and API response."""
    try:
        event_doc = frappe.get_doc({
            "doctype": "ZATCA ERPGulf Event Log",
            "title": title or f"ZATCA API Call for {invoice_number} [{status}] {uuid or \"\"}",
            "invoice_number": invoice_number,
            "time": now_datetime(),
            "api_response": response_text,
            "custom_uuid": uuid or "",
            "status": status,
        })
        event_doc.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to log ZATCA Event: {str(e)}", "ZATCA Event Log")
