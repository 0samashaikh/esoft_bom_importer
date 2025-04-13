// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Tool", {
    refresh(frm) {
        frm.add_custom_button(__('Start Process'), function() {
            frappe.call({
                method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.get_bom_preview',
                args: { docname: frm.doc.name },
                callback(r) {
                    if (r.message) {
                        const bom_list = r.message;
                        let message = __('The following BOMs will be created:') + '<br><ul>';
                        
                        bom_list.forEach(bom => {
                            message += `<li>${bom}</li>`;
                        });
                        
                        message += '</ul>' + __('Do you want to proceed?');
                        
                        frappe.confirm(
                            message,
                            () => { // Yes
                                frappe.call({
                                    method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.enqueue_bom_processing',
                                    args: { docname: frm.doc.name },
                                    callback(r) {
                                        if (r.message.status === 'exists') {
                                            frappe.msgprint(__('A job is already running for this document.'));
                                        } else {
                                            frappe.msgprint(__('BOM creation started successfully. Check background jobs for progress.'));
                                        }
                                    }
                                });
                            },
                            () => { // No
                                frappe.msgprint(__('BOM creation cancelled.'));
                            }
                        );
                    }
                }
            });
        });
    }
});
