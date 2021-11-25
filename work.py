from decimal import Decimal
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.modules.product import price_digits


class Expense(ModelSQL, ModelView):
    'Projecte Expense'
    __name__ = 'project.expense'
    _states = {
        'readonly': Bool(Eval('invoice_line')),
        }
    _depends = ['invoice_line']

    work = fields.Many2One('project.work', 'Work', required=True, select=True,
        states=_states, depends=_depends)
    origin = fields.Reference('Origin', selection='get_origin', readonly=True)
    product = fields.Many2One('product.product', 'Product', required=True,
        states=_states, depends=_depends)
    uom = fields.Many2One('product.uom', 'UoM', required=True, states=_states,
        depends=_depends)
    uom_category = fields.Function(fields.Many2One('product.uom.category',
            'UoM Category'), 'on_change_with_uom_category')
    uom_digits = fields.Function(fields.Integer('UoM Digits'),
        'on_change_with_uom_digits')
    cost_price = fields.Numeric('Cost Price', digits=price_digits,
        states=_states, depends=_depends)
    # TODO: Show field and apply price list
    unit_price = fields.Numeric('Unit Price', digits=price_digits,
        states=_states, depends=_depends)
    # TODO: Add currency digits
    #amount = fields.Function(fields.Numeric('Amount'), '')
    quantity = fields.Float('Quantity', digits=(16, Eval('uom_digits', 2)),
        required=True, states=_states, depends=_depends + ['uom_digits'])
    description = fields.Char('Description', states=_states, depends=_depends)
    invoiceable = fields.Selection([
            (None, ''),
            ('yes', 'Yes'),
            ('no', 'No'),
            ], 'Invoiceable', states=_states, depends=_depends)
    invoice_line = fields.Many2One('account.invoice.line', 'Invoice Line',
        readonly=True)

    del _states

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        pool = Pool()

        res = []
        for model in ('purchase.line', 'stock.move'):
            try:
                pool.get(model)
                res.append(model)
            except KeyError:
                pass
        return res

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        models = cls._get_origin()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [(None, '')] + [(m.model, m.name) for m in models]

    @fields.depends('product')
    def on_change_product(self):
        if not self.product:
            return
        self.uom = self.product.default_uom

    @fields.depends('product')
    def on_change_with_uom_category(self, name=None):
        if not self.product:
            return
        return self.product.uom.category.id

    @fields.depends('uom')
    def on_change_with_uom_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    def _get_invoice_lines(self):
        if not self.invoiceable == 'yes' or not self.quantity:
            # TODO: Raise a UserError if invoiceable is empty
            return []

        return [{
                'product': self.product,
                'quantity': self.quantity,
                'unit': self.uom,
                'unit_price': self.unit_price or Decimal(0),
                'origins': [self],
                'description': self.description,
                }]


class Project(metaclass=PoolMeta):
    __name__ = 'project.work'
    expenses = fields.One2Many('project.expense', 'work', 'Expenses')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._buttons.update({
                'sync_expenses': {
                    }
                })

    @classmethod
    @ModelView.button
    def sync_expenses(cls, works):
        pool = Pool()
        Expense = pool.get('project.expense')
        Uom = pool.get('product.uom')

        to_save = []
        to_delete = []
        for work in works:
            expenses = work._get_expenses()
            expenses = {x.origin: x for x in expenses}

            for existing in work.expenses:
                if not existing.origin:
                    continue
                expense = expenses.get(existing.origin)
                if not expense:
                    to_delete.append(existing)
                    continue
                existing_qty = Uom.compute_qty(existing.uom, existing.quantity,
                    expense.uom)
                expense.quantity -= existing_qty

            for expense in expenses.values():
                if not expense.quantity:
                    continue
                to_save.append(expense)

        Expense.save(to_save)
        Expense.delete(to_delete)

    def _get_expenses(self):
        expenses = []
        if hasattr(self, 'moves'):
            for move in self.moves:
                expense = self._get_expense_move(move)
                if expense:
                    expenses.append(expense)
        if hasattr(self, 'purchase_lines'):
            for line in self.purchase_lines:
                expense = self._get_expense_purchase_line(line)
                if expense:
                    expenses.append(expense)
        return expenses

    def _get_expense_move(self, move):
        Expense = Pool().get('project.expense')

        if move.state != 'done':
            return
        expense = Expense()
        expense.work = self
        expense.origin = move
        expense.product = move.product
        expense.uom = move.uom
        expense.quantity = move.quantity
        expense.cost_price = move.cost_price
        return expense

    def _get_expense_purchase_line(self, purchase_line):
        Expense = Pool().get('project.expense')

        expense = Expense()
        expense.work = self
        expense.origin = purchase_line
        expense.product = purchase_line.product
        expense.uom = purchase_line.unit
        expense.quantity = purchase_line.quantity
        expense.cost_price = purchase_line.unit_price
        return expense

    def _get_lines_to_invoice(self):
        lines = super()._get_lines_to_invoice()
        lines += self._get_expense_lines_to_invoice()
        return lines

    def _get_expense_lines_to_invoice(self):
        lines = []
        for expense in self.expenses:
            lines += expense._get_invoice_lines()
        return lines


class AnalyticAccountEntry(metaclass=PoolMeta):
    __name__ = 'analytic.account.entry'

    @classmethod
    def _get_origin(cls):
        origins = super(AnalyticAccountEntry, cls)._get_origin()
        return origins + ['project.expense']

    @fields.depends('origin')
    def on_change_with_company(self, name=None):
        pool = Pool()
        ProjectExpense = pool.get('project.expense')

        company = super(AnalyticAccountEntry, self).on_change_with_company(
            name)
        if isinstance(self.origin, ProjectExpense):
            company = self.origin.work.company.id
        return company

    @classmethod
    def search_company(cls, name, clause):
        domain = super(AnalyticAccountEntry, cls).search_company(name, clause),
        return ['OR',
            domain,
            (('origin.work.' + clause[0],) + tuple(clause[1:3])
                + ('project.expense',) + tuple(clause[3:])),
            ]
