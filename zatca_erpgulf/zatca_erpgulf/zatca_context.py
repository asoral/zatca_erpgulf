"""
ZATCA Context & Multi-Company Resolution Engine
Author: Grand Hyper Development Team
Description:
    Centralized resolver for ZATCA multi-company / child-company architecture,
    cryptographic key-pair integrity validation, VAT registration alignment,
    and buyer identifier validation (BT-46 / BT-48).

    Strictly preserves the customer's custom child-company architecture where
    operational branches are modeled as separate ERPNext `Company` records
    linked to a parent company group.
"""

import re
import datetime
import frappe
from frappe import _
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ObjectIdentifier, ExtensionOID

# ZATCA Valid Schemes for BT-46 Other Buyer ID
VALID_BUYER_ID_SCHEMES = {
    "TIN": {
        "regex": r"^3\d{13}3$",
        "desc": "Tax Identification Number (15 digits, starting and ending with 3)",
        "rule": "BR-KSA-F-07",
    },
    "IQA": {
        "regex": r"^2\d{9}$",
        "desc": "Iqama Number (10 digits, starting with 2)",
        "rule": "BR-KSA-F-11",
    },
    "NAT": {
        "regex": r"^1\d{9}$",
        "desc": "National ID (10 digits, starting with 1)",
        "rule": "BR-KSA-F-11",
    },
    "CRN": {
        "regex": r"^\d{10}$",
        "desc": "Commercial Registration Number (10 digits)",
        "rule": "BR-KSA-F-11",
    },
    "700": {
        "regex": r"^7\d{9}$",
        "desc": "700 Number (10 digits, starting with 7)",
        "rule": "BR-KSA-F-11",
    },
    "MOM": {
        "regex": r"^[A-Za-z0-9\-\_]{3,30}$",
        "desc": "Ministry of Municipal and Rural Affairs license",
        "rule": "BR-KSA-F-11",
    },
    "MLS": {
        "regex": r"^[A-Za-z0-9\-\_]{3,30}$",
        "desc": "Ministry of Labor license",
        "rule": "BR-KSA-F-11",
    },
    "SAG": {
        "regex": r"^[A-Za-z0-9\-\_]{3,30}$",
        "desc": "SAGIA license",
        "rule": "BR-KSA-F-11",
    },
    "OTH": {
        "regex": r"^[A-Za-z0-9\-\_]{1,50}$",
        "desc": "Other identifier",
        "rule": "BR-KSA-F-11",
    },
}

SUPPORTED_INVOICES = ["Sales Invoice", "POS Invoice", "Purchase Invoice"]


def clean_pem_certificate(cert_str):
    """Clean and normalize a PEM certificate string."""
    if not cert_str:
        return ""
    cleaned = (
        cert_str.replace("-----BEGIN CERTIFICATE-----", "")
        .replace("-----END CERTIFICATE-----", "")
        .replace("\n", "")
        .replace("\r", "")
        .strip()
    )
    if not cleaned:
        return ""
    wrapped = "\n".join([cleaned[i : i + 64] for i in range(0, len(cleaned), 64)])
    return f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----\n"


def clean_pem_private_key(key_str):
    """Clean and normalize a PEM private key string."""
    if not key_str:
        return ""
    key_str = key_str.strip()
    # If already has headers, return normalized lines
    if "-----BEGIN" in key_str and "-----END" in key_str:
        return key_str.strip() + "\n"

    # Otherwise treat as base64 and wrap as EC PRIVATE KEY
    cleaned = key_str.replace("\n", "").replace("\r", "").strip()
    wrapped = "\n".join([cleaned[i : i + 64] for i in range(0, len(cleaned), 64)])
    return f"-----BEGIN EC PRIVATE KEY-----\n{wrapped}\n-----END EC PRIVATE KEY-----\n"


def get_zatca_company_context(doc_or_company, throw_on_missing=True):
    """
    Resolve ZATCA multi-company architecture context.

    For Grand Hyper:
        Customer models physical branches as separate child `Company` records
        linked to a parent company (e.g. 'Grand Hyper One person Company').
        - Child company provides: Seller name, branch address, branch CRN, branch VAT (or parent VAT).
        - Parent company provides: ZATCA CSID, certificate, private key, API environment.
    """
    invoice_company_name = None
    source_doc = None

    if hasattr(doc_or_company, "doctype"):
        source_doc = doc_or_company
        invoice_company_name = doc_or_company.get("company")
    elif isinstance(doc_or_company, dict):
        source_doc = frappe._dict(doc_or_company)
        invoice_company_name = doc_or_company.get("company")
    elif isinstance(doc_or_company, str):
        invoice_company_name = doc_or_company
    else:
        invoice_company_name = str(doc_or_company)

    if not invoice_company_name:
        if throw_on_missing:
            frappe.throw(_("Company is required to resolve ZATCA context."))
        return None

    if not frappe.db.exists("Company", invoice_company_name):
        # Could be an abbreviation
        by_abbr = frappe.db.get_value("Company", {"abbr": invoice_company_name}, "name")
        if by_abbr:
            invoice_company_name = by_abbr
        else:
            if throw_on_missing:
                frappe.throw(_("Company '{0}' not found.").format(invoice_company_name))
            return None

    invoice_company_doc = frappe.get_doc("Company", invoice_company_name)

    # Check child-company branch architecture:
    # A child company represents a branch when it is not a group, has custom_costcenter enabled,
    # and has a parent_company defined.
    is_child_branch = bool(
        not invoice_company_doc.is_group
        and getattr(invoice_company_doc, "custom_costcenter", 0)
        and invoice_company_doc.parent_company
    )

    if is_child_branch:
        parent_company_name = invoice_company_doc.parent_company
        parent_company_doc = frappe.get_doc("Company", parent_company_name)
        credential_company_doc = parent_company_doc
        operational_company_doc = invoice_company_doc
    else:
        parent_company_name = None
        parent_company_doc = None
        credential_company_doc = invoice_company_doc
        operational_company_doc = invoice_company_doc

    # Seller Name & Abbreviation
    seller_name = operational_company_doc.company_name or operational_company_doc.name
    abbr = operational_company_doc.abbr
    credential_abbr = credential_company_doc.abbr

    # VAT / Tax ID Resolution
    vat_number = (
        operational_company_doc.tax_id
        or credential_company_doc.tax_id
        or ""
    ).strip().replace(" ", "").replace("-", "")

    # Commercial Registration Resolution
    registration_type = (
        operational_company_doc.get("custom_registration_type")
        or credential_company_doc.get("custom_registration_type")
        or "CRN"
    )
    registration_number = (
        operational_company_doc.get("custom_company_registration")
        or credential_company_doc.get("custom_company_registration")
        or ""
    )

    # Address Resolution
    address_doc = None
    if is_child_branch and operational_company_doc.get("custom_zatca_branch_address"):
        branch_addr_name = operational_company_doc.get("custom_zatca_branch_address")
        if frappe.db.exists("Address", branch_addr_name):
            address_doc = frappe.get_doc("Address", branch_addr_name)

    if not address_doc:
        # Fall back to primary company address lookup
        addr_names = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Company",
                "link_name": operational_company_doc.name,
                "parenttype": "Address",
            },
            pluck="parent",
            limit=1,
        )
        if addr_names and frappe.db.exists("Address", addr_names[0]):
            address_doc = frappe.get_doc("Address", addr_names[0])
        elif parent_company_doc:
            # Fall back to parent company address
            parent_addr_names = frappe.get_all(
                "Dynamic Link",
                filters={
                    "link_doctype": "Company",
                    "link_name": parent_company_doc.name,
                    "parenttype": "Address",
                },
                pluck="parent",
                limit=1,
            )
            if parent_addr_names and frappe.db.exists("Address", parent_addr_names[0]):
                address_doc = frappe.get_doc("Address", parent_addr_names[0])

    # POS / Machine Override (Zatca Multiple Setting)
    multiple_setting_doc = None
    cert_raw = (credential_company_doc.get("custom_certificate") or "").strip()
    key_raw = (credential_company_doc.get("custom_private_key") or "").strip()

    pos_setting_name = None
    if source_doc:
        if hasattr(source_doc, "get"):
            pos_setting_name = source_doc.get("custom_zatca_pos_name")
        elif hasattr(source_doc, "custom_zatca_pos_name"):
            pos_setting_name = source_doc.custom_zatca_pos_name

    if pos_setting_name and (
        frappe.db.exists("ZATCA Multiple Setting", pos_setting_name)
        or frappe.db.exists("Zatca Multiple Setting", pos_setting_name)
    ):
        multiple_setting_doctype = (
            "ZATCA Multiple Setting"
            if frappe.db.exists("ZATCA Multiple Setting", pos_setting_name)
            else "Zatca Multiple Setting"
        )
        multiple_setting_doc = frappe.get_doc(multiple_setting_doctype, pos_setting_name)
        if multiple_setting_doc.get("custom_certficate"):
            cert_raw = (multiple_setting_doc.get("custom_certficate") or "").strip()
        if multiple_setting_doc.get("custom_private_key"):
            key_raw = (multiple_setting_doc.get("custom_private_key") or "").strip()

    certificate_pem = clean_pem_certificate(cert_raw)
    private_key_pem = clean_pem_private_key(key_raw)

    environment = (
        credential_company_doc.get("custom_select")
        or "sandbox"
    ).lower().strip()

    pih = credential_company_doc.get("custom_pih") or ""

    context = {
        "invoice_company": invoice_company_doc.name,
        "invoice_company_doc": invoice_company_doc,
        "parent_company": parent_company_name,
        "parent_company_doc": parent_company_doc,
        "credential_company": credential_company_doc.name,
        "credential_company_doc": credential_company_doc,
        "operational_company": operational_company_doc.name,
        "operational_company_doc": operational_company_doc,
        "is_child_branch": is_child_branch,
        "seller_name": seller_name,
        "abbr": abbr,
        "credential_abbr": credential_abbr,
        "vat_number": vat_number,
        "seller_vat": vat_number,
        "registration_type": registration_type,
        "registration_number": registration_number,
        "address": address_doc,
        "seller_address": address_doc,
        "certificate": certificate_pem,
        "certificate_raw": cert_raw,
        "private_key": private_key_pem,
        "private_key_raw": key_raw,
        "csid": (
            (
                multiple_setting_doc.get("custom_final_auth_csid")
                or multiple_setting_doc.get("custom_basic_auth_from_csid")
            )
            if multiple_setting_doc
            else (
                credential_company_doc.get("custom_basic_auth_from_production")
                or credential_company_doc.get("custom_basic_auth_from_csid")
                or credential_company_doc.get("custom_basic_auth_production")
                or credential_company_doc.get("custom_basic_auth_sandbox")
            )
        ),
        "environment": environment,
        "pih": (
            multiple_setting_doc.get("custom_pih")
            if multiple_setting_doc and multiple_setting_doc.get("custom_pih")
            else pih
        ),
        "multiple_setting": multiple_setting_doc,
    }

    return context


def get_zatca_credential_context(context):
    """
    Resolve certificate/private-key/CSID source without changing the
    operational child-company/parent-company architecture.

    If a POS ZATCA Multiple Setting explicitly says to use the linked
    Company's certificate/keys, only the cryptographic credential source is
    switched. Seller/company/address/VAT context remains unchanged.
    """
    credential_company_doc = context.get("credential_company_doc")
    multiple_setting_doc = context.get("multiple_setting")
    cert_raw = context.get("certificate_raw") or ""
    key_raw = context.get("private_key_raw") or ""
    csid = context.get("csid") or ""

    if multiple_setting_doc:
        use_company_keys = multiple_setting_doc.get(
            "custom__use_company_certificate__keys"
        )
        linked_company = multiple_setting_doc.get("custom_linked_doctype")

        if use_company_keys != 1 and linked_company:
            if frappe.db.exists("Company", linked_company):
                linked_company_doc = frappe.get_doc("Company", linked_company)
                cert_raw = linked_company_doc.get("custom_certificate") or cert_raw
                key_raw = linked_company_doc.get("custom_private_key") or key_raw
                csid = (
                    linked_company_doc.get("custom_basic_auth_from_production")
                    or linked_company_doc.get("custom_basic_auth_production")
                    or linked_company_doc.get("custom_final_auth_csid")
                    or linked_company_doc.get("custom_basic_auth_from_csid")
                    or linked_company_doc.get("custom_basic_auth_sandbox")
                    or csid
                )
                return {
                    "credential_company_doc": linked_company_doc,
                    "certificate_raw": cert_raw,
                    "certificate": clean_pem_certificate(cert_raw),
                    "private_key_raw": key_raw,
                    "private_key": clean_pem_private_key(key_raw),
                    "csid": csid,
                    "multiple_setting": multiple_setting_doc,
                }

    return {
        "credential_company_doc": credential_company_doc,
        "certificate_raw": cert_raw,
        "certificate": clean_pem_certificate(cert_raw),
        "private_key_raw": key_raw,
        "private_key": clean_pem_private_key(key_raw),
        "csid": csid,
        "multiple_setting": multiple_setting_doc,
    }


def validate_buyer_identifier(customer_doc_or_name, is_b2c=False):
    """
    Validate buyer identifier for ZATCA BT-46 Other Buyer ID.

    Rules:
    - For B2C:
        If `custom_buyer_id` is empty/missing, returns None.
        In ZATCA XML, the entire <cac:PartyIdentification> tag MUST be omitted
        to prevent BR-KSA-F-07 and BR-KSA-F-13.
    - If `custom_buyer_id` is provided (or mandatory for B2B):
        Strictly validates the scheme and format against ZATCA rules:
        - TIN: 15 digits, starting and ending with 3 (rule BR-KSA-F-07)
        - IQA: 10 digits, starting with 2
        - NAT: 10 digits, starting with 1
        - CRN: 10 digits
        - 700: 10 digits, starting with 7
    """
    if not customer_doc_or_name:
        return None

    if isinstance(customer_doc_or_name, str):
        if not frappe.db.exists("Customer", customer_doc_or_name):
            return None
        customer_doc = frappe.get_doc("Customer", customer_doc_or_name)
    elif hasattr(customer_doc_or_name, "get"):
        customer_doc = customer_doc_or_name
    else:
        return None

    buyer_id = (customer_doc.get("custom_buyer_id") or "").strip()
    buyer_id_type = (customer_doc.get("custom_buyer_id_type") or "").strip().upper()

    # Rule: If B2C and no buyer ID is supplied, omit BT-46 completely
    if is_b2c and not buyer_id:
        # A B2C customer without an identifier must not emit BT-46.
        # Ignore a leftover Buyer ID Type value when the actual ID is empty.
        return None

    # If neither scheme nor ID is provided, nothing to output
    if not buyer_id:
        return None

    # Default scheme if empty but ID provided
    if not buyer_id_type:
        buyer_id_type = "OTH"

    cust_name = getattr(customer_doc, "name", None) or customer_doc.get("name", "Customer")
    if buyer_id_type not in VALID_BUYER_ID_SCHEMES:
        valid_schemes_str = ", ".join(sorted(VALID_BUYER_ID_SCHEMES.keys()))
        frappe.throw(
            _(
                "Invalid Buyer ID Scheme '{0}' for Customer {1}. Valid ZATCA schemes are: {2}"
            ).format(buyer_id_type, cust_name, valid_schemes_str)
        )

    scheme_info = VALID_BUYER_ID_SCHEMES[buyer_id_type]
    pattern = scheme_info["regex"]

    if not re.match(pattern, buyer_id):
        frappe.throw(
            _(
                "Invalid Buyer Identifier for Customer {0}. Scheme '{1}' expects {2}. Provided value: '{3}' (ZATCA Rule: {4})."
            ).format(
                cust_name,
                buyer_id_type,
                scheme_info["desc"],
                buyer_id,
                scheme_info["rule"],
            )
        )

    return {"scheme": buyer_id_type, "id": buyer_id}


def extract_certificate_vat(cert_pem):
    """
    Extract the 15-digit VAT number from an X.509 certificate.

    In ZATCA certificates:
    - Subject Alternative Name (SAN) contains dirName with organizationIdentifier (OID 2.5.4.97)
    - Subject contains organizationIdentifier (OID 2.5.4.97) or CN with VAT number.
    """
    if not cert_pem:
        return None

    try:
        cert_bytes = cert_pem.encode("utf-8") if isinstance(cert_pem, str) else cert_pem
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

        vat_pattern = re.compile(r"3\d{13}3")

        # 1. Inspect Subject Attributes
        for attr in cert.subject:
            val_str = str(attr.value)
            match = vat_pattern.search(val_str)
            if match:
                return match.group(0)

        # 2. Inspect Subject Alternative Name (SAN)
        try:
            san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            for general_name in san_ext.value:
                val_str = str(general_name.value)
                match = vat_pattern.search(val_str)
                if match:
                    return match.group(0)
        except x509.ExtensionNotFound:
            pass

        # 3. Inspect all other extensions for OID 2.5.4.97
        for ext in cert.extensions:
            val_str = str(ext.value)
            match = vat_pattern.search(val_str)
            if match:
                return match.group(0)

    except Exception as e:
        frappe.log_error(f"Error parsing certificate VAT: {str(e)}", "ZATCA Context")

    return None


def verify_certificate_and_key_pair(cert_pem, key_pem):
    """
    Cryptographically verify that an X.509 certificate and private key match each other.

    Returns:
        tuple (is_match: bool, error_message: str or None)
    """
    if not cert_pem:
        return False, "Certificate is missing."
    if not key_pem:
        return False, "Private key is missing."

    try:
        cert_bytes = cert_pem.encode("utf-8") if isinstance(cert_pem, str) else cert_pem
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

        key_bytes = key_pem.encode("utf-8") if isinstance(key_pem, str) else key_pem
        private_key = serialization.load_pem_private_key(
            key_bytes, password=None, backend=default_backend()
        )

        cert_pub_der = cert.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        key_pub_der = private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )

        if cert_pub_der != key_pub_der:
            return (
                False,
                "Cryptographic mismatch: The stored Private Key does NOT correspond to the stored Certificate.",
            )

        return True, None

    except Exception as e:
        return False, f"Failed to verify certificate and key pair: {str(e)}"


def validate_zatca_invoice_before_submission(sales_invoice_doc):
    """
    Pre-flight validation before any ZATCA API submission.

    Guarantees:
    1. Seller VAT is valid (15 digits, starting and ending with 3).
    2. Stored Certificate is present and valid.
    3. Stored Private Key is present and cryptographically matches the Certificate.
    4. Certificate validity window is active (not expired).
    5. Certificate VAT matches the Invoice Seller VAT.
    6. Customer Buyer Identifier conforms to ZATCA scheme rules.
    7. Return / Credit Note has required original reference.

    Blocks submission locally if any condition fails, preventing:
    - 'invalid-signing-certificate'
    - 'BR-KSA-F-07' / 'BR-KSA-F-11' / 'BR-KSA-F-13'
    - ZATCA rejection errors.
    """
    context = get_zatca_company_context(sales_invoice_doc)
    company_name = context["invoice_company"]
    cred_company = context["credential_company"]

    # 1. Seller VAT validation
    seller_vat = context["vat_number"]
    if not seller_vat:
        frappe.throw(
            _(
                "ZATCA Error: Tax ID (VAT) is missing for Company '{0}' (or parent '{1}')."
            ).format(company_name, cred_company)
        )

    if not re.match(r"^3\d{13}3$", seller_vat):
        frappe.throw(
            _(
                "ZATCA Error: Invalid Seller VAT '{0}' for Company '{1}'. Must be exactly 15 digits starting and ending with 3."
            ).format(seller_vat, company_name)
        )

    # 2. Certificate Presence
    cert_pem = context["certificate"]
    if not cert_pem:
        frappe.throw(
            _(
                "ZATCA Error: Missing X.509 Certificate for Company '{0}' (stored in '{1}'). Please complete ZATCA onboarding."
            ).format(company_name, cred_company)
        )

    # 3. Private Key Presence
    key_pem = context["private_key"]
    if not key_pem:
        frappe.throw(
            _(
                "ZATCA Error: Missing Private Key for Company '{0}' (stored in '{1}')."
            ).format(company_name, cred_company)
        )

    # 4. Cryptographic Key-Pair Validation
    is_valid_pair, pair_error = verify_certificate_and_key_pair(cert_pem, key_pem)
    if not is_valid_pair:
        frappe.throw(
            _(
                "ZATCA Configuration Error in Company '{0}': {1} "
                "Submission blocked locally to prevent 'invalid-signing-certificate' warning. "
                "Please regenerate CSR and re-onboard the CSID."
            ).format(cred_company, pair_error)
        )

    # 5. Certificate Expiration & Validity Window
    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"), default_backend())
        now = datetime.datetime.now(datetime.timezone.utc)
        if now < cert.not_valid_before_utc:
            frappe.throw(
                _(
                    "ZATCA Error: Certificate in Company '{0}' is not yet valid (valid from {1})."
                ).format(cred_company, cert.not_valid_before_utc)
            )
        if now > cert.not_valid_after_utc:
            frappe.throw(
                _(
                    "ZATCA Error: Certificate in Company '{0}' has expired on {1}. Please renew ZATCA CSID."
                ).format(cred_company, cert.not_valid_after_utc)
            )
    except Exception as e:
        frappe.throw(f"ZATCA Certificate Parse Error: {str(e)}")

    # 6. Certificate VAT Alignment
    cert_vat = extract_certificate_vat(cert_pem)
    if cert_vat and cert_vat != seller_vat:
        frappe.throw(
            _(
                "ZATCA VAT Mismatch: Invoice Seller VAT ({0}) does not match Certificate VAT ({1}) in Company '{2}'. "
                "Submission blocked to prevent 'invalid-signing-certificate' rejection."
            ).format(seller_vat, cert_vat, cred_company)
        )

    # 7. Customer Buyer ID validation
    customer_name = sales_invoice_doc.get("customer")
    is_b2c = bool(sales_invoice_doc.get("custom_b2c"))
    if customer_name:
        validate_buyer_identifier(customer_name, is_b2c=is_b2c)

    # 8. Credit Note / Debit Note original reference validation
    is_return = bool(sales_invoice_doc.get("is_return"))
    is_debit = bool(sales_invoice_doc.get("is_debit_note"))
    if is_return or is_debit:
        orig_ref = (
            sales_invoice_doc.get("return_against")
            or sales_invoice_doc.get("custom_return_against_for_zatca")
        )
        if not orig_ref:
            note_type = "Debit Note" if is_debit else "Credit Note / Return"
            frappe.throw(
                _(
                    "ZATCA Error: '{0}' requires an original invoice reference. "
                    "Please set 'Return Against' or 'Custom Return Against For ZATCA'."
                ).format(note_type)
            )

    return True
