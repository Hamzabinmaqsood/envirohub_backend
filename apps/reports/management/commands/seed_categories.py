from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.reports.models import Category


DEFAULT_CATEGORIES = [
    ("Garbage", "Solid waste, overflowing bins, or litter."),
    ("Sewage", "Open sewage, blocked drains, or sewage overflow."),
    ("Water Pollution", "Polluted water bodies or contaminated discharge."),
    ("Air Pollution", "Smoke, burning waste, dust, or harmful emissions."),
    ("Dead Animal", "Dead animal requiring safe municipal removal."),
    ("Illegal Dumping", "Unauthorized dumping of waste or debris."),
    ("Other", "Any other environmental issue."),
]


class Command(BaseCommand):
    help = "Create or update the default citizen report categories."

    def handle(self, *args, **options):
        for index, (name, description) in enumerate(DEFAULT_CATEGORIES, start=1):
            obj, created = Category.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "description": description,
                    "sort_order": index,
                    "is_active": True,
                },
            )
            self.stdout.write(f"{'Created' if created else 'Updated'}: {obj.name}")
        self.stdout.write(self.style.SUCCESS("Default categories are ready."))
