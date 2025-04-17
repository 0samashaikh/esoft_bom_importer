// Copyright (c) 2025, shaikhosama504 and contributors
// For license information, please see license.txt

frappe.ui.form.on("BOM Creator Tool History", {
    refresh(frm) {
        addCustomButton(frm)
    },
});


function addCustomButton(frm) {
    frm.add_custom_button("BOM Creator Tool", () => {
        frappe.set_route("Form", "BOM Creator Tool")
    })

}