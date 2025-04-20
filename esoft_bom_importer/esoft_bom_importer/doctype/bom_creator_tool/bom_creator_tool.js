// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Tool", {
    refresh(frm) {
        addCustomButtons(frm)
    },
    
    bom_creator_history(frm) {
        redirect_to_bom_history(frm)
    },

    bom_creator(frm){
        frm.set_value("status", "")
        
    }
});

function redirect_to_bom_history(frm) {
    frappe.route_options = {
        job_name: "bom_creator_job",
        file: frm.doc.bom_creator,
        job_status: "Failed"
    };
    frappe.set_route("List", "BOM Creator Tool History");
}

function addCustomButtons(frm) {
    addImportButton(frm)
    addProgressButton(frm)
}

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

function initiateBomCreation(frm) {
    frappe.call({
        method: 'esoft_bom_importer.api.import_bom_creator',
        args: { filename: frm.doc.bom_creator },
        freeze: true,
        freeze_message: "Processing file, please wait...",
        callback: (response) => {
            const msg = ('BOM creation started successfully. Please wait while its being created.');
            frappe.show_alert(msg);
            setTimeout(() => {
                frm.reload_doc()
            }, 2000)
        }
    });
}


function addImportButton(frm) {
    frm.add_custom_button(('Import BOM Creator'), () => {
        frappe.call({
            method: 'esoft_bom_importer.api.validate_and_get_fg_products',
            args: { file: frm.doc.bom_creator },
            callback: (response) => {
                const bomList = response.message || [];
                if (bomList.length === 0) return;

                showConfirmationDialog(bomList, frm);
            }
        });
    })
}

function addProgressButton(frm) {
    function showProgress() {
        frappe.call({
            method: 'esoft_bom_importer.progress.get_import_progress',
            freeze: true,
            callback: res => {
                frm.set_intro('');
                if (res.message.progress) {
                    const color = res.message?.progress?.includes('100')
                        ? 'green'
                        : 'orange';
                    let message = res.message.job ? `${res.message.job}: ` : '';
                    message += res.message.progress;
                    frm.set_intro(message, color);
                } else {
                    frm.set_intro('No Import Jobs running', 'blue');
                }
            },
        });
    }

    showProgress();

    frm.add_custom_button('Get Progress', () => {
        showProgress();
    });
}

