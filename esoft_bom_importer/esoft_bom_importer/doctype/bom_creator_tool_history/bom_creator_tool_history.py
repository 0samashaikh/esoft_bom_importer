# Copyright (c) 2025, shaikhosama504 and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from esoft_bom_importer.validator import is_migration_jobs_queued


class BOMCreatorToolHistory(Document):
    def onload(self):
        self.update_seen_status()

    def update_seen_status(self):
        # skip updating db if job is running to avoid db bottleneck
        if is_migration_jobs_queued() or self.job_status in ["Validating", "In Progress"]:
            return

        if not self.seen:
            self.db_set("seen", 1, update_modified=0)
            frappe.db.commit()
