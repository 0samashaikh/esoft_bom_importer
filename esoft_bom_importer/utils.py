from esoft_bom_importer.progress import set_progress
import pandas as pd
import frappe
from pathlib import Path
from erpnext import get_default_company
from frappe.utils import now
from datetime import datetime
from frappe.desk.treeview import get_all_nodes
from collections import defaultdict
import math

def create_bom_from_hierarchy(
    bom_structure, current_index, total_length, history, should_proceed=True
):
    item_code = bom_structure.get("item")
    index = bom_structure.get("index")
    is_last_itr = current_index + 1 == total_length,

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

    frappe.cache().delete_key("bom_importer_all_item_group_nodes")
    frappe.cache().delete_key("bom_importer_child_groups_of_POWDER")
    frappe.cache().delete_key("bom_importer_child_groups_of_RM")
    frappe.cache().delete_key("bom_importer_child_groups_of_SFI-CUST")
    frappe.cache().delete_key("bom_importer_child_groups_of_BO")
    frappe.cache().delete_key("bom_importer_child_groups_of_CO")
    frappe.cache().delete_key("bom_importer_child_groups_of_HW")

    for index, bom_structure in enumerate(bom_tree):
        is_last_itr = index == (total_length - 1)
        should_proceed = validate_bom_structure(bom_structure, history_doc, is_last_itr)
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
    final_product=None,
    should_proceed=True
):
    if not final_product:
        final_product = bom_structure.get("item")

    item_group = bom_structure.get("item_group")
    index = bom_structure.get("index")
    operations = bom_structure.get("operation")
    operations = operations.split("+")
    material = bom_structure.get("matl")

    if material:
        rm_groups = get_child_groups("RM", leaf_only=True)
        if not _validate_item_group(rm_groups, material):
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

    blank_item_group_rows = get_item_group_blank_rows(df)
    err = []

    if blank_item_group_rows:
        err.append(
            f"<li>The following rows are missing the <b>ITEM GROUP</b> value in the attached BOM Creator file:</li>\n{', '.join('Row '+str(row) for row in blank_item_group_rows)}"
        )
    if err:
        frappe.throw("<br /><br />".join(err))

def get_item_group_blank_rows(df):
    item_group = df["ITEM GROUP"].isna() | (df["ITEM GROUP"].astype(str).str.strip() == "")
    blank_item_group_rows = (df[item_group].index + 2).tolist()

    return blank_item_group_rows

def get_bom_tree_json(df):
    node_map = {}

    def clean(val):
        """Clean and convert a value to a string, handling NaN."""
        return str(val).strip() if pd.notna(val) else ""

    for idx, row in df.iterrows():
        sr_no = clean(row.get("SR NO"))
        if not sr_no:
            continue

        if sr_no in node_map:
            frappe.throw(f"Duplicate Sr. No '{sr_no}' in the spreadsheet at row {idx + 2}. Ensure 'SR NO' column is formatted as Text in Excel and read as string dtype.")

        item_name = clean(row.get("ITEM"))
        rev = clean(row.get("REV"))
        bo_groups = get_child_groups("BO")
        co_groups = get_child_groups("CO")
        hardware_groups = get_child_groups("HW")

        if not _validate_item_group(bo_groups + co_groups + hardware_groups, clean(row.get("ITEM GROUP"))):
            item_name = f"{item_name}_{rev or 0}"

        node = {
            "index": idx + 2,
            "item": item_name,
            "rev": rev or 0,
            "description": clean(row.get("PART DESCRIPTION")),
            "item_group": clean(row.get("ITEM GROUP")),
            "matl": clean(row.get("MATL")),
            "operation": clean(row.get("OPERATION")),
            "qty_per_set": clean(row.get("QTY/ SET")) or "1",
            "length": clean(row.get("LENGTH")) or 0,
            "width": clean(row.get("WIDTH")) or 0,
            "thickness": clean(row.get("THICKNESS")) or 0,
            "children": []
        }

        node_map[sr_no] = node
        powder_item_name = clean(row.get("POWDER COATING"))

        if powder_item_name:
            if not frappe.db.exists("Item", powder_item_name):
                frappe.throw(f"Powder Coating item '{powder_item_name}' does not exist in the system. Please create it before importing BOM.")

            powder_sr_no = f"{sr_no}.0"

            if powder_sr_no in node_map:
                frappe.throw(f"Duplicate Sr. No '{powder_sr_no}' generated for Powder Coating item. Please check your spreadsheet data.")

            powder_item = frappe.get_doc("Item", powder_item_name)

            powder_node = {
                "index": f"{idx + 2}",
                "item": powder_item_name,
                "description": "Powder Coating Material",
                "item_group": powder_item.item_group,
                "matl": "",
                "rev": clean(row.get("REV")),
                "operation": "Powder Coating",
                "qty_per_set": "1",
                "length":  0,
                "width":   0,
                "thickness":   0,
                "children": []
            }
            node_map[powder_sr_no] = powder_node

    map_children_to_parents(node_map)
    root_node = node_map.get("0")
    if root_node:
        return [root_node]
    else:
        frappe.throw("No root node with Sr. No '0' found in the spreadsheet.")

def get_parent_sr_no(sr_no):
    if sr_no == "0":
        return None
    parts = sr_no.split(".")
    if len(parts) == 1:
        return "0"
    else:
        return ".".join(parts[:-1])

def map_children_to_parents(node_map):
    for sr_no, node in node_map.items():
        parent_sr_no = get_parent_sr_no(sr_no)
        if parent_sr_no is None:
            continue

        parent_node = node_map.get(parent_sr_no)
        if not parent_node:
            frappe.throw(f"Parent Sr. No '{parent_sr_no}' not found for item '{node.get('item')}' with Sr. No '{sr_no}'")

        node["parent_id"] = parent_node["item"]
        parent_node["children"].append(node)


def get_fg_products(bom_tree):
    fg_products = [bom.get("item") for bom in bom_tree if bom.get("item")]
    if not fg_products:
        frappe.throw("No valid BOM structures found in the file.")

    return fg_products


def get_or_create_item(bom_structure):
    item_code = bom_structure.get("item")
    rev = bom_structure.get("rev")

    description = bom_structure.get("description") or item_code
    item_group = bom_structure.get("item_group")

    hsn_code =  frappe.db.get_value("Item Group",  get_item_group(item_group) , "gst_hsn_code",cache=True)
    uom =  frappe.db.get_value("Item Group",  get_item_group(item_group) , "custom_default_uom", cache=True) or "Nos"
    # uom = "KG" if _validate_item_group(powder_groups, bom_structure.get("item_group")) else "Nos"

    if frappe.db.exists("Item", item_code):
        return frappe.get_doc("Item", item_code)

    item_data = {
        "doctype": "Item",
        "item_code": item_code,
        "item_name": item_code,
        "description": description,
        "item_group": get_item_group(item_group),
        "custom_rev": rev or 0,
        "stock_uom": uom,
        "is_stock_item": 1 ,
        "gst_hsn_code": hsn_code,
        "custom_length": bom_structure.get("length", 0),
        "custom_width": bom_structure.get("width", 0),
        "custom_thickness": bom_structure.get("thickness", 0),
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
    item_group = frappe.db.exists("Item Group", group_name,cache=True)
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
    bom_data["custom_summary"] = summarize_item_group_summary(bom_data)
    bom_creator = frappe.get_doc(bom_data)

    bom_creator.insert(ignore_permissions=True)
    bom_creator.set_reference_id()  # Mandatory for BOM Creator Items to set fg_reference_id

    bom_creator.set("__unsaved", 1)
    bom_creator.save(ignore_permissions=True)

    frappe.db.commit()


def summarize_item_group_summary(bom_data):
    acc = defaultdict(lambda: [0.0, 0.0])
    powder_groups = get_child_groups("POWDER")

    for r in bom_data["items"]:
        grp = r["custom_material"]

        if not grp or _validate_item_group(powder_groups, grp) or r["include_in_summary"] != 1:
            continue

        key = (
            grp,
            r["custom_rangethickness"],
            r["custom_range"],
        )
        acc[key][0] += float(r.get("custom_blwt") or 0)
        acc[key][1] += float(r.get("custom_area_sqft")   or 0)

    result = []
    for (group, range_t, range_l), (w_sum, a_sum) in acc.items():
        result.append({
            "ig": group,
            "rt": range_t,
            "rl": range_l,
            "bw": round(w_sum, 3),
            "ar": round(a_sum, 3),
        })

    result.sort(key=lambda r: (r["ig"], r["rt"], r["rl"]))

    return result

# TODO - set proper parameter names for the function
def calculate_bom_creator_item_bl_wt(l, w, t, qty, density ):
    return round((l * w * t * qty * density) / 1000000, 3) if l and w and t and qty and density else 0.0
# TODO - set proper parameter names for the function
def calculate_bom_creator_item_area_sqft(l, w, qty):
    return round((l * w * qty * 2) / 92903.04, 3) if l and w and qty else 0.0

def get_sub_assembly(items, parent_index=None, parent_item_code=None, flat_list=None):

    if flat_list is None:
        flat_list = []

    powder_groups = get_child_groups("POWDER")
    sfi_groups = get_child_groups("SFI-CUST")

    for child in items:

        if _validate_item_group(sfi_groups, child.get("item_group")) and parent_item_code:
            original_code = child.get("item")
            child["item"] = f"{parent_item_code}-{original_code}"
        # else:
        #     original_code = child.get("item")
        #     child["item"] = f"{original_code}"

        it = get_or_create_item(child)

        #BUG : change fetch of density to material column
        # density = frappe.db.get_value("Item Group", it.item_group, "custom_density", cache=True) or 0.0
        operations = get_operations(child.get("operation"))
        operations = ", ".join(operations) if operations else ""
        qty=str(child.get("qty_per_set", 1))
        material = child.get("matl")
        include_in_summary, density = frappe.db.get_value(
            "Item Group",
            material,
            ("custom_include_in_summary", "custom_density"),
            cache=True
        ) or (0, 0.0)
        # include_in_summary = frappe.db.get_value("Item Group", material, "custom_include_in_summary", cache=True) or 0
        length = float(child.get("length"))
        width = float(child.get("width"))
        thickness = float(child.get("thickness"))
        bl_weight = calculate_bom_creator_item_bl_wt(
            length, width, thickness, float(qty), density
        )
        area_sq_ft = calculate_bom_creator_item_area_sqft(
            length, width, float(qty)
        )

        length_range = "Above 3 Mtrs" if length > 3000 else "Till 3 Mtrs"
        thickness_range = "Above 3 MM" if thickness > 3 else "Till 3 MM"
        uom = it.stock_uom

        item = {
            "doctype": "BOM Creator Item",
            "item_code": it.name,
            "item_name": it.item_name,
            "item_group": it.item_group,
            "include_in_summary": include_in_summary,
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
            "custom_previous_qty": qty,
            "is_expandable": 1 if child.get("children") else 0,
            "uom": uom,
            "fg_item": parent_item_code,  # Set parent item code directly
            "parent_row_no": parent_index + 1 if parent_index is not None else None,  # Use parent index
        }


        if _validate_item_group(powder_groups, item["item_group"]):
            if parent_index is not None:
                try:
                    parent = flat_list[parent_index]
                    item["qty"]= calculate_powder_item_qty(it, parent)
                except IndexError:
                    frappe.log_error(f"Bad parent_index {parent_index} for item {item['item_code']}")


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

def calculate_powder_item_qty(item, parent_item):
    coverage = float(item.get("custom_coverage_area") or 0)
    area = float(parent_item.get("custom_area_sqft") or 0)

    if not coverage or not area:
        return 0.1

    qty = area / coverage

    if 0 < qty < 0.001:
        return 0.001

    return math.ceil(qty * 1000) / 1000

def _validate_item_group(group_list, item_group):
    if item_group not in group_list:
        return False
    return True

def _clean_hierarchical_json(data, leaf_only, root="RM"):
    def collect_items(parent_key, leaf_only, data_map):
        collected = []
        children = data_map.get(parent_key, [])
        for item in children:
            if leaf_only:
                if item["expandable"]:
                    collected.extend(collect_items(item["value"], leaf_only, data_map))
                else:
                    collected.append(item["value"])
            else:
                collected.append(item["value"])
                if item["expandable"]:
                    collected.extend(collect_items(item["value"], leaf_only, data_map))
        return collected

    data_map = {entry["parent"]: entry["data"] for entry in data}

    return collect_items(root, leaf_only, data_map)

def get_all_item_group_nodes():

    cache_key = "bom_importer_all_item_group_nodes"
    nodes = frappe.cache().get_value(cache_key)

    if nodes is None:
        # Fetches all groups under the main "All Item Groups" root
        nodes = get_all_nodes("Item Group","All Item Groups", "All Item Groups", "frappe.desk.treeview.get_children")
        frappe.cache().set_value(cache_key, nodes, expires_in_sec=3600)

    return nodes

def get_child_groups(root_group, leaf_only=False):

    cache_key = f"bom_importer_child_groups_of_{root_group}"
    child_groups = frappe.cache().get_value(cache_key)

    if child_groups is None:
        all_nodes = get_all_item_group_nodes()
        child_groups = _clean_hierarchical_json(all_nodes, leaf_only, root=root_group)
        frappe.cache().set_value(cache_key, child_groups, expires_in_sec=3600)

    return child_groups
