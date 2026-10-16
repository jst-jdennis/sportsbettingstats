"""Census Bureau Population Estimates: annual state totals for per capita denominators.

Two access paths, tried in order:

1. The published dataset CSV for the current decade, which carries every
   July 1 estimate in the vintage (POPESTIMATE2020 ... POPESTIMATE20NN):
   https://www2.census.gov/programs-surveys/popest/datasets/2020-20NN/state/totals/NST-EST20NN-ALLDATA.csv
2. The Population Estimates API for one vintage year:
   https://api.census.gov/data/20NN/pep/population?get=NAME,POP_20NN&for=state:*

The CSV is preferred because it yields the whole series in one document and
has a stable layout. Non-JSON API responses (the API returns an HTML error
page with status 200 when a vintage does not exist) raise LayoutChanged so
the CLI moves on to the next candidate.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date
from typing import Any

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "census-pep-state-totals"
CSV_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-{v}/state/totals/NST-EST{v}-ALLDATA.csv"
API = "https://api.census.gov/data/{v}/pep/population?get=NAME,POP_{v}&for=state:*"
EXCLUDE_FIPS = {"72"}  # Puerto Rico is outside the site's scope


class CensusPopulation:
    source_id = SOURCE_ID
    dataset = "reference/population.csv"

    def discover(self, period: Period | None) -> list[Document]:
        # Vintage N is released in December of year N; before that the latest is N-1.
        today = date.today()
        latest = today.year if today.month == 12 else today.year - 1
        docs: list[Document] = []
        for v in (latest, latest - 1):
            docs.append(Document(url=CSV_URL.format(v=v), kind="csv", label=f"Census NST-EST{v}-ALLDATA", meta=(("vintage", v),)))
        for v in (latest, latest - 1):
            docs.append(Document(url=API.format(v=v), kind="json", label=f"Census PEP API vintage {v}", meta=(("vintage", v),)))
        return docs

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        text = raw.path.read_text(encoding="utf-8", errors="replace")
        if raw.doc.kind == "csv":
            return self._parse_csv(text, raw)
        return self._parse_api(text, raw)

    def _parse_csv(self, text: str, raw: RawDocument) -> list[dict[str, Any]]:
        rdr = csv.DictReader(io.StringIO(text))
        cols = rdr.fieldnames or []
        est_cols = [c for c in cols if re.fullmatch(r"POPESTIMATE\d{4}", c)]  # skips POPESTIMATE042020, the April 1 base
        if "STATE" not in cols or "SUMLEV" not in cols or not est_cols:
            raise LayoutChanged(f"{raw.path.name}: expected SUMLEV, STATE and POPESTIMATEyyyy columns; got {cols[:12]}")
        vintage = int(raw.doc.get("vintage"))
        out = []
        for r in rdr:
            if r["SUMLEV"] != "040":  # states and DC only (not regions or the nation)
                continue
            fips = r["STATE"].zfill(2)
            if fips in EXCLUDE_FIPS:
                continue
            for c in est_cols:
                year = int(c[len("POPESTIMATE"):])
                out.append({"fips": fips, "year": year, "population": int(float(r[c])), "vintage": vintage})
        if not out:
            raise LayoutChanged(f"{raw.path.name}: no SUMLEV 040 rows found")
        return out

    def _parse_api(self, text: str, raw: RawDocument) -> list[dict[str, Any]]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise LayoutChanged(f"{raw.path.name}: response is not JSON (first 80 chars: {text[:80]!r}); the vintage is probably not published")
        if not isinstance(data, list) or not data or "NAME" not in data[0]:
            raise LayoutChanged(f"Unexpected Census API shape: {str(data)[:120]}")
        header = data[0]
        pop_col = next(i for i, h in enumerate(header) if h.startswith("POP_"))
        vintage = int(header[pop_col].split("_")[1])
        st = header.index("state")
        out = []
        for r in data[1:]:
            fips = r[st]
            if fips in EXCLUDE_FIPS:
                continue
            out.append({"fips": fips, "year": vintage, "population": int(r[pop_col]), "vintage": vintage})
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        rows = []
        for rec in records:
            prov = provenance.block(SOURCE_ID, raw, method="bulk_download" if raw.doc.kind == "csv" else "api", entered_by="wpdc_ingest.census_population")
            rows.append(Row(values=rec, provenance=provenance.csv_columns(prov), transform_steps=[f"July 1 estimate POPESTIMATE{rec['year']} from vintage {rec['vintage']}"]))
        return rows
