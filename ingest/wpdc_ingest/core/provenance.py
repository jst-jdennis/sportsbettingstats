"""Build the standard provenance block for a row."""
from __future__ import annotations

from typing import Any

from .source import RawDocument


def block(source_id: str, raw: RawDocument, *, method: str, entered_by: str, page_or_table: str | None = None, transform: str | None = None, notes: str | None = None) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "source_url": raw.doc.url,
        "archive_url": raw.archive_url,
        "retrieved_at": raw.retrieved_at.isoformat(),
        "retrieval_method": method,
        "transform": transform,
        "entered_by": entered_by,
        "reviewed_by": None,
        "status": "pending_review",
        "page_or_table": page_or_table,
        "notes": notes,
    }


def csv_columns(p: dict[str, Any]) -> dict[str, Any]:
    """The subset of the block that CSV datasets carry as columns."""
    return {k: p.get(k) for k in ("source_id", "source_url", "archive_url", "retrieved_at", "status", "entered_by", "reviewed_by", "notes")}
