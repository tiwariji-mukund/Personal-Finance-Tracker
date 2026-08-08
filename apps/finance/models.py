from django.db import models

# Create your models here.
class BaseModel(models.Model):
    '''
    Abstract base model that provides common timestamp fields.
    '''
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        abstract = True

class Category(models.Model):
    """
    Represents an expense category.
    🍔 Food
    🚕 Travel
    🛒 Shopping

    Food      → #EF4444
    Travel    → #3B82F6
    Shopping  → #10B981
    """

    name = models.CharField(max_length=100)
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

class Account(models.Model):
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

class Expense(BaseModel):
    """
    Represents a single expense transaction.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='expenses',
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.PROTECT,
        related_name='expenses',
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
    transaction_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    class Meta:
        ordering = ["-transaction_at", "-created_at"]
    def __str__(self):
        return f"{self.category} - {self.amount}"
