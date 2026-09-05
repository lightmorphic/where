"""Talks to Ollama in a background thread so saving never waits on the model."""
import base64
import json
import logging
import queue
import re
import threading
import time
import urllib.error
import urllib.request

from . import config, db, photos

log = logging.getLogger("where.vision")

_queue = queue.Queue()
_started = False
_state = {"ok": None, "checked": 0, "detail": ""}

DESCRIBE_PROMPT = (
    "This photo shows an item called \"{name}\". In one short sentence, list only the "
    "details that would tell it apart from other similar items: colour, size, shape, "
    "connectors, markings, brand. Do not repeat the name. Do not describe the background."
)

BULK_PROMPT = (
    "List every separate object you can see in this photo. Write one object per line "
    "with a short plain name, such as \"USB-C cable\" or \"AA batteries\". "
    "Do not describe the tray, box, table or background. Do not number the lines."
)


# ---- Ollama HTTP ----

def _post(path, payload, timeout):
    req = urllib.request.Request(
        config.OLLAMA_HOST + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _get(path, timeout=5):
    with urllib.request.urlopen(config.OLLAMA_HOST + path, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def generate(prompt, image_path, max_tokens=80):
    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    out = _post(
        "/api/generate",
        {
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            # Small models happily ramble in circles; cap the length and keep
            # the sampling tight so the answer stays factual.
            "options": {"num_predict": max_tokens, "temperature": 0.2, "repeat_penalty": 1.3},
        },
        timeout=config.OLLAMA_TIMEOUT,
    )
    return (out.get("response") or "").strip()


def model_present():
    tags = _get("/api/tags")
    wanted = config.OLLAMA_MODEL
    names = {m.get("name", "") for m in tags.get("models", [])}
    return wanted in names or f"{wanted}:latest" in names


def ensure_model():
    """Pull the model if Ollama is up but does not have it yet. Slow the first time."""
    if model_present():
        return True
    log.info("pulling model %s", config.OLLAMA_MODEL)
    _post("/api/pull", {"name": config.OLLAMA_MODEL, "stream": False}, timeout=3600)
    return model_present()


def status(max_age=30):
    """Cheap health check for the UI, cached for a little while."""
    now = time.time()
    if now - _state["checked"] < max_age and _state["ok"] is not None:
        return dict(_state)
    try:
        present = model_present()
        _state.update(ok=present, detail="" if present else f"model {config.OLLAMA_MODEL} not downloaded yet")
    except Exception as exc:
        _state.update(ok=False, detail=f"cannot reach the model at {config.OLLAMA_HOST}")
    _state["checked"] = now
    return dict(_state)


# ---- clean-up of model output ----

LEAD_IN = re.compile(
    r"^(the|this)\s+(image|photo|picture)\s+(shows|is of|depicts|contains)\s+(an?\s+)?",
    re.I,
)


def clean_sentence(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = LEAD_IN.sub("", text)
    text = dedupe_fragments(text)
    text = text.strip(" ,;.")
    if len(text) > 300:
        # Cut at the last whole word rather than mid-word.
        text = text[:300].rsplit(" ", 1)[0].rstrip(" ,;")
    if text:
        text = text[0].upper() + text[1:]
    return text


def dedupe_fragments(text):
    """Small models loop: "black, right-angle, black, right-angle, ...".
    Keep the first appearance of each comma-separated fragment."""
    parts = [p.strip() for p in text.split(",")]
    out, seen = [], set()
    for p in parts:
        key = p.lower().rstrip(".")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return ", ".join(out)


def parse_list(text):
    names, seen = [], set()
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", raw).strip().strip(".").strip()
        if not line or len(line) > 60:
            continue
        # A sentence rather than a name: keep the bit before the first comma or colon.
        line = re.split(r"[:,]", line)[0].strip()
        key = line.lower()
        if key in seen or key in ("tray", "box", "table", "background"):
            continue
        seen.add(key)
        names.append(line[0].upper() + line[1:])
        if len(names) >= 40:
            break
    return names


def friendly_error(exc):
    if isinstance(exc, (urllib.error.URLError, ConnectionError, TimeoutError)):
        return "The model could not be reached. Check that Ollama is running, then try again."
    if isinstance(exc, urllib.error.HTTPError):
        return f"The model returned an error ({exc.code})."
    return (str(exc) or exc.__class__.__name__)[:200]


# ---- the worker ----

def enqueue_describe(item_id):
    _queue.put(("describe", item_id))


def enqueue_bulk(job_id):
    _queue.put(("bulk", job_id))


def _describe(item_id):
    with db.db() as conn:
        item = db.get_item(conn, item_id)
    if item is None or not item["photo"] or item["desc_status"] != "pending":
        return
    try:
        ensure_model()
        text = clean_sentence(generate(DESCRIBE_PROMPT.format(name=item["name"]), photos.path(item["photo"])))
        with db.db() as conn:
            db.set_description(conn, item_id, text, "done")
    except Exception as exc:
        log.warning("describe item %s failed: %s", item_id, exc)
        with db.db() as conn:
            db.set_description(conn, item_id, "", "failed")


def _bulk(job_id):
    with db.db() as conn:
        job = db.get_bulk_job(conn, job_id)
    if job is None or job["status"] != "pending":
        return
    try:
        ensure_model()
        names = parse_list(generate(BULK_PROMPT, photos.path(job["photo"]), max_tokens=300))
        with db.db() as conn:
            db.finish_bulk_job(conn, job_id, result="\n".join(names))
    except Exception as exc:
        log.warning("bulk job %s failed: %s", job_id, exc)
        with db.db() as conn:
            db.finish_bulk_job(conn, job_id, error=friendly_error(exc))


def _loop():
    while True:
        kind, ident = _queue.get()
        try:
            if kind == "describe":
                _describe(ident)
            elif kind == "bulk":
                _bulk(ident)
        except Exception:
            log.exception("worker error on %s %s", kind, ident)
        finally:
            _queue.task_done()


def start():
    """Start the single worker thread and re-queue anything left over from
    before a restart."""
    global _started
    if _started:
        return
    _started = True
    with db.db() as conn:
        for item_id in db.pending_item_ids(conn):
            enqueue_describe(item_id)
        for job_id in db.pending_bulk_job_ids(conn):
            enqueue_bulk(job_id)
    threading.Thread(target=_loop, name="vision", daemon=True).start()
