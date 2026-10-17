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
    ing.add_argument("--candidate", type=int, default=0, help="With --local: index of the discovered document the file stands for (see wpdc discover)")
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
    raws = []
    if a.local:
        doc = docs[a.candidate]
        if doc.kind == "html":
            # A manual drop skips page discovery; the file is the document itself.
            kind = a.local.suffix.lstrip(".").lower() or "pdf"
            doc = Document(url=doc.url, period=doc.period, kind=kind, label=doc.label, meta=(("measure", "quarter"),))
        raws.append(archive.from_local(src.source_id, doc, a.local, doc.kind))
    else:
        last_err: Exception | None = None
        done_measures: set[str] = set()  # with fetch_all, one parsed document per measure is enough
        failures: list[tuple[str, str]] = []
        parsed_ok: list = []
        for doc in docs:
            try:
                candidate = []
                if doc.kind == "html":
                    html = archive.fetch_bytes(doc.url).decode("utf-8", "replace")
                    files = [f for f in src.resolve(doc, html) if not (f.get("measure") and f.get("measure") in done_measures)]
                    print(f"resolved {len(files)} document(s) still needed from {doc.url}")
                    if not files:
                        continue
                    for f in files:
                        if getattr(src, "fetch_all", False):
                            # A back series: one bad month must not take the others down. Fetch and parse
                            # each file on its own, keep the ones that parse and report the rest.
                            try:
                                raw = archive.fetch(src.source_id, f, f.kind, wayback=not a.no_wayback)
                                print(f"parsing {raw.path.name} ({raw.doc.label}) sha256={raw.sha256[:12]} archive_url={raw.archive_url}")
                                src.parse(raw)
                                candidate.append(raw)
                            except Exception as e:  # noqa: BLE001
                                failures.append((f.url, f"{type(e).__name__}: {e}"))
                                print(f"failed {f.label or f.url}: {type(e).__name__}: {e}")
                        else:
                            candidate.append(archive.fetch(src.source_id, f, f.kind, wayback=not a.no_wayback))
                else:
                    if doc.get("measure") and doc.get("measure") in done_measures:
                        continue
                    candidate.append(archive.fetch(src.source_id, doc, doc.kind, wayback=not a.no_wayback))
                # Parse now so that a wrong-shaped candidate (an HTML error page served as 200) falls through.
                for raw in candidate:
                    if raw in parsed_ok:
                        continue
                    print(f"parsing {raw.path.name} ({raw.doc.label}) sha256={raw.sha256[:12]} archive_url={raw.archive_url}")
                    src.parse(raw)
                    parsed_ok.append(raw)
                raws.extend(candidate)
                done_measures.update(m for m in (r.doc.get("measure") for r in candidate) if m)
                if not getattr(src, "fetch_all", False):
                    break
            except Exception as e:  # noqa: BLE001
                last_err = e
                print(f"skip {doc.url}: {type(e).__name__}: {e}")
        if failures:
            print(f"\n{len(failures)} document(s) in the series could not be parsed and were left out:")
            for u, err in failures:
                print(f"  {u}\n    {err[:300]}")
        if not raws:
            raise SystemExit(f"no document could be fetched and parsed for {src.source_id}: {last_err}")
    rows = []
    for raw in raws:
        records = src.parse(raw)
        rows.extend(r.finalize() for r in src.normalize(records, raw))
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
