import frappe
from frappe import _
from frappe.utils.background_jobs import get_jobs


def validate_migration_jobs():
    if is_migration_jobs_queued():
        frappe.throw(
            "There are unfinished jobs in the queue. Please try again later."
        )  # noqa: 501


def is_migration_jobs_queued():
    jobs = get_jobs(site=frappe.local.site, key="job_name")[frappe.local.site]

    return any("bom_creator_job" in job for job in jobs)  # noqa: 501
