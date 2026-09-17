"""Remove duplicate NovelChunk (same page_start) and CharacterStateLog rows.

Keeps the earliest-inserted object per key. Run after ingestion completes.
Usage: python -m askbook.dedupe [--apply] (default dry-run)
"""
import argparse

from .store import connect


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    client = connect()

    ncol = client.collections.get("NovelChunk")
    seen, dupes = {}, 0
    for obj in ncol.iterator(include_vector=False):
        key = obj.properties.get("page_start")
        if key in seen:
            dupes += 1
            if args.apply:
                ncol.data.delete_by_id(obj.uuid)
        else:
            seen[key] = obj.uuid
    print(f"[dedupe] NovelChunk: {len(seen)} unique, {dupes} duplicates"
          + (" (deleted)" if args.apply else " (dry-run)"), flush=True)

    slog = client.collections.get("CharacterStateLog")
    seen2, dupes2 = {}, 0
    for obj in slog.iterator(include_vector=False):
        p = obj.properties
        key = (p.get("page"), p.get("character_canonical_name"),
               p.get("stat_type"), p.get("value_text"))
        if key in seen2:
            dupes2 += 1
            if args.apply:
                slog.data.delete_by_id(obj.uuid)
        else:
            seen2[key] = obj.uuid
    print(f"[dedupe] CharacterStateLog: {len(seen2)} unique, {dupes2} duplicates"
          + (" (deleted)" if args.apply else " (dry-run)"), flush=True)
    client.close()


if __name__ == "__main__":
    main()
