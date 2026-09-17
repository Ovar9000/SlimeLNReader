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


def run(pause=3.0):
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
    fresh = [j for j in jobs if j[1] not in seen_urls]
    print(f"[wiki] {len(fresh)} new chunks from {len(manifest)} pages", flush=True)

    texts = [c for (_, _, c) in fresh]
    vecs = embed_texts(texts) if texts else []
    for (title, url, text), vec in zip(fresh, texts, vecs):
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

    # Prompt C over character content (source_type wiki, confidence capped low)
    n_rows = 0
    for i, (title, url, text) in enumerate(fresh):
        prompt = PROMPT_C_SYSTEM.format(
            volume=22, chapter=f"wiki:{title}",
            page_start=TOTAL_PAGES, page_end=TOTAL_PAGES, chunk_text=text[:6000])
        try:
            items = extract_json_array(generate(prompt, max_tokens=1024, temperature=0.0))
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
            print(f"  [wiki-extract] {i + 1}/{len(fresh)} chunks", flush=True)
        time.sleep(pause)
    print(f"[wiki] {n_rows} wiki state rows", flush=True)
    print("[wiki] counts:", {n: count(client, n) for n in
          ["NovelChunk", "WikiChunk", "CharacterStateLog"]}, flush=True)
    client.close()
