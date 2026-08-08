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
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
    )
    color = models.CharField(
        max_length=7,
        default='#3B82F6',
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

class Transaction(BaseModel):
    """
    Represents any financial transaction.
    """
    class TransactionType(models.TextChoices):
        EXPENSE = "EXPENSE", "Expense"
        INCOME = "INCOME", "Income"
        TRANSFER = "TRANSFER", "Transfer"
        SETTLEMENT = "SETTLEMENT", "Settlement"

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
            f"{self.category.name} | ₹{self.amount}"
        )