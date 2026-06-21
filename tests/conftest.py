"""
Shared pytest fixtures for the arm_songs test suite.

Database access is enabled per-test via the ``django_db`` mark (handled by
pytest-django). The fixtures here provide small, deterministic factories so
individual tests stay readable.
"""
import pytest

from hymns.models import Song, Theme, Service


@pytest.fixture
def make_song(db):
    """Return a factory that creates a Song with sensible defaults."""
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        defaults = {
            "book": Song.BOOK_NEW,
            "number": str(overrides.get("number", counter["n"])),
            "title": "Test Song {}".format(counter["n"]),
        }
        defaults.update(overrides)
        # avoid unique clashes when caller passes explicit number
        defaults.setdefault("title", "Test Song {}".format(defaults["number"]))
        return Song.objects.create(**defaults)

    return _make


@pytest.fixture
def make_theme(db):
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        defaults = {"number": counter["n"], "name": "Theme {}".format(counter["n"])}
        defaults.update(overrides)
        return Theme.objects.create(**defaults)

    return _make


@pytest.fixture
def make_service(db):
    counter = {"n": 0}

    def _make(**overrides):
        counter["n"] += 1
        defaults = {"filename": "service_{}.docx".format(counter["n"])}
        defaults.update(overrides)
        return Service.objects.create(**defaults)

    return _make
