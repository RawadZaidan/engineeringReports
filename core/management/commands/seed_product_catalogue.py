"""
Management command to seed the product catalogue with predefined categories and product names.
Run: python manage.py seed_product_catalogue

Products are stored with manufacturer='' and model=<product name> so that the
unique_together constraint (manufacturer, model) is satisfied for each entry.
"""
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from core.models import Product
from core.catalogue_data import CATALOGUE


class Command(BaseCommand):
    help = "Seed the Product catalogue with predefined categories and product names."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing products before seeding (use with caution).',
        )

    def handle(self, *args, **options):
        if options['clear']:
            count, _ = Product.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing products."))

        created_total = 0
        skipped_total = 0

        for category, names in CATALOGUE.items():
            created_cat = 0
            for name in names:
                # Use the product name as the 'model' field so the unique_together
                # constraint (manufacturer, model) is satisfied per entry.
                try:
                    obj, created = Product.objects.get_or_create(
                        manufacturer='',
                        model=name,
                        defaults={
                            'name': name,
                            'category': category,
                            'notes': '',
                        }
                    )
                    if created:
                        created_cat += 1
                        created_total += 1
                    else:
                        skipped_total += 1
                except IntegrityError:
                    skipped_total += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"[{category}] {created_cat} created, "
                    f"{len(names) - created_cat} already existed."
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Total created: {created_total}, skipped: {skipped_total}."
            )
        )
