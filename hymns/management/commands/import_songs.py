from django.conf import settings
from django.core.management.base import BaseCommand

from hymns.importer import import_json


class Command(BaseCommand):
    help = "Import/refresh songs, lyrics, themes from the JSON data dir (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-dir",
            default=str(getattr(settings, "DATA_DIR", "data")),
            help="Directory containing the JSON source files.",
        )

    def handle(self, *args, **options):
        stats = import_json(options["data_dir"])
        self.stdout.write(self.style.SUCCESS("Import complete:"))
        for key, val in stats.items():
            self.stdout.write(f"  {key:>16}: {val}")
