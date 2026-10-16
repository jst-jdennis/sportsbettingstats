"""Deterministic writers. Stable column order and sorting keep diffs reviewable."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .archive import REPO_ROOT

SCHEMAS = REPO_ROOT / "schemas"
DATA = REPO_ROOT / "data"


def table_columns(dataset_schema: str) -> list[str]:
    s = json.loads((SCHEMAS / f"{dataset_schema}.tableschema.json").read_text())
    return [f["name"] for f in s["fields"]]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def upsert_csv(path: Path, dataset_schema: str, new_rows: Iterable[dict[str, Any]], key: tuple[str, ...], sort: tuple[str, ...]) -> tuple[int, int]:
    """Insert or supersede rows by key.

    When a new row has the same key as an existing non-superseded row and
    different values, the existing row is kept with status superseded and the
    new row is added. Identical rows are skipped. Returns (added, superseded).
    """
    cols = table_columns(dataset_schema)
    existing = read_csv(path)
    value_cols = [c for c in cols if c not in ("source_id", "source_url", "archive_url", "retrieved_at", "status", "entered_by", "reviewed_by", "notes")]

    def k(r: dict[str, Any]) -> tuple:
        return tuple(str(r.get(c, "")) for c in key)

    def v(r: dict[str, Any]) -> tuple:
        return tuple(str(r.get(c, "") if r.get(c) is not None else "") for c in value_cols if c not in key)

    by_key: dict[tuple, list[dict[str, Any]]] = {}
    for r in existing:
        by_key.setdefault(k(r), []).append(r)

    added = superseded = 0
    for nr in new_rows:
        nr = {c: ("" if nr.get(c) is None else nr.get(c)) for c in cols}
        current = [r for r in by_key.get(k(nr), []) if r.get("status") != "superseded"]
        if any(v(r) == v(nr) for r in current):
            continue
        for r in current:
            r["status"] = "superseded"
            superseded += 1
        if nr.get("is_revised") is not None and current:
            nr["is_revised"] = "true"
        existing.append(nr)
        by_key.setdefault(k(nr), []).append(nr)
        added += 1

    existing.sort(key=lambda r: tuple(str(r.get(c, "")) for c in sort))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in existing:
            w.writerow({c: _fmt(r.get(c, "")) for c in cols})
    return added, superseded


def _fmt(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    if x is None:
        return ""
    return str(x)
