from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

class BaseModel(models.Model):
    '''
    Abstract base model that provides common timestamp fields.
    '''
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Category(BaseModel):
    """
    Represents an expense category.
    🍔 Food
    🚕 Travel
    🛒 Shopping

    Food      → #EF4444
    Travel    → #3B82F6
    Shopping  → #10B981
    """
    class CategoryType(models.TextChoices):
        EXPENSE = 'EXPENSE', 'Expense'
        INCOME = 'INCOME', 'Income'
        TRANSFER = 'TRANSFER', 'Investment'

    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
    )
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
    )
    category_type = models.CharField(
        max_length=20,
        choices=CategoryType.choices,
        default=CategoryType.EXPENSE,
    )
    is_active = models.BooleanField(
        default=True,
    )
    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Categories"
    def __str__(self):
        return self.name

class Account(BaseModel):
    """
    Represents the source account from which money is spent.
    """
    class AccountType(models.TextChoices):
        SAVINGS = 'SAVINGS', 'Savings'
        CREDIT_CARD = 'CREDIT_CARD', 'Credit Card'
        CASH = 'CASH', 'Cash'
        UPI = 'UPI', 'UPI'

    name = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=20,
        choices=AccountType.choices,
        default=AccountType.SAVINGS,
    )
    is_active = models.BooleanField(
        default=True,
    )
    class Meta:
        ordering = ["name"]
    def __str__(self):
        return self.name

class CreditCard(BaseModel):
    """
    Billing details for an Account of type CREDIT_CARD. Outstanding balance
    is derived (EXPENSE minus CARD_PAYMENT transactions on the account),
    not stored here.
    """
    account = models.OneToOneField(
        Account,
        on_delete=models.CASCADE,
        related_name="credit_card",
        limit_choices_to={"account_type": Account.AccountType.CREDIT_CARD},
    )
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2)
    billing_day = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    due_day = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(28)],
    )
    def __str__(self):
        return f"{self.account.name} (limit ₹{self.credit_limit})"

class Person(BaseModel):
    """
    Someone the user shares expenses with or owes/is owed money by.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["name"]
        verbose_name_plural = "People"
    def __str__(self):
        return self.name

class Loan(BaseModel):
    """
    Money borrowed from a lender, tracked as a single outstanding balance
    (principal minus payments) rather than an amortization schedule.
    """
    lender_name = models.CharField(max_length=100)
    principal = models.DecimalField(max_digits=10, decimal_places=2)
    # Annual %, informational only — not used to compute interest/amortization.
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    disbursed_at = models.DateField()
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ["-disbursed_at"]
    def __str__(self):
        return f"{self.lender_name} — ₹{self.principal}"

class Transaction(BaseModel):
    """
    Represents any financial transaction.
    """
    class TransactionType(models.TextChoices):
        EXPENSE = "EXPENSE", "Expense"
        INCOME = "INCOME", "Income"
        TRANSFER = "TRANSFER", "Transfer"
        SETTLEMENT = "SETTLEMENT", "Settlement"
        LOAN_PAYMENT = "LOAN_PAYMENT", "Loan Payment"
        CARD_PAYMENT = "CARD_PAYMENT", "Card Payment"

    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        default=TransactionType.EXPENSE,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    # Only set on SETTLEMENT transactions: who paid the user back.
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="settlements",
        null=True,
        blank=True,
    )
    # Only set on LOAN_PAYMENT transactions: which loan this pays down.
    loan = models.ForeignKey(
        Loan,
        on_delete=models.PROTECT,
        related_name="payments",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    merchant = models.CharField(
        max_length=100,
        blank=True,
    )
    description = models.CharField(
        max_length=255,
        blank=True,
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    transaction_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    class Meta:
        ordering = [
            "-transaction_at",
            "-created_at",
        ]

    def __str__(self):
        return (
            f"{self.get_transaction_type_display()} | "
            f"{self.category.name if self.category else (self.person or self.loan)} | ₹{self.amount}"
        )

class TransactionShare(BaseModel):
    """
    One person's share of a shared EXPENSE transaction — the portion the
    user paid on their behalf, owed back until a SETTLEMENT is recorded.
    """
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="shares",
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        related_name="shares",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    class Meta:
        unique_together = ("transaction", "person")
    def __str__(self):
        return f"{self.person.name} owes ₹{self.amount} for #{self.transaction_id}"