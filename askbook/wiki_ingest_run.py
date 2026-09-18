"""Embed + insert cached wiki pages and run Prompt C over character content.

Fail-closed: character pages describe eventual end-state, so estimates sit at
the document end with low confidence. Called by `ingest_wiki --ingest`.
"""
import json
import os
import time

from .config import BASE_DIR, TOTAL_PAGES
from .gemini import embed_texts, generate, extract_json_array
from .prompts import PROMPT_C_SYSTEM
from .store import connect, count
from .ingest_novel import normalize_name
from .ingest_wiki import CACHE_DIR, chunk_text

STAT_TYPES = {"EP", "level", "location", "affiliation", "title", "goal_stated"}


def existing_urls(client):
    col = client.collections.get("WikiChunk")
    return {o.properties.get("source_url")
            for o in col.iterator(include_vector=False)}


def run(pause=3.0, embed_only=False, offset=0, limit=0):
    manifest_path = os.path.join(CACHE_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        print("[wiki] nothing cached; run --fetch-only first", flush=True)
        return
    manifest = json.load(open(manifest_path, encoding="utf-8"))
    client = connect()
    seen_urls = existing_urls(client)
    wcol = client.collections.get("WikiChunk")
    slog = client.collections.get("CharacterStateLog")

    jobs = []
    for name, meta in manifest.items():
        page = json.load(open(os.path.join(CACHE_DIR, meta["file"]), encoding="utf-8"))
        for ch in chunk_text(page["extract"]):
            jobs.append((page["title"], page["url"], ch))
    if offset:
        jobs = jobs[offset:]
    if limit:
        jobs = jobs[:limit]
    fresh = [j for j in jobs if j[1] not in seen_urls]
    print(f"[wiki] {len(fresh)} new chunks from {len(manifest)} pages", flush=True)

    texts = [c for (_, _, c) in fresh]
    vecs = embed_texts(texts) if texts else []
    for job, vec in zip(fresh, vecs):
        title, url, text = job
        wcol.data.insert(properties={
            "text": text,
            "source_url": url,
            "content_type": "character",
            # Fail closed: character pages describe end-state.
            "global_position_estimate": TOTAL_PAGES,
            "confidence": "low",
            "characters_mentioned": [title],
            "is_ground_truth": False,
        }, vector=vec)
    print(f"[wiki] inserted {len(fresh)} chunks", flush=True)
    if embed_only:
        print("[wiki] embed-only mode: skipping Prompt C extraction", flush=True)
        print("[wiki] counts:", {n: count(client, n) for n in
              ["NovelChunk", "WikiChunk", "CharacterStateLog"]}, flush=True)
        client.close()
        return

    # Prompt C over character content (source_type wiki, confidence capped low)
    done_titles = set()
    for obj in slog.iterator(include_vector=False):
        ch = obj.properties.get("chapter", "")
        if ch.startswith("wiki:"):
            done_titles.add(ch[5:])
    n_rows = 0
    # NB: extraction pending derives from ALL jobs in range (minus done),
    # not from `fresh` — fresh only tracks what still needs embedding.
    pending = [(t, u, c) for (t, u, c) in jobs if t not in done_titles]
    print(f"[wiki-extract] {len(pending)} chunks pending", flush=True)
    for i, (title, url, text) in enumerate(pending):
        prompt = PROMPT_C_SYSTEM.format(
            volume=22, chapter=f"wiki:{title}",
            page_start=TOTAL_PAGES, page_end=TOTAL_PAGES, chunk_text=text[:6000])
        try:
            items = extract_json_array(generate(prompt, max_tokens=4096, temperature=0.0))
        except Exception as e:
            print(f"  [wiki-extract] failed {title}: {str(e)[:120]}", flush=True)
            continue
        for it in items:
            try:
                name = str(it.get("character", "")).strip()
                st = str(it.get("stat_type", "")).strip()
                val = str(it.get("value_text", "")).strip()
                if not name or st not in STAT_TYPES or not val:
                    continue
                slog.data.insert(properties={
                    "character_canonical_name": name,
                    "character_aliases": [],
                    "stat_type": st,
                    "value_text": val,
                    "global_position": TOTAL_PAGES,
                    "volume": 22,
                    "chapter": f"wiki:{title}",
                    "page": TOTAL_PAGES,
                    "source_type": "wiki",
                    "confidence": "low",  # capped per spec (end-state risk)
                })
                n_rows += 1
            except Exception:
                continue
        if (i + 1) % 10 == 0:
            print(f"  [wiki-extract] {i + 1}/{len(pending)} chunks", flush=True)
        time.sleep(pause)
    print(f"[wiki] {n_rows} wiki state rows", flush=True)
    # NOTE: resume is title-granular (a title with any rows is skipped on
    # rerun). Titles with partial failures are listed above as [wiki-extract]
    # failures; recover them by deleting that title's rows and re-running.
    print("[wiki] counts:", {n: count(client, n) for n in
          ["NovelChunk", "WikiChunk", "CharacterStateLog"]}, flush=True)
    client.close()
