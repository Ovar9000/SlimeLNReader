# Local PDF Reader

A local, plug-and-play PDF reading app for desktop browsers. Drop in any PDF and read it three ways: reflowable text, page-flip book, or continuous scroll. No account, no uploads, everything runs on `localhost`.

---

## How to Run

Requirements: Python 3 with `pymupdf` installed (`pip install pymupdf`).

### Quick Start (Windows)

Double-click:

```bat
start_viewer.bat
```

or run from terminal:

```bash
python run_viewer.py
```

This starts the local server and opens the reader at **`http://127.0.0.1:8080`**.

### Use Any PDF

1. Copy any PDF next to `server.py` and name it `document.pdf`.
2. (Recommended) Generate `static/book_data.json` so Reader mode and offline search work:

```bash
python -c "import json, pymupdf; doc=pymupdf.open('document.pdf'); p0=doc[0]; json.dump({'title':'Local Document','shortTitle':'Document','totalPages':len(doc),'pageWidth':round(p0.rect.width,2),'pageHeight':round(p0.rect.height,2),'aspectRatio':round(p0.rect.width/p0.rect.height,4),'toc':[],'pages':[pg.get_text() for pg in doc]}, open('static/book_data.json','w',encoding='utf-8'), ensure_ascii=False)"
```

Without `book_data.json`, the app still works: pages render from the PDF via the local server and search uses the live `/api/search` endpoint.

PDFs and extracted text are git-ignored sample data placeholders only. Bring your own files.

### Optional: App Window Mode

Run without browser chrome:

```bash
python run_viewer.py --app
```

---

## Features

- **Reader Mode (default)**: extracted PDF text rendered as large, selectable, reflowable pages. Adjustable font size, column width, line-density presets, secondary-line toggle, and serif/sans switch. Pages without extractable text fall back to the scanned image.
- **Flipbook Mode**: page-flip book view of the original PDF pages. Single-page by default, optional two-page spread.
- **Scroll Mode**: continuous vertical reading of the original PDF pages with lazy loading.
- **Performance**: sliding render window plus disk and memory caching keep large documents responsive.
- **Table of Contents**: jump list when the document defines sections.
- **Thumbnails**: bottom tray with lazy-loaded page previews and instant jump.
- **Full-text search**: results with highlighted snippets; works offline from `book_data.json` or live via the server.
- **Bookmarks and resume**: per-page bookmarks plus automatic last-position restore.
- **Themes**: dark, warm, pure-black, and light paper options.
- **Zoom and pan**: button, Ctrl+wheel, and drag controls up to 250%.
- **Auto-flip**: optional timed page advance.
- **Page sounds**: optional synthesized page-turn sound.

---

## Ask the Book (optional reading companion)

A floating `?` button opens a chat scoped to your exact page: summaries, recaps,
stat/location lookups, and theories — with a hard no-spoilers rule (nothing past
your current page is ever retrieved or revealed). Runs fully local except the
Gemini API calls. Requires Docker (Weaviate) + a Gemini key; the reader works
fine without it.

```bash
pip install "weaviate-client>=4,<5>"
# key via env GEMINI_API_KEY or untracked secrets.local.json (never commit it)
docker run -d --name slime-weaviate --restart unless-stopped -p 8081:8080 -p 50051:50051 \
  -e QUERY_DEFAULTS_LIMIT=20 -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate -v slime-weaviate-data:/var/lib/weaviate \
  semitechnologies/weaviate:1.39.5
python -m askbook.ingest_novel            # novel chunks + character-state extraction
python -m askbook.ingest_wiki --fetch-only # cache wiki pages (no API use)
python -m askbook.ingest_wiki --ingest     # wiki chunks + extraction
python -m askbook.test_acceptance          # deterministic checks (no API use)
python -m askbook.test_acceptance --live   # end-to-end (needs data + quota)
```

`POST /api/ask` with `{page, question, history?}` returns `{answer, intent, entities}`.
Ingestion is resumable (re-run safely) and `python -m askbook.dedupe --apply`
cleans any duplicate rows.

---

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| `→` / `D` / `PageDown` / `Space` | Next Page |
| `←` / `A` / `PageUp` | Previous Page |
| `Home` / `End` | Jump to First / Last Page |
| `F` | Toggle Fullscreen |
| `T` | Open Table of Contents |
| `S` | Open Full-Text Search |
| `B` | Open Bookmarks |
| `M` | Cycle Reading Mode (Reader → Flipbook → Scroll) |
| `J` | Toggle secondary text lines (Reader mode) |
| `+` / `-` | Reader: font size · PDF modes: zoom |
| `0` | Reset Zoom (100%) |
| `Esc` | Close Open Drawers / Reset Zoom |
