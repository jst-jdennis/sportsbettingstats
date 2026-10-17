"""Fetch, hash, Wayback-capture and text-extract a list of documents.

Used by the ingest workflow for research PDFs and regulator documents so that
figures can be read from the document itself rather than from summaries.

  python -m wpdc_ingest.archive_docs <out_dir> <url> [<url> ...]
  python -m wpdc_ingest.archive_docs <out_dir> --request <request.yaml>

A request file carries ``urls`` (plain GETs) and may carry ``forms``: entries
with ``url`` and ``data`` that are fetched by first GETting the page, taking
its hidden inputs (ASP.NET view state and the like), merging ``data`` over
them and POSTing the result to the same URL. The index records the method
and the form fields so the fetch can be repeated.

Writes, per URL: <sha256>.<ext>, <sha256>.txt (extracted text for PDFs),
and appends a line to index.jsonl with url, sha256, size, wayback URL and
retrieval date. Never raises on a single failure; failures go in the index.

URLs are fetched by a small pool of workers (WPDC_ARCHIVE_WORKERS, default
6) because a slow host or a slow Wayback capture otherwise holds up every
document behind it. A document has a hard budget: the download must finish
within FETCH_DEADLINE seconds and DOWNLOAD_CAP bytes (a server that trickles
bytes never trips a socket timeout), PDF text extraction stops after
MAX_PDF_PAGES pages, and a document that is still not done DOC_DEADLINE
seconds after its turn began is written to the index as an error so the run
ends and pushes what it has. The index is written one complete line at a
time under a lock, in the order the fetches finish. Extension is decided
from the Content-Type header, the URL and the file's leading bytes, so an
xlsx or csv served without a type is kept as such.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date
from pathlib import Path

import html as html_mod
import re

import requests

from .core.archive import USER_AGENT, sha256_bytes, wayback_capture

_lock = threading.Lock()
FETCH_DEADLINE = int(os.environ.get("WPDC_FETCH_DEADLINE", "180"))     # seconds for the whole download
DOWNLOAD_CAP = int(os.environ.get("WPDC_DOWNLOAD_CAP", str(80 * 1024 * 1024)))
MAX_PDF_PAGES = int(os.environ.get("WPDC_MAX_PDF_PAGES", "400"))
DOC_DEADLINE = int(os.environ.get("WPDC_DOC_DEADLINE", "480"))         # seconds per document, all steps


BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
# The Wayback Machine throttles concurrent save requests from one address, so captures are serialized.
_wayback_gate = threading.Semaphore(int(os.environ.get("WPDC_WAYBACK_CONCURRENCY", "1")))


class FetchAborted(Exception):
    pass


def fetch_within(url: str, deadline: int = FETCH_DEADLINE, cap: int = DOWNLOAD_CAP) -> tuple[requests.Response, bytes]:
    """Download with a wall-clock deadline and a size cap, not only a socket timeout.

    A watchdog closes the connection when the deadline passes, which makes a blocked read raise
    even against a server that trickles bytes forever.
    """
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=(30, 60), allow_redirects=True, stream=True)
    if r.status_code in (403, 406):
        # Several state web application firewalls refuse anything that does not look like a browser.
        # Retry once with ordinary browser headers; the index records that the fallback was used.
        r.close()
        r = requests.get(url, headers=BROWSER_HEADERS, timeout=(30, 60), allow_redirects=True, stream=True)
        r.headers["X-WPDC-UA-Fallback"] = "1"
    expired = threading.Event()

    def kill() -> None:
        expired.set()
        # Closing the response does not interrupt a read blocked in another thread; shutting the
        # socket down does.
        try:
            conn = getattr(r.raw, "connection", None) or getattr(r.raw, "_connection", None)
            sock = getattr(conn, "sock", None)
            if sock is None:  # fall back to the socket under http.client's buffered reader
                sock = getattr(getattr(getattr(r.raw, "_fp", None), "fp", None), "raw", None)
                sock = getattr(sock, "_sock", None)
            if sock is not None:
                sock.shutdown(socket.SHUT_RDWR)
        except Exception as e:  # noqa: BLE001
            print(f"watchdog: could not shut down the socket for {url}: {e!r}", file=sys.stderr, flush=True)
        # Do not call r.close() here: closing the buffered reader waits for the lock held by the
        # blocked read in the worker thread. The worker closes the response itself when the read fails.

    timer = threading.Timer(deadline, kill)
    timer.daemon = True
    timer.start()
    chunks: list[bytes] = []
    size = 0
    try:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if size > cap:
                r.close()
                raise FetchAborted(f"download exceeded {cap} bytes")
    except FetchAborted:
        raise
    except Exception as e:  # noqa: BLE001
        if expired.is_set():
            raise FetchAborted(f"download exceeded {deadline}s ({size} bytes received)") from None
        raise e
    finally:
        timer.cancel()
    if expired.is_set():
        raise FetchAborted(f"download exceeded {deadline}s ({size} bytes received)")
    return r, b"".join(chunks)


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


def hidden_inputs(html: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r'<input[^>]*type="hidden"[^>]*>', html, re.I):
        tag = m.group(0)
        n = re.search(r'name="([^"]*)"', tag)
        v = re.search(r'value="([^"]*)"', tag)
        if n:
            out[n.group(1)] = html_mod.unescape(v.group(1)) if v else ""
    return out


def post_form(url: str, data: dict, deadline: int = FETCH_DEADLINE) -> tuple[requests.Response, bytes]:
    """GET the page for its hidden fields, then POST the merged form. Browser headers throughout."""
    page = requests.get(url, headers=BROWSER_HEADERS, timeout=(30, 60))
    page.raise_for_status()
    form = hidden_inputs(page.text)
    form.update({k: str(v) for k, v in data.items()})
    r = requests.post(url, data=form, headers={**BROWSER_HEADERS, "Referer": url}, timeout=(30, deadline), allow_redirects=True)
    r.raise_for_status()
    return r, r.content


def archive_one(out: Path, url: str, form: dict | None = None) -> dict:
    rec: dict = {"url": url, "retrieved_at": date.today().isoformat()}
    if form is not None:
        rec["method"] = "post"
        rec["form"] = form
    try:
        if form is not None:
            r, content = post_form(url, form)
        else:
            r, content = fetch_within(url)
        ctype = r.headers.get("Content-Type", "")
        ext = extension(url, ctype, content)
        digest = sha256_bytes(content)
        path = out / f"{digest}.{ext}"
        path.write_bytes(content)
        rec.update({"final_url": r.url, "sha256": digest, "bytes": len(content), "content_type": ctype, "file": path.name})
        if r.headers.get("X-WPDC-UA-Fallback"):
            rec["user_agent_fallback"] = True
        if ext == "pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    total = len(pdf.pages)
                    pages = [(p.extract_text() or "") for p in pdf.pages[:MAX_PDF_PAGES]]
                (out / f"{digest}.txt").write_text("\n\n".join(f"=== page {i+1} ===\n{t}" for i, t in enumerate(pages)))
                rec["pages"] = total
                rec["text_file"] = f"{digest}.txt"
                if total > MAX_PDF_PAGES:
                    rec["text_truncated_at_page"] = MAX_PDF_PAGES
            except Exception as e:  # noqa: BLE001
                rec["text_error"] = str(e)
        with _wayback_gate:
            rec["archive_url"] = wayback_capture(url)
    except Exception as e:  # noqa: BLE001
        rec["error"] = str(e)
    return rec


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    idx = out / "index.jsonl"
    jobs: list[tuple[str, dict | None]] = []
    if len(argv) >= 3 and argv[1] == "--request":
        import yaml
        req = yaml.safe_load(Path(argv[2]).read_text()) or {}
        jobs += [(u, None) for u in req.get("urls") or []]
        jobs += [(f["url"], dict(f.get("data") or {})) for f in req.get("forms") or []]
    else:
        jobs = [(u, None) for u in argv[1:]]
    workers = max(1, min(int(os.environ.get("WPDC_ARCHIVE_WORKERS", "6")), len(jobs) or 1))
    rc = 0

    def emit(rec: dict) -> None:
        with _lock:
            with idx.open("a") as f:
                f.write(json.dumps(rec) + "\n")
            print(json.dumps(rec), flush=True)

    begun: dict[int, float] = {}  # job id -> when a worker actually started it (several forms may share a URL)

    def run(job: tuple[str, dict | None]) -> dict:
        url, form = job
        with _lock:
            begun[id(job)] = time.monotonic()
        rec = archive_one(out, url, form)
        emit(rec)
        return rec

    # Each document gets DOC_DEADLINE seconds from the moment a worker picks it up. Workers cannot be
    # interrupted, so a document that overruns is recorded as an error and the process exits without
    # waiting for the stuck thread once every other document is done.
    pool = ThreadPoolExecutor(max_workers=workers)
    pending: dict = {}
    queue = list(jobs)

    def submit_next() -> None:
        while queue and len(pending) < workers:
            j = queue.pop(0)
            pending[pool.submit(run, j)] = j

    submit_next()
    gave_up = False
    while pending:
        done, _ = wait(list(pending), timeout=5, return_when=FIRST_COMPLETED)
        for fut in done:
            j = pending.pop(fut)
            try:
                if fut.result().get("error"):
                    rc = 1
            except Exception as e:  # noqa: BLE001
                rc = 1
                emit({"url": j[0], "retrieved_at": date.today().isoformat(), "error": f"worker crashed: {e}"})
        now = time.monotonic()
        for fut, j in list(pending.items()):
            with _lock:
                t0 = begun.get(id(j))
            if t0 is not None and now - t0 > DOC_DEADLINE:
                pending.pop(fut)
                emit({"url": j[0], "retrieved_at": date.today().isoformat(), "error": f"gave up after {DOC_DEADLINE}s"})
                rc = 1
                gave_up = True
        submit_next()
    if gave_up:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(rc)  # stuck worker threads would otherwise keep the process alive
    pool.shutdown(wait=True)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
