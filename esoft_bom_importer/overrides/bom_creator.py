import frappe

def before_save(self, method=None):
    validate_row_uoms(self)

def before_submit(self, method=None):
    validate_row_uoms(self)

def validate_row_uoms(doc):
    errors = []

    for row in doc.items:
        if row.uom == "Nos":
            try:
                if not float(row.qty).is_integer():
                    errors.append(row.idx)
            except (ValueError, TypeError):
                frappe.throw(f"Row {row.idx}: Quantity is invalid.")
    if errors:
        frappe.throw(f"""Rows with non-integer quantities when UOM is 'Nos':
                     {', '.join(map(str, errors))}.
                     Please change the UOM in the Item master for the given rows.""")
