function applyTooltips(context, fieldsWithTooltips) {
    fieldsWithTooltips.forEach((field) => {
        let fieldContainer;
        if (context.fields_dict?.[field.fieldname]) {
            fieldContainer = context.fields_dict[field.fieldname];
        }
        else if (context.dialog?.fields_dict?.[field.fieldname]) {
            fieldContainer = context.dialog.fields_dict[field.fieldname];
        }
        else if (context.page) {
            fieldContainer = $(context.page).find(`[data-fieldname="${field.fieldname}"]`).closest('.frappe-control');
        }
        if (!fieldContainer) {
            console.error(`Field '${field.fieldname}' not found in the provided context.`);
            return;
        }
        const fieldWrapper = fieldContainer.$wrapper || $(fieldContainer); // Handle both Doctype/Dialog and Page contexts
        if (!fieldWrapper || fieldWrapper.length === 0) {
            console.error(`Field wrapper for '${field.fieldname}' not found.`);
            return;
        }
        let labelElement;
        if (fieldWrapper.find('label').length > 0) {
            labelElement = fieldWrapper.find('label').first();
        } else if (fieldWrapper.find('.control-label').length > 0) {
            labelElement = fieldWrapper.find('.control-label').first();
        }
        if (!labelElement && (context.dialog || context.page)) {
            labelElement = fieldWrapper.find('.form-control').first();
        }

        if (!labelElement || labelElement.length === 0) {
            console.error(`Label for field '${field.fieldname}' not found.`);
            return;
        }
        const tooltipContainer = labelElement.next('.tooltip-container');
        if (tooltipContainer.length === 0) {
            const tooltip = new Tooltip({
                containerClass: "tooltip-container",
                tooltipClass: "custom-tooltip",
                iconClass: "info-icon",
                text: field.text,
                links: field.links,
            });
            tooltip.renderTooltip(labelElement[0]);
        }
    });
}
frappe.realtime.on('hide_gif', () => {
    $('#custom-gif-overlay').remove();
});

frappe.realtime.on('show_gif', (data) => {
    const gifHtml = `
        <div id="custom-gif-overlay" style="
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255, 255, 255, 0.8);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 1050;">
            <img src="${data.gif_url}" alt="Loading..." style="width: 100px; height: 100px;">
        </div>`;
    $('body').append(gifHtml);
});

// Listen for the event to hide the GIF
frappe.realtime.on('hide_gif', () => {
    $('#custom-gif-overlay').remove();
});

frappe.ui.form.on("Sales Invoice", {
    refresh: function (frm) {        
        update_field_visibility(frm);

        if (frm.doc.docstatus === 1 && !["CLEARED", "REPORTED"].includes(frm.doc.custom_zatca_status)) {
            frappe.db.get_value("Company", frm.doc.company, "country").then((r)=>{
                if(r.message && r.message.country === "Saudi Arabia"){

                    frm.add_custom_button(__("Send invoice to Zatca"), function () {
                        frm.call({
                            method: "zatca_erpgulf.zatca_erpgulf.sign_invoice.zatca_background",
                            args: {
                                "invoice_number": frm.doc.name,
                                "source_doc": frm.doc

                            },
                            callback: function (r) {

                                console.log("response.message");
                                frm.reload_doc();

                            }
                        })
                    }, __("Zatca Phase-2"));

                }
            })
        }
        frm.page.add_menu_item(__('Print PDF-A3'), function () {
            // Create a dialog box with fields for Print Format, Letterhead, and Language
            const dialog = new frappe.ui.Dialog({
                title: __('Generate PDF-A3'),
                fields: [
                    {
                        fieldtype: 'Link',
                        fieldname: 'print_format',
                        label: __('Print Format'),
                        options: 'Print Format',
                        // default: 'Claudion Invoice Format', // Default print format if any
                        reqd: 1,
                        get_query: function () {
                            return {
                                filters: {
                                    doc_type: 'Sales Invoice' // Filters print formats related to Sales Invoice
                                }
                            };
                        }
                    },
                    {
                        fieldtype: 'Link',
                        fieldname: 'letterhead',
                        label: __('Letterhead'),
                        options: 'Letter Head', // Options should be the 'Letter Head' doctype
                        reqd: 0
                    },
                    {
                        fieldtype: 'Link',
                        fieldname: 'language',
                        label: __('Language'),
                        options: 'Language', // Options should be the 'Language' doctype
                        // default: 'en', // Default language
                        reqd: 1
                    }
                ],
                primary_action_label: __('Generate PDF-A3'),
                primary_action: function () {
                    const values = dialog.get_values();
                    frappe.call({
                        method: 'zatca_erpgulf.zatca_erpgulf.pdf_a3.embed_file_in_pdf',
                        args: {
                            invoice_name: frm.doc.name,
                            print_format: values.print_format,
                            letterhead: values.letterhead,
                            language: values.language
                        },
                        callback: function (r) {
                            if (r.message) {
                                // Open the generated PDF in a new tab
                                console.log(r.message)
                                const pdf_url = r.message;
                                window.open(pdf_url, '_blank');
                                frm.reload_doc();

                            } else {
                                frappe.msgprint(__('Failed to generate PDF-A3'));
                            }
                        }

                    });
                    dialog.hide();
                }
            });
            dialog.show();
        });



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
        'custom_submit_line_item_discount_to_zatca',
        'custom_integrations'
    ];
    
    fields_to_hide.forEach(field => {
        frm.set_df_property(field, 'hidden', 1);
    });
    
    $('a[data-fieldname="custom_integrations"]').hide();
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
        'custom_integrations'
    ];
    
    fields_to_show.forEach(field => {
        frm.set_df_property(field, 'hidden', 0);
    });
    
    $('a[data-fieldname="custom_integrations"]').show();
}
frappe.ui.form.on('Sales Invoice', {
    refresh: function (frm) {
        const fieldsWithTooltips = [
            {
                fieldname: "custom_zatca_third_party_invoice",
                text: `
                    An external party such as an accounting firm can issue invoices on behalf of the seller after fulfilling specific requirements as mentioned in the VAT legislation.
                `,
                links: [
                    "https://docs.claudion.com/Claudion-Docs/Third%20party",
                ],
            },
            {
                fieldname: "custom_zatca_nominal_invoice",
                text: `
                    A taxable person provides goods or services to a customer at no cost or at a reduced price, typically as part of a promotional activity.
                `,
                links: [
                    "https://docs.claudion.com/Claudion-Docs/nominal",
                ],
            },
            {
                fieldname: "custom_zatca_export_invoice",
                text: `
                    The supplier and customer both intend that the goods are transported outside the GCC territory as a consequence of that supply.
                `,
                links: [
                    "https://docs.claudion.com/Claudion-Docs/export",
                ],
            },
            {
                fieldname: "custom_summary_invoice",
                text: `
                    Summary tax invoices are issued where there is more than one supply of goods or services.
                `,
                links: [
                    "https://docs.claudion.com/Claudion-Docs/Summary%20invoice",
                ],
            },
            {
                fieldname: "custom_self_billed_invoice",
                text: `
                    Self-billing is a case where the buyer raises a tax invoice for the goods and services received on behalf of the vendor.
                `,
                links: [
                    "https://docs.claudion.com/Claudion-Docs/selfbilled",
                ],
            },
        ];
        applyTooltips(frm, fieldsWithTooltips);
        const css = `
            .popover-content {
                font-family: Arial, sans-serif;
                background-color: #f9f9f9;
                color: #007bff; /* Blue text */
                border: 1px solid #cfe2f3;
                border-radius: 8px;
                padding: 15px;
                max-width: 300px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }

            .popover-title {
                font-size: 16px;
                font-weight: bold;
                color: #0056b3; /* Darker blue for the title */
                margin-bottom: 10px;
            }

            .popover-body {
                font-size: 14px;
                line-height: 1.6;
                color: #007bff;
            }
        `;
        $('<style>').text(css).appendTo('head'); // Add the CSS dynamically

        // Attach popover to the "subject" field
        const attachPopover = (fieldname, title, body) => {
            setTimeout(() => {
                $(`[data-fieldname="${fieldname}"]`).popover({
                    trigger: 'hover',
                    placement: 'top',
                    content: `
                        <div class="popover-content">
                            <h4 class="popover-title">${title}</h4>
                            <p class="popover-body">${body}</p>
                        </div>
                    `,
                    html: true
                });
            }, 500);
        };

        // Attach popovers to specific fields

    }
});

