// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Tool", {
    refresh(frm) {
        addBomImportButton(frm);
    }
});

/**
 * Adds the Import BOM Creator button to the form
 * @param {object} frm - The current form instance
 */
function addBomImportButton(frm) {
    frm.add_custom_button(('Import BOM Creator'), () => handleBomImport(frm));
}

/**
 * Handles the BOM import process flow
 * @param {object} frm - The current form instance
 */
function handleBomImport(frm) {
    fetchBomPreview(frm).then(bomList => {
        showConfirmationDialog(bomList, frm);
    });
}

/**
 * Fetches BOM preview data from the server
 * @param {object} frm - The current form instance
 * @returns {Promise<Array>} - Promise resolving to BOM list
 */
function fetchBomPreview(frm) {
    return new Promise((resolve) => {
        frappe.call({
            method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.get_bom_preview',
            args: { docname: frm.doc.name },
            callback(response) {
                resolve(response.message || []);
            }
        });
    });
}

/**
 * Shows confirmation dialog with BOM list
 * @param {Array<string>} bomList - List of BOMs to be created
 * @param {object} frm - The current form instance
 */
function showConfirmationDialog(bomList, frm) {
    const dialogContent = {
        title: ('Confirm BOM Creation'),
        message: buildBomListMessage(bomList),
        primary_action_label: ('Proceed'),
        primary_action: () => processBomCreation(frm),
        secondary_action_label: ('Cancel'),
        secondary_action: () => showCancellationMessage()
    };

    frappe.confirm(
        dialogContent.message,
        dialogContent.primary_action,
        dialogContent.secondary_action,
        dialogContent.title,
        [dialogContent.primary_action_label, dialogContent.secondary_action_label]
    );
}

/**
 * Builds HTML message listing BOMs to be created
 * @param {Array<string>} bomList - List of BOM names
 * @returns {string} Formatted HTML message
 */
function buildBomListMessage(bomList) {
    const bomItems = bomList.map(bom => `<li>${bom}</li>`).join('');
    return `
        ${('The following finished goods BOMs will be created:')}
        <br><ul>${bomItems}</ul>
        ${('Do you want to proceed?')}
    `;
}

/**
 * Initiates BOM creation process
 * @param {object} frm - The current form instance
 */
function processBomCreation(frm) {
    frappe.call({
        method: 'esoft_bom_importer.esoft_bom_importer.doctype.bom_creator_tool.bom_creator_tool.enqueue_bom_processing',
        args: { docname: frm.doc.name },
        callback(response) {
            handleBomProcessingResponse(response.message);
        }
    });
}

/**
 * Handles response from BOM processing request
 * @param {object} result - Server response
 */
function handleBomProcessingResponse(result) {
    if (result.status === 'exists') {
        frappe.msgprint('A job is already running for this document.');
    } else {
        frappe.msgprint('BOM creation started successfully. Check background jobs for progress.');
    }
}

/**
 * Shows cancellation message to user
 */
function showCancellationMessage() {
    frappe.msgprint('BOM creation cancelled.');
}