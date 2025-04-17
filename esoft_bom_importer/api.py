from esoft_bom_importer.utils import (
    convert_spreadsheet_to_json,
    get_fg_products,
    validate_and_enqueue_bom_creation
)
import frappe
from esoft_bom_importer.validator import validate_migration_jobs
from frappe.utils import now

@frappe.whitelist()
def validate_and_get_fg_products(file):
    """Return list of BOMs that will be created from the Excel file"""
    if not file:
        frappe.throw("Please upload a file first.")

    # convert attached file to json
    bom_tree = convert_spreadsheet_to_json(file)

    return get_fg_products(bom_tree)


@frappe.whitelist()
def import_bom_creator(filename):
    """Start background job for BOM processing"""
    validate_migration_jobs()

    bom_tree = convert_spreadsheet_to_json(filename)
    
    history = frappe.get_doc({
        "doctype": "BOM Creator Tool History",
        "job_name": "bom_creator_job",
        "job_status": "Validating",
        "started_at": now(),
        "started_by": frappe.session.user,
        "file": filename,
        }).insert(ignore_permissions=True)
    
    frappe.db.set_single_value("BOM Creator Tool", "status", "Validating")
    
    frappe.enqueue(
        method=validate_and_enqueue_bom_creation,
        queue="long",
        job_name="bom_creator_job",
        bom_tree=bom_tree,
        history=history.name
    )

