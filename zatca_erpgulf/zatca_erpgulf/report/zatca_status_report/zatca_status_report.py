import frappe
from frappe import _

def get_columns():
    return [
        {'fieldname':'name','label':_('Inv.Number'),'fieldtype':'Link','options':'Sales Invoice','width':220},
        {'fieldname':'posting_date','label':_('Date'),'fieldtype':'Date','width':160},
        {'fieldname':'customer_name','label':_('Customer'),'fieldtype':'Data','width':220},
        {'fieldname':'grand_total','label':_('Total'),'fieldtype':'Currency','width':160},
        {'fieldname':'custom_zatca_status','label':_('Status'),'fieldtype':'Data','width':180}
    ]

def execute(filters=None):
    filters=filters or {}; conditions=['1=1']; values={}
    if filters.get('company'): conditions.append('company = %(company)s'); values['company']=filters['company']
    if filters.get('dt_from'): conditions.append('posting_date >= %(dt_from)s'); values['dt_from']=filters['dt_from']
    if filters.get('dt_to'): conditions.append('posting_date <= %(dt_to)s'); values['dt_to']=filters['dt_to']
    if filters.get('status') and filters['status']!='Not Submitted': conditions.append('custom_zatca_status = %(status)s'); values['status']=filters['status']
    where_clause=' AND '.join(conditions)
    query='SELECT name, customer_name, posting_date, grand_total, custom_zatca_status, docstatus FROM `tabSales Invoice` WHERE '+where_clause+' ORDER BY posting_date DESC'
    invoices=frappe.db.sql(query,values,as_dict=True)
    if filters.get('status')=='Not Submitted':
        invoices=[inv for inv in invoices if inv.get('docstatus')==1 and (not inv.get('custom_zatca_status') or inv.get('custom_zatca_status')=='Not Submitted')]
    return get_columns(),invoices
