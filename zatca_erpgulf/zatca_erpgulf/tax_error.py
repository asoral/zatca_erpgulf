"""this module contains functions that are used to validate tax information
in sales invoices."""

from erpnext import get_region
from frappe import _
import frappe
from zatca_erpgulf.zatca_erpgulf.zatca_context import get_zatca_company_context


def validate_sales_invoice_taxes(doc, event=None):
    """
    Validate that the sales invoice has valid tax entries and required ZATCA fields.
    Raises a validation error if tax or compliance rules are violated.
    """
    context = get_zatca_company_context(doc, throw_on_missing=False)
    if not context:
        return

    company_doc = context["credential_company_doc"]
    op_company_doc = context["operational_company_doc"]

    # Exit early if ZATCA is not enabled on the company
    if hasattr(company_doc, "custom_zatca_invoice_enabled") and not company_doc.custom_zatca_invoice_enabled:
        return

    if doc.doctype == "Sales Invoice" and getattr(doc, "custom_zatca_pmm", 0) == 1:
        return
    is_gpos_installed = "gpos" in frappe.get_installed_apps()
    field_exists = frappe.get_meta(doc.doctype).has_field("custom_unique_id")
    if is_gpos_installed and field_exists:
        if getattr(doc, "custom_unique_id", None) and not getattr(doc, "custom_zatca_pos_name", None):
            frappe.throw(_(
                "ZATCA POS Machine name is missing for invoice, Add ZATCA POS machine name"
            ))

    if getattr(doc, "custom_zatca_pos_name", None):
        zatca_settings = frappe.get_doc("ZATCA Multiple Setting", doc.custom_zatca_pos_name)
        linked_company_doc = frappe.get_doc("Company", zatca_settings.custom_linked_doctype)
        if linked_company_doc.name != doc.company:
            frappe.throw(_(
                "Company mismatch: Document company '{0}' does not match linked ZATCA company '{1}' of machine setting."
            ).format(doc.company, linked_company_doc.name))

    customer_doc = frappe.get_doc("Customer", doc.customer)
    if (
        customer_doc.custom_b2c != 1
        and getattr(company_doc, "custom_send_invoice_to_zatca", "") == "Background"
    ):
        frappe.throw(_("This customer should be B2C for Background"))

    region = get_region(op_company_doc.name)
    if region not in ["Saudi Arabia"]:
        return

    # Child company branch validation
    if context["is_child_branch"]:
        if not op_company_doc.get("custom_zatca_branch_address"):
            frappe.throw(
                _(
                    "The Branch Company '{0}' is missing a valid branch address. "
                    "Please update the Company with a valid `custom_zatca_branch_address`."
                ).format(op_company_doc.name)
            )
        if not op_company_doc.get("custom_registration_type"):
            frappe.throw(
                _(
                    "The Branch Company '{0}' is missing a valid registration type. "
                    "Please update the Company with a valid `custom_registration_type`."
                ).format(op_company_doc.name)
            )
        if not op_company_doc.get("custom_company_registration"):
            frappe.throw(
                _(
                    "The Branch Company '{0}' is missing a valid registration number. "
                    "Please update the Company with a valid `custom_company_registration`."
                ).format(op_company_doc.name)
            )

    # Validate invoice-level exemption reason when no Item Tax Template is used
    if not any(item.item_tax_template for item in doc.items):
        if (
            getattr(doc, "custom_exemption_reason_code", None) == "VATEX-SA-OOS"
            and not getattr(doc, "custom_tax_exemption_reason", None)
        ):
            frappe.throw(
                _(
                    "Tax Exemption Reason is mandatory when the "
                    "Exemption Reason Code is VATEX-SA-OOS."
                )
            )

    for item in doc.items:
        # Check if the item has a valid Item Tax Template
        if item.item_tax_template:
            try:
                item_tax_template = frappe.get_doc("Item Tax Template", item.item_tax_template)
                if (
                    getattr(item_tax_template, "custom_exemption_reason_code", None) == "VATEX-SA-OOS"
                    and not getattr(item_tax_template, "custom_tax_exemption_reason", None)
                ):
                    frappe.throw(
                        _(
                            "Tax Exemption Reason is mandatory in Item Tax Template "
                            "'{0}' when the Exemption Reason Code is VATEX-SA-OOS."
                        ).format(item.item_tax_template)
                    )
                continue
            except frappe.DoesNotExistError:
                frappe.throw(
                    _(
                        "The Item Tax Template '{0}' for item '{1}' does not exist."
                    ).format(item.item_tax_template, item.item_code)
                )

        if not doc.taxes or len(doc.taxes) == 0:
            frappe.throw(
                _(
                    "Tax information is missing from the Sales Invoice. "
                    "Either add an Item Tax Template for all items or include taxes in the invoice."
                )
            )

    # Billing reference check for Return / Credit Note
    if doc.is_return == 1 and doc.doctype in ["Sales Invoice", "POS Invoice"]:
        custom_return_against = getattr(doc, "custom_return_against_for_zatca", None)
        if not doc.return_against and not custom_return_against:
            frappe.throw(
                _(
                    "As per ZATCA regulation, the Billing Reference ID "
                    "(Original Invoice Number) is mandatory for Credit Notes and Return Invoices. "
                    "Please select the original invoice in the 'Return Against' or 'Custom Return Against For ZATCA' field."
                )
            )

    # Billing reference check for Debit Note
    if doc.doctype == "Sales Invoice" and getattr(doc, "is_debit_note", 0) == 1:
        custom_return_against = getattr(doc, "custom_return_against_for_zatca", None)
        if not doc.return_against and not custom_return_against:
            frappe.throw(
                _("Debit Note must reference an original invoice in 'Return Against' or 'Custom Return Against For ZATCA'.")
            )

    if doc.doctype == "Sales Invoice" and "claudion4saudi" in frappe.get_installed_apps():
        if hasattr(doc, "custom_advances_copy") and doc.custom_advances_copy:
            for advance_row in doc.custom_advances_copy:
                if getattr(advance_row, "difference_posting_date", None) and not getattr(advance_row, "reference_name", None):
                    frappe.throw(_(
                        "Missing Advance Sales Invoice reference name in advance details. "
                        "If there is no advance sales invoice, remove the row."
                    ))

