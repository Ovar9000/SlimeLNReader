# 📖 Tensura Volume 22 — AnyFlip / FlipHTML5 Local Viewer

An **AnyFlip / FlipHTML5** style digital flipbook reader built for smooth and immersive reading of **That Time I Got Reincarnated as a Slime — Volume 22: Godly Destruction and Chaos** (586 pages).

---

## 🚀 How to Run

### Quick Start (Windows)
Double-click:
```bat
start_viewer.bat
```
or run from terminal:
```bash
python run_viewer.py
```
This starts the local caching server and automatically opens your web browser to **`http://127.0.0.1:8080`**.

### 📂 Supply your own files (PDF + text data are git-ignored)
The novel PDF and extracted text are **not committed** to this repo. To run locally:

1. Place your PDF next to `server.py` as `Volume_22_MTL.pdf`.
2. (Recommended) Generate `static/book_data.json` for Reader mode + offline search:
```bash
python -c "import json, pymupdf; doc=pymupdf.open('Volume_22_MTL.pdf'); p0=doc[0]; json.dump({'title':'That Time I Got Reincarnated as a Slime - Volume 22: Godly Destruction and Chaos','shortTitle':'Tensura Vol 22','totalPages':len(doc),'pageWidth':round(p0.rect.width,2),'pageHeight':round(p0.rect.height,2),'aspectRatio':round(p0.rect.width/p0.rect.height,4),'toc':[{'title':'Prologue: Pure Malice (純粋な悪意)','page':1},{'title':'Chapter 1: The Lord of Vice (悪徳の王)','page':11},{'title':'Chapter 2: Time of Despair (絶望の時)','page':167},{'title':'Chapter 3: The Apex's Showdown (頂上決戦)','page':306},{'title':'Epilogue: Evil God Awakening (邪神覚醒)','page':583}],'pages':[pg.get_text() for pg in doc]}, open('static/book_data.json','w',encoding='utf-8'), ensure_ascii=False)"
```
Without `book_data.json`, Reader mode shows the original scans and search falls back to the live `/api/search` backend (requires the PDF + server running).

### Optional: Standalone App Window Mode
To launch the reader inside a native desktop app window without browser tabs or URL bars:
```bash
python run_viewer.py --app
```

---

## ✨ Features

- **📖 Reflowable Reader Mode (default, recommended)**: Solves the "it's a PDF" problem — instead of tiny fixed scan images, extracted text is rendered large, selectable, and reflowable like Kindle/EPUB. Includes A−/A+ font size, narrow/comfortable/wide column, JP original line toggle, serif/sans switch, chapter header, and progress bar. Illustration pages fall back to the original scan with one click.
- **📖 3D Realistic Page-Flip Animation**: Real paper curling, dynamic drop shadows, book spine curvature, and realistic depth stack edges (original PDF scans, now single-page by default for 2× larger text, sharper 180 DPI).
- **📜 Triple Reading Modes**: Switch seamlessly between:
  - **Reader Mode**: Large reflowable bilingual text (default).
  - **Flipbook Mode**: Interactive 3D physical book (1-page default, 2-page optional).
  - **Continuous Scroll Mode**: Vertical flow reading (webtoon style) with smooth scrolling and live page indicators.
- **⚡ High-Performance Virtualization & Memory Management**:
  - Handles all **586 pages** smoothly.
  - Active sliding window renders only visible and adjacent pages, unloading distant pages to keep RAM usage under 60MB.
  - Disk and memory caching ensures instant, zero-delay flipping.
- **🔊 Realistic Page Turn Sound**: Synthesized on-the-fly via Web Audio API (toggleable in toolbar).
- **📑 Table of Contents**:
  - *Prologue: Pure Malice (純粋な悪意)* (Page 1)
  - *Chapter 1: The Lord of Vice (悪徳の王)* (Page 11)
  - *Chapter 2: Time of Despair (絶望の時)* (Page 167)
  - *Chapter 3: The Apex's Showdown (頂上決戦)* (Page 306)
  - *Epilogue: Evil God Awakening (邪神覚醒)* (Page 583)
- **🖼️ Visual Thumbnail Drawer**: Browse all 586 page previews in a bottom tray with lazy loading and instant jump.
- **🔍 Instant Full-Text Search**: Search any character, monster, skill, or quote with instant results and highlighted snippets.
- **🔖 Bookmarks & Resume Reading**:
  - Automatically saves your reading position.
  - Add bookmarks to any page with timestamp.
- **🎨 4 Reading Themes**:
  - **AnyFlip Dark**: Modern dark slate with golden accents.
  - **Cozy Desk**: Warm mahogany wood library backdrop.
  - **Midnight OLED**: Pure black background for night reading.
  - **Clean Paper**: Soft light reader mode.
- **🔍 Zoom & Pan**: Zoom in/out up to 250% with mouse wheel or buttons, and click-and-drag panning.
- **⏯️ Auto-Flip / Slideshow**: Hands-free reading with adjustable timer.

---

## ⌨️ Keyboard Shortcuts

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
| `J` | Show / Hide Japanese lines (Reader mode) |
| `+` / `-` | Reader: font size · PDF modes: zoom |
| `0` | Reset Zoom (100%) |
| `Esc` | Close Open Drawers / Reset Zoom |
