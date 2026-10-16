"""Render the review checklist that goes into a data pull request body."""
from __future__ import annotations

from typing import Any, Iterable


def checklist(source_id: str, rows: Iterable[dict[str, Any]], value_cols: Iterable[str]) -> str:
    rows = list(rows)
    value_cols = list(value_cols)
    lines = [f"## Data review: `{source_id}`", "", f"{len(rows)} row(s). For each row, open the source link, find the page or table named, and confirm the values. Tick the box only when every value matches.", ""]
    for r in rows:
        vals = ", ".join(f"{c}={r.get(c)}" for c in value_cols if r.get(c) not in (None, ""))
        arch = f" ([archived]({r['archive_url']}))" if r.get("archive_url") else " (no archive capture; local hash on file)"
        lines.append(f"- [ ] {r.get('fips','')} {r.get('period_start','')}..{r.get('period_end','')}: {vals}. [Source]({r.get('source_url')}){arch}")
    lines += ["", "Reviewer: approving this pull request records your handle in `reviewed_by` and sets `status: verified` on these rows."]
    return "\n".join(lines)
