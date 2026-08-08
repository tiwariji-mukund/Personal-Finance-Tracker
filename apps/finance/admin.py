from django.contrib import admin
from .models import Account, Transaction, Category
# Register your models here.

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "icon",
        "color",
        "transaction_count",
        "is_active",
        "created_at",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "name",
    )
    ordering = (
        "name",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Category Information",
            {
                "fields": (
                    "name",
                    "icon",
                    "color",
                    "is_active",
                )
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Transactions")
    def transaction_count(self, obj):
        return obj.transactions.count()

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "account_type",
        "transaction_count",
        "is_active",
        "created_at",
    )

    list_filter = (
        "account_type",
        "is_active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Account Information",
            {
                "fields": (
                    "name",
                    "account_type",
                    "is_active",
                )
            },
        ),
        (
            "Audit Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Transactions")
    def transaction_count(self, obj):
        return obj.transactions.count()

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):

    def _display_or_dash(self, value):
        return value if value else "-"

    list_display = (
        "transaction_at",
        "transaction_type",
        "formatted_amount",
        "category",
        "account",
        "display_merchant",
    )

    list_filter = (
        "transaction_type",
        "category",
        "account",
    )

    list_select_related = (
        "category",
        "account",
    )

    search_fields = (
        "merchant",
        "description",
        "reference",
    )

    ordering = (
        "-transaction_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    date_hierarchy = "transaction_at"

    fieldsets = (
        (
            "Transaction Details",
            {
                "fields": (
                    "transaction_type",
                    "amount",
                    "category",
                    "account",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": (
                    "merchant",
                    "description",
                    "reference",
                    "notes",
                )
            },
        ),
        (
            "Timeline",
            {
                "fields": (
                    "transaction_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Amount")
    def formatted_amount(self, obj):
        return f"₹{obj.amount:,.2f}"

    @admin.display(description="Merchant")
    def display_merchant(self, obj):
        return self._display_or_dash(obj.merchant)