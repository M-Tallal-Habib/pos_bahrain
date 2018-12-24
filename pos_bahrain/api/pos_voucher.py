# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import frappe
from frappe.utils import now


@frappe.whitelist()
def create_opening(
    opening_amount, company, pos_profile, user=None, posting=None
):
    pv = frappe.get_doc({
        'doctype': 'POS Voucher',
        'period_from': posting or now(),
        'company': company,
        'pos_profile': pos_profile,
        'user': user or frappe.session.user,
        'opening_amount': opening_amount,
    }).insert(ignore_permissions=True)
    return pv.name


def get_unclosed(user, pos_profile, company):
    return frappe.db.exists('POS Voucher', {
        'user': user,
        'pos_profile': pos_profile,
        'company': company,
        'docstatus': 0,
    })


@frappe.whitelist()
def get_data(
    company, pos_profile, period_from, period_to=None, user=None
):
    args = {
        'pos_profile': pos_profile,
        'company': company,
        'user': user or frappe.session.user,
        'period_from': period_from,
        'period_to': period_to or frappe.utils.now(),
    }
    invoices = frappe.db.sql(
        """
            SELECT
                name,
                pos_total_qty,
                base_grand_total AS grand_total,
                base_net_total AS net_total
            FROM `tabSales Invoice`
            WHERE docstatus = 1 AND
                is_pos = 1 AND
                pos_profile = %(pos_profile)s AND
                company = %(company)s AND
                owner = %(user)s AND
                TIMESTAMP(posting_date, posting_time) >= %(period_from)s AND
                TIMESTAMP(posting_date, posting_time) <= %(period_to)s
        """,
        values=args,
        as_dict=1,
    )
    payments = frappe.db.sql(
        """
            SELECT
                mode_of_payment,
                type,
                SUM(base_amount) AS base_amount,
                mop_currency,
                SUM(mop_amount) AS mop_amount
            FROM `tabSales Invoice Payment`
            WHERE parent in %(invoices)s
            GROUP BY mode_of_payment
        """,
        values={'invoices': map(lambda x: x.name, invoices)},
        as_dict=1,
    ) if invoices else []
    cash_payments = filter(lambda x: x.type == 'Cash', payments)
    noncash_amount = sum([
        x.get('base_amount', 0) for x in filter(
            lambda x: x.type != 'Cash', payments
        )
    ])
    taxes = frappe.db.sql(
        """
            SELECT
                rate,
                SUM(base_tax_amount) AS tax_amount
            FROM `tabSales Taxes and Charges`
            WHERE parent in %(invoices)s
            GROUP BY rate
        """,
        values={'invoices': map(lambda x: x.name, invoices)},
        as_dict=1,
    ) if invoices else []
    return {
        'period_from': args.get('period_from'),
        'period_to': args.get('period_to'),
        'user': args.get('user'),
        'invoices': invoices,
        'payments': cash_payments,
        'noncash_amount': noncash_amount,
        'taxes': taxes,
    }
