from esoft_bom_importer.handle_exception import log_exception
from esoft_bom_importer.progress import set_progress
import pandas as pd
import frappe
from pathlib import Path
from erpnext import get_default_company



def create_bom_from_hierarchy(bom_structure, current_index, total_length):
    # return
    """Create BOM Creator document from hierarchical structure"""
    if not bom_structure:
        return None

    item_code = bom_structure.get("item")
    parent_item = bom_structure.get("parent_item")
    description = bom_structure.get("description") or item_code
    item_group = bom_structure.get("matl")
    operations = bom_structure.get("operation")
    index = bom_structure.get("index")

    existing_name = frappe.db.exists("BOM Creator", {"item_code": item_code})
    if existing_name:
        existing_doc = frappe.get_doc("BOM Creator", existing_name)
        if existing_doc.docstatus == 0:
            frappe.delete_doc("BOM Creator", existing_name)
        else:
            # Skip if already submitted
            return None
    try:
        item = get_or_create_item(item_code, description, item_group, operations)
        create_bom_creator_document(bom_structure, item)

        progress = set_progress(current_index+1, total_length, "Import BOM Creator")
        doc = frappe.get_single("BOM Creator Tool")

        # ToDo:
        #  check if jobs are running then set Running state else Success

        if not doc.error:
            doc.status = "Success"
        else:
            doc.status = "Failed"
        
        if progress < 100:
            doc.status = "In Progress"

        doc.save()
    except Exception as e:
        traceback = frappe.get_traceback()
        # create Error Log entry for better debugging
        log_exception(
            title=f"Creation of {item_code} failed",
            error_obj={
                "reason": str(e),
                "row": index,
                "full_traceback": traceback,
            },
            reference_doctype="BOM Creator Tool",
        )

        # store last error here
        # ToDo: move it to new history doctype
        doc = frappe.get_single("BOM Creator Tool")
        doc.error = e
        doc.status = "Failed"
        doc.save()

def get_file_full_path(file):
    file_doc = frappe.get_doc("File", {"file_url": file})
    return file_doc.get_full_path()


def convert_spreadsheet_to_json(file: str) -> pd.DataFrame:
    file_path = get_file_full_path(file)
    ext = Path(file_path).suffix.lower()

    if ext == ".xlsx":
        df = pd.read_excel(file_path, engine="openpyxl", dtype=str)
    elif ext == ".csv":
        df = pd.read_csv(file_path, dtype=str)
    else:
        frappe.throw(f"Unsupported file format: {ext}")

    df = clean_dataframe(df)

    validate_matl_col(df)

    return get_bom_tree_json(df)


def clean_dataframe(dataframe):
    return dataframe.fillna("").map(lambda x: x.strip() if isinstance(x, str) else x)


def validate_matl_col(df):
    """Return row numbers with Parent present but MATL blank"""
    matl = df["MATL"].isna() | (df["MATL"].astype(str).str.strip() == "")
    blank_matl_rows = (df[matl].index + 2).tolist()

    frappe.throw(
        f"The following rows are missing the MATL value in the attached BOM Creator file:\n{', '.join('Row '+str(row) for row in blank_matl_rows)}"
    )


def get_bom_tree_json(df):
    """Build a hierarchical BOM structure from a DataFrame."""
    node_map = {}
    root_nodes = []

    def clean(val):
        return str(val).strip() if pd.notna(val) else ""

    for idx, row in df.iterrows():
        item_id = clean(row.get("Sub-Assembly")) or clean(row.get("SR NO"))
        if not item_id:
            continue

        node = {
            "index": idx + 2,
            "item": item_id,
            "rev": clean(row.get("REV")),
            "description": clean(row.get("PART DESCRIPTION")),
            "parent_item": clean(row.get("Parent")),
            "matl": clean(row.get("MATL")),
            "operation": clean(row.get("operation")),
            "den": clean(row.get("Den")),
            "qty_per_set": clean(row.get("QTY/ SET")) or "1",
            "length": clean(row.get("L")),
            "width": clean(row.get("W")),
            "thickness": clean(row.get("T")),
            "bl_weight": clean(row.get("BL.WT.")),
            "area_sq_ft": clean(row.get("AREA SQ.FT.")),
            "children": [],
        }

        node_map[item_id] = node
        parent_id = node["parent_item"]

        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node)
        else:
            root_nodes.append(node)

    return root_nodes


def get_bom_json(dataframe):
    """Build hierarchical BOM structure from DataFrame"""
    node_map = {}
    root_nodes = []

    for row_index, row_data in dataframe.iterrows():
        node = get_item_obj(row_data, row_index)
        if not node:
            continue

        node_map[node["item"]] = node
        parent_item = row_data.get("Parent", "").strip()

        if parent_item:
            add_node_to_parent(parent_item, node, node_map, root_nodes)
        else:
            root_nodes.append(node)

    return root_nodes


def get_item_obj(row_data, row_index):
    """Create a BOM node from DataFrame row"""
    sub_assembly = row_data.get("Sub-Assembly", "").strip()
    sr_no = row_data.get("SR NO", "").strip()
    item_id = sub_assembly or sr_no

    if not item_id:
        return None

    return {
        "row": row_index + 2,
        "item": item_id,
        "rev": row_data.get("REV", "").strip(),
        "description": row_data.get("PART DESCRIPTION", "").strip(),
        "parent_item": row_data.get("Parent", "").strip(),
        "matl": row_data.get("MATL", "").strip(),
        "operation": row_data.get("operation", "").strip(),
        "den": row_data.get("Den", "").strip(),
        "qty_per_set": row_data.get("QTY/ SET", "1").strip(),
        "length": row_data.get("L", "").strip(),
        "width": row_data.get("W", "").strip(),
        "thickness": row_data.get("T", "").strip(),
        "bl_weight": row_data.get("BL.WT.", "").strip(),
        "area_sq_ft": row_data.get("AREA SQ.FT.", "").strip(),
        "children": [],
    }


def add_node_to_parent(parent_item, node, node_map, root_nodes):
    """Add node to its parent or root if parent not found"""
    parent_node = node_map.get(parent_item)
    if parent_node:
        parent_node["children"].append(node)
    else:
        root_nodes.append(node)


def get_fg_products(bom_tree):
    fg_products = [bom.get("item") for bom in bom_tree if bom.get("item")]
    if not fg_products:
        frappe.throw("No valid BOM structures found in the file.")

    return fg_products


def get_or_create_item(item_code, description="", item_group="", operations=""):
    if frappe.db.exists("Item", item_code):
        return frappe.get_doc("Item", item_code)

    # ToDo: add these opetions in item child table
    operations = get_operations(operations)

    item_data = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "description": description,
        "item_group": get_item_group(item_group),
        "stock_uom": "Nos",
        "is_stock_item": 0,
    }

    item = frappe.get_doc(item_data).insert(ignore_permissions=True)
    return item


def get_operations(operations):
    if not operations:
        return None
    
    operations = operations.split("+")
    
    for operation in operations:
        operation = operation.strip()
        if operation and not frappe.db.exists("Operation", operation):
            frappe.throw(
                f"Operation Master {operation} does not exist in the system. Please create it before importing BOM"
            )
    return operations


def get_item_group(group_name):
    item_group = frappe.db.exists("Item Group", group_name)
    if not item_group:
        frappe.throw(
            f"Item Group Master {group_name} does not exist in the system. Please create it before importing BOM."
        )

    return item_group


def create_bom_creator_document(bom_structure, item):
    """Create complete BOM Creator document with all required fields"""
    company = get_default_company()
    bom_data = {
        "doctype": "BOM Creator",
        "item_code": item.name,
        "item_name": item.description,
        "qty": 1,
        "uom": "Nos",
        "company": company,
        "status": "Draft",
        "items": get_sub_assembly(bom_structure.get("children", []), bom_structure),
        "__newname": item.name,
    }

    bom_creator = frappe.get_doc(bom_data)
    bom_creator.insert(ignore_permissions=True)
    frappe.db.commit()


def get_sub_assembly(items, parent_item=None, flat_list=None):
    if flat_list is None:
        flat_list = []

    for child in items:
        it = get_or_create_item(
            child.get("item"),
            child.get("description"),
            child.get("matl"),
            child.get("operation"),
        )
        item = {
            "doctype": "BOM Creator Item",
            "item_code": it.name,
            "item_name": it.item_name,
            "description": it.description,
            "qty": str(child.get("qty_per_set", 1)),
            "is_expandable": 1 if child.get("children") else 0,
            "fg_item": parent_item["item"] if parent_item else None,
            "parent_row_no": None,
        }

        # Add to flat list
        flat_list.append(item)

        # Set parent_row_no by finding index in flat_list
        if parent_item:
            item["parent_row_no"] = next(
                (
                    i + 1
                    for i, obj in enumerate(flat_list)
                    if obj.get("item_code") == parent_item["item"]
                ),
                None,
            )

        # Recurse if there are children
        if child.get("children"):
            get_sub_assembly(child["children"], parent_item=child, flat_list=flat_list)

    return flat_list
