"""
Scheduled tasks for django-q2 (in-app scheduler).

Run the worker cluster alongside gunicorn:
    python manage.py qcluster

Then register the periodic importer once:
    python manage.py setup_scheduler
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
