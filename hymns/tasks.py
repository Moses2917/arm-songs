"""
Scheduled tasks for the in-app scheduler.

The scheduler is a small threading-based loop started by:
    python manage.py run_scheduler

It periodically calls `scheduled_import` below so that dropped-in JSON
data refreshes the database.
"""
import logging

from django.conf import settings

from .importer import import_json

logger = logging.getLogger(__name__)


def scheduled_import():
    """Re-run the JSON importer so dropped-in data refreshes the DB."""
    try:
        stats = import_json(getattr(settings, "DATA_DIR", "data"))
        logger.info("scheduled_import ok: %s", stats)
        return stats
    except Exception:
        logger.exception("scheduled_import failed")
        raise
