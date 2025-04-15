from esoft_bom_importer.utils import (
    convert_spreadsheet_to_json,
    create_bom_from_hierarchy,
    get_fg_products,
)
import frappe
from esoft_bom_importer.validator import validate_migration_jobs


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

    doc = frappe.get_single("BOM Creator Tool")
    doc.error = ""
    doc.bom_creator_status = ""
    doc.save()

    bom_tree = convert_spreadsheet_to_json(filename)
    total_length = len(bom_tree)
    for index, bom_structure in enumerate(bom_tree):
        frappe.enqueue(
            method=create_bom_from_hierarchy,
            queue="default",
            job_name="bom_creator_job",
            bom_structure=bom_structure,
            current_index=index,
            total_length=total_length,
        )
