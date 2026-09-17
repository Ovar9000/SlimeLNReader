"""Minimal Gemini REST client (embed + generate) with retries. No extra deps."""
import json
import re
import time
import urllib.request
import urllib.error

from .config import load_api_key, EMBED_MODEL, CHAT_MODEL

_API = "https://generativelanguage.googleapis.com/v1beta"


class QuotaExceededError(RuntimeError):
    """Raised when Gemini rate/quota limits are exhausted after backoff."""


def _retry_delay(err_body, attempt):
    m = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', err_body)
    if m:
        return min(int(m.group(1)) + 2, 120)
    return 5 * (attempt + 1)


def _post(path, payload, timeout=60, tries=3):
    key = load_api_key()
    body = json.dumps(payload).encode("utf-8")
    last = None
    saw_429 = False
    for attempt in range(tries):
        try:
            req = urllib.request.Request(
                f"{_API}{path}?key={key}",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            err = e.read()[:600].decode("utf-8", "replace")
            last = f"HTTP {e.code}: {err[:200]}"
            if e.code in (400, 401, 403):
                raise RuntimeError(last)
            if e.code == 429:
                saw_429 = True
                time.sleep(_retry_delay(err, attempt))
                continue
            time.sleep(2 * (attempt + 1))
        except Exception as e:  # network blips
            last = str(e)
            time.sleep(2 * (attempt + 1))
    if saw_429:
        raise QuotaExceededError(
            "Gemini rate limit still exhausted after backoff.")
    raise RuntimeError(f"Gemini call failed after {tries} tries: {last}")


def embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", batch=8):
    """Returns list of vectors. Batches internally (small batches respect RPM)."""
    out = []
    for i in range(0, len(texts), batch):
        out += _embed_batch(texts[i : i + batch], task_type)
    if len(out) != len(texts):
        raise RuntimeError(f"embed count mismatch: {len(out)} != {len(texts)}")
    return out


def _embed_batch(batch, task_type, tries=6):
    last = None
    for attempt in range(tries):
        try:
            data = _post(
                f"/models/{EMBED_MODEL}:batchEmbedContents",
                {"requests": [
                    {"model": f"models/{EMBED_MODEL}",
                     "content": {"parts": [{"text": t}]},
                     "task_type": task_type}
                    for t in batch
                ]},
                timeout=90,
                tries=1,
            )
            embs = data.get("embeddings", [])
            if len(embs) != len(batch):
                raise RuntimeError("short embedding batch")
            return [e["values"] for e in embs]
        except QuotaExceededError as e:
            last = str(e)
            time.sleep(_retry_delay(last, attempt))
            continue
        except RuntimeError as e:
            last = str(e)
            if "429" in last:
                time.sleep(_retry_delay(last, attempt))
                continue
            raise
    raise RuntimeError(f"embed batch failed after {tries} tries: {last}")


def embed_query(text):
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]


def generate(prompt, model=None, max_tokens=1024, temperature=0.2):
    model = model or CHAT_MODEL
    data = _post(
        f"/models/{model}:generateContent",
        {"contents": [{"parts": [{"text": prompt}]}],
         "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature}},
        timeout=90,
    )
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        raise RuntimeError(f"Unexpected generate response: {str(data)[:300]}")


def extract_json_array(text):
    """Pulls a JSON array out of model output (tolerant of fences/prose).

    Repairs common model sloppiness (trailing commas) before giving up.
    """
    import re
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON array in output: {text[:200]}")
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        return json.loads(repaired)


def extract_json_object(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"No JSON object in output: {text[:200]}")
    return json.loads(text[start : end + 1])
