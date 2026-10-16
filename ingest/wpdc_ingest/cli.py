"""Command line entry point.

  wpdc ingest <source_id> [--period YYYY-MM | YYYY-Qn] [--local PATH] [--no-wayback]
  wpdc validate
  wpdc list
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .core import archive, validate, writers
from .core.review import checklist
from .core.source import Document, Period
from .sources import REGISTRY, load

KEYS = {
    "outcomes/bankruptcy.csv": (("fips", "period_start", "period_end", "measure", "chapter"), ("fips", "period_start", "chapter")),
    "outcomes/handle_revenue.csv": (("fips", "period_start", "period_end", "channel", "market_segment"), ("fips", "period_start", "channel")),
    "reference/population.csv": (("fips", "year", "vintage"), ("fips", "year")),
}
SCHEMA_FOR = {"outcomes/bankruptcy.csv": "bankruptcy", "outcomes/handle_revenue.csv": "handle_revenue", "reference/population.csv": "population"}


def parse_period(s: str | None) -> Period | None:
    if not s:
        return None
    if "Q" in s.upper():
        y, q = s.upper().split("Q")
        return Period.quarter_ending(int(y.rstrip("-")), int(q) * 3)
    y, m = s.split("-")
    return Period.month(int(y), int(m))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wpdc")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="Fetch, parse, normalize and write one source")
    ing.add_argument("source_id", choices=sorted(REGISTRY))
    ing.add_argument("--period", help="YYYY-MM for monthly sources, YYYY-Qn for quarterly")
    ing.add_argument("--local", type=Path, help="Use a downloaded file instead of fetching (manual drop or fixture)")
    ing.add_argument("--no-wayback", action="store_true")
    ing.add_argument("--dry-run", action="store_true", help="Parse and print rows; write nothing")
    sub.add_parser("validate", help="Run the repository validator")
    sub.add_parser("list", help="List registered sources")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for k in sorted(REGISTRY):
            print(k)
        return 0
    if a.cmd == "validate":
        return validate.run()

    src = load(a.source_id)
    period = parse_period(a.period)
    docs = src.discover(period)
    doc = docs[0]
    ext = doc.kind
    if a.local:
        raw = archive.from_local(src.source_id, Document(url=doc.url, period=doc.period, kind=doc.kind, label=doc.label), a.local, ext)
    else:
        raw = archive.fetch(src.source_id, doc, ext, wayback=not a.no_wayback)
    records = src.parse(raw)
    rows = [r.finalize() for r in src.normalize(records, raw)]
    key, sort = KEYS[src.dataset]
    if a.dry_run:
        for r in rows:
            print(r)
        return 0
    added, superseded = writers.upsert_csv(writers.DATA / src.dataset, SCHEMA_FOR[src.dataset], rows, key, sort)
    print(f"{src.dataset}: {added} row(s) added, {superseded} superseded")
    print()
    print(checklist(src.source_id, rows, [c for c in rows[0] if c not in ("source_id", "source_url", "archive_url", "retrieved_at", "status", "entered_by", "reviewed_by", "notes")] if rows else []))
    return validate.run()


if __name__ == "__main__":
    sys.exit(main())
