import re

from django.db.models import Q, IntegerField
from django.db.models.functions import Cast
from django.shortcuts import get_object_or_404, render
from django.core.paginator import Paginator

from .models import Song, Theme
from .transliteration import transliterate


ARMENIAN_LETTERS = [
    "Ա", "Բ", "Գ", "Դ", "Ե", "Զ", "Է", "Ը", "Թ", "Ժ", "Ի", "Լ", "Խ", "Ծ",
    "Կ", "Հ", "Ձ", "Ղ", "Ճ", "Մ", "Յ", "Ն", "Շ", "Ո", "Չ", "Պ", "Ջ", "Ս",
    "Վ", "Տ", "Ց", "ՈՒ", "Փ", "Ք", "ԵՒ", "Օ",
]

PER_PAGE = 60


def _numeric():
    return Cast("number", output_field=IntegerField())


def home(request):
    new_qs = Song.objects.filter(book=Song.BOOK_NEW)
    old_qs = Song.objects.filter(book=Song.BOOK_OLD)
    counts = {
        "new": new_qs.count(),
        "old": old_qs.count(),
        "themes": Theme.objects.count(),
    }
    featured = (
        Song.objects.only("book", "number", "title_display", "title")
        .order_by("?")[:6]
    )
    return render(request, "hymns/home.html", {
        "counts": counts,
        "featured": featured,
    })


def tsank_number(request):
    book = request.GET.get("book", "New")
    if book not in (Song.BOOK_NEW, Song.BOOK_OLD):
        book = Song.BOOK_NEW
    qs = (
        Song.objects.filter(book=book)
        .annotate(num=_numeric())
        .order_by("num")
        .only("book", "number", "title_display", "title")
    )
    page = Paginator(qs, PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "hymns/tsank_number.html", {
        "page": page, "book": book, "book_label": dict(Song.BOOK_CHOICES)[book],
    })


def themes_list(request):
    themes = Theme.objects.all()
    return render(request, "hymns/themes_list.html", {"themes": themes})


def theme_detail(request, number):
    theme = get_object_or_404(Theme, number=number)
    songs = (
        theme.songs.all()
        .annotate(num=_numeric())
        .order_by("num")
        .only("book", "number", "title_display", "title")
    )
    return render(request, "hymns/theme_detail.html", {"theme": theme, "songs": songs})


def alpha_index(request):
    book = request.GET.get("book", Song.BOOK_NEW)
    if book not in (Song.BOOK_NEW, Song.BOOK_OLD):
        book = Song.BOOK_NEW
    return render(request, "hymns/alpha_index.html", {
        "letters": ARMENIAN_LETTERS,
        "book": book,
        "book_label": dict(Song.BOOK_CHOICES)[book],
    })


def alpha_letter(request, letter):
    book = request.GET.get("book", Song.BOOK_NEW)
    if book not in (Song.BOOK_NEW, Song.BOOK_OLD):
        book = Song.BOOK_NEW
    # normalize alternate forms (e.g. ՈՒ / ու / Ու)
    norm = letter.upper()
    qs = (
        Song.objects.filter(book=book, title__istartswith=norm)
        .annotate(num=_numeric())
        .order_by("num")
        .only("book", "number", "title_display", "title")
    )
    page = Paginator(qs, PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "hymns/alpha_letter.html", {
        "page": page, "letter": letter, "letters": ARMENIAN_LETTERS,
        "book": book, "book_label": dict(Song.BOOK_CHOICES)[book],
    })


def search(request):
    q = request.GET.get("q", "").strip()
    book = request.GET.get("book", "")
    results = Song.objects.none()
    suggestions = []
    if q:
        qs = Song.objects.filter(
            Q(title__icontains=q) | Q(lyrics__icontains=q) | Q(number__icontains=q)
        )
        if book in (Song.BOOK_NEW, Song.BOOK_OLD):
            qs = qs.filter(book=book)
        results = (
            qs.annotate(num=_numeric())
            .order_by("book", "num")
            .only("book", "number", "title_display", "title")
        )
    page = Paginator(results, PER_PAGE).get_page(request.GET.get("page"))

    # Did-you-mean: on no hits, offer loose title matches (across both books).
    if q and not page.object_list:
        tokens = [t for t in re.split(r"\W+", q) if len(t) >= 2]
        loose = Song.objects.none()
        for tok in tokens:
            loose |= Song.objects.filter(title__icontains=tok)
        seen = set()
        for s in loose.annotate(num=_numeric()).order_by("num")[:8]:
            key = (s.book, s.number)
            if key in seen:
                continue
            seen.add(key)
            suggestions.append(s)

    return render(request, "hymns/search.html", {
        "page": page, "q": q, "book": book, "has_query": bool(q),
        "count": page.paginator.count, "suggestions": suggestions,
    })


_VERSE_RE = re.compile(r"^\s*(\d+)\s*[.):]\s*(.*)$")


def _parse_lyrics(raw):
    """
    Split raw lyrics into ordered blocks.
    Returns list of {"num": str|None, "lines": [str,...], "refrain": bool}.
    A numbered line starts a new verse; leading/un-numbered lines form a
    refrain block (refrain=True).
    """
    if not raw:
        return []
    lines = raw.splitlines()
    # drop a leading standalone song-number line
    while lines and re.fullmatch(r"\s*-{0,2}\d{1,4}\s*", lines[0]):
        lines.pop(0)

    blocks = []
    current = None
    for line in lines:
        if not line.strip():
            continue
        m = _VERSE_RE.match(line)
        if m:
            current = {"num": m.group(1), "lines": [], "refrain": False}
            if m.group(2).strip():
                current["lines"].append(m.group(2).strip())
            blocks.append(current)
        else:
            is_refrain = line.startswith(("    ", "\t")) or current is None
            if current is None or is_refrain and current.get("num") is not None:
                current = {"num": None, "lines": [], "refrain": True}
                blocks.append(current)
            current["lines"].append(line.strip())
    return blocks


def song_detail(request, book, number):
    book = book.strip().capitalize()
    if book not in (Song.BOOK_NEW, Song.BOOK_OLD):
        book = Song.BOOK_NEW
    song = get_object_or_404(Song, book=book, number=str(number))
    matched = song.matched_song()
    show_translit = request.GET.get("translit") == "1"

    verses = _parse_lyrics(song.lyrics)
    if show_translit:
        for v in verses:
            v["lines"] = [transliterate(ln) for ln in v["lines"]]

    title_arm = song.display_title()
    title_lat = transliterate(title_arm) if show_translit else ""

    return render(request, "hymns/song_detail.html", {
        "song": song,
        "verses": verses,
        "matched": matched,
        "show_translit": show_translit,
        "title_lat": title_lat,
    })
