# Copyright (c) 2025, shaikhosama504 and contributors
# For license information, please see license.txt

import os
import frappe
import pandas as pd
from frappe.model.document import Document
from rq.job import Job
from frappe.utils.background_jobs import get_redis_conn

class BOMCreatorTool(Document):
    def process_uploaded_file(self):
        """Main method to process uploaded file and create BOMs"""
        if not self.bom_creator:
            frappe.throw("Please upload a file first.")

        bom_hierarchy = parse_excel_data_to_hierarchy(self.bom_creator)
        created_documents = []

        for bom_structure in bom_hierarchy:
            new_bom = create_bom_from_hierarchy(bom_structure)
            if new_bom:
                created_documents.append(new_bom)

        return {"created_docs": created_documents}

@frappe.whitelist()
def validate_and_get_fg_products(docname):
    """Return list of BOMs that will be created from the Excel file"""
    doc = frappe.get_doc("BOM Creator Tool", docname)
    if not doc.bom_creator:
        frappe.throw("Please upload a file first.")
    
    bom_data = parse_excel_data_to_hierarchy(doc.bom_creator)
    preview_items = [bom.get('item') for bom in bom_data if bom.get('item')]
    
    if not preview_items:
        frappe.throw("No valid BOM structures found in the file.")
    
    return preview_items

@frappe.whitelist()
def process_file_and_enqueue(docname):
    """Wrapper function to process file from background job"""
    doc = frappe.get_doc("BOM Creator Tool", docname)
    return doc.process_uploaded_file()

@frappe.whitelist(allow_guest=True)
def parse_excel_data_to_hierarchy(file_path):
    """Convert Excel/CSV file data into hierarchical BOM structure"""
    file_doc = frappe.get_doc("File", {"file_url": file_path})
    full_path = file_doc.get_full_path()
    file_extension = os.path.splitext(full_path)[1].lower()

    dataframe = read_spreadsheet_file(full_path, file_extension)
    dataframe = clean_dataframe(dataframe)
    
    return build_bom_hierarchy(dataframe)

def read_spreadsheet_file(file_path, file_extension):
    """Read Excel or CSV file into pandas DataFrame"""
    if file_extension == '.xlsx':
        return pd.read_excel(file_path, engine='openpyxl', dtype=str)
    if file_extension == '.csv':
        return pd.read_csv(file_path, dtype=str)
    
    frappe.throw(f"Unsupported file format: {file_extension}")

def clean_dataframe(dataframe):
    """Clean and prepare DataFrame for processing"""
    return dataframe.fillna('').applymap(
        lambda x: x.strip() if isinstance(x, str) else x
    )

def build_bom_hierarchy(dataframe):
    """Build hierarchical BOM structure from DataFrame"""
    nodes = []
    node_map = {}
    root_nodes = []

    for row_index, row_data in dataframe.iterrows():
        node = create_node_from_row(row_data, row_index)
        if not node:
            continue

        node_map[node['item']] = node
        parent_item = row_data.get('Parent', '').strip()

        if parent_item:
            add_node_to_parent(parent_item, node, node_map, root_nodes)
        else:
            root_nodes.append(node)

    return root_nodes

def create_node_from_row(row_data, row_index):
    """Create a BOM node from DataFrame row"""
    sub_assembly = row_data.get('Sub-Assembly', '').strip()
    sr_no = row_data.get('SR NO', '').strip()
    item_id = sub_assembly or sr_no

    if not item_id:
        return None

    return {
        'uid': row_index,
        'item': item_id,
        'rev': row_data.get('REV', '').strip(),
        'description': row_data.get('PART DESCRIPTION', '').strip(),
        'parent_item': row_data.get('Parent', '').strip(),
        'matl': row_data.get('MATL', '').strip(),
        'operation': row_data.get('operation', '').strip(),
        'den': row_data.get('Den', '').strip(),
        'qty_per_set': row_data.get('QTY/ SET', '1').strip(),
        'length': row_data.get('L', '').strip(),
        'width': row_data.get('W', '').strip(),
        'thickness': row_data.get('T', '').strip(),
        'bl_weight': row_data.get('BL.WT.', '').strip(),
        'area_sq_ft': row_data.get('AREA SQ.FT.', '').strip(),
        'children': []
    }

def add_node_to_parent(parent_item, node, node_map, root_nodes):
    """Add node to its parent or root if parent not found"""
    parent_node = node_map.get(parent_item)
    if parent_node:
        parent_node['children'].append(node)
    else:
        root_nodes.append(node)

def create_bom_from_hierarchy(bom_structure):
    """Create BOM Creator document from hierarchical structure"""
    if not bom_structure:
        return None

    item_code = bom_structure.get("item")
    description = bom_structure.get("description") or item_code

    if frappe.db.exists("BOM Creator", {"item_code": item_code}):
        frappe.log_info(f"Skipping existing BOM Creator for item: {item_code}")
        return None

    ensure_item_exists(item_code, description)
    bom_items = build_bom_items(bom_structure)

    bom_creator = create_bom_creator_document(item_code, description, bom_items)
    return bom_creator.name

def ensure_item_exists(item_code, description):
    """Create Item if it doesn't exist"""
    if frappe.db.exists("Item", item_code):
        return

    item_data = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "description": description,
        "item_group": "Demo Item Group",
        "stock_uom": "Nos",
        "is_stock_item": 0
    }
    frappe.get_doc(item_data).insert(ignore_permissions=True)
    frappe.db.commit()

def build_bom_items(bom_structure):
    """Recursively build BOM items from hierarchy while ensuring all items exist"""
    items = []
    parent_item_code = bom_structure.get("item")

    def add_child_items(node, parent_code, parent_idx=None):
        # Ensure this item exists first
        ensure_item_exists(node['item'], node.get('description', node['item']))
        
        # Create item entry
        item_entry = create_bom_item_entry(node, parent_code, parent_idx)
        items.append(item_entry)
        current_idx = len(items)

        # Handle operations before processing children
        handle_operations(node.get("operation", ""))

        # Process children recursively
        for child in node.get('children', []):
            add_child_items(child, parent_code=node['item'], parent_idx=current_idx)

    # First ensure all child items exist
    for child in bom_structure.get('children', []):
        recursively_ensure_items(child)

    # Now build the BOM items
    for child in bom_structure.get('children', []):
        add_child_items(child, parent_item_code)

    return items

def recursively_ensure_items(node):
    """Recursively ensure all items in hierarchy exist"""
    ensure_item_exists(node['item'], node.get('description', node['item']))
    for child in node.get('children', []):
        recursively_ensure_items(child)

def create_bom_item_entry(node, parent_code, parent_idx):
    """Create complete BOM Creator Item entry with all required fields"""
    return {
        "doctype": "BOM Creator Item",
        "item_code": node['item'],
        "item_name": node['item'],
        "description": node.get('description', node['item']),
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
        "fg_item": parent_code,
        "parent_row_no": str(parent_idx) if parent_idx is not None else None,
    }

def handle_operations(operations_str):
    """Create Operations if they don't exist"""
    for operation in operations_str.split("+"):
        operation = operation.strip()
        if operation and not frappe.db.exists("Operation", operation):
            create_operation(operation)

def create_operation(operation_name):
    """Create new Operation document"""
    operation_data = {
        "doctype": "Operation",
        "name": operation_name,
        "description": operation_name,
    }
    frappe.get_doc(operation_data).insert(ignore_permissions=True)
    frappe.db.commit()

def create_bom_creator_document(item_code, description, items):
    """Create complete BOM Creator document with all required fields"""
    bom_data = {
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
    }
    
    bom_creator = frappe.get_doc(bom_data)
    bom_creator.insert(ignore_permissions=True)
    frappe.db.commit()
    return bom_creator

def check_job_status(job_id):
    """Check if background job is running"""
    try:
        job = Job.fetch(job_id, connection=get_redis_conn())
        return job.get_status() in ['queued', 'started', 'deferred']
    except Exception:
        return False

@frappe.whitelist()
def import_bom_creator(docname):
    """Start background job for BOM processing"""
    job_id = f"bom_processing_{docname}"

    if check_job_status(job_id):
        frappe.msgprint("BOM processing is already in progress")
        return {"status": "already_running"}

    frappe.enqueue(
        method=process_file_and_enqueue,
        queue="long",
        job_id=job_id,
        docname=docname,
    )

    return {"status": "started"}