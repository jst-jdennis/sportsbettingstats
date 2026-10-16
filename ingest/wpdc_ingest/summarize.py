"""Print a compact, log-friendly summary of an ingest run's outputs.

The workflow calls this after the requests so that a maintainer who cannot
download artifacts can still see what came back: the archive index, every
link on archived HTML pages that matches a pattern, the first lines of each
extracted PDF text (title page), and lines matching request-supplied grep
patterns. Output is capped per section to keep the log readable.

  python -m wpdc_ingest.summarize out/ [--grep PATTERN ...] [--href PATTERN ...]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--grep", action="append", default=[], help="regex to search in extracted texts and logs")
    ap.add_argument("--href", action="append", default=[], help="regex an href must match to be listed")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args(argv)
    out = Path(a.out)
    for idx in sorted(out.rglob("index.jsonl")):
        print(f"::group::index {idx.relative_to(out)}")
        print(idx.read_text()[:20000])
        print("::endgroup::")
    hrefs_re = [re.compile(p, re.I) for p in a.href] or [re.compile(r".")]
    for html in sorted(out.rglob("*.html")):
        text = html.read_text(errors="replace")
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', text, re.I | re.S)
        hits = []
        for href, label in links:
            lab = re.sub(r"<[^>]+>|\s+", " ", label).strip()[:80]
            if any(r.search(href) or r.search(lab) for r in hrefs_re):
                hits.append(f"{href}  [{lab}]")
        print(f"::group::hrefs {html.relative_to(out)} ({len(hits)} of {len(links)} links)")
        print("\n".join(hits[: a.max]))
        print("::endgroup::")
    greps = [re.compile(p, re.I) for p in a.grep]
    for txt in sorted(out.rglob("*.txt")):
        if txt.name == "git-status.txt":
            continue
        lines = txt.read_text(errors="replace").splitlines()
        print(f"::group::text {txt.relative_to(out)} ({len(lines)} lines)")
        print("\n".join(lines[:14]))
        if greps:
            print("--- matches ---")
            n = 0
            for i, line in enumerate(lines):
                if any(g.search(line) for g in greps):
                    print(f"{i+1}: {line[:220]}")
                    n += 1
                    if n >= a.max:
                        print("... (capped)")
                        break
        print("::endgroup::")
    for log in sorted(out.rglob("*.log")):
        print(f"::group::log {log.relative_to(out)}")
        print(log.read_text(errors="replace")[-6000:])
        print("::endgroup::")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
