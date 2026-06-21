# Հայ Երգարան — Armenian Pentecostal Worship Lyrics

A Django site to browse, search, and read Armenian Pentecostal worship
lyrics from two collections:

- **Կարմիր Երգարան (Red Hymnal)** — the New book (`REDergaran.json`)
- **Word Songs** — the older collection (`wordSongsIndex.json`)

## Features
- **Դասականգ (Tsank)** — songs by number
- **Թեմաներ (Themes)** — 29 thematic sections (New book, from `temmas.json`)
- **Այբենական (Alphabetical)** — by Armenian initial letter
- **Որոնում (Search)** — across titles, lyrics, and numbers
- **Song page** — numbered verses, refrain offset, NEW/OLD badge, cross-book
  match link, music metadata, copy/print, and a Western-Armenian
  transliteration toggle
- Two books clearly distinguished; matched songs cross-linked via the
  `match` field
- Polished Django admin for content management
- Email/password accounts via django-allauth

## Stack
Django + SQLite · django-allauth · a tiny threading-based in-app
scheduler (`run_scheduler` management command) · Gunicorn behind Nginx.
Typography: GHEA Mariam (serif) + GHEA Grapalat (sans), self-hosted.

## Layout
The project is intentionally flat — `manage.py` and the `arm_songs/`
config package live at this top level (no extra nesting).

```
arm_songs/
  manage.py
  arm_songs/            # project config (settings/urls/wsgi)
  hymns/                # the app (models, views, importer, tasks, admin)
  data/                 # JSON source data (imported into SQLite)
  templates/            # base layout
  static/               # css, fonts, js
  deploy/               # gunicorn / scheduler / nginx / env configs
```

## Local development
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_songs          # load JSON data into SQLite
python manage.py createsuperuser       # admin access
python manage.py runserver
```

## Importing / refreshing data
The importer is idempotent (safe to re-run):
```bash
python manage.py import_songs          # reads data/*.json
```
It handles the messy bits in `temmas.json` (`<br>` splits, HTML artifacts,
duplicate numbers) and links New-book songs to the 29 themes. The
DOCX-ready path (`hymns/importer.py::import_docx_file`) will ingest real
`.docx` files laid out as `[songnum] [lyrics]` once they are available.

### In-app scheduler (threading)
A single background thread re-runs the importer on a fixed interval — no
extra database tables, no separate worker cluster.
```bash
python manage.py run_scheduler              # foreground, every 30 min
python manage.py run_scheduler --minutes 15 # custom interval
python manage.py run_scheduler --once       # single run, then exit
```
In production `run_scheduler` runs as its own service (see
`deploy/scheduler.service`).

## Production deploy
```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/
sudo cp deploy/scheduler.service /etc/systemd/system/
sudo cp deploy/nginx.conf /etc/nginx/sites-available/arm_songs
sudo ln -s /etc/nginx/sites-available/arm_songs /etc/nginx/sites-enabled/
python manage.py collectstatic --noinput
sudo systemctl enable --now gunicorn scheduler
sudo systemctl reload nginx
```
Edit `deploy/*.service` and `deploy/nginx.conf` to match your paths/domain,
and create `/srv/arm_songs/.env` from `deploy/env.example`.

## Fonts
GHEA Mariam and GHEA Grapalat are free for commercial use
(official Republic of Armenia fonts by Edik Ghabuzyan, via fonter.am),
vendored in `static/fonts/`.
