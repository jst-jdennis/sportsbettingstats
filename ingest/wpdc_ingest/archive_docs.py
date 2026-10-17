"""Fetch, hash, Wayback-capture and text-extract a list of documents.

Used by the ingest workflow for research PDFs and regulator documents so that
figures can be read from the document itself rather than from summaries.

  python -m wpdc_ingest.archive_docs <out_dir> <url> [<url> ...]

Writes, per URL: <sha256>.<ext>, <sha256>.txt (extracted text for PDFs),
and appends a line to index.jsonl with url, sha256, size, wayback URL and
retrieval date. Never raises on a single failure; failures go in the index.

URLs are fetched by a small pool of workers (WPDC_ARCHIVE_WORKERS, default
6) because a slow host or a slow Wayback capture otherwise holds up every
document behind it. Each URL still gets the same per-request timeouts, and
the index is written one complete line at a time under a lock, in the order
the fetches finish. Extension is decided from the Content-Type header, the
URL and the file's leading bytes, so an xlsx or csv served without a type is
kept as such.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

from .core.archive import USER_AGENT, sha256_bytes, wayback_capture

_lock = threading.Lock()


def extension(url: str, ctype: str, content: bytes) -> str:
    low = url.lower().split("?", 1)[0]
    ct = ctype.lower()
    if "pdf" in ct or low.endswith(".pdf") or content[:5] == b"%PDF-":
        return "pdf"
    if "spreadsheetml" in ct or low.endswith(".xlsx") or (content[:2] == b"PK" and b"xl/" in content[:4000]):
        return "xlsx"
    if "ms-excel" in ct or low.endswith(".xls"):
        return "xls"
    if "csv" in ct or low.endswith(".csv"):
        return "csv"
    if "json" in ct or low.endswith(".json"):
        return "json"
    if "html" in ct or content[:200].lstrip().lower().startswith((b"<!doctype", b"<html")):
        return "html"
    return "bin"


def archive_one(out: Path, url: str) -> dict:
    rec: dict = {"url": url, "retrieved_at": date.today().isoformat()}
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, allow_redirects=True)
        r.raise_for_status()
        content = r.content
        ctype = r.headers.get("Content-Type", "")
        ext = extension(url, ctype, content)
        digest = sha256_bytes(content)
        path = out / f"{digest}.{ext}"
        path.write_bytes(content)
        rec.update({"final_url": r.url, "sha256": digest, "bytes": len(content), "content_type": ctype, "file": path.name})
        if ext == "pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    pages = [(p.extract_text() or "") for p in pdf.pages]
                (out / f"{digest}.txt").write_text("\n\n".join(f"=== page {i+1} ===\n{t}" for i, t in enumerate(pages)))
                rec["pages"] = len(pages)
                rec["text_file"] = f"{digest}.txt"
            except Exception as e:  # noqa: BLE001
                rec["text_error"] = str(e)
        rec["archive_url"] = wayback_capture(url)
    except Exception as e:  # noqa: BLE001
        rec["error"] = str(e)
    return rec


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    idx = out / "index.jsonl"
    urls = argv[1:]
    workers = max(1, min(int(os.environ.get("WPDC_ARCHIVE_WORKERS", "6")), len(urls) or 1))
    rc = 0

    def run(url: str) -> dict:
        rec = archive_one(out, url)
        with _lock:
            with idx.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)
        return rec

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for rec in pool.map(run, urls):
            if rec.get("error"):
                rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
