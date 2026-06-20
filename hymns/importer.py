"""
Data ingestion for the hymns app.

Two paths share the same Song upsert logic:
  * JSON  (active now)  - reads REDergaran.json / wordSongsIndex.json /
                          AllLyrics.json / temmas.json from the data dir.
  * DOCX (ready, later) - reads .docx files whose text is laid out as
                          "[songnum] [lyrics]", producing the same shape.

All writes are idempotent upserts keyed on (book, number), so re-running
the importer (also via the in-app scheduler) safely refreshes the DB.
"""
import ast
import json
import os
import re
from datetime import datetime

from .models import Song, Theme, Service, ServiceSong


THEME_NAMES = [
    "ԱՍՏՎԱԾ",
    "ՍՈՒՐԲ ՀՈԳԻ",
    "ՀԱՎԱՏՔ ԵՎ ՎՍՏԱՀՈւԹՅՈւՆ",
    "ՔԱՋՈւԹՅՈւՆ ԵՎ ՀԱՂԹՈւԹՅՈւՆ",
    "ՈւՐԱԽՈւԹՅՈւՆ ԵՎ ՑՆԾՈւԹՅՈւՆ",
    "ՊՍԱԿ, ՀԱՐՍԱՆԻՔ, ԸՆՏԱՆԻՔ ԵՎ ՀԱՐՍ ԵԿԵՂԵՑԻ",
    "ՄԱՆԿԱՆՑ ԵՐԳԵՐ",
    "ՍՈւՐԲ ԾՆՈւՆԴ",
    "ՀԻՍՈւՍ ՔՐԻՍՏՈՍ",
    "ԲԱՐԻ ՀՈՎԻՎ",
    "ՀԱՂՈՐԴՈւԹՅՈւՆ (ոտնլվա)",
    "ՉԱՐՉԱՐԱՆՔ, ԽԱՉ, ՄԱՀ",
    "ԱՐՅՈւՆ, ՔԱՎՈւԹՅՈւՆ ԵՎ ԹՈՂՈւԹՅՈւՆ",
    "ՍՐԲՈւԹՅՈւՆ",
    "ԵՂԲԱՅՐԱՍԻՐՈւԹՅՈւՆ",
    "ՇԱՐԱԿԱՆՆԵՐ",
    "ՀԱՐՈւԹՅՈւՆ",
    "ՇՆՈՐՀՔ",
    "ՀՈԳԵՎՈՐ ՓՈՐՁՈւԹՅՈւՆ, ՊԱՅՔԱՐ, ՊԱՏԵՐԱԶՄ",
    "ԱՊԱՇԽԱՐՈւԹՅՈւՆ, ԶՂՋՈւՄ, ԴԱՐՁ",
    "ՄԱՀ, ՀԱՎԻՏԵՆՈւԹՅուՆ",
    "ԳԱԼՈւՍՏ",
    "ԱՎԵՏԱՐԱՆՉՈւԹՅուՆ",
    "ՓԱՌԱԲԱՆՈՒԹ. ԵՐԿՐՊԱԳՈւԹ. ՊԱՇՏԱՄՈՒՆՔ",
    "ՔՐԻՍՏՈՆԵԱԿԱՆ ԿՅԱՆՔ",
    "ՍԵՐ",
    "ՀՐԱՎԵՐ, ՀՈՐԴՈՐ",
    "ԱՂՈԹՔ, ԽՆԴՐՎԱԾՔ",
    "ԱՍՏԾՈ ԽՈՍՔ",
]


def normalize_book(book):
    if not book:
        return ""
    b = book.strip().lower()
    if b in ("old", "wordsongs", "wordsongsindex"):
        return Song.BOOK_OLD
    return Song.BOOK_NEW


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _meta_field(entry, *keys):
    for k in keys:
        if k in entry and entry[k] not in (None, ""):
            return _clean(entry[k])
    return ""


def _parse_match(match):
    """match is like [["old", "1", 0.97]] -> ("Old", "1", 0.97) or empties."""
    if not match:
        return "", "", None
    try:
        m = match[0]
        return normalize_book(m[0]), _clean(m[1]), float(m[2])
    except (IndexError, ValueError, TypeError):
        return "", "", None


def upsert_song(book, number, **fields):
    number = _clean(number)
    if not number:
        return None, False
    defaults = {
        "title": fields.get("title", ""),
        "title_display": fields.get("title_display", ""),
        "lyrics": fields.get("lyrics", ""),
        "key": fields.get("key", ""),
        "speed": fields.get("speed", ""),
        "style": fields.get("style", ""),
        "song_type": fields.get("song_type", ""),
        "time_sig": fields.get("time_sig", ""),
        "comments": fields.get("comments", ""),
        "match_book": fields.get("match_book", ""),
        "match_number": fields.get("match_number", ""),
        "match_score": fields.get("match_score"),
    }
    obj, created = Song.objects.update_or_create(
        book=book, number=number, defaults=defaults
    )
    return obj, created


def _load_index(path, book):
    """Read a REDergaran/wordSongsIndex file and upsert metadata for one book."""
    created = 0
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    songs = data.get("SongNum", {})
    for num, entry in songs.items():
        num = _clean(num)
        if not num.isdigit():
            continue
        if not isinstance(entry, dict):
            continue
        mb, mn, ms = _parse_match(entry.get("match"))
        upsert_song(
            book,
            num,
            title=entry.get("Title", "") or "",
            key=_meta_field(entry, "key"),
            speed=_meta_field(entry, "speed"),
            style=_meta_field(entry, "style"),
            song_type=_meta_field(entry, "song_type"),
            time_sig=_meta_field(entry, "timeSig", "time_sig"),
            comments=_meta_field(entry, "Comments", "Comment"),
            match_book=mb,
            match_number=mn,
            match_score=ms,
        )
        created += 1
    return created


def _load_lyrics(path):
    """Read AllLyrics.json and attach lyrics to existing songs."""
    attached = 0
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for which, book in (("new", Song.BOOK_NEW), ("old", Song.BOOK_OLD)):
        for num, lyrics in (data.get(which) or {}).items():
            updated = Song.objects.filter(book=book, number=_clean(num)).update(
                lyrics=lyrics or ""
            )
            attached += updated
    return attached


def _load_themes(path):
    """temmas.json: array of 29 strings -> theme[i] gets the listed New songs."""
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    linked = 0
    for i, name in enumerate(THEME_NAMES, start=1):
        theme, _ = Theme.objects.update_or_create(number=i, defaults={"name": name})
        theme.songs.clear()
        blob = raw[i - 1] if i - 1 < len(raw) else ""
        if not blob:
            continue
        chunks = re.split(r"<\s*br\s*/?>", blob)
        numbers = set()
        for chunk in chunks:
            nums = re.findall(r"\d+", re.sub(r"</?\w+>", "", chunk))
            if nums:
                numbers.add(_clean(nums[-1]))
        for number in numbers:
            song = Song.objects.filter(book=Song.BOOK_NEW, number=number).first()
            if song:
                theme.songs.add(song)
                linked += 1
    return linked


_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})")


def _load_services(path):
    """songs.json: service history (optional, non-fatal)."""
    created = links = 0
    if not os.path.exists(path):
        return 0, 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for filename, entry in data.items():
        song_list_str = entry.get("songList", "[]")
        try:
            tuples = ast.literal_eval(song_list_str) if song_list_str else []
        except (ValueError, SyntaxError):
            tuples = []
        date = None
        m = _DATE_RE.match(filename)
        if m:
            mm, dd, yy = m.groups()
            year = 2000 + int(yy) if int(yy) < 50 else 1900 + int(yy)
            try:
                date = datetime(year, int(mm), int(dd)).date()
            except ValueError:
                date = None
        svc, svc_created = Service.objects.get_or_create(
            filename=filename,
            defaults={"date": date, "base_path": entry.get("basePth", "")},
        )
        if svc_created:
            created += 1
        for idx, (book, num) in enumerate(tuples):
            song = Song.objects.filter(book=normalize_book(book), number=_clean(num)).first()
            if song:
                _, did = ServiceSong.objects.get_or_create(
                    service=svc, song=song, defaults={"position": idx}
                )
                links += int(did)
    return created, links


def import_json(data_dir):
    """Full JSON load: metadata + lyrics + themes + (optional) services."""
    stats = {}
    stats["new_meta"] = _load_index(os.path.join(data_dir, "REDergaran.json"), Song.BOOK_NEW)
    stats["old_meta"] = _load_index(os.path.join(data_dir, "wordSongsIndex.json"), Song.BOOK_OLD)
    stats["lyrics"] = _load_lyrics(os.path.join(data_dir, "AllLyrics.json"))
    stats["themes_linked"] = _load_themes(os.path.join(data_dir, "temmas.json"))
    svc_c, svc_l = _load_services(os.path.join(data_dir, "songs.json"))
    stats["services"] = svc_c
    stats["service_links"] = svc_l
    return stats


# --- DOCX path (forward-looking) -----------------------------------------

def parse_docx_songs(text):
    """
    Parse docx-as-text laid out as `[songnum] [lyrics]`.

    A song boundary is a line containing only a number (the song number);
    everything until the next boundary is that song's lyrics. Returns a list
    of (number, lyrics) tuples.
    """
    songs = []
    current_num = None
    buf = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.fullmatch(r"\d{1,4}", stripped):
            if current_num is not None:
                songs.append((current_num, "\n".join(buf).strip()))
            current_num = stripped
            buf = []
        elif current_num is not None and stripped:
            buf.append(stripped)
    if current_num is not None:
        songs.append((current_num, "\n".join(buf).strip()))
    return songs


def import_docx_text(text, book):
    """Upsert songs parsed from a docx text blob into the given book."""
    count = 0
    for number, lyrics in parse_docx_songs(text):
        obj = Song.objects.filter(book=book, number=number).first()
        if obj:
            obj.lyrics = lyrics
            obj.save(update_fields=["lyrics", "updated_at"])
        else:
            Song.objects.create(book=book, number=number, title=lyrics.split("\n")[0][:300], lyrics=lyrics)
        count += 1
    return count


def import_docx_file(path, book):
    from docx import Document
    doc = Document(path)
    text = "\n".join(p.text for p in doc.paragraphs)
    return import_docx_text(text, book)
