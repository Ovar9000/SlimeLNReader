"""Ask-the-Book runtime: router (A) -> routed retrieval -> synthesis (B).

Fail-closed throughout: every retrieval path enforces global_position <=
reader_position, and synthesis inputs are re-checked before prompting.
"""
import re

from weaviate.classes.query import Filter, Sort

from .config import VOLUME, chapter_for_page
from .gemini import embed_query, generate, extract_json_object
from .prompts import PROMPT_A_SYSTEM, PROMPT_B_SYSTEM
from .store import connect, search_chunks_vec

INTENTS = {
    "page_summary", "recap_summary", "stat_or_location_lookup",
    "character_profile", "theory_discussion", "meta_commentary",
    "future_request", "meta_app",
}

STAT_TYPES = ["EP", "level", "location", "affiliation", "title", "goal_stated"]

FUTURE_DECLINE = (
    "That's ahead of where you are right now, so I'll keep quiet rather than "
    "spoil it — ask me again once you get there!"
)

META_APP_HELP = (
    "I'm a reading companion pinned to your exact page. Ask me to summarize the "
    "page, recap what led here, look up a character's current stats or whereabouts, "
    "or chew over a theory — I only ever use what you've already read, so no spoilers."
)


def normalize_name(name):
    n = (name or "").strip().lower()
    n = re.sub(r"(-sama|-san|-kun|-chan|-dono|-sempai)$", "", n)
    return re.sub(r"\s+", " ", n)


FUTURE_RE = re.compile(
    r"(what happens next|tell me what happens|what(?:'s| is) (?:going to happen )?"
    r"(?:on|at) the (?:last|final) page|(?:last|final) page|upcoming|"
    r"next chapter|spoilers?|spoil (?:me|it|for me))",
    re.IGNORECASE,
)


def route_question(question, reader_position):
    """Prompt A: classify + extract. Returns dict; fails closed to page_summary."""
    # Deterministic pre-route: explicit future asks never spend an LLM call
    # and can never be misrouted by model wobble.
    if FUTURE_RE.search(question or ""):
        return {"intent": "future_request", "entities": [], "queries": []}
    prompt = PROMPT_A_SYSTEM.format(
        reader_position_json=str(reader_position), user_question=question)
    for _ in range(2):  # one retry: truncated/garbled outputs happen
        try:
            out = extract_json_object(generate(prompt, max_tokens=1024, temperature=0.0))
            intent = out.get("intent", "page_summary")
            if intent not in INTENTS:
                continue
            return {
                "intent": intent,
                "entities": [str(e) for e in out.get("entities", [])][:5],
                "queries": [str(q) for q in out.get("queries", [])][:3],
            }
        except Exception:
            continue
    return {"intent": "page_summary", "entities": [], "queries": []}


def _safe_chunks(rows, reader_pos, pos_key="global_position"):
    """Defense in depth: drop anything past the reader even if filters slipped."""
    return [r for r in rows if r.get(pos_key) is not None and r.get(pos_key) <= reader_pos]


def retrieve_novel(client, query_vector, reader_pos, limit=5, section=None):
    filt = None
    if section:
        filt = Filter.by_property("section_label").equal(section)
    rows = search_chunks_vec(client, "NovelChunk", query_vector,
                             reader_pos, "global_position", limit=limit, extra_filter=filt)
    return _safe_chunks(rows, reader_pos)


def retrieve_wiki(client, query_vector, reader_pos, limit=4):
    rows = search_chunks_vec(client, "WikiChunk", query_vector,
                             reader_pos, "global_position_estimate", limit=limit)
    return _safe_chunks(rows, reader_pos, "global_position_estimate")


def lookup_states(client, entity, reader_pos):
    """All latest-per-stat rows for a character (canonical or alias match)."""
    variants = list(dict.fromkeys([entity.strip(), normalize_name(entity)]))
    col = client.collections.get("CharacterStateLog")
    filt = (
        Filter.by_property("character_canonical_name").equal(entity)
        | Filter.by_property("character_aliases").contains_any(variants)
        | Filter.by_property("character_canonical_name").equal(normalize_name(entity))
    ) & Filter.by_property("global_position").less_or_equal(reader_pos)
    res = col.query.fetch_objects(
        filters=filt,
        sort=Sort.by_property("global_position", ascending=False),
        limit=60,
    )
    best = {}
    for o in res.objects:
        p = o.properties
        if p.get("global_position", 0) > reader_pos:
            continue
        st = p.get("stat_type")
        if st and st not in best:
            best[st] = p
    return best


def fmt_novel(rows):
    return "\n\n".join(
        f"[p.{r.get('page_start')}-{r.get('page_end')}, {r.get('chapter', '')}] {r.get('text', '')[:900]}"
        for r in rows)


def fmt_wiki(rows):
    return "\n\n".join(
        f"(fan wiki: {r.get('source_url', '')} [{r.get('content_type', '')}]) {r.get('text', '')[:700]}"
        for r in rows)


def fmt_state(best):
    lines = []
    for st in STAT_TYPES:
        if st in best:
            r = best[st]
            lines.append(
                f"{r.get('character_canonical_name')} | {st} = {r.get('value_text')} "
                f"(p.{r.get('page')}, {r.get('chapter', '')}, {r.get('source_type', '')}/{r.get('confidence', '')})")
    return "\n".join(lines)


def fmt_history(history):
    return "\n".join(f"{'Reader' if i % 2 == 0 else 'Companion'}: {t[:400]}"
                     for i, t in enumerate(history or []))[-1500:]


def ask(question, page, page_text="", history=None, volume=VOLUME):
    """Full pipeline. Returns {answer, intent, entities, sources}."""
    reader_pos = page
    chapter = chapter_for_page(page)
    route = route_question(question, {"volume": volume, "chapter": chapter, "page": page})
    intent, entities = route["intent"], route["entities"]
    # Quota discipline: cap retrieval queries and embed each unique query ONCE
    # per question (one vector serves every collection), so a question costs
    # at most 2 generates + 2 embeds instead of up to 8 calls.
    queries = (route["queries"] or [question])[:2]
    vec_cache = {}

    def vec_for(text):
        if text not in vec_cache:
            vec_cache[text] = embed_query(text)
        return vec_cache[text]

    if intent == "future_request":
        return {"answer": FUTURE_DECLINE, "intent": intent,
                "entities": entities, "sources": {"novel": [], "state": [], "wiki": []}}
    if intent == "meta_app":
        return {"answer": META_APP_HELP, "intent": intent,
                "entities": entities, "sources": {"novel": [], "state": [], "wiki": []}}

    novel_ctx, wiki_ctx, state_ctx = "", "", ""
    sources = {"novel": [], "state": [], "wiki": []}
    with connect() as client:
        if intent == "page_summary":
            pass  # raw page text only, zero retrieval
        elif intent == "stat_or_location_lookup":
            merged = {}
            for ent in entities or [""]:
                for st, row in lookup_states(client, ent, reader_pos).items():
                    merged.setdefault(st, row)
            state_ctx = fmt_state(merged)
            sources["state"] = list(merged.values())
        elif intent == "theory_discussion":
            rows = []
            for q in queries:
                rows += retrieve_novel(client, vec_for(q), reader_pos, limit=4)
            novel_ctx = fmt_novel(rows)
            sources["novel"] = rows
        else:  # recap_summary, character_profile, meta_commentary(fallback below)
            if intent in ("recap_summary", "character_profile"):
                rows, wrows = [], []
                for q in queries:
                    v = vec_for(q)
                    rows += retrieve_novel(client, v, reader_pos, limit=4)
                    wrows += retrieve_wiki(client, v, reader_pos, limit=3)
                novel_ctx = fmt_novel(rows)
                wiki_ctx = fmt_wiki(wrows)
                sources["novel"], sources["wiki"] = rows, wrows

    prompt = PROMPT_B_SYSTEM.format(
        volume=volume, chapter=chapter, page=page, intent=intent,
        user_question=question, page_text=(page_text or "")[:2500],
        novel_context=novel_ctx[:5000], state_log_context=state_ctx[:2500],
        wiki_context=wiki_ctx[:3500], recent_chat=fmt_history(history))
    answer = ""
    for _ in range(2):  # one retry: empty responses happen
        answer = generate(prompt, max_tokens=768, temperature=0.4).strip()
        if answer:
            break
    return {"answer": answer, "intent": intent,
            "entities": entities, "sources": sources}
