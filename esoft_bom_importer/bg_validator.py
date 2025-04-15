import frappe
from frappe import _

def validate_migration_jobs():
    if is_migration_jobs_queued():
        frappe.throw(_("There are unfinished jobs in the queue. Please try again later."))

def is_migration_jobs_queued():
    unfinished_statuses = ["queued", "started"]
    jobs = frappe.get_all(
        "RQ Job",
        filters={
            "job_name": "bom_creator_job",
            "status": ["in", unfinished_statuses]
        },
        fields=["name", "job_name", "status"],
    )
    return bool(jobs)