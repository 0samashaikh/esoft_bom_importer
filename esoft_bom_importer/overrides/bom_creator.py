import frappe
from frappe.utils import flt

def validate(self, method=None):
    validate_row_uoms(self)

def validate_row_uoms(doc):
    problematic_rows = []
    uom_cache = {}

    for row in doc.items:
        uom_name = row.uom

        if uom_name not in uom_cache:
            must_be_whole_number = frappe.db.get_value("UOM", uom_name, "must_be_whole_number")
            uom_cache[uom_name] = must_be_whole_number
        else:
            must_be_whole_number = uom_cache[uom_name]

        must_be_whole_number = bool(must_be_whole_number)

        if must_be_whole_number:
            try:
                quantity = flt(row.qty)
                if not quantity.is_integer():
                    problematic_rows.append(row.idx)
            except (ValueError, TypeError):
                frappe.throw(f"Row {row.idx}: Quantity '{row.qty}' is invalid. Please enter a valid number.")

    if problematic_rows:
        problematic_rows.sort()
        row_numbers_str = ', '.join(map(str, problematic_rows))
        frappe.throw(f"""The following rows have non-whole number quantities for UOMs that require whole numbers:
                     {row_numbers_str}.
                     Please adjust the quantities to whole numbers, or change the UOM in the Item Master if decimals are allowed.""")
