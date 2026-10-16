"""US Courts Bankruptcy Filings Statistics, Table F-2.

Table F-2 reports business and nonbusiness filings by chapter for each of the
94 federal judicial districts, for the quarter and for the twelve months ending
the quarter. It is published as an xlsx about four to six weeks after quarter
end on the Bankruptcy Filings Statistics page; quarters before 2025 were
published as PDF only, and the PDF edition is parsed from its text.

Layout fingerprint (confirmed against the June 2026 tables): a group row
containing "Business" and "Nonbusiness", a header row beneath with "All
Chapters" (or "Total"), "Chapter 7", "Chapter 11", "Chapter 13", and
district rows labelled "NJ", "OK,N", "NY,S", "DC" and so on, with circuit
rows ("1st") and the national "Total" interleaved. Arkansas appears once
as "AR" for both districts. Puerto Rico, the Virgin Islands, Guam and the
Northern Mariana Islands are skipped. If the header cannot be located the
parser raises LayoutChanged with what it saw.

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
import pdfplumber

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

    fetch_all = True  # both tables are ingested; the CLI fetches every candidate that parses rather than stopping at the first

    def discover(self, period: Period | None) -> list[Document]:
        if period is None:
            today = date.today()
            qm = ((today.month - 1) // 3) * 3
            y, m = (today.year, qm) if qm else (today.year - 1, 12)
            period = Period.quarter_ending(y, m)
        last = period.end
        stamp = f"{last.month:02d}{last.day:02d}.{last.year}"
        return [
            # File names confirmed on the AO's per-table pages, e.g. /data-news/data-tables/2026/06/30/bankruptcy-filings/f-2-three-months
            Document(url=f"https://www.uscourts.gov/sites/default/files/document/bf_f2.3_{stamp}.xlsx", period=period, kind="xlsx", label=f"F-2 three months ending {last.isoformat()}", meta=(("measure", "quarter"),)),
            Document(url=f"https://www.uscourts.gov/sites/default/files/document/bf_f2_{stamp}.xlsx", period=period, kind="xlsx", label=f"F-2 twelve months ending {last.isoformat()}", meta=(("measure", "twelve_months_ending"),)),
            Document(url=QUARTER_PAGE.format(month=last.strftime("%B").lower(), y=last.year), period=period, kind="html", label=f"Bankruptcy statistics page, quarter ending {last.isoformat()}"),
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
        e = doc.period.end if doc.period else None
        if e:
            stamp = f"{e.month:02d}{e.day:02d}.{e.year}"
            # Table pages are linked as .../bankruptcy-filings/f-2 and .../f-2-three-months; the files follow a fixed naming convention.
            if re.search(r'href="[^"]*/bankruptcy-filings/f-2-three-months"', html):
                out.append(Document(url=f"https://www.uscourts.gov/sites/default/files/document/bf_f2.3_{stamp}.xlsx", period=doc.period, kind="xlsx", label=f"F-2 three months ending {e.isoformat()}", meta=(("measure", "quarter"),)))
            if re.search(r'href="[^"]*/bankruptcy-filings/f-2"', html):
                out.append(Document(url=f"https://www.uscourts.gov/sites/default/files/document/bf_f2_{stamp}.xlsx", period=doc.period, kind="xlsx", label=f"F-2 twelve months ending {e.isoformat()}", meta=(("measure", "twelve_months_ending"),)))
            if out:
                return out
            if out:
                return out
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
        if out:
            return out
        e = doc.period.end if doc.period else None
        if e:
            stamp = f"{e.month:02d}{e.day:02d}.{e.year}"
            # Quarter pages link the files directly. The directory moved over the years (data_tables/, the
            # bare files/ root, dated folders such as 2025-01/, document/) and quarters before 2025 are PDF
            # only, so take whatever the page offers: xlsx when present, else pdf, per measure.
            found: dict[str, dict[str, str]] = {}
            for m in re.finditer(r'href="([^"]*?/bf_f2(\.3)?_' + re.escape(stamp) + r'\.(xlsx|pdf))"', html, re.I):
                href, three, ext = m.group(1), m.group(2), m.group(3).lower()
                url = href if href.startswith("http") else "https://www.uscourts.gov" + href
                found.setdefault("quarter" if three else "twelve_months_ending", {}).setdefault(ext, url)
            for measure, by_ext in found.items():
                url = by_ext.get("xlsx") or by_ext.get("pdf")
                label = "three" if measure == "quarter" else "twelve"
                out.append(Document(url=url, period=doc.period, kind=url.rsplit(".", 1)[-1].lower(), label=f"F-2 {label} months ending {e.isoformat()}", meta=(("measure", measure),)))
            if out:
                return out
        raise LayoutChanged(f"No F-2 xlsx, xls or pdf link found on {doc.url}; anchors seen: {LINK_RE.findall(html)[:10]}")

    # ---- parse ----
    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        if raw.path.suffix.lower() == ".pdf":
            return self._parse_pdf(raw)
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
            cell = str(r[0]).strip().upper()
            # District labels are two letters, optionally followed by a comma and a division letter ("OK,N", "NY, S").
            # Circuit rows ("2nd", "10th") and totals contain digits or longer words and must not be normalized:
            # stripping non-letters from "2nd" yields "ND", which would hand the Second Circuit total to North Dakota.
            # A trailing footnote mark ("AR ²", "TX,E *") is allowed; it is not part of the code.
            m = re.fullmatch(r"([A-Z]{2})(?:\s*,\s*([A-Z]))?\s*[\u00b9\u00b2\u00b3\u2070-\u2079*\u2020\u2021]*", cell)
            if not m:
                continue
            code = m.group(1) + (m.group(2) or "")
            if code == "AR":
                code = "ARE"  # the AO reports Arkansas as one court covering both districts; both map to fips 05
            if code not in districts:
                continue  # territories (PR, VI, GU, NMI) and anything unknown
            rec: dict[str, Any] = {"district_code": code}
            for key, idx in cols.items():
                v = r[idx]
                rec[key] = int(v) if isinstance(v, (int, float)) else int(str(v).replace(",", "")) if v not in (None, "", "-") else 0
            out.append(rec)
        if not out:
            raise LayoutChanged(f"{raw.path.name}: header found at row {header_idx} but no district rows matched known codes; first cells were {[str(r[0])[:12] for r in rows[header_idx+1:header_idx+6] if r]}")
        return out

    # ---- PDF edition (quarters before 2025 have no spreadsheet) ----
    DISTRICT_LINE = re.compile(r"^([A-Z]{2})(?:\s*,\s*([A-Z]))?\s*[\u00b9\u00b2\u00b3\u2070-\u2079*\u2020\u2021]*\s+(.*)$")

    def _parse_pdf(self, raw: RawDocument) -> list[dict[str, Any]]:
        """Read district rows from the PDF edition of Table F-2.

        Two column layouts exist. From 2020 the columns are Total (All, 7, 11, 13, Other), Business (All,
        7, 11, 13, Other), Nonbusiness (All, 7, 11, 13): fourteen numbers. Up to 2019 they are Total (All,
        7, 11, 12, 13), Business (All, 7, 11, 12, 13), Nonbusiness (All, 7, 11, 13), also fourteen, and the
        text extraction glues a trailing one-character column onto the last number ("2,4890"); that last
        value is therefore checked against nonbusiness total minus chapters 7 and 11 and repaired from it.
        The layout is read from each page's header, so a mixed file is handled page by page.
        """
        districts = _districts()
        out: list[dict[str, Any]] = []
        with pdfplumber.open(raw.path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = [l.strip() for l in text.splitlines()]
                # The last page ends with footnotes and a small "cases not reflected elsewhere" list
                # (chapter 9 and 15 cases by district); nothing after the first footnote is a district row.
                for i, l in enumerate(lines):
                    if l.startswith("Note:") or re.match(r"^[\u00b9\u00b2\u00b3]\s", l):
                        lines = lines[:i]
                        break
                header = " ".join(l for l in lines[:12]).upper()
                if "NONBUSINESS" not in header:
                    continue
                legacy = bool(re.search(r"\bCHAPTER\s+CHAPTER\s+CHAPTER\s+CHAPTER\s+CHAPTER", header)) and re.search(r"\b7\s+11\s+12\s+13\b", header) is not None
                for line in lines:
                    m = self.DISTRICT_LINE.match(line)
                    if not m:
                        continue
                    code = m.group(1) + (m.group(2) or "")
                    if code == "AR":
                        code = "ARE"
                    if code not in districts:
                        continue
                    toks = re.findall(r"\d[\d,]*|-", m.group(3))
                    if len(toks) != 14:
                        raise LayoutChanged(f"{raw.path.name}: district row {code!r} has {len(toks)} numbers, expected 14: {line!r}")
                    nums = [0 if t == "-" else int(t.replace(",", "")) for t in toks]
                    nb_total, nb7, nb11, nb13 = nums[10], nums[11], nums[12], nums[13]
                    if legacy:
                        expected = nb_total - nb7 - nb11  # nonbusiness chapter 12 is not broken out and is practically zero
                        raw13 = toks[13].replace(",", "")
                        if nb13 != expected:
                            if raw13.startswith(str(expected)) and len(raw13) == len(str(expected)) + 1:
                                nb13 = expected
                            elif len(raw13) > 1 and 0 <= expected - int(raw13[:-1]) <= 50:
                                nb13 = int(raw13[:-1])
                            else:
                                raise LayoutChanged(f"{raw.path.name}: {code}: nonbusiness chapter 13 {toks[13]!r} does not reconcile with total {nb_total} minus chapters 7 ({nb7}) and 11 ({nb11})")
                    elif nb_total < nb7 + nb11 + nb13:
                        raise LayoutChanged(f"{raw.path.name}: {code}: nonbusiness chapters exceed the nonbusiness total: {line!r}")
                    out.append({"district_code": code, "all_nonbusiness": nb_total, "7": nb7, "11": nb11, "13": nb13})
        if not out:
            raise LayoutChanged(f"{raw.path.name}: no district rows found in the PDF edition of Table F-2")
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
                    norm = [re.sub(r"\s+", " ", c.replace("\n", " ")).strip() for c in hc]
                    try:
                        total = next(j for j in range(nb_start, len(norm)) if norm[j] in ("total", "all chapters", "total all chapters"))
                        c7 = next(j for j in range(nb_start, len(norm)) if norm[j] in ("chapter 7", "7"))
                        c11 = next(j for j in range(nb_start, len(norm)) if norm[j] in ("chapter 11", "11"))
                        c13 = next(j for j in range(nb_start, len(norm)) if norm[j] in ("chapter 13", "13"))
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
        if measure == "twelve_months_ending":
            # The twelve-month table covers the year ending on the quarter's last day.
            end = period.end
            period = Period(start=end.replace(year=end.year - 1) + __import__("datetime").timedelta(days=1), end=end)
        sums: dict[tuple[str, str], int] = defaultdict(int)
        counted: dict[str, list[str]] = defaultdict(list)
        for rec in records:
            fips = districts[rec["district_code"]]
            counted[fips].append(rec["district_code"])
            for ch in ("all_nonbusiness",) + CHAPTERS:
                sums[(fips, ch)] += rec[ch]
        rows: list[Row] = []
        for (fips, ch), n in sorted(sums.items()):
            method = "pdf" if raw.path.suffix.lower() == ".pdf" else "xlsx"
            prov = provenance.block(SOURCE_ID, raw, method=method, entered_by="wpdc_ingest.uscourts_bankruptcy", page_or_table="Table F-2" + (" (PDF edition)" if method == "pdf" else ""))
            rows.append(Row(values={"fips": fips, "period_start": period.start.isoformat(), "period_end": period.end.isoformat(), "measure": measure, "chapter": ch, "filings": n},
                            provenance=provenance.csv_columns(prov),
                            transform_steps=[f"summed nonbusiness {ch} across districts {','.join(counted[fips])}"]))
        return rows
