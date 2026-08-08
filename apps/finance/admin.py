from django.contrib import admin
from .models import Account, Expense, Category
# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name"]

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["name", "account_type", "is_active"]
    list_filter = ["account_type"]

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["transaction_at", "amount", "category", "account"]
    list_filter = ["category", "account"]
    search_fields = ["merchant", "description"]