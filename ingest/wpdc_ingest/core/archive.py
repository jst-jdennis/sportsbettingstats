"""Immutable raw-document archive and Wayback capture."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import date
from pathlib import Path

import requests

from .source import Document, RawDocument

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = REPO_ROOT / "archive" / "raw"
USER_AGENT = "wpdc-ingest/0.1 (+https://github.com/jst-jdennis/sportsbettingstats)"
# Several state web application firewalls refuse anything that does not look like a browser; a refused
# fetch is retried once with these headers (the archive index and the review checklist say when).
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_wayback_lock = threading.Lock()
_wayback_last = [0.0]
WAYBACK_GAP_SECONDS = 2.0


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def store(source_id: str, doc: Document, content: bytes, ext: str, archive_url: str | None) -> RawDocument:
    d = ARCHIVE / source_id
    d.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(content)
    path = d / f"{digest}.{ext}"
    if not path.exists():
        path.write_bytes(content)
    retrieved = date.today()
    with (d / "index.jsonl").open("a") as f:
        f.write(json.dumps({"sha256": digest, "url": doc.url, "retrieved_at": retrieved.isoformat(), "archive_url": archive_url, "label": doc.label}) + "\n")
    return RawDocument(doc=doc, path=path, sha256=digest, retrieved_at=retrieved, archive_url=archive_url)


def fetch_bytes(url: str, timeout: int = 60) -> bytes:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    if r.status_code in (403, 406):
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.content


def post_form(url: str, data: dict, timeout: int = 120) -> bytes:
    """GET the page for its hidden inputs (ASP.NET view state and the like), merge ``data`` and POST."""
    import html as html_mod

    page = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout)
    page.raise_for_status()
    form: dict[str, str] = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', page.text, re.I):
        n = re.search(r'name="([^"]*)"', m.group(0))
        v = re.search(r'value="([^"]*)"', m.group(0))
        if n:
            form[n.group(1)] = html_mod.unescape(v.group(1)) if v else ""
    form.update({k: str(v) for k, v in data.items()})
    r = requests.post(url, data=form, headers={**BROWSER_HEADERS, "Referer": url}, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    return r.content


def wayback_capture(url: str, timeout: int = 60) -> str | None:
    """Ask the Wayback Machine to capture the URL. Returns the capture URL or None.

    Failure is not fatal: the local hash still proves what was parsed, and the
    record goes through with archive_url null and a warning in the review
    checklist.
    """
    # The Wayback Machine throttles bursts from one address: captures are spaced out and a throttled or
    # failed save is retried once after a pause.
    for attempt in range(2):
        with _wayback_lock:
            wait = WAYBACK_GAP_SECONDS - (time.monotonic() - _wayback_last[0])
            if wait > 0:
                time.sleep(wait)
            _wayback_last[0] = time.monotonic()
        try:
            r = requests.get(f"https://web.archive.org/save/{url}", headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
            loc = r.headers.get("Content-Location") or r.url
            if not loc.startswith("http"):
                loc = "https://web.archive.org" + loc
            # Only a capture URL counts; a /save/ URL that was not redirected is a failed capture,
            # even when the requested URL itself was a web.archive.org address.
            if re.match(r"^https?://web\.archive\.org/web/\d{14}", loc):
                return loc
            if r.status_code not in (429, 500, 502, 503, 504):
                return None
        except requests.RequestException:
            return None  # no route to the Machine: nothing a retry would change
        if attempt == 0:
            time.sleep(10)  # throttled: pause, then try once more
    return None


PART_MARKER = "==== wpdc part: {name} ===="


def fetch(source_id: str, doc: Document, ext: str, *, wayback: bool = True) -> RawDocument:
    """Fetch a document. A document whose meta carries ``posts`` (a JSON list of {name, data}) is a set of
    form posts to its URL; the responses are stored as one file, each part preceded by a marker line, and
    no Wayback capture is requested because the Machine cannot replay a post."""
    posts = doc.get("posts")
    if posts:
        parts = []
        for part in json.loads(posts):
            body = post_form(doc.url, part["data"]).decode("utf-8", "replace")
            parts.append(PART_MARKER.format(name=part["name"]) + "\n" + body.strip() + "\n")
        return store(source_id, doc, "".join(parts).encode("utf-8"), ext, None)
    content = fetch_bytes(doc.url)
    archive_url = wayback_capture(doc.url) if wayback else None
    return store(source_id, doc, content, ext, archive_url)


def from_local(source_id: str, doc: Document, path: Path, ext: str) -> RawDocument:
    """Register a document a contributor downloaded by hand (or a test fixture)."""
    return store(source_id, doc, path.read_bytes(), ext, None)
