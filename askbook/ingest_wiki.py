"""Tensura Fandom wiki ingestion (fetch now, embed/extract with --ingest).

Titles are resolved via the MediaWiki search API (no guessed URLs).
Raw fetches are cached under .wiki_cache/ (git-ignored, re-runnable offline).

Usage:
  python -m askbook.ingest_wiki --fetch-only      # network fetch, no LLM/quota
  python -m askbook.ingest_wiki --ingest           # embed + insert + Prompt C
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

API = "https://tensura.fandom.com/api.php"

# Curated for Vol 22 relevance; resolved through search, skipped if absent.
CHARACTERS = [
    "Rimuru Tempest", "Ivarage", "Veldanava", "Luminus Valentine",
    "Testarossa", "Benimaru", "Souei", "Diablo", "Shion", "Milim Nava",
    "Guy Crimson", "Velgrynd", "Velzard", "Gadra", "Vega", "Zelanus",
]

from html.parser import HTMLParser

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         ".wiki_cache")

SKIP_TAGS = {"script", "style", "table", "sup", "nav", "aside", "footer",
             "figure", "figcaption"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag in ("p", "h1", "h2", "h3", "li", "br"):
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag in ("p", "h1", "h2", "h3", "li"):
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_to_text(html):
    t = _TextExtractor()
    t.feed(html or "")
    text = re.sub(r"[ \t]+", " ", "".join(t.out))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


UA = {"User-Agent": "SlimeLNReader/1.0 (local reading-companion research; contact: local)"}


def api(params):
    qs = urllib.parse.urlencode({"format": "json", **params})
    req = urllib.request.Request(API + "?" + qs, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def resolve_title(name):
    d = api({"action": "query", "list": "search", "srsearch": name, "srlimit": 3})
    hits = d.get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def fetch_extract(title):
    d = api({"action": "parse", "page": title, "prop": "text"})
    try:
        html = d["parse"]["text"]["*"]
    except KeyError:
        return None
    text = html_to_text(html)
    if not text:
        return None
    return {"title": d["parse"].get("title", title),
            "pageid": str(d["parse"].get("pageid", "")),
            "extract": text,
            "url": f"https://tensura.fandom.com/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"}


def chunk_text(text, target=1000):
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if cur and len(cur) + len(p) > target:
            chunks.append(cur)
            cur = p
        else:
            cur = (cur + "\n" + p).strip()
    if cur:
        chunks.append(cur)
    return [c for c in chunks if len(c) > 120]


def fetch_all():
    os.makedirs(CACHE_DIR, exist_ok=True)
    manifest_path = os.path.join(CACHE_DIR, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        manifest = json.load(open(manifest_path, encoding="utf-8"))
    for name in CHARACTERS:
        if name in manifest:
            print(f"  cached: {name} -> {manifest[name]['title']}", flush=True)
            continue
        try:
            title = resolve_title(name)
            if not title:
                print(f"  no hit: {name}", flush=True)
                continue
            page = fetch_extract(title)
            if not page or not page["extract"]:
                print(f"  empty: {name} -> {title}", flush=True)
                continue
            safe = re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")
            with open(os.path.join(CACHE_DIR, safe + ".json"), "w", encoding="utf-8") as f:
                json.dump(page, f, ensure_ascii=False)
            manifest[name] = {"title": title, "file": safe + ".json",
                              "chars": len(page["extract"])}
            print(f"  fetched: {name} -> {title} ({len(page['extract'])} chars)", flush=True)
        except Exception as e:
            print(f"  error {name}: {str(e)[:120]}", flush=True)
        time.sleep(1)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    return manifest


def plan_chunks():
    from .config import BASE_DIR
    manifest_path = os.path.join(CACHE_DIR, "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8")) if os.path.exists(manifest_path) else {}
    total = 0
    for name, meta in manifest.items():
        page = json.load(open(os.path.join(CACHE_DIR, meta["file"]), encoding="utf-8"))
        n = len(chunk_text(page["extract"]))
        total += n
        print(f"  {meta['title']}: {n} chunks", flush=True)
    print(f"[wiki] {total} chunks from {len(manifest)} pages", flush=True)
    return total


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--ingest", action="store_true")
    ap.add_argument("--embed-only", action="store_true",
                    help="with --ingest: embed+insert chunks, skip LLM extraction")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if args.fetch_only or not args.ingest:
        manifest = fetch_all()
        print(f"[wiki] manifest: {len(manifest)} pages cached", flush=True)
    if args.ingest:
        from .wiki_ingest_run import run as run_ingest
        run_ingest(embed_only=args.embed_only, offset=args.offset, limit=args.limit or 0)


if __name__ == "__main__":
    main()
