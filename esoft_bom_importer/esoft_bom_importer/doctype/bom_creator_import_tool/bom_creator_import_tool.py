# Copyright (c) 2025, shaikhosama504 and contributors
# For license information, please see license.txt

import uuid
import frappe
import pandas as pd
from frappe.model.document import Document


def convert_sr_no_to_numeric(sr):
    """
    Convert an alphabetical serial number to numeric.
    For example, "A" -> "1", "B" -> "2", etc.
    If sr is already numeric, return it as is.
    """
    if sr.isdigit():
        return sr
    else:
        # Convert first character (assumes one-letter value; adjust if needed)
        return str(ord(sr.upper()[0]) - 64) if sr else None


class BOMCreatorImportTool(Document):
    def process_file(self):
        file_url = self.excel_file
        if not file_url:
            frappe.throw("Please upload a file first.")
        else:
            data = get_file(file_url)  # returns a list of BOMs
            created_docs = []
            for bom_json in data:
                docname = create_bom_creator_from_json(bom_json)
                if docname:
                    created_docs.append(docname)
            return {"created_docs": created_docs}


@frappe.whitelist()
def process_file():
    docname = frappe.form_dict.docname
    doc = frappe.get_doc("BOM Creator Import Tool", docname)
    return doc.process_file()


@frappe.whitelist()
def get_file(file_url):
    file_path = get_file_full_path(file_url)
    df = pd.read_csv(file_path, dtype=str).fillna("")
    result = []
    current_parent = None
    current_child = None

    for _, row in df.iterrows():
        sr_no = row["SR NO"].strip()
        part_data = {
            "sr_no": sr_no,
            "part_no": row["Sub-Assembly"].strip(),
            "rev": row["REV"].strip(),
            "description": row["PART DESCRIPTION"].strip(),
            "material": row.get("MATL", "").strip(),
            "operation": row.get("operation", "").strip(),
            "den": row.get("Den", "").strip(),
            "qty_per_set": row.get("QTY/ SET", "").strip(),
            "length": row.get("L", "").strip(),
            "width": row.get("W", "").strip(),
            "thickness": row.get("T", "").strip(),
            "bl_weight": row.get("BL.WT.", "").strip(),
            "area_sq_ft": row.get("AREA SQ.FT.", "").strip(),
            "children": []
        }

        # If SR NO is numeric, this is a top-level row.
        if sr_no.isdigit():
            current_parent = part_data
            current_parent["children"] = []
            current_parent["direct_children"] = []
            result.append(current_parent)
            current_child = None

        # If SR NO is alphabetic, this row is a child (sub‑assembly) of current parent.
        elif sr_no.isalpha():
            current_child = part_data
            current_child["children"] = []
            if current_parent:
                current_parent["children"].append(current_child)

        # If SR NO is empty but description is given, treat as leaf under current child or parent.
        elif sr_no == "" and part_data["description"]:
            sub_child = part_data
            if current_child:
                current_child["children"].append(sub_child)
            elif current_parent:
                current_parent["direct_children"].append(sub_child)

    def flatten_bom(parent, parent_id=None):
        flat = []
        parent_code = parent.get("part_no") or parent.get("description")
        parent_id = parent_id or str(uuid.uuid4())[:10]
        parent["item_id"] = parent_id

        for child in parent.get("children", []) + parent.get("direct_children", []):
            child_code = child.get("part_no") or child.get("description")
            child_id = str(uuid.uuid4())[:10]
            child["item_id"] = child_id

            flat.append({
                "item_code": child_code,
                "item_name": child.get("description") or child_code,
                "description": child.get("description"),
                "qty": child.get("qty_per_set") or 1,
                "uom": "Nos",
                "fg_item": parent_code,
                "fg_reference_id": parent_id,
                # For children of a sub-assembly, convert parent's sr_no to numeric.
                "parent_row_no": (convert_sr_no_to_numeric(parent.get("sr_no"))
                                  if parent.get("sr_no") and not parent.get("sr_no").isdigit()
                                  else None),
                "part_no": child.get("part_no"),
                "is_expandable": 1 if child.get("children") else 0,
            })

            if child.get("children"):
                flat.extend(flatten_bom(child, parent_id=child_id))
        return flat

    final_result = []
    for parent in result:
        parent_code = parent.get("part_no") or parent.get("description")
        parent["item_code"] = parent_code
        parent["item_name"] = parent.get("description")
        parent["items"] = flatten_bom(parent)
        final_result.append(parent)

    return final_result


def get_file_full_path(file):
    if "private" not in file:
        return frappe.get_site_path() + "/public" + file
    else:
        return frappe.get_site_path() + file


def create_bom_creator_from_json(bom_json):
    if not bom_json:
        return

    def ensure_item_exists(item_code, item_name=None, description=None, item_group="Demo Item Group"):
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": item_name or item_code,
                "description": description or item_code,
                "item_group": item_group,
                "stock_uom": "Nos",
                "is_stock_item": 0
            }).insert(ignore_permissions=True)

    top_item = (bom_json.get("item_code") or
                bom_json.get("item_name") or
                bom_json.get("part_no") or
                bom_json.get("description"))
    top_item_name = bom_json.get("item_name") or bom_json.get("description") or top_item
    description = bom_json.get("description") or bom_json.get("part_no") or top_item

    ensure_item_exists(top_item, top_item_name, description)

    items = []
    item_map = {}
    # Insert the top-level item in the map.
    item_map[top_item] = str(uuid.uuid4())[:10]

    # For each flattened child item, build BOM Creator Item entries.
    for idx, child in enumerate(bom_json.get("items", []), start=1):
        item_code = (child.get("item_code") or
                     child.get("item_name") or
                     child.get("part_no") or
                     child.get("description"))
        item_name = child.get("item_name") or child.get("description") or item_code
        item_desc = child.get("description") or item_name

        ensure_item_exists(item_code, item_name, item_desc)
        item_id = str(uuid.uuid4())[:10]
        item_map[item_code] = item_id

        child_item = {
            "doctype": "BOM Creator Item",
            "item_code": item_code,
            "item_name": item_name,
            "description": item_desc,
            "qty": child.get("qty", 1),
            "rate": child.get("rate", 0),
            "uom": child.get("uom", "Nos"),
            "is_expandable": child.get("is_expandable", 0),
            "bom_created": 0,
            "allow_alternative_item": 1,
            "do_not_explode": 1,
            "stock_qty": 1,
            "conversion_factor": 1,
            "stock_uom": "Nos",
            "amount": child.get("amount", 0),
            "fg_item": child.get("fg_item", top_item),
            "fg_reference_id": item_map.get(child.get("fg_item", top_item)),
            # Use the parent_row_no already set by flattening.
            "parent_row_no": child.get("parent_row_no"),
        }
        items.append(child_item)

    bom_doc = frappe.get_doc({
        "doctype": "BOM Creator",
        "name": str(uuid.uuid4())[:10],
        "item_code": top_item,
        "item_name": top_item_name,
        "item_group": bom_json.get("item_group", "Demo Item Group"),
        "qty": bom_json.get("qty", 1),
        "uom": bom_json.get("uom", "Nos"),
        "rm_cost_as_per": "Valuation Rate",
        "company": bom_json.get("company", frappe.defaults.get_user_default("Company")),
        "default_warehouse": bom_json.get("default_warehouse", "Stores - ESOFT"),
        "currency": bom_json.get("currency", "INR"),
        "conversion_rate": 1,
        "items": items
    })

    bom_doc.insert(ignore_permissions=True)
    return bom_doc.name