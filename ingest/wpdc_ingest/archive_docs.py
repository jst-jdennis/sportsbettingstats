"""Fetch, hash, Wayback-capture and text-extract a list of documents.

Used by the ingest workflow for research PDFs and regulator documents so that
figures can be read from the document itself rather than from summaries.

  python -m wpdc_ingest.archive_docs <out_dir> <url> [<url> ...]

Writes, per URL: <sha256>.<ext>, <sha256>.txt (extracted text for PDFs),
and appends a line to index.jsonl with url, sha256, size, wayback URL and
retrieval date. Never raises on a single failure; failures go in the index.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import requests

from .core.archive import USER_AGENT, sha256_bytes, wayback_capture


def main(argv: list[str]) -> int:
    out = Path(argv[0])
    out.mkdir(parents=True, exist_ok=True)
    idx = out / "index.jsonl"
    rc = 0
    for url in argv[1:]:
        rec: dict = {"url": url, "retrieved_at": date.today().isoformat()}
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, allow_redirects=True)
            r.raise_for_status()
            content = r.content
            ctype = r.headers.get("Content-Type", "")
            ext = "pdf" if "pdf" in ctype or url.lower().endswith(".pdf") or content[:5] == b"%PDF-" else "html" if "html" in ctype else "bin"
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
            rc = 1
        with idx.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(json.dumps(rec))
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
