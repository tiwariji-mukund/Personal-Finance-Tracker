from django.core.management.base import BaseCommand
from constants import DEFAULT_ACCOUNTS, DEFAULT_CATEGORIES
from apps.finance.models import Category, Account

class Command(BaseCommand):
    help = 'Seeds inital application data.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting seed process...\n"))

        self.seed_categories()
        self.stdout.write("")

        self.seed_accounts()
        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS("Seed process completed successfully.")
        )

    def seed_categories(self):
        self.stdout.write(self.style.HTTP_INFO("Seeding categories..."))
        created = skipped = 0

        for category in DEFAULT_CATEGORIES:
            _, is_created = Category.objects.get_or_create(
                name=category["name"],
                defaults={
                    "color": category["color"],
                    "icon": category["icon"],
                    "category_type": category["category_type"],
                    "is_active": True,
                },
            )

            if is_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✔ Created: {category['name']}")
                )
            else:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"  • Exists : {category['name']}")
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Categories -> Created: {created}, Skipped: {skipped}"
                )
            )

    def seed_accounts(self):
        self.stdout.write(self.style.HTTP_INFO("Seeding accouts..."))
        created = skipped = 0

        for account in DEFAULT_ACCOUNTS:
            _, is_created = Account.objects.get_or_create(
                name=account["name"],
                defaults={
                    "account_type": Account.AccountType(account["account_type"]),
                    "is_active": True,
                },
            )

            if is_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✔ Created: {account['name']}")
                )
            else:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"  • Exists : {account['name']}")
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Accounts -> Created: {created}, Skipped: {skipped}"
                )
            )