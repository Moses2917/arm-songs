from datetime import date

import pytest
from django.db import IntegrityError

from hymns.models import Song, Theme, Service, ServiceSong

pytestmark = pytest.mark.django_db


# --- Song.display_title -------------------------------------------------

def test_display_title_prefers_title_display():
    s = Song.objects.create(
        book=Song.BOOK_NEW, number="1",
        title="Raw Title", title_display="Display Title",
    )
    assert s.display_title() == "Display Title"


def test_display_title_falls_back_to_first_line():
    s = Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="First Line\nSecond Line",
    )
    assert s.display_title() == "First Line"


def test_display_title_strips_punctuation_and_whitespace():
    s = Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="  Hello, World.  ",
    )
    # strip(" ,.") only trims leading/trailing chars, inner punctuation stays
    assert s.display_title() == "Hello, World"


def test_display_title_uses_number_when_title_empty():
    s = Song.objects.create(book=Song.BOOK_NEW, number="42", title="")
    assert s.display_title() == "#42"


def test_display_title_uses_number_when_title_blank_lines():
    s = Song.objects.create(book=Song.BOOK_NEW, number="42", title="   ")
    assert s.display_title() == "#42"


# --- Song.__str__ / book_label ------------------------------------------

def test_song_str_truncates_long_title():
    long = "A" * 200
    s = Song.objects.create(book=Song.BOOK_NEW, number="5", title=long)
    assert str(s) == "New #5: " + ("A" * 60)


def test_book_label_for_each_book():
    new = Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    old = Song.objects.create(book=Song.BOOK_OLD, number="1", title="y")
    assert new.book_label == "Կարմիր Երգարան (New)"
    assert old.book_label == "Word Songs (Old)"


def test_book_label_unknown_book_falls_back_to_raw():
    s = Song.objects.create(book="??", number="1", title="x")
    assert s.book_label == "??"


# --- Song.matched_song --------------------------------------------------

def test_matched_song_returns_none_without_match_fields():
    s = Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    assert s.matched_song() is None


def test_matched_song_returns_none_when_target_missing():
    s = Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="x",
        match_book="Old", match_number="999",
    )
    assert s.matched_song() is None


def test_matched_song_returns_the_linked_song():
    new = Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="x",
        match_book="Old", match_number="2",
    )
    old = Song.objects.create(book=Song.BOOK_OLD, number="2", title="y")
    matched = new.matched_song()
    assert matched is not None
    assert matched.pk == old.pk


# --- Song constraints / ordering ----------------------------------------

def test_song_unique_book_number():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    with pytest.raises(IntegrityError):
        Song.objects.create(book=Song.BOOK_NEW, number="1", title="y")


def test_song_unique_per_book_allows_same_number_other_book():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    Song.objects.create(book=Song.BOOK_OLD, number="1", title="y")
    assert Song.objects.count() == 2


def test_song_meta_orders_by_book_then_number_as_string():
    Song.objects.create(book=Song.BOOK_NEW, number="10", title="x")
    Song.objects.create(book=Song.BOOK_NEW, number="2", title="y")
    Song.objects.create(book=Song.BOOK_OLD, number="3", title="z")
    nums = [(s.book, s.number) for s in Song.objects.all()]
    # 'Old' < 'New' lexicographically, and number is string-sorted ('10' < '2')
    assert nums == [("New", "10"), ("New", "2"), ("Old", "3")]


def test_song_updated_at_is_set():
    s = Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    assert s.updated_at is not None


# --- Theme --------------------------------------------------------------

def test_theme_str():
    t = Theme.objects.create(number=1, name="ԱՍՏՎԱԾ")
    assert str(t) == "1. ԱՍՏՎԱԾ"


def test_theme_number_unique():
    Theme.objects.create(number=1, name="A")
    with pytest.raises(IntegrityError):
        Theme.objects.create(number=1, name="B")


def test_theme_ordering_by_number():
    Theme.objects.create(number=5, name="B")
    Theme.objects.create(number=1, name="A")
    nums = [t.number for t in Theme.objects.all()]
    assert nums == [1, 5]


def test_theme_song_m2m_is_bidirectional():
    song = Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    theme = Theme.objects.create(number=1, name="A")
    theme.songs.add(song)
    assert list(theme.songs.all()) == [song]
    assert list(song.themes.all()) == [theme]


# --- Service / ServiceSong ---------------------------------------------

def test_service_str():
    svc = Service.objects.create(filename="20.06.24.docx")
    assert str(svc) == "20.06.24.docx"


def test_service_filename_unique():
    Service.objects.create(filename="a.docx")
    with pytest.raises(IntegrityError):
        Service.objects.create(filename="a.docx")


def test_service_ordering_descending_date_then_filename():
    Service.objects.create(filename="a.docx", date=date(2024, 1, 1))
    Service.objects.create(filename="b.docx", date=date(2025, 1, 1))
    Service.objects.create(filename="c.docx", date=None)
    order = [s.filename for s in Service.objects.all()]
    # NULL dates sort last in descending order, then filename desc as tiebreak
    assert order == ["b.docx", "a.docx", "c.docx"]


def test_service_song_str_and_ordering():
    song = Song.objects.create(book=Song.BOOK_NEW, number="1", title="First")
    svc = Service.objects.create(filename="svc.docx")
    ServiceSong.objects.create(service=svc, song=song, position=0)
    link = svc.service_songs.first()
    assert str(link) == "svc.docx - New #1: First"
    assert svc.service_songs.first().position == 0


def test_service_song_cascade_delete_with_service():
    song = Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    svc = Service.objects.create(filename="svc.docx")
    ServiceSong.objects.create(service=svc, song=song, position=0)
    svc.delete()
    assert ServiceSong.objects.count() == 0
    # song should remain (FK is on the link, not the song)
    assert Song.objects.filter(pk=song.pk).exists()
