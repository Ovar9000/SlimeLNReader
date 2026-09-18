"""
Local Flipbook Server for Light Novel Viewer
Uses PyMuPDF (fitz) for high-speed page rendering and caching.
"""
import os
import sys
import json
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import pymupdf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BASE_DIR, "Volume_22_MTL.pdf")
CACHE_DIR = os.path.join(BASE_DIR, ".page_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Load document once
print(f"Loading PDF from {PDF_PATH}...")
doc = pymupdf.open(PDF_PATH)
TOTAL_PAGES = len(doc)
print(f"Loaded '{PDF_PATH}' with {TOTAL_PAGES} pages.")

# In-memory LRU cache for recent pages (page_num, dpi) -> bytes
MEMORY_CACHE = {}
MAX_MEM_CACHE = 120

TOC = [
    {"title": "Prologue: Pure Malice (純粋な悪意)", "page": 1},
    {"title": "Chapter 1: The Lord of Vice (悪徳の王)", "page": 11},
    {"title": "Chapter 2: Time of Despair (絶望の時)", "page": 167},
    {"title": "Chapter 3: The Apex's Showdown (頂上決戦)", "page": 306},
    {"title": "Epilogue: Evil God Awakening (邪神覚醒)", "page": 583}
]

def render_page(page_num, dpi=160):
    """Render a 1-based page number to JPEG bytes with disk and memory cache."""
    cache_key = f"{page_num}_{dpi}"
    if cache_key in MEMORY_CACHE:
        return MEMORY_CACHE[cache_key]

    disk_file = os.path.join(CACHE_DIR, f"p{page_num}_d{dpi}.jpg")
    if os.path.exists(disk_file):
        with open(disk_file, "rb") as f:
            data = f.read()
        if len(MEMORY_CACHE) < MAX_MEM_CACHE:
            MEMORY_CACHE[cache_key] = data
        return data

    # Render via pymupdf
    idx = page_num - 1
    if idx < 0 or idx >= TOTAL_PAGES:
        return None

    page = doc[idx]
    pix = page.get_pixmap(dpi=dpi)
    quality = 85 if dpi >= 100 else 65
    data = pix.tobytes("jpeg", jpg_quality=quality)

    # Save to disk
    try:
        with open(disk_file, "wb") as f:
            f.write(data)
    except Exception as e:
        print(f"Cache write error: {e}", file=sys.stderr)

    if len(MEMORY_CACHE) < MAX_MEM_CACHE:
        MEMORY_CACHE[cache_key] = data
    return data

class FlipbookHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        # Suppress routine 200 logs for images to keep console clean
        if len(args) > 0 and ("GET /api/page/" in str(args[0]) or "GET /api/thumbnail/" in str(args[0])):
            return
        super().log_message(format, *args)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health / status check
        if path == "/api/status":
            self.send_json({"status": "ok", "engine": "pymupdf", "pages": TOTAL_PAGES})
            return

        # Book info & table of contents
        if path == "/api/info":
            first_p = doc[0]
            self.send_json({
                "title": "That Time I Got Reincarnated as a Slime — Volume 22: Godly Destruction and Chaos",
                "shortTitle": "Tensura Vol. 22",
                "totalPages": TOTAL_PAGES,
                "width": round(first_p.rect.width, 2),
                "height": round(first_p.rect.height, 2),
                "aspectRatio": round(first_p.rect.width / first_p.rect.height, 4),
                "toc": TOC
            })
            return

        # Single page image endpoint
        if path.startswith("/api/page/"):
            try:
                parts = path.strip("/").split("/")
                page_num = int(parts[2])
                dpi = int(query.get("dpi", ["160"])[0])
                dpi = min(max(dpi, 50), 250)
                img_data = render_page(page_num, dpi=dpi)
                if img_data:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(img_data)))
                    self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                    self.end_headers()
                    self.wfile.write(img_data)
                else:
                    self.send_error(404, "Page Not Found")
            except Exception as e:
                self.send_error(500, f"Error rendering page: {e}")
            return

        # Thumbnail image endpoint
        if path.startswith("/api/thumbnail/"):
            try:
                parts = path.strip("/").split("/")
                page_num = int(parts[2])
                img_data = render_page(page_num, dpi=35)
                if img_data:
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(img_data)))
                    self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                    self.end_headers()
                    self.wfile.write(img_data)
                else:
                    self.send_error(404, "Thumbnail Not Found")
            except Exception as e:
                self.send_error(500, f"Error rendering thumbnail: {e}")
            return

        # Full-text Search
        if path == "/api/search":
            q = query.get("q", [""])[0].strip().lower()
            if not q:
                self.send_json({"query": q, "count": 0, "results": []})
                return

            results = []
            for i, page in enumerate(doc):
                text = page.get_text()
                lower_text = text.lower()
                if q in lower_text:
                    idx = lower_text.find(q)
                    start = max(0, idx - 40)
                    end = min(len(text), idx + len(q) + 60)
                    snippet = text[start:end].replace("\n", " ").strip()
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(text):
                        snippet = snippet + "..."

                    current_chap = "Prologue"
                    page_num = i + 1
                    for chap in TOC:
                        if page_num >= chap["page"]:
                            current_chap = chap["title"]

                    results.append({
                        "page": page_num,
                        "snippet": snippet,
                        "chapter": current_chap
                    })
                    if len(results) >= 50:
                        break

            self.send_json({"query": q, "count": len(results), "results": results})
            return

        # Root redirect or default index
        if path == "/" or path == "":
            self.path = "/index.html"

        return super().do_GET()

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_api_error(self, code, message):
        body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/ask":
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                return self.send_api_error(400, "Missing Content-Length")
            if length <= 0 or length > 32768:
                return self.send_api_error(400, "Bad request size")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return self.send_api_error(400, "Invalid JSON")
            try:
                page = int(payload.get("page", 0))
            except (TypeError, ValueError):
                return self.send_api_error(400, "Invalid page")
            question = str(payload.get("question", ""))[:500].strip()
            history = payload.get("history", [])
            if not isinstance(history, list):
                history = []
            history = [str(t)[:500] for t in history][-6:]
            if not question:
                return self.send_api_error(400, "Empty question")
            if page < 1 or page > TOTAL_PAGES:
                return self.send_api_error(400, "Page out of range")
            try:
                page_text = doc[page - 1].get_text() or ""
            except Exception as e:
                return self.send_api_error(500, f"Could not read page text: {e}")
            try:
                # Import lazily so the reader works without the companion deps.
                # stderr is muted for the import only: authlib force-enables its
                # own deprecation warning at import time (after any filter we
                # could set), which would otherwise spam the terminal.
                import contextlib
                import io
                with contextlib.redirect_stderr(io.StringIO()):
                    from askbook import runtime
                    from askbook.gemini import QuotaExceededError
                result = runtime.ask(question, page, page_text=page_text, history=history)
            except ImportError as e:
                return self.send_api_error(503, f"Reading companion not installed: {e}")
            except ConnectionError as e:
                return self.send_api_error(503, f"Reading companion store unreachable: {e}")
            except QuotaExceededError:
                return self.send_api_error(
                    429, "The AI service is rate-limited right now — "
                         "please wait a minute and try again.")
            except RuntimeError as e:
                return self.send_api_error(502, f"Reading companion error: {e}")
            except Exception as e:
                return self.send_api_error(500, f"Reading companion failed: {e}")
            return self.send_json({
                "answer": result.get("answer", ""),
                "intent": result.get("intent", ""),
                "entities": result.get("entities", []),
            })
        return self.send_error(404, "Not Found")

def start_server(port=8080):
    server = ThreadingHTTPServer(("127.0.0.1", port), FlipbookHTTPRequestHandler)
    print(f"Flipbook server running at http://127.0.0.1:{port}/")
    return server

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = start_server(port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        server.server_close()
