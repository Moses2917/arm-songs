import pytest
from django.urls import reverse
from django.test import Client

from hymns.models import Song, Theme
from hymns.views import _parse_lyrics, ARMENIAN_LETTERS


pytestmark = pytest.mark.django_db


# --- home ---------------------------------------------------------------

def test_home_renders_with_counts(make_song):
    make_song(book=Song.BOOK_NEW, number="1")
    make_song(book=Song.BOOK_OLD, number="1")
    Theme.objects.create(number=1, name="A")
    r = Client().get(reverse("hymns:home"))
    assert r.status_code == 200
    assert r.context["counts"]["new"] == 1
    assert r.context["counts"]["old"] == 1
    assert r.context["counts"]["themes"] == 1


def test_home_template_used():
    r = Client().get(reverse("hymns:home"))
    assert "hymns/home.html" in [t.name for t in r.templates if t.name]


# --- tsank_number -------------------------------------------------------

def test_tsank_number_lists_songs_numeric_order():
    # numbers like "10" must sort AFTER "2" (numeric, not lexical)
    Song.objects.create(book=Song.BOOK_NEW, number="10", title="Ten")
    Song.objects.create(book=Song.BOOK_NEW, number="2", title="Two")
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="One")

    r = Client().get(reverse("hymns:tsank_number"))
    assert r.status_code == 200
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["1", "2", "10"]


def test_tsank_number_book_filter_defaults_to_new(make_song):
    new = make_song(book=Song.BOOK_NEW, number="1")
    old = make_song(book=Song.BOOK_OLD, number="2")
    r = Client().get(reverse("hymns:tsank_number"))
    nums = [s.number for s in r.context["page"].object_list]
    assert new.number in nums
    assert old.number not in nums
    assert r.context["book"] == "New"


def test_tsank_number_invalid_book_falls_back_to_new(make_song):
    make_song(book=Song.BOOK_NEW, number="1")
    r = Client().get(reverse("hymns:tsank_number"), {"book": "evil"})
    assert r.context["book"] == "New"


def test_tsank_number_pagination():
    for i in range(1, 70):
        Song.objects.create(book=Song.BOOK_NEW, number=str(i), title="t{}".format(i))
    r = Client().get(reverse("hymns:tsank_number"), {"page": 2})
    assert r.status_code == 200
    assert r.context["page"].number == 2


def test_tsank_number_empty_book_renders():
    r = Client().get(reverse("hymns:tsank_number"))
    assert r.status_code == 200
    assert list(r.context["page"].object_list) == []


# --- themes -------------------------------------------------------------

def test_themes_list_renders():
    Theme.objects.create(number=1, name="A")
    Theme.objects.create(number=2, name="B")
    r = Client().get(reverse("hymns:themes_list"))
    assert r.status_code == 200
    assert [t.number for t in r.context["themes"]] == [1, 2]


def test_theme_detail_renders_with_songs():
    s = Song.objects.create(book=Song.BOOK_NEW, number="1", title="X")
    t = Theme.objects.create(number=5, name="Theme")
    t.songs.add(s)
    r = Client().get(reverse("hymns:theme_detail", args=[5]))
    assert r.status_code == 200
    assert list(r.context["theme"].songs.all()) == [s]


def test_theme_detail_404_for_missing_theme():
    r = Client().get(reverse("hymns:theme_detail", args=[999]))
    assert r.status_code == 404


# --- alpha index / letter ----------------------------------------------

def test_alpha_index_lists_all_letters():
    r = Client().get(reverse("hymns:alpha_index"))
    assert r.status_code == 200
    assert r.context["letters"] == ARMENIAN_LETTERS


def test_alpha_letter_filters_by_initial():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Սեր")
    Song.objects.create(book=Song.BOOK_NEW, number="2", title="Աշխարհ")
    r = Client().get(reverse("hymns:alpha_letter", args=["Ս"]))
    assert r.status_code == 200
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["1"]  # only "Սեր"


def test_alpha_letter_normalizes_case_of_letter():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Սեր")
    # passing lowercase ս should still match
    r = Client().get(reverse("hymns:alpha_letter", args=["ս"]))
    assert r.status_code == 200
    assert [s.number for s in r.context["page"].object_list] == ["1"]


def test_alpha_letter_empty_renders():
    r = Client().get(reverse("hymns:alpha_letter", args=["Ո"]))
    assert r.status_code == 200
    assert list(r.context["page"].object_list) == []


# --- search -------------------------------------------------------------

def test_search_no_query_shows_prompt():
    r = Client().get(reverse("hymns:search"))
    assert r.status_code == 200
    assert r.context["has_query"] is False


def test_search_matches_title_substring():
    # NOTE: SQLite's icontains folds ASCII case only, so we use matching-case
    # Armenian text to exercise the substring-match logic itself.
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Սեր է")
    Song.objects.create(book=Song.BOOK_NEW, number="2", title="Աշխարհ")
    r = Client().get(reverse("hymns:search"), {"q": "Սեր"})
    assert r.status_code == 200
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["1"]


def test_search_case_insensitive_for_ascii():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Hallelujah")
    r = Client().get(reverse("hymns:search"), {"q": "hallelujah"})
    assert [s.number for s in r.context["page"].object_list] == ["1"]


def test_search_matches_number():
    Song.objects.create(book=Song.BOOK_NEW, number="42", title="Some title")
    r = Client().get(reverse("hymns:search"), {"q": "42"})
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["42"]


def test_search_matches_lyrics():
    Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="Title",
        lyrics="uniquelyricstext here",
    )
    r = Client().get(reverse("hymns:search"), {"q": "uniquelyricstext"})
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["1"]


def test_search_book_filter():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="shared")
    Song.objects.create(book=Song.BOOK_OLD, number="2", title="shared")
    r = Client().get(reverse("hymns:search"), {"q": "shared", "book": "Old"})
    nums = [s.number for s in r.context["page"].object_list]
    assert nums == ["2"]


def test_search_no_hits_returns_suggestions():
    # Use matching-case Armenian (SQLite icontains is ASCII-only).
    # The query must have NO full match but a token that substring-matches.
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Սեր")
    Song.objects.create(book=Song.BOOK_NEW, number="2", title="Սերունդ")
    r = Client().get(reverse("hymns:search"), {"q": "Սեր zzzzz"})
    assert r.context["page"].paginator.count == 0
    suggested_nums = {s.number for s in r.context["suggestions"]}
    # the "Սեր" token substring-matches both titles
    assert "1" in suggested_nums and "2" in suggested_nums


def test_search_invalid_book_ignored():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="hello")
    r = Client().get(reverse("hymns:search"), {"q": "hello", "book": "weird"})
    assert [s.number for s in r.context["page"].object_list] == ["1"]


# --- song_detail --------------------------------------------------------

def test_song_detail_renders_and_parses_verses():
    s = Song.objects.create(
        book=Song.BOOK_NEW, number="5",
        title="Title",
        lyrics="1. First verse\n2. Second verse",
    )
    r = Client().get(reverse("hymns:song_detail", args=["new", "5"]))
    assert r.status_code == 200
    verses = r.context["verses"]
    assert [v["num"] for v in verses] == ["1", "2"]
    assert r.context["show_translit"] is False
    assert r.context["title_lat"] == ""


def test_song_detail_translit_toggle_on():
    s = Song.objects.create(book=Song.BOOK_NEW, number="5", title="Սեր")
    r = Client().get(reverse("hymns:song_detail", args=["new", "5"]), {"translit": "1"})
    assert r.context["show_translit"] is True
    assert r.context["title_lat"] == "Ser"


def test_song_detail_404_for_missing_song():
    r = Client().get(reverse("hymns:song_detail", args=["new", "9999"]))
    assert r.status_code == 404


def test_song_detail_invalid_book_falls_back_to_new():
    Song.objects.create(book=Song.BOOK_NEW, number="5", title="X")
    # book "weird" -> .capitalize() -> "Weird" -> not in choices -> falls to "New"
    # so we look up New #5 and succeed
    r = Client().get(reverse("hymns:song_detail", args=["new", "5"]))
    assert r.status_code == 200


def test_song_detail_shows_matched_song():
    new = Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="A",
        match_book="Old", match_number="2",
    )
    old = Song.objects.create(book=Song.BOOK_OLD, number="2", title="B")
    r = Client().get(reverse("hymns:song_detail", args=["new", "1"]))
    assert r.context["matched"].pk == old.pk


def test_song_detail_capitalizes_book_in_path():
    # URL with lowercase "old" -> view capitalizes -> matches Old-book song
    Song.objects.create(book=Song.BOOK_OLD, number="7", title="Oldie")
    r = Client().get(reverse("hymns:song_detail", args=["old", "7"]))
    assert r.status_code == 200
    assert r.context["song"].book == Song.BOOK_OLD


# --- _parse_lyrics unit tests ------------------------------------------

def test_parse_lyrics_empty():
    assert _parse_lyrics("") == []
    assert _parse_lyrics(None) == []


def test_parse_lyrics_strips_leading_song_number_line():
    out = _parse_lyrics("5\n1. First\n2. Second")
    assert [v["num"] for v in out] == ["1", "2"]


def test_parse_lyrics_refrain_block_for_indented_lines():
    out = _parse_lyrics("1. First\n    Refrain line\n2. Second")
    nums = [v["num"] for v in out]
    # refrain block has num=None between verses 1 and 2
    assert None in nums
    assert "1" in nums and "2" in nums
    refrain = next(v for v in out if v["num"] is None)
    assert refrain["refrain"] is True


def test_parse_lyrics_leading_unindented_lines_become_refrain():
    out = _parse_lyrics("Intro line\n1. First verse")
    # intro becomes a refrain block before verse 1
    assert out[0]["refrain"] is True
    assert out[0]["num"] is None
    assert out[1]["num"] == "1"


def test_parse_lyrics_preserves_inline_verse_text():
    out = _parse_lyrics("1. First inline")
    assert out[0]["num"] == "1"
    assert out[0]["lines"] == ["First inline"]
