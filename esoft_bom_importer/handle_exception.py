import json

import frappe


def log_exception(title, error_obj):
    frappe.log_error(
        title=title,
        message=json.dumps(error_obj),
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
