from django.core.management.base import BaseCommand
from django_q.models import Schedule
from django_q.tasks import schedule


class Command(BaseCommand):
    help = "Register (or refresh) the periodic in-app importer schedule."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes", type=int, default=30,
            help="How often (in minutes) to re-run the importer.",
        )
        parser.add_argument(
            "--remove", action="store_true",
            help="Delete the schedule instead of creating it.",
        )

    def handle(self, *args, **options):
        name = "importer-refresh"
        Schedule.objects.filter(name=name).delete()

        if options["remove"]:
            self.stdout.write(self.style.SUCCESS(f"Removed schedule '{name}'."))
            return

        schedule(
            "hymns.tasks.scheduled_import",
            name=name,
            schedule_type=Schedule.MINUTES,
            minutes=options["minutes"],
            repeats=-1,
        )
        self.stdout.write(self.style.SUCCESS(
            f"Scheduled '{name}' to run every {options['minutes']} min. "
            f"Start the worker with: python manage.py qcluster"
        ))
