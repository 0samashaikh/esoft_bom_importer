// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Import Tool", {
    refresh(frm) {
        frm.add_custom_button(__('Start Process'), function () {
            frappe.call({
                method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_import_tool.bom_creator_import_tool.process_file',
                args: {
                    docname: frm.doc.name
                },
                callback(r) {
                    if (r.message) {
                        console.log(r.message);
                        frappe.msgprint(__('Import has been started successfully.'));
                    }
                },
            });
        });
    }
});
