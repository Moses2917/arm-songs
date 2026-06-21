"""
Lightweight in-process scheduler (replaces django-q2's qcluster).

A single background thread calls `hymns.tasks.scheduled_import` on a fixed
interval. The main thread owns SIGINT/SIGTERM handling so the worker can
finish the current run and then exit cleanly.

Run in the foreground (dev or under systemd):
    python manage.py run_scheduler
    python manage.py run_scheduler --minutes 15
    python manage.py run_scheduler --once      # single run, then exit
"""
import logging
import signal
import threading

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from hymns.tasks import scheduled_import

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Run a lightweight in-process scheduler that periodically calls "
        "hymns.tasks.scheduled_import. Foreground replacement for "
        "django-q2's qcluster."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutes",
            type=int,
            default=30,
            help="How often (in minutes) to re-run the importer (default 30).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run scheduled_import a single time and exit (dry run).",
        )

    def handle(self, *args, **options):
        if options["once"]:
            self.stdout.write(self.style.NOTICE("Running scheduled_import once."))
            self._run_once()
            return

        interval = max(1, options["minutes"]) * 60
        stop = threading.Event()

        def _stop(signum, _frame):
            self.stdout.write(self.style.WARNING(
                "Received stop signal; scheduler shutting down..."
            ))
            stop.set()

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        self.stdout.write(self.style.SUCCESS(
            f"Scheduler started: running scheduled_import every "
            f"{options['minutes']} min (Ctrl-C to stop)."
        ))

        worker = threading.Thread(
            target=self._loop,
            args=(interval, stop),
            name="hymns-scheduler",
            daemon=True,
        )
        worker.start()
        worker.join()
        self.stdout.write(self.style.SUCCESS("Scheduler stopped."))

    def _loop(self, interval, stop):
        """Run the task immediately, then every `interval` seconds."""
        while not stop.is_set():
            self._run_once()
            # Interruptible sleep: returns True immediately if stop is set.
            stop.wait(interval)

    def _run_once(self):
        try:
            stats = scheduled_import()
            self.stdout.write(self.style.SUCCESS(
                f"scheduled_import ok: {stats}"
            ))
        except Exception:
            logger.exception("scheduled_import failed")
            self.stderr.write(self.style.ERROR(
                "scheduled_import failed (see logs for details)"
            ))
        finally:
            # Avoid leaking DB connections across iterations / threads.
            close_old_connections()
