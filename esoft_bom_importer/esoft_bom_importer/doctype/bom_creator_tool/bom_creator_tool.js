// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Tool", {
    refresh(frm) {
        frm.add_custom_button(('Import BOM Creator'), () => handleImportClick(frm));
    }
});

// Main click handler
function handleImportClick(frm) {
    frappe.call({
        method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.validate_and_get_fg_products',
        args: { docname: frm.doc.name },
        callback: (response) => {
            const bomList = response.message || [];
            if (bomList.length === 0) return;

            showConfirmationDialog(bomList, frm);
        }
    });
}

// Confirmation dialog management
function showConfirmationDialog(bomList, frm) {
    const message = `
        ${('The following finished goods BOMs will be created:')}
        <br><ul>${bomList.map(bom => `<li>${bom}</li>`).join('')}</ul>
        ${('Do you want to proceed?')}
    `;

    frappe.confirm(
        message,
        () => initiateBomCreation(frm),  // Proceed
        () => frappe.msgprint(('BOM creation cancelled.')),  // Cancel
        ('Confirm BOM Creation'),
        [('Proceed'), ('Cancel')]
    );
}

// BOM creation server call
function initiateBomCreation(frm) {
    frappe.call({
        method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.import_bom_creator',
        args: { docname: frm.doc.name },
        callback: (response) => {
            const result = response.message;
            const msg = result.status === 'exists'
                ? ('A job is already running for this document.')
                : ('BOM creation started successfully. Check background jobs for progress.');

            frappe.msgprint(msg);
        }
    });
}