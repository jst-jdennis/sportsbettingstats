"""Ohio Casino Control Commission, Ohio Sports Gaming Revenue report.

The Commission publishes one PDF per calendar year, updated monthly, on the
State's asset server (dam.assets.ohio.gov, under
casinocontrol.ohio.gov/revenue-reports/<year>/Sports/). Page one is a
statewide table of months with Online Revenue, Retail Revenue, Total Revenue
and Total Taxable Revenue. Each later page is one month: Type A proprietors
(online) and Type B proprietors (retail), each row with Total Gross
Receipts, Winnings Paid, Voided Wagers, Promotional, Revenue and Taxable
Revenue, a subtotal per type and a Total Online and Retail row. The notes
page defines Revenue as sports gaming receipts under R.C. 5753.01(H): gross
receipts less winnings paid and voided wagers; promotional credits are
wagers included in gross receipts and are not deductible before 2027.
Taxable Revenue floors each operator's negative month at zero.

The text layer splits digits inside numbers ("8 15,852,742"); the parser
repairs a one or two digit token followed by a number whose leading group is
short, and then requires exactly six numbers on each subtotal row.

Layout fingerprint: the year title on page one, month page titles of the
form "JANUARY 2026 OHIO SPORTS GAMING REVENUE", the two subtotal rows and
the total row. Cross-checks: online plus retail equals the total row for
receipts, revenue and taxable revenue, and the month page agrees with the
page one statewide table.

Output per month: online, retail and all rows with handle (total gross
receipts), gross revenue (Revenue) and adjusted revenue (Taxable Revenue).
Tax is not printed and is not computed here.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import pdfplumber

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "oh-occc-sports-gaming-monthly"
BASE = "https://dam.assets.ohio.gov/image/upload/casinocontrol.ohio.gov/revenue-reports/"
REVENUE_DEFINITION = ("Revenue is sports gaming receipts under R.C. 5753.01(H): total gross receipts less winnings paid and voided wagers, with "
                      "promotional credits counted in gross receipts and not deductible before 2027; taxable revenue floors each proprietor's "
                      "negative month at zero; handle is total gross receipts; amounts as reported to the Casino Control Commission, which may "
                      "differ from the Department of Taxation; lottery sports gaming kiosks are not included")
MONTHS = {m: i + 1 for i, m in enumerate(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"])}
PAGE_TITLE = re.compile(r"^([A-Z]+) (\d{4}) OHIO SPORTS GAMING REVENUE\s*$")
YEAR_TITLE = re.compile(r"^(\d{4}) OHIO SPORTS GAMING REVENUE\s*$")
TOKEN = re.compile(r"\(?-?[\d,]+\)?|-")


def repair_numbers(tail: str) -> list[int]:
    """Numbers from a row's numeric tail, re-joining digits that pdfplumber split with a space."""
    s = re.sub(r"(\d) ,", r"\1,", tail.strip())
    toks = s.split()
    out: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        if re.fullmatch(r"\d{1,2}", t) and i + 1 < len(toks):
            nxt = toks[i + 1]
            m = re.fullmatch(r"\(?(\d{1,2})((?:,\d{3})+)\)?", nxt)
            if m and len(t) + len(m.group(1)) <= 3:
                out.append(nxt.replace(m.group(1) + m.group(2), t + m.group(1) + m.group(2), 1))
                i += 2
                continue
        out.append(t)
        i += 1
    nums: list[int] = []
    for t in out:
        if t == "-":
            nums.append(0)
            continue
        if not re.fullmatch(r"\(?-?[\d,]+\)?", t):
            raise ValueError(f"not a number: {t!r} in {tail!r}")
        v = int(t.strip("()-").replace(",", ""))
        nums.append(-v if t.startswith("(") or t.startswith("-") else v)
    return nums


def _months_in_year(y: int) -> list[int]:
    today = date.today()
    return list(range(1, 13)) if y < today.year else list(range(1, today.month + 1))


class OHOCCCSportsGaming:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"
    fetch_all = False

    def discover(self, period: Period | None) -> list[Document]:
        """Candidate report files for the year, newest edition first; a 404 falls through to the next."""
        today = date.today()
        years = list(range(2023, today.year + 1)) if period is None else [period.start.year]
        self.fetch_all = period is None
        docs: list[Document] = []
        for y in years:
            start = 12 if y < today.year else today.month
            stop = 1 if period is None else period.start.month
            for mm in range(start, stop - 1, -1):
                docs.append(Document(url=f"{BASE}{y}/Sports/{y}_Sports_Gaming_Revenue_Report{mm:02d}.pdf", period=period, kind="pdf", label=f"Ohio sports gaming revenue report {y}, edition through month {mm:02d}", meta=(("year", y), ("measure", str(y)))))
            docs.append(Document(url=f"{BASE}{y}/{y}_Sports_Gaming_Revenue_Report.pdf.pdf", period=period, kind="pdf", label=f"Ohio sports gaming revenue report {y} (full year file)", meta=(("year", y), ("measure", str(y)))))
            docs.append(Document(url=f"{BASE}{y}/{y}_Sports_Gaming_Revenue_Report.pdf", period=period, kind="pdf", label=f"Ohio sports gaming revenue report {y} (full year file)", meta=(("year", y), ("measure", str(y)))))
        return docs

    def resolve(self, doc: Document, html: str) -> list[Document]:  # pragma: no cover - no html documents
        raise LayoutChanged("not used")

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        with pdfplumber.open(raw.path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        first = [l.strip() for l in pages[0].splitlines() if l.strip()] if pages else []
        ym = YEAR_TITLE.match(first[0]) if first else None
        if not ym:
            raise LayoutChanged(f"{raw.path.name}: page 1 does not open with the year title; first line {first[:1]}")
        year = int(ym.group(1))
        # statewide table on page 1
        statewide: dict[int, list[int]] = {}
        for l in first[1:]:
            m = re.match(r"^([A-Z][a-z]+)\s+(.*)$", l)
            if m and m.group(1).upper() in MONTHS:
                nums = repair_numbers(m.group(2))
                if len(nums) != 4:
                    raise LayoutChanged(f"{raw.path.name}: page 1 row for {m.group(1)} has {len(nums)} numbers, expected 4: {l!r}")
                statewide[MONTHS[m.group(1).upper()]] = nums
        if not statewide:
            raise LayoutChanged(f"{raw.path.name}: no month rows in the page 1 statewide table")
        out: list[dict[str, Any]] = []
        for n, text in enumerate(pages[1:], start=2):
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not lines:
                continue
            tm = PAGE_TITLE.match(lines[0])
            if not tm:
                continue
            mon, y = MONTHS.get(tm.group(1)), int(tm.group(2))
            if mon is None or y != year:
                raise LayoutChanged(f"{raw.path.name} page {n}: title {lines[0]!r} does not match year {year}")
            found: dict[str, list[int]] = {}
            for l in lines:
                for key, lab in (("online", "Subtotal Type A Online"), ("retail", "Subtotal Type B Retail"), ("all", "Total Online and Retail")):
                    if l.startswith(lab):
                        nums = repair_numbers(l[len(lab):])
                        if len(nums) != 6:
                            raise LayoutChanged(f"{raw.path.name} page {n}: {lab} row has {len(nums)} numbers, expected 6: {l!r}")
                        found[key] = nums
            if set(found) != {"online", "retail", "all"}:
                raise LayoutChanged(f"{raw.path.name} page {n}: subtotal or total rows missing, found {sorted(found)}")
            for k in (0, 4, 5):
                if abs(found["online"][k] + found["retail"][k] - found["all"][k]) > 2:
                    raise LayoutChanged(f"{raw.path.name} page {n}: online + retail differs from total in column {k}")
            sw = statewide.get(mon)
            if sw is None or sw[0] != found["online"][4] or sw[1] != found["retail"][4] or sw[2] != found["all"][4] or sw[3] != found["all"][5]:
                raise LayoutChanged(f"{raw.path.name} page {n}: month page totals {found['online'][4]}, {found['retail'][4]}, {found['all'][4]}, {found['all'][5]} disagree with the page 1 row {sw}")
            for key, nums in found.items():
                out.append({"year": year, "month": mon, "channel": key, "page": n, "handle_usd": nums[0], "winnings": nums[1], "voided": nums[2], "promotional": nums[3], "gross_revenue_usd": nums[4], "adjusted_revenue_usd": nums[5]})
        if not out:
            raise LayoutChanged(f"{raw.path.name}: no month pages parsed")
        if len({r["month"] for r in out}) != len(statewide):
            raise LayoutChanged(f"{raw.path.name}: page 1 lists {sorted(statewide)} but month pages cover {sorted({r['month'] for r in out})}")
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        want = raw.doc.period
        if want is not None:
            records = [r for r in records if (r["year"], r["month"]) == (want.start.year, want.start.month)]
            if not records:
                raise LayoutChanged(f"{raw.path.name}: {want.start:%B %Y} is not in this edition of the report")
        rows: list[Row] = []
        for r in records:
            p = Period.month(r["year"], r["month"])
            label = {"online": "Subtotal Type A Online", "retail": "Subtotal Type B Retail", "all": "Total Online and Retail"}[r["channel"]]
            prov = provenance.block(SOURCE_ID, raw, method="pdf", entered_by="wpdc_ingest.oh_occc_sports_gaming",
                                    page_or_table=f"page {r['page']} ({p.start:%B %Y}), {label} row; page 1 statewide table",
                                    notes="Promotional credits are wagers inside gross receipts and not a deduction before 2027, so promo_deductions_usd is left empty; the 20 percent tax is not printed in the report")
            vals = {"fips": "39", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": r["channel"], "market_segment": "regulated_sportsbook",
                    "handle_usd": r["handle_usd"], "gross_revenue_usd": r["gross_revenue_usd"], "adjusted_revenue_usd": r["adjusted_revenue_usd"], "promo_deductions_usd": None,
                    "state_tax_usd": None, "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=[f"{label} row: Total Gross Receipts, Revenue and Taxable Revenue columns", "split digits in the text layer re-joined", "dollars as printed"]))
        return rows
