"""Source protocol and shared types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol


class LayoutChanged(Exception):
    """Raised by parse() when a document does not match the expected layout.

    The message must say what fingerprint was expected and what was found so
    that a contributor can add a fixture and a parser branch.
    """


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @classmethod
    def month(cls, year: int, month: int) -> "Period":
        import calendar
        return cls(date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1]))

    @classmethod
    def quarter_ending(cls, year: int, month: int) -> "Period":
        """Calendar quarter ending in the given month (3, 6, 9 or 12)."""
        import calendar
        start_month = month - 2
        return cls(date(year, start_month, 1), date(year, month, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class Document:
    """Something discover() found: a URL to fetch or a local path a contributor dropped.

    When ``kind`` is ``html``, the CLI fetches the page and calls the source's
    ``resolve(doc, html)`` to turn it into the file documents to ingest.
    ``meta`` carries per-document facts such as the measure of a table.
    """
    url: str
    period: Period | None = None
    kind: str = "pdf"          # pdf, xlsx, html, json, csv
    label: str = ""             # human label used in review checklists
    meta: tuple = ()            # tuple of (key, value) pairs; frozen dataclasses cannot hold a dict

    def get(self, key: str, default=None):
        return dict(self.meta).get(key, default)


@dataclass(frozen=True)
class RawDocument:
    doc: Document
    path: Path                  # archive/raw/<source_id>/<sha256>.<ext>
    sha256: str
    retrieved_at: date
    archive_url: str | None     # Wayback capture URL, or None if the capture failed


@dataclass
class Row:
    """A normalized output row plus the provenance that will be written with it."""
    values: dict[str, Any]
    provenance: dict[str, Any]
    transform_steps: list[str] = field(default_factory=list)

    def finalize(self) -> dict[str, Any]:
        prov = dict(self.provenance)
        if self.transform_steps and not prov.get("transform"):
            prov["transform"] = "; ".join(self.transform_steps)
        return {**self.values, **prov}


class Source(Protocol):
    source_id: str
    dataset: str                # e.g. "outcomes/bankruptcy.csv"

    def discover(self, period: Period | None) -> list[Document]: ...
    def resolve(self, doc: Document, html: str) -> list[Document]: ...  # only for kind == "html"
    def parse(self, raw: RawDocument) -> list[dict[str, Any]]: ...
    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]: ...
