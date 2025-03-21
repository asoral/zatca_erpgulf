frappe.ui.form.on('Purchase Invoice',{

    refresh: function(frm){       
        
        if (frm.doc.docstatus === 1 && !["CLEARED", "REPORTED"].includes(frm.doc.custom_zatca_status)){
            frappe.db.get_value("Company" , frm.doc.company , "country" , (r)=>{

                if(r.country === "Saudi Arabia"){
                
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
            })
            
        }
        
    },
    company: function(frm){
        if (frm.doc.company){
            frappe.db.get_value("Company", frm.doc.company , "country" , (r)=>{
                if(r.country == "Saudi Arabia"){

                    frm.set_df_property('custom_zatca_third_party_invoice', 'hidden' , 0);
                    frm.set_df_property('custom_zatca_nominal_invoice', 'hidden' , 0);
                    frm.set_df_property('custom_zatca_export_invoice','hidden',0);
                    frm.set_df_property('custom_summary_invoice','hidden',0);
                    frm.set_df_property('custom_self_billed_invoice','hidden',0);
                    
                }else{
                    frm.set_df_property('custom_zatca_third_party_invoice' , 'hidden' , 1);
                    frm.set_df_property('custom_zatca_nominal_invoice', 'hidden' , 1);
                    frm.set_df_property('custom_zatca_export_invoice','hidden',1);
                    frm.set_df_property('custom_summary_invoice','hidden',1);
                    frm.set_df_property('custom_self_billed_invoice','hidden',1);
                }
            })
        }
    }   

})




