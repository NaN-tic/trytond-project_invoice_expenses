# This file is part project_invoice_expenses module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
import unittest


from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import suite as test_suite


class ProjectInvoiceExpensesTestCase(ModuleTestCase):
    'Test Project Invoice Expenses module'
    module = 'project_invoice_expenses'


class ProjectInvoiceExpensesPurchaseTestCase(ModuleTestCase):
    'Test Project Invoice Expenses module'
    module = 'project_invoice_expenses'
    extras = ['purchase']



def suite():
    suite = test_suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProjectInvoiceExpensesTestCase))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
            ProjectInvoiceExpensesPurchaseTestCase))
    return suite
