import json

import frappe


def log_exception(title, error_obj, reference_doctype=None, reference_name=None):
    frappe.log_error(
        title=title,
        message=json.dumps(error_obj),
        reference_doctype=reference_doctype,
        reference_name=reference_name
    )


def log_warning(title, warning_msg, payload={}, filename="", index=None):
    error_obj = {
        "Traceback": warning_msg,
    }

    if filename:
        error_obj["filename"] = filename

    if index:
        error_obj["index"] = index

    if payload:
        error_obj["object"] = payload

    log_exception(
        title=title,
        error_obj=error_obj,  # noqa: 501
    )
