# Copyright (c) 2025, shaikhosama504 and contributors
# For license information, please see license.txt

import os
import frappe
import pandas as pd
from frappe.model.document import Document


class BOMCreatorTool(Document):
    def process_file(self):
        if not self.excel_file:
            frappe.throw("Please upload a file first.")
        bom_data = give_json(self.excel_file)
        created_docs = []
        for bom_json in bom_data:
            docname = create_bom_creator_from_json(bom_json)
            if docname:
                created_docs.append(docname)
        return {"created_docs": created_docs}

@frappe.whitelist()
def process_file():
    docname = frappe.form_dict.docname
    doc = frappe.get_doc("BOM Creator Tool", docname)
    return doc.process_file()

@frappe.whitelist(allow_guest=True)
def give_json(file_url=None):
    if not file_url:
        frappe.throw("File URL is required.")

    # Retrieve the file document
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()

    # Determine file extension
    _, file_extension = os.path.splitext(file_path)
    file_extension = file_extension.lower()

    # Read the file based on its extension
    try:
        if file_extension == '.xlsx':
            df = pd.read_excel(file_path, engine='openpyxl', dtype=str).fillna('')
        elif file_extension == '.csv':
            df = pd.read_csv(file_path, dtype=str).fillna('')
        else:
            frappe.throw(f"Unsupported file extension: {file_extension}")
    except Exception as e:
        frappe.throw(f"Error reading file: {str(e)}")

    # List to store node dictionaries
    nodes = []

    # Convert each row into a node dictionary
    for idx, row in df.iterrows():
        item_id = row['Sub-Assembly'].strip() if row['Sub-Assembly'].strip() else row['SR NO'].strip()
        if not item_id:
            continue

        node = {
            'uid': idx,
            'item': item_id,
            'rev': str(row.get('REV', '')).strip(),
            'description': row.get('PART DESCRIPTION', '').strip(),
            'parent_item': row.get('Parent', '').strip(),
            'matl': row.get('MATL', '').strip(),
            'operation': row.get('operation', '').strip(),
            'den': row.get('Den', '').strip(),
            'qty_per_set': str(row.get('QTY/ SET', 1)),  # Convert to float
            'length': row.get('L', '').strip(),
            'width': row.get('W', '').strip(),
            'thickness': row.get('T', '').strip(),
            'bl_weight': row.get('BL.WT.', '').strip(),
            'area_sq_ft': row.get('AREA SQ.FT.', '').strip(),
            'children': []
        }
        nodes.append(node)

    # Build the tree structure
    root_nodes = []
    node_map = {node['item']: node for node in nodes}  # Create lookup map
    
    for node in nodes:
        parent_item = node['parent_item']
        if parent_item and parent_item in node_map:
            parent_node = node_map[parent_item]
            parent_node['children'].append(node)
        elif not parent_item:
            root_nodes.append(node)

    # Clean up nodes - preserve all technical fields
    preserved_fields = [
        'item', 'rev', 'description', 'matl', 'operation',
        'den', 'qty_per_set', 'length', 'width', 'thickness',
        'bl_weight', 'area_sq_ft', 'children'
    ]

    def cleanup(node):
        keys = list(node.keys())
        for key in keys:
            if key not in preserved_fields:
                node.pop(key, None)
        for child in node['children']:
            cleanup(child)

    for root in root_nodes:
        cleanup(root)

    return root_nodes

def create_bom_creator_from_json(bom_json):
    if not bom_json:
        return

    def ensure_item_exists(item_code, item_name=None, description=None, item_group="Demo Item Group"):
        if not frappe.db.exists("Item", item_code):
            item_doc = {
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name or item_code,
                "description": description or item_code,
                "item_group": item_group,
                "stock_uom": "Nos",
                "is_stock_item": 0
            }
            frappe.get_doc(item_doc).insert(ignore_permissions=True)
            frappe.db.commit()

    top_item = bom_json.get("item") or bom_json.get("description")
    top_item_name = bom_json.get("description") or top_item
    description = bom_json.get("description") or top_item

    ensure_item_exists(top_item, top_item_name, description)

    items = []

    def process_children(children, parent_row_no=None, parent_item_code=None):
        for child in children:
            item_code = child.get("item") or child.get("description")
            item_name = child.get("description") or item_code
            item_desc = child.get("description") or item_name

            ensure_item_exists(item_code, item_name, item_desc)

            child_item = {
                "doctype": "BOM Creator Item",
                "item_code": item_code,
                "item_name": item_name,
                "description": item_desc,
                "qty": child.get("qty_per_set", 1),
                "rate": 0,
                "uom": "Nos",
                "is_expandable": 1 if child.get("children") else 0,
                "bom_created": 0,
                "allow_alternative_item": 1,
                "do_not_explode": 1,
                "stock_qty": child.get("qty_per_set", 1),
                "conversion_factor": 1,
                "stock_uom": "Nos",
                "amount": 0,
                "fg_item": parent_item_code,
                "fg_reference_id": parent_item_code,  # Use parent's item_code
                "parent_row_no": str(parent_row_no) if parent_row_no is not None else None,
            }
            items.append(child_item)
            current_idx = len(items)  # Current 1-based index (idx starts at 1)
            if child.get("children"):
                process_children(child["children"], parent_row_no=current_idx, parent_item_code=item_code)

    if bom_json.get("children"):
        process_children(bom_json["children"], parent_row_no=None, parent_item_code=top_item)

    bom_doc = frappe.get_doc({
        "doctype": "BOM Creator",
        "item_code": top_item,
        "item_name": top_item_name,
        "item_group": "Demo Item Group",
        "qty": 1,
        "uom": "Nos",
        "rm_cost_as_per": "Valuation Rate",
        "company": frappe.defaults.get_user_default("Company"),
        "default_warehouse": "Stores - ESOFT",
        "currency": "INR",
        "conversion_rate": 1,
        "items": items
    })

    bom_doc.insert(ignore_permissions=True)
    return bom_doc.name


# class BOMCreatorTool(Document):
#     def process_file(self):
#         if not self.excel_file:
#             frappe.throw("Please upload a file first.")
#         bom_data = give_json(self.excel_file)
#         created_docs = []
#         for bom_json in bom_data:
#             docname = create_bom_creator_from_json(bom_json)
#             if docname:
#                 created_docs.append(docname)
#         return {"created_docs": created_docs}