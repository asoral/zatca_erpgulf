frappe.ui.form.on('Purchase Invoice',{

    refresh: function(frm){
        
        if (frm.doc.docstatus === 1 && !["CLEARED", "REPORTED"].includes(frm.doc.custom_zatca_status)){
            frm.add_custom_button(__("Send Invoice to Zatca"), function(){
                frm.call({
                    method: "zatca_erpgulf.zatca_erpgulf.our_purchase_invoice.zatca_background",
                    args:{

                        "invoice_number": frm.doc.name,
                        "source_doc": frm.doc
                    },
                    callback: function(r){                
                        
                        
                        
                        frm.reload_doc();
                    }
                })
                
            }, __("Zatca Phase-2"));
        }
        
    }

})