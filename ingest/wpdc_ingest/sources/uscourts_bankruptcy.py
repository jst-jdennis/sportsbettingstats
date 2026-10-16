"""US Courts Bankruptcy Filings Statistics, Table F-2.

Table F-2 reports business and nonbusiness filings by chapter for each of the
94 federal judicial districts, for the quarter and for the twelve months ending
the quarter. It is published as an xlsx about four to six weeks after quarter
end on the Bankruptcy Filings Statistics page.

Layout fingerprint: a sheet whose header row contains "Circuit and District"
(or "District") and chapter columns labelled "Chapter 7", "Chapter 11" and
"Chapter 13" under a "Nonbusiness" group. District rows are labelled with the
short codes the AO uses ("ALN", "NYS", "DC", ...). Total and circuit rows are
skipped. If none of the expected labels is found the parser raises
LayoutChanged with what it saw.

Output: outcomes/bankruptcy.csv rows per state, chapter in {7, 11, 13,
all_nonbusiness}, summed across the state's districts via
reference/districts.csv.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import openpyxl

from ..core import provenance
from ..core.archive import REPO_ROOT
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "uscourts-bankruptcy-f2"
LANDING = "https://www.uscourts.gov/data-news/reports/statistical-reports/bankruptcy-filings-statistics"
# The AO publishes each quarter under a dated node, e.g. .../bankruptcy-filings-statistics/2026/03/31,
# with one row per table and a Download link. discover() returns that page as an html document; resolve()
# finds the F-2 links on it. Both the three-month and the twelve-month F-2 tables are ingested, with
# measure recorded on each.
QUARTER_PAGE = "https://www.uscourts.gov/data-news/reports/statistical-reports/bankruptcy-filing-statistics/{month}-{y}-quarterly-bankruptcy-filings"
LINK_RE = re.compile(r'href="([^"]+\.(?:xlsx|xls|pdf))"[^>]*>([^<]*)', re.I)
CHAPTERS = ("7", "11", "13")


def _districts() -> dict[str, str]:
    with (REPO_ROOT / "data" / "reference" / "districts.csv").open(newline="") as f:
        return {r["district_code"]: r["fips"] for r in csv.DictReader(f)}


class USCourtsBankruptcyF2:
    source_id = SOURCE_ID
    dataset = "outcomes/bankruptcy.csv"

    def discover(self, period: Period | None) -> list[Document]:
        if period is None:
            today = date.today()
            # most recent completed quarter end
            qm = ((today.month - 1) // 3) * 3
            y, m = (today.year, qm) if qm else (today.year - 1, 12)
            period = Period.quarter_ending(y, m)
        last = period.end
        return [
            Document(url=QUARTER_PAGE.format(month=last.strftime("%B").lower(), y=last.year), period=period, kind="html", label=f"Bankruptcy statistics page, quarter ending {last.isoformat()}"),
            Document(url=LANDING, period=period, kind="html", label=f"Bankruptcy statistics landing page, looking for quarter ending {last.isoformat()}", meta=(("landing", True),)),
        ]

    def resolve(self, doc: Document, html: str) -> list[Document]:
        """Find the F-2 table downloads on the quarterly statistics page.

        The page lists tables as rows such as "F-2 Three Months" / "F-2 Twelve Months" with a download
        link per format. We take xlsx when offered, otherwise xls, and skip pdf. Any F-2 link whose
        surrounding text does not say three or twelve months is treated as twelve months, which is how
        the AO labels the main F-2 table.
        """
        out: list[Document] = []
        seen: set[str] = set()
        # Work on a window of text around each link so the table label (in the same row) is visible.
        for m in re.finditer(r'<a[^>]+href="([^"]+\.(?:xlsx|xls))"[^>]*>', html, re.I):
            href = m.group(1)
            # The table label precedes its download link in the same row; use the last label before the link.
            before = re.sub(r"<[^>]+>", " ", html[max(0, m.start() - 600): m.start()])
            labels = list(re.finditer(r"\bF-?(\d+[A-Z]?)\b", before))
            if not labels or labels[-1].group(1) != "2":
                continue
            text = before[labels[-1].start():]  # this row's label and whatever follows it up to the link
            url = href if href.startswith("http") else "https://www.uscourts.gov" + href
            if url in seen:
                continue
            if doc.get("landing") and doc.period:
                # On the landing page several quarters are listed; keep only links that name this period.
                e = doc.period.end
                stamps = (f"{e.month:02d}{e.day:02d}.{e.year}", f"{e.month:02d}{e.day:02d}{e.year}", f"{e.year}_{e.month:02d}", e.strftime("%B %d, %Y").replace(" 0", " "), e.strftime("%B %Y"))
                if not any(st.lower() in (url + " " + text).lower() for st in stamps):
                    continue
            seen.add(url)
            low = text.lower()
            measure = "quarter" if re.search(r"3[- ]month|three[- ]month", low) else "twelve_months_ending"
            out.append(Document(url=url, period=doc.period, kind=url.rsplit(".", 1)[-1].lower(), label=f"F-2 ({measure}) {doc.period.end.isoformat() if doc.period else ''}", meta=(("measure", measure),)))
        if not out:
            raise LayoutChanged(f"No F-2 xlsx or xls link found on {doc.url}; anchors seen: {LINK_RE.findall(html)[:10]}")
        return out

    # ---- parse ----
    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        if raw.path.suffix.lower() == ".xls":
            raise LayoutChanged(f"{raw.path.name} is a legacy .xls file; convert to xlsx (libreoffice --headless --convert-to xlsx) and re-run with --local, or add xlrd support")
        wb = openpyxl.load_workbook(raw.path, read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = [[c for c in r] for r in ws.iter_rows(values_only=True)]
        header_idx, cols = self._find_header(rows)
        out: list[dict[str, Any]] = []
        districts = _districts()
        for r in rows[header_idx + 1:]:
            if not r or r[0] is None:
                continue
            code = str(r[0]).strip().upper()
            if code not in districts:
                continue  # circuit subtotal, US total, territories, blank
            rec: dict[str, Any] = {"district_code": code}
            for key, idx in cols.items():
                v = r[idx]
                rec[key] = int(v) if isinstance(v, (int, float)) else int(str(v).replace(",", "")) if v not in (None, "", "-") else 0
            out.append(rec)
        if not out:
            raise LayoutChanged(f"{raw.path.name}: header found at row {header_idx} but no district rows matched known codes; first cells were {[str(r[0])[:12] for r in rows[header_idx+1:header_idx+6] if r]}")
        return out

    def _find_header(self, rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
        """Locate the header row and map our keys to column indexes.

        Expected: a group row with 'Nonbusiness' and a header row beneath with
        'Total', 'Chapter 7', 'Chapter 11', 'Chapter 13' under that group.
        """
        for i, r in enumerate(rows[:40]):
            cells = [str(c).strip() if c is not None else "" for c in r]
            if any("nonbusiness" in c.lower() for c in cells):
                nb_start = next(j for j, c in enumerate(cells) if "nonbusiness" in c.lower())
                # header row is this row or one of the next two
                for h in range(i, min(i + 3, len(rows))):
                    hc = [str(c).strip().lower() if c is not None else "" for c in rows[h]]
                    try:
                        total = next(j for j in range(nb_start, len(hc)) if hc[j] == "total")
                        c7 = next(j for j in range(nb_start, len(hc)) if hc[j] in ("chapter 7", "7"))
                        c11 = next(j for j in range(nb_start, len(hc)) if hc[j] in ("chapter 11", "11"))
                        c13 = next(j for j in range(nb_start, len(hc)) if hc[j] in ("chapter 13", "13"))
                    except StopIteration:
                        continue
                    return h, {"all_nonbusiness": total, "7": c7, "11": c11, "13": c13}
        seen = [[str(c)[:15] for c in r[:8]] for r in rows[:8]]
        raise LayoutChanged(f"Could not find a 'Nonbusiness' header group with Total/Chapter 7/11/13 columns. First rows: {seen}")

    # ---- normalize ----
    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        districts = _districts()
        period = raw.doc.period
        assert period is not None
        measure = raw.doc.get("measure", "quarter")
        sums: dict[tuple[str, str], int] = defaultdict(int)
        counted: dict[str, list[str]] = defaultdict(list)
        for rec in records:
            fips = districts[rec["district_code"]]
            counted[fips].append(rec["district_code"])
            for ch in ("all_nonbusiness",) + CHAPTERS:
                sums[(fips, ch)] += rec[ch]
        rows: list[Row] = []
        for (fips, ch), n in sorted(sums.items()):
            prov = provenance.block(SOURCE_ID, raw, method="bulk_download", entered_by="wpdc_ingest.uscourts_bankruptcy", page_or_table="Table F-2")
            rows.append(Row(values={"fips": fips, "period_start": period.start.isoformat(), "period_end": period.end.isoformat(), "measure": measure, "chapter": ch, "filings": n},
                            provenance=provenance.csv_columns(prov),
                            transform_steps=[f"summed nonbusiness {ch} across districts {','.join(counted[fips])}"]))
        return rows
