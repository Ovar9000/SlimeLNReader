"""Ingest the novel: 2-page chunks -> NovelChunk (+embeddings), Prompt C ->
CharacterStateLog, alias backfill. Idempotent: skips pages already present.

Usage: python -m askbook.ingest_novel [--offset N] [--limit N]
"""
import argparse
import json
import os
import re
import sys
import time

from .config import BASE_DIR, VOLUME, TOC, section_for_page, chapter_for_page
from .gemini import embed_texts, generate, extract_json_array
from .prompts import PROMPT_C_SYSTEM
from .store import connect, count

PAGES_PER_CHUNK = 2
STAT_TYPES = {"EP", "level", "location", "affiliation", "title", "goal_stated"}


def normalize_name(name):
    n = name.strip().lower()
    n = re.sub(r"(-sama|-san|-kun|-chan|-dono|-sempai)$", "", n)
    n = re.sub(r"\s+", " ", n)
    return n


def load_pages():
    with open(os.path.join(BASE_DIR, "static", "book_data.json"), encoding="utf-8") as f:
        return json.load(f)["pages"]


def existing_pages(client):
    """page_start -> uuid for ingested chunks (resume support)."""
    col = client.collections.get("NovelChunk")
    seen = {}
    for obj in col.iterator(include_vector=False):
        seen[obj.properties.get("page_start")] = obj.uuid
    return seen


def existing_state_pages(client):
    col = client.collections.get("CharacterStateLog")
    seen = set()
    for obj in col.iterator(include_vector=False):
        seen.add(obj.properties.get("page"))
    return seen


def extract_states(chunk_text, page_start, page_end, chapter, tries=2):
    prompt = PROMPT_C_SYSTEM.format(
        volume=VOLUME, chapter=chapter,
        page_start=page_start, page_end=page_end, chunk_text=chunk_text[:6000],
    )
    last_err = None
    for _ in range(tries):
        try:
            raw = generate(prompt, max_tokens=2048, temperature=0.0)
            items = extract_json_array(raw)
            break
        except Exception as e:
            last_err = e
    else:
        print(f"  [extract] failed p{page_start}-{page_end}: {last_err}", flush=True)
        return []
    rows = []
    for it in items:
        try:
            name = str(it.get("character", "")).strip()
            st = str(it.get("stat_type", "")).strip()
            val = str(it.get("value_text", "")).strip()
            conf = str(it.get("confidence", "low")).strip().lower()
            if not name or st not in STAT_TYPES or not val:
                continue
            if conf not in ("high", "low"):
                conf = "low"
            rows.append({
                "character_canonical_name": name,
                "character_aliases": [],
                "stat_type": st,
                "value_text": val,
                # Fail closed: attribute to chunk END so a reader mid-chunk
                # can't see facts from its later pages.
                "global_position": page_end,
                "volume": VOLUME,
                "chapter": chapter,
                "page": page_end,
                "source_type": "novel",
                "confidence": conf,
            })
        except Exception:
            continue
    return rows


def backfill_aliases(client):
    """Union aliases across rows sharing a normalized canonical name."""
    col = client.collections.get("CharacterStateLog")
    groups = {}
    uuids = {}
    for obj in col.iterator(include_vector=False):
        p = obj.properties
        key = normalize_name(p.get("character_canonical_name", ""))
        if not key:
            continue
        groups.setdefault(key, set()).add(p.get("character_canonical_name", ""))
        uuids.setdefault(key, []).append(obj.uuid)
    for key, names in groups.items():
        if len(names) < 2:
            continue
        aliases = sorted(names)
        for u in uuids[key]:
            col.data.update(uuid=u, properties={"character_aliases": aliases})
    print(f"[aliases] merged {sum(1 for v in groups.values() if len(v) > 1)} name groups", flush=True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-alias-backfill", action="store_true")
    ap.add_argument("--pause", type=float, default=3.0,
                    help="seconds between extraction calls (rate-limit pacing)")
    ap.add_argument("--log-file", type=str, default="",
                    help="tee progress output to this file (for detached runs)")
    args = ap.parse_args()
    if args.log_file:
        _log_fh = open(args.log_file, "w", encoding="utf-8")
        _real_print = print

        def _tee(*a, **k):
            _real_print(*a, **{**k, "flush": True})
            _real_print(*a, file=_log_fh, flush=True)

        import builtins
        builtins.print = _tee

    pages = load_pages()
    total = len(pages)
    chunks = []
    for start in range(1, total + 1, PAGES_PER_CHUNK):
        end = min(start + PAGES_PER_CHUNK - 1, total)
        chunks.append((start, end))
    if args.offset:
        chunks = chunks[args.offset:]
    if args.limit:
        chunks = chunks[: args.limit]
    print(f"[ingest] {len(chunks)} chunks (pages 1-{total})", flush=True)

    client = connect()
    done_pages = existing_pages(client)
    done_state = existing_state_pages(client)
    ncol = client.collections.get("NovelChunk")
    slog = client.collections.get("CharacterStateLog")
    uuid_by_start = dict(done_pages)

    # Phase 1: chunks + embeddings, inserted per batch so every batch
    # is a resume checkpoint (a kill loses at most one batch, not everything).
    pending = [(s, e) for (s, e) in chunks if s not in done_pages]
    print(f"[ingest] {len(pending)} new chunks to embed", flush=True)
    BATCH = 8
    for b in range(0, len(pending), BATCH):
        group = pending[b : b + BATCH]
        texts = ["\n".join(pages[s - 1 : e]) for (s, e) in group]
        vecs = embed_texts(texts)
        for (s, e), text, vec in zip(group, texts, vecs):
            chapter = chapter_for_page(s)
            props = {
                "text": text,
                # Fail closed: chunk becomes visible only once its END is reached.
                "volume": VOLUME,
                "chapter": chapter,
                "page_start": s,
                "page_end": e,
                "global_position": e,
                "section_label": section_for_page(s),
                "arc_name": "",
                "characters_mentioned": [],
                "is_ground_truth": True,
            }
            uuid_by_start[s] = ncol.data.insert(properties=props, vector=vec)
        print(f"[ingest] embedded+inserted {min(b + BATCH, len(pending))}/{len(pending)} chunks",
              flush=True)

    # Phase 2: Prompt C extraction -> state rows
    n_rows = 0
    targets = [(s, e) for (s, e) in chunks if e not in done_state]
    print(f"[ingest] extracting states for {len(targets)} chunks", flush=True)
    for i, (s, e) in enumerate(targets):
        text = "\n".join(pages[s - 1 : e])
        rows = extract_states(text, s, e, chapter_for_page(s))
        names = set()
        for r in rows:
            slog.data.insert(properties=r)
            names.add(r["character_canonical_name"])
            n_rows += 1
        if s in uuid_by_start and names:
            ncol.data.update(uuid=uuid_by_start[s], properties={"characters_mentioned": sorted(names)})
        print(f"  [{i + 1}/{len(targets)}] p{s}-{e}: {len(rows)} state rows", flush=True)
        if args.pause and i + 1 < len(targets):
            time.sleep(args.pause)
    print(f"[ingest] {n_rows} state rows total", flush=True)

    if not args.no_alias_backfill:
        backfill_aliases(client)
    print("[ingest] counts:", {n: count(client, n) for n in
          ["NovelChunk", "WikiChunk", "CharacterStateLog"]}, flush=True)
    client.close()


if __name__ == "__main__":
    main()
