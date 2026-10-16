"""Immutable raw-document archive and Wayback capture."""
from __future__ import annotations

import hashlib
import re
import json
from datetime import date
from pathlib import Path

import requests

from .source import Document, RawDocument

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = REPO_ROOT / "archive" / "raw"
USER_AGENT = "wpdc-ingest/0.1 (+https://github.com/jst-jdennis/sportsbettingstats)"


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
    r.raise_for_status()
    return r.content


def wayback_capture(url: str, timeout: int = 60) -> str | None:
    """Ask the Wayback Machine to capture the URL. Returns the capture URL or None.

    Failure is not fatal: the local hash still proves what was parsed, and the
    record goes through with archive_url null and a warning in the review
    checklist.
    """
    try:
        r = requests.get(f"https://web.archive.org/save/{url}", headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
        loc = r.headers.get("Content-Location") or r.url
        if not loc.startswith("http"):
            loc = "https://web.archive.org" + loc
        # Only a capture URL counts; a /save/ URL that was not redirected is a failed capture,
        # even when the requested URL itself was a web.archive.org address.
        if re.match(r"^https?://web\.archive\.org/web/\d{14}", loc):
            return loc
    except requests.RequestException:
        return None
    return None


def fetch(source_id: str, doc: Document, ext: str, *, wayback: bool = True) -> RawDocument:
    content = fetch_bytes(doc.url)
    archive_url = wayback_capture(doc.url) if wayback else None
    return store(source_id, doc, content, ext, archive_url)


def from_local(source_id: str, doc: Document, path: Path, ext: str) -> RawDocument:
    """Register a document a contributor downloaded by hand (or a test fixture)."""
    return store(source_id, doc, path.read_bytes(), ext, None)
