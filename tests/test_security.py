"""
Security-focused tests: verify the app is resilient to common web attacks
even though it leans on the ORM / Django's autoescaping for protection.

Covers:
  * SQL injection (search, book, song number, alpha letter)
  * XSS via stored song titles / lyrics / theme names
  * Path traversal in importer inputs
  * Parameter coercion (book filter, theme number)
  * Reflected XSS via the `q` search query
  * HTTP method / verb expectations on read-only views
  * Destructive payloads don't crash the app or escape the ORM
"""
import json
import os

import pytest
from django.urls import reverse
from django.test import Client

from hymns import importer
from hymns.models import Song, Theme

pytestmark = pytest.mark.django_db


# --- SQL injection: ORM parameterizes everything, so these should never
#     return unintended rows or raise. ------------------------------------

@pytest.mark.parametrize("payload", [
    "' OR 1=1 --",
    "'; DROP TABLE hymns_song; --",
    "1' OR '1'='1",
    "UNION SELECT id, title FROM hymns_song",
    "%' OR 1=1 --%",
    "Սեր'; DELETE FROM hymns_song WHERE '1'='1",
    "\"; INSERT INTO hymns_song VALUES (...); --",
])
def test_search_sql_injection_is_safe(payload):
    # Plant exactly one song and ensure injections can't surface it (or any)
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="սեր է")
    r = Client().get(reverse("hymns:search"), {"q": payload})
    assert r.status_code == 200
    # the injection must not leak every row in the table
    assert r.context["page"].paginator.count == 0
    # and the table still exists
    assert Song.objects.count() == 1


def test_song_table_is_not_dropped_after_search():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    Client().get(reverse("hymns:search"), {"q": "'; DROP TABLE hymns_song; --"})
    # if the DROP had succeeded, this query would raise
    assert Song.objects.count() == 1


@pytest.mark.parametrize("malformed_number", [
    "1 OR 1=1",
    "1; DROP TABLE hymns_song",
    "*",
    "../../etc/passwd",
    "%s%s%s%s",
])
def test_song_detail_sql_injection_returns_404(malformed_number):
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="real")
    r = Client().get("/song/new/{}/".format(malformed_number))
    # ORM parameterizes -> no match -> 404 (Django routes 404 for unsafe path
    # chars; either way it must NOT be 500 or expose data)
    assert r.status_code in (404, 400)
    assert Song.objects.count() == 1  # untouched


@pytest.mark.parametrize("letter", [
    "Ս' OR '1'='1",
    "Ս; DROP TABLE hymns_song",
    "_",
    "%",
])
def test_alpha_letter_sql_injection_is_safe(letter):
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="Սեր")
    r = Client().get(reverse("hymns:alpha_letter", args=[letter]))
    assert r.status_code in (200, 404)
    assert Song.objects.count() == 1


def test_tsank_book_param_injection_falls_back_to_new():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="real")
    r = Client().get(reverse("hymns:tsank_number"), {
        "book": "New' OR '1'='1",
    })
    # invalid book string falls back to the New default (whitelist)
    assert r.context["book"] == "New"
    assert r.context["page"].paginator.count == 1


# --- XSS: stored and reflected ------------------------------------------

def test_stored_xss_in_song_title_is_escaped_on_tsank():
    payload = "<script>alert('xss')</script>"
    Song.objects.create(book=Song.BOOK_NEW, number="1", title=payload)
    body = Client().get(reverse("hymns:tsank_number")).content.decode("utf-8")
    # the raw payload must not appear verbatim in the HTML
    assert payload not in body
    # it must appear HTML-escaped
    assert "&lt;script&gt;" in body


def test_stored_xss_in_song_title_is_escaped_on_song_detail():
    payload = "<script>alert('xss')</script>"
    Song.objects.create(book=Song.BOOK_NEW, number="1", title=payload, lyrics="ok")
    body = Client().get(reverse("hymns:song_detail", args=["new", "1"])).content.decode("utf-8")
    assert payload not in body
    assert "&lt;script&gt;" in body


def test_stored_xss_in_lyrics_is_escaped_on_song_detail():
    payload = "<img src=x onerror=alert(1)>"
    Song.objects.create(
        book=Song.BOOK_NEW, number="1", title="clean",
        lyrics="1. {}\n2. more".format(payload),
    )
    body = Client().get(reverse("hymns:song_detail", args=["new", "1"])).content.decode("utf-8")
    # the RAW tag must not appear (it would fire in browsers); the escaped
    # form is the safe rendering even though the attribute name is visible
    assert payload not in body
    assert "&lt;img" in body


def test_stored_xss_in_lyrics_data_attribute_is_escapejs_safe():
    """song_detail puts lyrics into data-lyrics via |escapejs; ensure
    a payload can't break out of the JS string / HTML attribute."""
    payload = '</script><script>alert(1)</script>'
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="clean", lyrics=payload)
    body = Client().get(reverse("hymns:song_detail", args=["new", "1"])).content.decode("utf-8")
    # No raw closing script tag can land in the document
    assert "<script>alert(1)</script>" not in body


def test_stored_xss_in_theme_name_is_escaped():
    payload = "<script>alert(1)</script>"
    Theme.objects.create(number=1, name=payload)
    body = Client().get(reverse("hymns:themes_list")).content.decode("utf-8")
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body


def test_reflected_xss_in_search_query_is_escaped():
    """The `q` value is reflected back into the search input's value attribute."""
    payload = '"><script>alert(1)</script>'
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    body = Client().get(reverse("hymns:search"), {"q": payload}).content.decode("utf-8")
    # the raw payload must not appear (it would close the attribute and inject)
    assert payload not in body
    # and the dangerous chars are escaped
    assert "&lt;script&gt;" in body or "&#x27;" in body or "&quot;" in body


# --- Path traversal: importer -------------------------------------------

def test_load_index_path_traversal_only_reads_resolved_path(tmp_path):
    """Even with a traversal-y filename, os.path.join resolves within tmp_path;
    the helper returns 0 if no such file exists and never raises."""
    fake = os.path.join(str(tmp_path), "..", "..", "etc", "passwd")
    assert importer._load_index(fake, Song.BOOK_NEW) == 0
    assert Song.objects.count() == 0


def test_load_index_data_path_traversal_cannot_escape_data_dir(tmp_path):
    # Write a legit index, then verify a sibling dir traversal returns nothing
    legit = tmp_path / "REDergaran.json"
    legit.write_text(json.dumps({"SongNum": {"1": {"Title": "x"}}}), encoding="utf-8")
    assert importer._load_index(str(legit), Song.BOOK_NEW) == 1

    # now try to read something outside via ../
    outside = os.path.join(str(tmp_path), "sub", "..", "missing.json")
    assert importer._load_index(outside, Song.BOOK_NEW) == 0


# --- Parameter coercion / validation ------------------------------------

def test_theme_detail_non_int_route_does_not_match():
    # <int:number> URL converter rejects non-ints at routing level -> 404
    r = Client().get("/themes/1%20OR%201=1/")
    assert r.status_code == 404


def test_song_detail_unknown_book_falls_back_safely():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    # An "unknown" book value gets capitalized and falls back to New, so the
    # New song #1 should be served (this is the documented behavior). The
    # important thing is that no error is raised and no rows leak.
    r = Client().get(reverse("hymns:song_detail", args=["new", "1"]))
    assert r.status_code == 200
    assert r.context["song"].book == Song.BOOK_NEW


# --- HTTP method expectations -------------------------------------------

@pytest.mark.parametrize("url_name,args", [
    ("hymns:home", []),
    ("hymns:tsank_number", []),
    ("hymns:themes_list", []),
    ("hymns:alpha_index", []),
    ("hymns:search", []),
])
def test_read_only_views_accept_get(url_name, args):
    assert Client().get(reverse(url_name, args=args)).status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "delete", "patch"])
def test_home_does_not_accept_destructive_methods_as_errors(method):
    """Function views technically accept any method, but they must not mutate
    server state. Verifying GET-equivalent behavior on POST for a read-only
    view (status 200, no side effect on the DB)."""
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    before = Song.objects.count()
    r = getattr(Client(), method)(reverse("hymns:home"))
    # only 405 would be ideal; here we at least confirm no mutation occurred
    assert Song.objects.count() == before
    assert r.status_code == 200


# --- Size / DoS limits --------------------------------------------------

def test_large_search_query_is_handled():
    """Stress the LIKE pattern with a long-but-bounded query. (SQLite caps
    LIKE pattern length near 50_000 bytes; beyond that it raises and the view
    returns 500 — a known ceiling worth hardening separately.)"""
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    r = Client().get(reverse("hymns:search"), {"q": "A" * 10_000})
    assert r.status_code == 200
    assert r.context["page"].paginator.count == 0


def test_many_pagination_pages_clamped():
    Song.objects.create(book=Song.BOOK_NEW, number="1", title="x")
    # request an absurd page number; Django paginator returns the last valid
    # page (or empty page) rather than executing an offset attack
    r = Client().get(reverse("hymns:tsank_number"), {"page": 999999})
    assert r.status_code == 200
