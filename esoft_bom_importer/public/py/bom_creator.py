from collections import defaultdict
from erpnext.manufacturing.doctype.bom_creator.bom_creator import BOMCreator
import frappe

class BomCreator(BOMCreator):

    def set_is_expandable(self):
        if self.flags.get("skip_set_is_expandable_for_bom_creator"):
            return

        super().set_is_expandable()
