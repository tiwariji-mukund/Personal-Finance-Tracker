from django.contrib import admin
from django.utils.html import format_html
from .models import Account, Category, Loan, Person, Transaction, TransactionShare
# Register your models here.

@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = (
        "lender_name",
        "principal",
        "interest_rate",
        "disbursed_at",
        "is_active",
    )
    list_filter = (
        "is_active",
    )
    search_fields = (
        "lender_name",
    )
    ordering = (
        "-disbursed_at",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "name",
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

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "icon",
        "color_swatch",
        "category_type",
        "transaction_count",
        "is_active",
        "created_at",
    )
    list_filter = (
        "category_type",
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
                    "category_type",
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

    @admin.display(description="Color")
    def color_swatch(self, obj):
        return format_html(
            '<span style="display:inline-block;width:12px;height:12px;'
            'border-radius:3px;background:{0};border:1px solid rgba(0,0,0,.2);'
            'vertical-align:middle;margin-right:6px;"></span>{0}',
            obj.color,
        )

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

class TransactionShareInline(admin.TabularInline):
    model = TransactionShare
    extra = 0
    fields = ("person", "amount")

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

    inlines = (TransactionShareInline,)

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
                    "person",
                    "loan",
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