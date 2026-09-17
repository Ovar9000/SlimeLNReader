"""Acceptance suite for Ask the Book (spec section 5).

Deterministic tests always run (no LLM calls). Live end-to-end tests need
ingested data + Gemini quota: python -m askbook.test_acceptance --live
"""
import argparse
import sys

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" — {detail}" if detail and not cond else ""),
          flush=True)


def test_spoiler_filter():
    from askbook.runtime import _safe_chunks
    rows = [
        {"global_position": 5, "text": "early"},
        {"global_position": 100, "text": "on-time"},
        {"global_position": 101, "text": "future-leak"},
        {"text": "no-position"},
    ]
    kept = _safe_chunks(rows, 100)
    check("spoiler-filter-drops-future", [r["text"] for r in kept] == ["early", "on-time"])
    check("spoiler-filter-drops-unpositioned", all("global_position" in r for r in kept))


def test_json_helpers():
    from askbook.gemini import extract_json_array, extract_json_object
    check("json-array-fences",
          extract_json_array('```json\n[{"a": 1,}]\n```') == [{"a": 1}])
    check("json-object-prose",
          extract_json_object('Sure! {"intent": "meta_app", "entities": [], "queries": []} ok')
          ["intent"] == "meta_app")
    try:
        extract_json_array("no json here")
        check("json-array-rejects-empty", False)
    except ValueError:
        check("json-array-rejects-empty", True)


def test_static_templates():
    from askbook.runtime import FUTURE_DECLINE, META_APP_HELP
    check("decline-no-spoiler-mention", "spoil" in FUTURE_DECLINE.lower())
    check("decline-short", len(FUTURE_DECLINE) < 300)
    check("help-no-spoiler-promise", "no spoiler" in META_APP_HELP.lower())


def test_store_ops():
    from askbook.store import connect, search_chunks, latest_state
    from weaviate.classes.query import Filter
    c = connect()
    try:
        col = c.collections.get("WikiChunk")
        import random
        random.seed(7)
        v = [[random.gauss(0, 1) for _ in range(3072)] for _ in range(2)]
        col.data.insert({"text": "early fact", "source_url": "t", "content_type": "event",
                         "global_position_estimate": 10, "confidence": "high",
                         "characters_mentioned": [], "is_ground_truth": False}, vector=v[0])
        col.data.insert({"text": "late spoiler", "source_url": "t", "content_type": "event",
                         "global_position_estimate": 900, "confidence": "low",
                         "characters_mentioned": [], "is_ground_truth": False}, vector=v[0])
        rows = search_chunks(c, "WikiChunk", v[0], 100, "global_position_estimate", limit=5)
        texts = [r["text"] for r in rows]
        check("store-filter-excludes-future", "late spoiler" not in texts and "early fact" in texts)
        # cleanup test rows
        doomed = col.query.fetch_objects(
            filters=Filter.by_property("source_url").equal("t"), limit=10).objects
        for o in doomed:
            col.data.delete_by_id(o.uuid)
    finally:
        c.close()


LIVE_CASES = [
    # (question, reader_page, expected_intent, check_fn_name)
    ("What happened in the epilogue of the last volume?", 586, "recap_summary", "novel-or-wiki"),
    ("What is Ivarage's current EP?", 300, "stat_or_location_lookup", "state-capped"),
    ("Where is Ivarage right now?", 300, "stat_or_location_lookup", "state-capped"),
    ("Doesn't this mean Ivarage is connected to Veldanava?", 300, "theory_discussion", "novel-only"),
    ("Why is the writing so dumb?", 300, "meta_commentary", "short-reply"),
    ("What is Ivarage's main goal?", 300, "character_profile", "so-far-framed"),
    ("Summarize the page", 300, "page_summary", "nonempty"),
]


def run_live():
    from askbook import runtime
    from askbook.config import BASE_DIR
    import json, os
    with open(os.path.join(BASE_DIR, "static", "book_data.json"), encoding="utf-8") as f:
        pages = json.load(f)["pages"]
    for question, page, want_intent, _ in LIVE_CASES:
        try:
            res = runtime.ask(question, page, page_text=pages[page - 1], history=[])
        except Exception as e:
            check(f"live:{question[:40]}", False, f"error: {str(e)[:150]}")
            continue
        ok_intent = res["intent"] == want_intent
        check(f"live:intent:{question[:40]}", ok_intent,
              f"want {want_intent}, got {res['intent']}")
        src = res["sources"]
        leaked = [r.get("page", r.get("global_position", 0)) or 0
                  for k in ("novel", "state", "wiki") for r in src[k]]
        check(f"live:no-future-leak:{question[:40]}",
              all((p or 0) <= page for p in leaked),
              f"max source pos {max(leaked) if leaked else '-'} > reader {page}")
        ans = res["answer"]
        if want_intent == "future_request":
            pass  # covered below separately
        check(f"live:answer-nonempty:{question[:40]}", len(ans.strip()) > 10)
    # future_request is always a static decline
    res = runtime.ask("Tell me what happens on the last page.", 300, page_text="", history=[])
    check("live:future-decline", res["intent"] == "future_request" and "spoil" in res["answer"].lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="run live end-to-end cases (needs data + quota)")
    args = ap.parse_args()
    test_spoiler_filter()
    test_json_helpers()
    test_static_templates()
    test_store_ops()
    if args.live:
        run_live()
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
