"""Census Bureau Population Estimates: annual state totals for per capita denominators.

Uses the Population Estimates API for the latest vintage. Example:
https://api.census.gov/data/2024/pep/population?get=NAME,POP_2024&for=state:*
(the variable name carries the vintage year; the module tries the current year
and falls back one year). No API key is required for low volumes.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Any

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "census-pep-state-totals"
API = "https://api.census.gov/data/{vintage}/pep/population?get=NAME,POP_{vintage}&for=state:*"


class CensusPopulation:
    source_id = SOURCE_ID
    dataset = "reference/population.csv"

    def discover(self, period: Period | None) -> list[Document]:
        vintage = date.today().year - 1 if date.today().month < 7 else date.today().year
        return [Document(url=API.format(vintage=v), kind="json", label=f"Census PEP vintage {v}") for v in (vintage, vintage - 1)]

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        data = json.loads(raw.path.read_text())
        if not isinstance(data, list) or not data or "NAME" not in data[0]:
            raise LayoutChanged(f"Unexpected Census API shape: {str(data)[:120]}")
        header = data[0]
        pop_col = next(i for i, h in enumerate(header) if h.startswith("POP_"))
        vintage = int(header[pop_col].split("_")[1])
        st = header.index("state")
        out = []
        for r in data[1:]:
            fips = r[st]
            if fips in ("72",):  # Puerto Rico not in scope
                continue
            out.append({"fips": fips, "year": vintage, "population": int(r[pop_col]), "vintage": vintage})
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        rows = []
        for rec in records:
            prov = provenance.block(SOURCE_ID, raw, method="api", entered_by="wpdc_ingest.census_population")
            rows.append(Row(values=rec, provenance=provenance.csv_columns(prov)))
        return rows
