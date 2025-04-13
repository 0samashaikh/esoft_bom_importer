# Copyright (c) 2025, shaikhosama504 and contributors
# For license information, please see license.txt

import os
import frappe
import pandas as pd
from frappe.model.document import Document
from rq.job import Job
from frappe.utils.background_jobs import get_redis_conn

class BOMCreatorTool(Document):
    def process_file(self):
        if not self.excel_file:
            frappe.throw("Please upload a file first.")

        bom_data = parse_excel_to_json(self.excel_file)
        created_documents = []

        for bom_structure in bom_data:
            new_docname = create_bom_from_json(bom_structure)
            if new_docname:
                created_documents.append(new_docname)

        return {"created_docs": created_documents}

@frappe.whitelist()
def get_bom_preview(docname):
    """Return list of BOMs that will be created from the Excel file"""
    doc = frappe.get_doc("BOM Creator Tool", docname)
    if not doc.excel_file:
        frappe.throw("Please upload a file first.")
    
    bom_data = parse_excel_to_json(doc.excel_file)
    preview_items = [bom.get('item') for bom in bom_data if bom.get('item')]
    
    if not preview_items:
        frappe.throw("No valid BOM structures found in the file.")
    
    return preview_items

@frappe.whitelist()
def process_file(docname):
    doc = frappe.get_doc("BOM Creator Tool", docname)
    return doc.process_file()

@frappe.whitelist(allow_guest=True)
def parse_excel_to_json(file_path):
    file_doc = frappe.get_doc("File", {"file_url": file_path})
    file_path = file_doc.get_full_path()
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()

    if file_extension == '.xlsx':
        df = pd.read_excel(file_path, engine='openpyxl', dtype=str).fillna('')
    elif file_extension == '.csv':
        df = pd.read_csv(file_path, dtype=str).fillna('')
    else:
        frappe.throw(f"Unsupported file extension: {file_extension}")

    df = df.applymap(lambda x: str(x).strip() if isinstance(x, str) else x)

    nodes = []
    node_map = {}
    root_nodes = []

    for idx, row in df.iterrows():
        sub_assembly = row.get('Sub-Assembly', '').strip()
        sr_no = row.get('SR NO', '').strip()
        parent = row.get('Parent', '').strip()

        item_id = sub_assembly or sr_no
        if not item_id:
            continue

        node = {
            'uid': idx,
            'item': item_id,
            'rev': row.get('REV', '').strip(),
            'description': row.get('PART DESCRIPTION', '').strip(),
            'parent_item': parent,
            'matl': row.get('MATL', '').strip(),
            'operation': row.get('operation', '').strip(),
            'den': row.get('Den', '').strip(),
            'qty_per_set': row.get('QTY/ SET', '1').strip(),
            'length': row.get('L', '').strip(),
            'width': row.get('W', '').strip(),
            'thickness': row.get('T', '').strip(),
            'bl_weight': row.get('BL.WT.', '').strip(),
            'area_sq_ft': row.get('AREA SQ.FT.', '').strip(),
            'children': []
        }

        node_map[item_id] = node

        if not parent:
            root_nodes.append(node)
        else:
            parent_node = node_map.get(parent)
            if parent_node:
                parent_node['children'].append(node)
            else:
                root_nodes.append(node)

    return root_nodes

def create_bom_from_json(bom_json):
    if not bom_json:
        return

    item_code = bom_json.get("item")
    description = bom_json.get("description") or item_code

    if frappe.db.exists("BOM Creator", {"item_code": item_code}):
        frappe.logger().info(f"BOM Creator for item {item_code} already exists. Skipping...")
        return None

    def ensure_item(item_code, name=None, description=None):
        if not frappe.db.exists("Item", item_code):
            item_doc = {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": name or item_code,
                "description": description or item_code,
                "item_group": "Demo Item Group",
                "stock_uom": "Nos",
                "is_stock_item": 0
            }
            frappe.get_doc(item_doc).insert(ignore_permissions=True)
            frappe.db.commit()

    ensure_item(item_code, item_code, description)

    items = []

    def add_items(node, parent_item_code, parent_idx=None):
        item_code = node['item']
        description = node.get('description', item_code)
        ensure_item(item_code, item_code, description)
        if node.get("operation"):
            operations = node.get("operation").split("+")
            for op in operations:
                op = op.strip()  # Clean up any extra spaces
                if not frappe.db.exists("Operation", op):
                    operation_doc = {
                        "doctype": "Operation",
                        "name": op,
                        "description": op,
                    }
                    frappe.get_doc(operation_doc).insert(ignore_permissions=True)
                    frappe.db.commit()
        item_entry = {
            "doctype": "BOM Creator Item",
            "item_code": item_code,
            "item_name": item_code,
            "description": description,
            "qty": str(node.get('qty_per_set', 1)),
            "rate": 0,
            "uom": "Nos",
            "is_expandable": 1 if node.get('children') else 0,
            "sourced_by_supplier": 0,
            "bom_created": 0,
            "allow_alternative_item": 1,
            "do_not_explode": 1,
            "stock_qty": str(node.get('qty_per_set', 1)),
            "conversion_factor": 1,
            "stock_uom": "Nos",
            "amount": 0,
            "base_rate": 0,
            "base_amount": 0,
            "fg_item": parent_item_code,
            "parent_row_no": str(parent_idx) if parent_idx is not None else None,
        }

        items.append(item_entry)
        current_idx = len(items)  # 1-based index

        for child in node.get('children', []):
            add_items(child, parent_item_code=item_code, parent_idx=current_idx)

    for child in bom_json.get('children', []):
        add_items(child, parent_item_code=item_code, parent_idx=None)

    bom_creator = frappe.get_doc({
        "doctype": "BOM Creator",
        "item_code": item_code,
        "item_name": description,
        "item_group": "Demo Item Group",
        "qty": 1,
        "uom": "Nos",
        "rm_cost_as_per": "Valuation Rate",
        "set_rate_based_on_warehouse": 0,
        "buying_price_list": "Standard Buying",
        "plc_conversion_rate": 0,
        "currency": "INR",
        "conversion_rate": 1,
        "default_warehouse": "Stores - ESOFT",
        "company": "Esoft (Demo)",
        "raw_material_cost": 0,
        "status": "Draft",
        "items": items
    })

    bom_creator.insert(ignore_permissions=True)
    frappe.db.commit()
    return bom_creator.name

def is_job_running(job_id):
    try:
        job = Job.fetch(job_id, connection=get_redis_conn())
        return job.get_status() in ['queued', 'started', 'deferred']
    except:
        return False

@frappe.whitelist()
def enqueue_bom_processing(docname):
    job_id = f"bom_creator_job_{docname}"

    if is_job_running(job_id):
        frappe.msgprint("A job is already running for this document.")
        return {"status": "exists"}

    frappe.enqueue(
        method="esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.process_file",
        queue="long",
        job_id=job_id,
        docname=docname,
    )

    return {"status": "started"}