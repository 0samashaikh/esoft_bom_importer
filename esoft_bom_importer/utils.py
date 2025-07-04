from esoft_bom_importer.progress import set_progress
import pandas as pd
import frappe
from pathlib import Path
from erpnext import get_default_company
from frappe.utils import now
from datetime import datetime
from frappe.desk.treeview import get_all_nodes

def create_bom_from_hierarchy(
    bom_structure, current_index, total_length, history, should_proceed=True
):
    item_code = bom_structure.get("item")
    index = bom_structure.get("index")
    is_last_itr = current_index + 1 == total_length

    update_bom_creator_tool_status(history, "In Progress")

    if should_proceed:
        existing_name = frappe.db.exists("BOM Creator", {"item_code": item_code})
        if existing_name:
            existing_doc = frappe.get_doc("BOM Creator", existing_name)
            if existing_doc.docstatus == 0:
                frappe.delete_doc("BOM Creator", existing_name)
            else:
                # Skip if already submitted
                return None

        try:
            create_bom_creator_document(bom_structure)
        except Exception as e:
            traceback = frappe.get_traceback()
            histoy_doc = frappe.get_doc("BOM Creator Tool History", history)
            histoy_doc.append(
                "error_logs",
                {
                    "error": str(e),
                    "final_product": item_code,
                    "row_number": int(index),
                    "failed_while": "Running",
                    "full_traceback": traceback,
                },
            )
            histoy_doc.save()

    set_progress(current_index + 1, total_length, "Import BOM Creator")

    if is_last_itr:
        update_bom_creation_tool_history(history)


def update_bom_creation_tool_history(history):
    status = "Success"

    # set Failed if entry is found in log child table
    if frappe.db.exists("BOM Creator History Log", {"parent": history}):
        status = "Failed"

    update_bom_creator_tool_status(history, status)

    completed_at = now()
    completed_at_parsed = datetime.strptime(completed_at, "%Y-%m-%d %H:%M:%S.%f")
    started_at = frappe.db.get_value("BOM Creator Tool History", history, "started_at")
    diff = completed_at_parsed - started_at
    diff = round(diff.total_seconds() / 60)

    frappe.db.set_value(
        "BOM Creator Tool History",
        history,
        {"completed_at": now(), "time_taken": str(diff)},
    )


def update_bom_creator_tool_status(history, status):
    frappe.db.set_single_value("BOM Creator Tool", "status", status)
    frappe.db.set_value("BOM Creator Tool History", history, "job_status", status)


def validate_and_enqueue_bom_creation(bom_tree, history):
    total_length = len(bom_tree)
    history_doc = frappe.get_doc("BOM Creator Tool History", history)
    nodes = get_all_nodes("Item Group", "RM", "RM", "frappe.desk.treeview.get_children")
    rm_groups =  clean_hierarchical_json(nodes, root="RM")

    for index, bom_structure in enumerate(bom_tree):
        is_last_itr = index == (total_length - 1)
        should_proceed = validate_bom_structure(bom_structure, history_doc, is_last_itr, rm_groups)
        frappe.enqueue(
            method=create_bom_from_hierarchy,
            queue="long",
            job_name="bom_creator_job",
            bom_structure=bom_structure,
            current_index=index,
            total_length=total_length,
            history=history,
            should_proceed=should_proceed,
        )

    history_doc.save()


def validate_bom_structure(
    bom_structure,
    history_doc,
    is_last_itr,
    rm_groups,
    final_product=None,
    should_proceed=True
):
    if not final_product:
        final_product = bom_structure.get("item")

    item_group = bom_structure.get("item_group")
    index = bom_structure.get("index")
    operations = bom_structure.get("operation")
    operations = operations.split("+")
    hsn_code = bom_structure.get("hsn_code")
    material = bom_structure.get("matl")
    uom = bom_structure.get("uom")

    if material:
        if not validate_material_group_in_rm_list(rm_groups, material):
            err = (
                f"Material: '{material}' is not under the allowed RM hierarchy. "
                f"Please ensure it belongs to the RM or its sub-groups."
            )
            history_doc.append(
                "error_logs",
                {
                    "error": err,
                    "final_product": final_product,
                    "row_number": int(index),
                    "failed_while": "Validating",
                },
            )
            should_proceed = False

    if not frappe.db.exists("Item Group", item_group):
        err = f"Item Group {item_group} does not exist in the system. Please create it before importing BOM."
        history_doc.append(
            "error_logs",
            {
                "error": err,
                "final_product": final_product,
                "row_number": int(index),
                "failed_while": "Validating",
            },
        )
        should_proceed = False

    if not frappe.db.exists("GST HSN Code", hsn_code):
        err = f"GST HSN Code {hsn_code} does not exist in the system. Please create it before importing BOM."
        history_doc.append(
            "error_logs",
            {
                "error": err,
                "final_product": final_product,
                "row_number": int(index),
                "failed_while": "Validating",
            },
        )
        should_proceed = False

    if not frappe.db.exists("UOM", uom):
        err = f"UOM '{uom}' does not exist in the system. Please create it before importing BOM."
        history_doc.append(
            "error_logs",
            {
                "error": err,
                "final_product": final_product,
                "row_number": int(index),
                "failed_while": "Validating",
            },
        )
        should_proceed = False

    for operation in operations:
        operation = operation.strip()

        if operation and not frappe.db.exists("Operation", operation):
            err = f"Operation {operation} does not exist in the system. Please create it before importing BOM."
            history_doc.append(
                "error_logs",
                {
                    "error": err,
                    "final_product": final_product,
                    "row_number": int(index),
                    "failed_while": "Validating",
                },
            )
            should_proceed = False

    for child in bom_structure.get("children", []):
        is_valid_child = validate_bom_structure(
            bom_structure=child,
            history_doc=history_doc,
            is_last_itr=is_last_itr,
            rm_groups=rm_groups,
            should_proceed=should_proceed,
            final_product=final_product,
        )

        # once its false, it will not be true again
        should_proceed &= is_valid_child

    return should_proceed


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

    validate_mandatory_cols(df)

    return get_bom_tree_json(df)


def clean_dataframe(dataframe):
    return dataframe.fillna("").map(lambda x: x.strip() if isinstance(x, str) else x)


def validate_mandatory_cols(df):

    blank_hsn_rows = get_hsn_blank_rows(df)
    blank_item_group_rows = get_item_group_blank_rows(df)
    uom_errors = get_invalid_uom_rows(df)
    err = []

    if uom_errors:
        err.append(
            "<b>UOM Validation Failed</b><br><br>"
            "The following rows have invalid UOM usage:<br><ul>"
            "<li><b>Powder Item Group</b> should use UOM = <code>KG</code>.</li>"
            "<li>If UOM = <code>Nos</code>, then quantity must be a whole number (no decimals).</li>"
            "</ul>"
            f"<br>Affected Rows: {', '.join('Row ' + str(row) for row in uom_errors)}"
        )

    if blank_hsn_rows:
        err.append(
            f"<li>The following rows are missing the <b>HSN/SAC</b> value in the attached BOM Creator file:</li>\n{', '.join('Row '+str(row) for row in blank_hsn_rows)}"
        )

    if blank_item_group_rows:
        err.append(
            f"<li>The following rows are missing the <b>ITEM GROUP</b> value in the attached BOM Creator file:</li>\n{', '.join('Row '+str(row) for row in blank_item_group_rows)}"
        )
    if err:
        frappe.throw("<br /><br />".join(err))


def get_hsn_blank_rows(df):
    matl = df["HSN/SAC"].isna() | (df["HSN/SAC"].astype(str).str.strip() == "")
    blank_hsn_rows = (df[matl].index + 2).tolist()

    return blank_hsn_rows

def get_item_group_blank_rows(df):
    item_group = df["ITEM GROUP"].isna() | (df["ITEM GROUP"].astype(str).str.strip() == "")
    blank_item_group_rows = (df[item_group].index + 2).tolist()

    return blank_item_group_rows

def get_invalid_uom_rows(df):
    bad_rows = []

    for idx, row in df.iterrows():
        item_group = str(row.get("ITEM GROUP", "")).strip().lower()
        uom = str(row.get("UOM", "")).strip().lower()
        qty = row.get("QTY/ SET", 0)

        if "powder" in item_group and uom != "kg":
            bad_rows.append(idx + 2)
            continue

        try:
            qty = float(qty)
            if uom == "nos" and not qty.is_integer():
                bad_rows.append(idx + 2)
        except (ValueError, TypeError):
            bad_rows.append(idx + 2)

    return bad_rows


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
            "item_group": clean(row.get("ITEM GROUP")),
            "operation": clean(row.get("operation")),
            "den": clean(row.get("Den")),
            "qty_per_set": clean(row.get("QTY/ SET")) or "1",
            "length": clean(row.get("L")) or 0,
            "width": clean(row.get("W")) or 0,
            "thickness": clean(row.get("T")) or 0,
            "bl_weight": clean(row.get("BL.WT.")) or 0,
            "area_sq_ft": clean(row.get("AREA SQ.FT.")) or 0,
            "hsn_code": clean(row.get("HSN/SAC")),
            "uom": clean(row.get("UOM")) or "Nos",
            "children": [],
        }

        node_map[item_id] = node
        parent_id = node["parent_item"]

        if parent_id and parent_id in node_map:
            node_map[parent_id]["children"].append(node)
        else:
            root_nodes.append(node)

    return root_nodes


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


def get_or_create_item(bom_structure):
    item_code = bom_structure.get("item")
    description = bom_structure.get("description") or item_code
    item_group = bom_structure.get("item_group")
    hsn_code = bom_structure.get("hsn_code")
    rev = bom_structure.get("rev") or 0
    uom = bom_structure.get("uom") or "Nos"

    if frappe.db.exists("Item", item_code):
        return frappe.get_doc("Item", item_code)

    item_data = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "description": description,
        "item_group": get_item_group(item_group),
        "custom_rev": rev,
        "stock_uom": uom,
        "is_stock_item": 1 ,
        "gst_hsn_code": get_gst_hsn_code(hsn_code),
    }

    item = frappe.get_doc(item_data).insert(ignore_permissions=True)
    return item


def get_gst_hsn_code(hsn_code):
    hsn_code = frappe.db.exists("GST HSN Code", hsn_code)
    if not hsn_code:
        frappe.throw(
            f"GST HSN Code {hsn_code} does not exist in the system. Please create it before importing BOM."
        )

    return hsn_code


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


def create_bom_creator_document(bom_structure):
    """Create complete BOM Creator document with all required fields"""
    item = get_or_create_item(bom_structure)
    company = get_default_company()

    root_item_code = bom_structure.get("item")

    bom_data = {
        "doctype": "BOM Creator",
        "item_code": item.name,
        "item_name": item.description,
        "qty": 1,
        "uom": item.stock_uom,
        "company": company,
        "status": "Draft",
        "items": get_sub_assembly(
            bom_structure.get("children", []),
            parent_index=None,
            parent_item_code=root_item_code,
            flat_list=None
        ),
        "__newname": item.name,
    }

    bom_creator = frappe.get_doc(bom_data)

    bom_creator.insert(ignore_permissions=True)
    bom_creator.set_reference_id()  # Mandatory for BOM Creator Items to set fg_reference_id

    bom_creator.set("__unsaved", 1)
    bom_creator.save(ignore_permissions=True)

    frappe.db.commit()

def get_sub_assembly(items, parent_index=None, parent_item_code=None, flat_list=None):
    if flat_list is None:
        flat_list = []

    for child in items:
        it = get_or_create_item(child)
        operations = get_operations(child.get("operation"))
        operations = ", ".join(operations) if operations else ""
        qty=str(child.get("qty_per_set", 1))
        material = child.get("matl")
        length = float(child.get("length"))
        width = float(child.get("width"))
        thickness = float(child.get("thickness"))
        bl_weight = float(child.get("bl_weight"))
        area_sq_ft = float(child.get("area_sq_ft"))
        length_range = "Above 3 Mtrs" if length > 3000 else "Till 3 Mtrs"
        thickness_range = "Above 3 MM" if thickness > 3 else "Till 3 MM"
        uom = it.stock_uom

        item = {
            "doctype": "BOM Creator Item",
            "item_code": it.name,
            "item_name": it.item_name,
            "item_group": it.item_group,
            "custom_fg_name": it.item_name,
            "description": it.description,
            "qty": qty,
            "custom_msf": operations,
            "custom_material": material,
            "custom_length": length,
            "custom_width": width,
            "custom_thickness": thickness,
            "custom_blwt": bl_weight,
            "custom_area_sqft": area_sq_ft,
            "custom_range": length_range,
            "custom_rangethickness": thickness_range,
            "is_expandable": 1 if child.get("children") else 0,
            "uom": uom,
            "fg_item": parent_item_code,  # Set parent item code directly
            "parent_row_no": parent_index + 1 if parent_index is not None else None,  # Use parent index
        }

        # Append to flat list
        flat_list.append(item)
        current_index = len(flat_list) - 1  # Current item's index in the list

        # Recurse for children, passing current index and item code
        if child.get("children"):
            get_sub_assembly(
                child["children"],
                parent_index=current_index,
                parent_item_code=it.name,
                flat_list=flat_list,
            )

    return flat_list

def validate_material_group_in_rm_list(rm_group_list, material_group):
    if material_group not in rm_group_list:
        return False
    return True

def clean_hierarchical_json(data, root="RM"):
    def collect_items(parent_key, data_map):
        collected = []
        children = data_map.get(parent_key, [])
        for item in children:
            collected.append(item["value"])
            if item["expandable"]:
                collected.extend(collect_items(item["value"], data_map))
        return collected

    data_map = {entry["parent"]: entry["data"] for entry in data}

    return collect_items(root, data_map)
