frappe.ui.form.on('Purchase Invoice', {
    refresh: function(frm) {        
        // Check company country and hide/show fields
        update_field_visibility(frm);
        
        // Add ZATCA button if conditions are met
        if (frm.doc.docstatus === 1 && !["CLEARED", "REPORTED"].includes(frm.doc.custom_zatca_status)) {
            frappe.db.get_value("Company", frm.doc.company, "country", (r) => {
                if (r.country === "Saudi Arabia") {
                    frm.add_custom_button(__("Send Invoice to Zatca"), function() {
                        frm.call({
                            method: "zatca_erpgulf.zatca_erpgulf.our_purchase_invoice.zatca_background",
                            args: {
                                "invoice_number": frm.doc.name,
                                "source_doc": frm.doc
                            },
                            callback: function(r) {
                                frm.reload_doc();
                            }
                        });
                    }, __("Zatca Phase-2"));
                }
            });
        }
    },
    
    company: function(frm) {
        update_field_visibility(frm);
    }   
});

// Common function to update field visibility based on company country
function update_field_visibility(frm) {
    if (!frm.doc.company) {
        // If no company selected, hide all fields
        hide_zatca_fields(frm);
        return;
    }
    
    frappe.db.get_value("Company", frm.doc.company, "country", (r) => {
        if (r.country === "Saudi Arabia") {
            show_zatca_fields(frm);
        } else {
            hide_zatca_fields(frm);
        }
    });
}
function hide_zatca_fields(frm) {
    const fields_to_hide = [
        'custom_zatca_third_party_invoice',
        'custom_zatca_nominal_invoice',
        'custom_zatca_export_invoice',
        'custom_summary_invoice',
        'custom_self_billed_invoice',
        'custom_zatca_status',
        'custom_zatca_tax_category',
        'custom_exemption_reason_code',
        'custom_zatca_discount_reason_code',
        'custom_zatca_discount_reason',
        'custom_submit_line_item_discount_to_zatca'
    ];
    
    fields_to_hide.forEach(field => {
        frm.set_df_property(field, 'hidden', 1);
    });
    
    $('a[data-fieldname="custom_offlineintegrations"]').hide();
}

function show_zatca_fields(frm) {
    const fields_to_show = [
        'custom_zatca_third_party_invoice',
        'custom_zatca_nominal_invoice',
        'custom_zatca_export_invoice',
        'custom_summary_invoice',
        'custom_self_billed_invoice',
        'custom_zatca_status',
        'custom_zatca_tax_category',
        'custom_exemption_reason_code',
        'custom_zatca_discount_reason_code',
        'custom_zatca_discount_reason',
        'custom_submit_line_item_discount_to_zatca',
        'custom_offlineintegrations'
    ];
    
    fields_to_show.forEach(field => {
        frm.set_df_property(field, 'hidden', 0);
    });
    
    $('a[data-fieldname="custom_offlineintegrations"]').show();
}