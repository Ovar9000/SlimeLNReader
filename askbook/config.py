"""Shared config: secrets (never committed), service endpoints, models."""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRETS_PATH = os.path.join(BASE_DIR, "secrets.local.json")


def load_api_key():
    """Gemini key from env (preferred) or untracked local secrets file."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, encoding="utf-8") as f:
            return json.load(f).get("gemini_api_key", "").strip()
    raise RuntimeError(
        "No Gemini API key: set GEMINI_API_KEY or create secrets.local.json "
        "(see README; never commit it)."
    )


WEAVIATE_HOST = os.environ.get("WEAVIATE_HOST", "127.0.0.1")
WEAVIATE_HTTP_PORT = int(os.environ.get("WEAVIATE_HTTP_PORT", "8081"))
WEAVIATE_GRPC_PORT = int(os.environ.get("WEAVIATE_GRPC_PORT", "50051"))

EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-3.6-flash"

VOLUME = 22
TOTAL_PAGES = 586

# Canonical TOC (matches server.py / book_data.json)
TOC = [
    {"title": "Prologue: Pure Malice (純粋な悪意)", "page": 1},
    {"title": "Chapter 1: The Lord of Vice (悪徳の王)", "page": 11},
    {"title": "Chapter 2: Time of Despair (絶望の時)", "page": 167},
    {"title": "Chapter 3: The Apex's Showdown (頂上決戦)", "page": 306},
    {"title": "Epilogue: Evil God Awakening (邪神覚醒)", "page": 583},
]


def section_for_page(page):
    if page < 11:
        return "prologue"
    if page >= 583:
        return "epilogue"
    return "body"


def chapter_for_page(page):
    cur = TOC[0]["title"]
    for c in TOC:
        if page >= c["page"]:
            cur = c["title"]
    return cur
