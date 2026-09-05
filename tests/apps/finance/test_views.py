from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.finance.models import Account, Category, CreditCard, Loan, Person, Transaction, TransactionShare


class DashboardViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Food', icon='🍔', is_active=True)
        self.account = Account.objects.create(name='Cash', is_active=True)

    def test_renders_successfully_with_no_transactions(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'finance/dashboard.html')
        self.assertEqual(response.context['income'], Decimal('0'))
        self.assertEqual(response.context['expenses'], Decimal('0'))

    def test_shows_totals_for_the_requested_month(self):
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('250'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['expenses'], Decimal('250'))
        self.assertContains(response, 'January 2026')

    def test_a_transaction_outside_the_requested_month_is_excluded(self):
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('250'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(2026, 2, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['expenses'], Decimal('0'))

    def test_an_investment_transfer_is_excluded_from_expenses_and_shown_as_invested(self):
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.TRANSFER,
            amount=Decimal('5000'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['expenses'], Decimal('0'))
        self.assertEqual(response.context['invested'], Decimal('5000'))
        self.assertEqual(response.context['category_breakdown'], [])

    def test_an_out_of_range_month_falls_back_to_the_current_month_instead_of_erroring(self):
        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 13})

        self.assertEqual(response.status_code, 200)

    def test_a_non_numeric_month_falls_back_to_the_current_month_instead_of_erroring(self):
        response = self.client.get(reverse('dashboard'), {'year': 'abc', 'month': 'xyz'})

        self.assertEqual(response.status_code, 200)

    def test_a_shared_expense_shows_up_as_outstanding_and_excluded_from_personal_expenses(self):
        alice = Person.objects.create(name='Alice', is_active=True)
        transaction = Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('25000'),
            category=self.category,
            account=self.account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )
        TransactionShare.objects.create(transaction=transaction, person=alice, amount=Decimal('5000'))

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['expenses'], Decimal('25000'))
        self.assertEqual(response.context['personal_expenses'], Decimal('20000'))
        balances = {row['person']: row['outstanding'] for row in response.context['outstanding_balances']}
        self.assertEqual(balances[alice], Decimal('5000'))

    def test_an_outstanding_loan_is_shown_on_the_dashboard(self):
        loan = Loan.objects.create(lender_name='Bank', principal=Decimal('10000'), disbursed_at=date(2026, 1, 1))
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.LOAN_PAYMENT,
            amount=Decimal('3000'),
            account=self.account,
            loan=loan,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        balances = {row['loan']: row['outstanding'] for row in response.context['outstanding_loans']}
        self.assertEqual(balances[loan], Decimal('7000'))
        self.assertContains(response, 'Bank')

    def test_a_fully_paid_loan_is_excluded_from_the_dashboard(self):
        loan = Loan.objects.create(lender_name='Bank', principal=Decimal('10000'), disbursed_at=date(2026, 1, 1))
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.LOAN_PAYMENT,
            amount=Decimal('10000'),
            account=self.account,
            loan=loan,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['outstanding_loans'], [])

    def test_an_outstanding_credit_card_bill_is_shown_on_the_dashboard(self):
        card_account = Account.objects.create(name='HDFC Card', account_type=Account.AccountType.CREDIT_CARD, is_active=True)
        card = CreditCard.objects.create(account=card_account, credit_limit=Decimal('50000'), billing_day=1, due_day=15)
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('3000'),
            category=self.category,
            account=card_account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        balances = {row['credit_card']: row['outstanding'] for row in response.context['outstanding_credit_cards']}
        self.assertEqual(balances[card], Decimal('3000'))
        self.assertContains(response, 'HDFC Card')

    def test_a_fully_paid_credit_card_is_excluded_from_the_dashboard(self):
        card_account = Account.objects.create(name='HDFC Card', account_type=Account.AccountType.CREDIT_CARD, is_active=True)
        card = CreditCard.objects.create(account=card_account, credit_limit=Decimal('50000'), billing_day=1, due_day=15)
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('3000'),
            category=self.category,
            account=card_account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.CARD_PAYMENT,
            amount=Decimal('3000'),
            account=card_account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 20)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['outstanding_credit_cards'], [])

    def test_total_debt_combines_loans_and_credit_cards(self):
        loan = Loan.objects.create(lender_name='Bank', principal=Decimal('10000'), disbursed_at=date(2026, 1, 1))
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.LOAN_PAYMENT,
            amount=Decimal('4000'),
            account=self.account,
            loan=loan,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )
        card_account = Account.objects.create(name='HDFC Card', account_type=Account.AccountType.CREDIT_CARD, is_active=True)
        CreditCard.objects.create(account=card_account, credit_limit=Decimal('50000'), billing_day=1, due_day=15)
        Transaction.objects.create(
            transaction_type=Transaction.TransactionType.EXPENSE,
            amount=Decimal('2500'),
            category=self.category,
            account=card_account,
            transaction_at=timezone.make_aware(datetime(2026, 1, 15)),
        )

        response = self.client.get(reverse('dashboard'), {'year': 2026, 'month': 1})

        self.assertEqual(response.context['total_debt'], Decimal('6000') + Decimal('2500'))
