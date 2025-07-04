from collections import defaultdict
from erpnext.manufacturing.doctype.bom_creator.bom_creator import BOMCreator
import frappe

class BomCreator(BOMCreator):

    def set_is_expandable(self):
        children_map = defaultdict(list)

        for row in self.items:
            if row.parent_row_no:
                children_map[frappe.cint(row.parent_row_no)].append(row)

        for row in self.items:
            row.is_expandable = 1 if children_map.get(row.idx) else 0
