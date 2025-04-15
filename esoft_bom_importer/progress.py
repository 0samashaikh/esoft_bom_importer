from esoft_bom_importer.validator import is_migration_jobs_queued
import frappe


def set_progress(current, total, job, expires_in_sec=500):
    progress = (current / total) * 100
    status = "Completed" if progress >= 100 else "In Progress"
    
    frappe.cache().set_value(
        "esoft_import_status",
        {"progress":  f"{progress:.2f}%", "job": job, "status": status},
        expires_in_sec=expires_in_sec,
    )
    frappe.db.commit()
    
    return progress


@frappe.whitelist()
def get_import_progress():
    esoft_import_status = frappe.cache().get_value("esoft_import_status")
    if not esoft_import_status and is_migration_jobs_queued():
        esoft_import_status = {
            "progress": "Background Jobs Queued. Please be patient while it's processed.",  # noqa: 501
            "job": None,
        }

    return esoft_import_status or {}
