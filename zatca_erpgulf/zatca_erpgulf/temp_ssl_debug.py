"""Temporary diagnostic endpoint for the gevent/ssl RecursionError investigation.
Delete this file once the root cause is confirmed and fixed.
"""
import sys
import ssl
import frappe


@frappe.whitelist(allow_guest=False)
def dump_ssl_state():
    """Dump ssl/gevent monkeypatch state from inside the current worker process."""
    result = {
        "ssl_module_file": getattr(ssl, "__file__", None),
        "ssl_module_id": id(ssl),
        "SSLContext_mro": [str(c) for c in ssl.SSLContext.__mro__],
        "SSLContext_module": ssl.SSLContext.__module__,
        "SSLContext_id": id(ssl.SSLContext),
        "gevent_in_sys_modules": "gevent" in sys.modules,
        "gevent_ssl_in_sys_modules": "gevent.ssl" in sys.modules,
    }

    try:
        import gevent.monkey as monkey  # noqa: PLC0415

        result["gevent_version"] = __import__("gevent").__version__
        result["gevent_ssl_patched"] = monkey.is_module_patched("ssl")
        result["gevent_saved_keys"] = list(monkey.saved.keys())
    except ImportError as e:
        result["gevent_import_error"] = str(e)

    try:
        test_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        test_ctx.check_hostname = False
        test_ctx.verify_mode = ssl.CERT_NONE
        result["manual_sslcontext_verify_mode_set"] = "OK"
    except RecursionError:
        result["manual_sslcontext_verify_mode_set"] = "RECURSION_ERROR"
    except Exception as e:  # noqa: BLE001
        result["manual_sslcontext_verify_mode_set"] = f"OTHER_ERROR: {e}"

    return result
