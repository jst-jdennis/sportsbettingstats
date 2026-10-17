"""Pennsylvania Gaming Control Board, monthly sports wagering report summary by fiscal year.

The Board publishes one workbook per state fiscal year (July to June) on a
fiscal year page under News and Transparency, Revenue. The first sheet lists
every licensee in a block of rows, and a GRAND TOTAL block at the bottom, each
with three sub-blocks: Total Sports Wagering, Retail Sports Wagering and
Online Sports Wagering. Row labels are Handle*, Revenue, Promotional Credits,
Gross Revenue (Taxable), State Tax Due (34%) and Local Share Assessment (2%)
(retail has no Revenue or Promotional Credits rows because promotional
credits are an online deduction). Months sit in every other column from C
with the month name in row 4, and the last value column is the fiscal year
total. The footnote sheet says Revenue is handle less only the payouts made
during the month, so wagers on future events inflate handle relative to
payouts in that month.

Layout fingerprint: row 4 month headers of the form "July 2024"; a GRAND
TOTAL row; the six labelled rows under it in the order above. Cross-checks:
retail plus online equals the total sub-block for handle and taxable revenue
in every month, and the months sum to the fiscal year total column.

Output per month: retail, online and all rows with handle, gross revenue
(the Revenue row; for retail the taxable figure, since nothing is deducted),
promotional credits, taxable revenue and the 34 percent state tax (the 2
percent local share assessment is not state tax and is left out).

With no period every month in every fiscal year workbook since 2018/19 is
written; with a period only that month, from the workbook of its fiscal year.
Workbooks for fiscal years before 2022/23 are checked against the same
fingerprint and fail loudly if their layout differs.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import openpyxl

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "pa-pgcb-sports-wagering-monthly"
REVENUE_PAGE = "https://gamingcontrolboard.pa.gov/news-and-transparency/revenue"
# The fiscal year pages follow two naming patterns; both are tried.
FY_PAGES = [
    "https://gamingcontrolboard.pa.gov/news-and-transparency/revenue/sports-wagering-fy-{a}{b}",
    "https://gamingcontrolboard.pa.gov/news-and-transparency/revenue/sports-wagering-revenue-fy-{a}{b}",
    "https://gamingcontrolboard.pa.gov/news-and-transparency/revenue/sports-wagering-revenue-fy-{a}{b}-0",
]
FIRST_FY = 2018  # sports wagering began in November 2018, fiscal year 2018/19
REVENUE_DEFINITION = ("Revenue is handle (wagers) less only the payouts on winning wagers made during the reporting month, so handle includes "
                      "wagers on future events whose payouts fall in later months; taxable gross revenue is revenue less promotional credits; "
                      "state tax is the 34 percent tax on taxable revenue and excludes the 2 percent local share assessment; "
                      "statewide totals from the Board's monthly sports wagering report summary")
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}
LABELS = {"handle": "handle*", "revenue": "revenue", "promo": "promotional credits", "taxable": "gross revenue (taxable)", "tax": "state tax due (34%)", "lsa": "local share assessment (2%)"}


def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def fiscal_year_of(p: Period) -> int:
    """Pennsylvania fiscal year is named by its starting calendar year (July)."""
    return p.start.year if p.start.month >= 7 else p.start.year - 1


class PAPGCBSportsWagering:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"
    fetch_all = False

    def discover(self, period: Period | None) -> list[Document]:
        if period is None:
            today = date.today()
            cur = today.year if today.month >= 7 else today.year - 1
            fys = list(range(FIRST_FY, cur + 1))
            self.fetch_all = True
        else:
            fys = [fiscal_year_of(period)]
            self.fetch_all = False
        docs: list[Document] = []
        for fy in fys:
            for pat in FY_PAGES:
                # measure lets the CLI stop at the first page per fiscal year that yields a parsed workbook
                docs.append(Document(url=pat.format(a=fy, b=fy + 1), period=period, kind="html", label=f"PGCB sports wagering revenue page, fiscal year {fy}/{fy + 1}", meta=(("fy", fy), ("measure", f"fy{fy}"))))
        return docs

    def resolve(self, doc: Document, html: str) -> list[Document]:
        fy = doc.get("fy")
        cands = []
        for m in re.finditer(r'href="([^"]+\.xlsx)"', html, re.I):
            href = m.group(1)
            low = href.lower().replace("%20", " ")
            if "sport" in low and "wager" in low:
                cands.append(href if href.startswith("http") else "https://gamingcontrolboard.pa.gov" + href)
        if not cands:
            raise LayoutChanged(f"No sports wagering xlsx link on {doc.url}")
        return [Document(url=cands[0], period=doc.period, kind="xlsx", label=f"PGCB monthly sports wagering report summary, fiscal year {fy}/{fy + 1}", meta=(("fy", fy), ("measure", f"fy{fy}")))]

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        wb = openpyxl.load_workbook(raw.path, data_only=True, read_only=False)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if len(rows) < 10:
            raise LayoutChanged(f"{raw.path.name}: sheet {ws.title!r} has {len(rows)} rows")
        # Month header row: the first row with at least six "Month YYYY" cells.
        hdr_i = None
        for i, r in enumerate(rows[:12]):
            if sum(1 for v in r if isinstance(v, str) and re.fullmatch(r"[A-Z][a-z]+ \d{4}", v.strip())) >= 6:
                hdr_i = i
                break
        if hdr_i is None:
            raise LayoutChanged(f"{raw.path.name}: no month header row in the first 12 rows of sheet {ws.title!r}")
        month_cols: list[tuple[int, int, int]] = []  # (col, year, month)
        total_col = None
        for c, v in enumerate(rows[hdr_i]):
            if isinstance(v, str):
                m = re.fullmatch(r"([A-Z][a-z]+) (\d{4})", v.strip())
                if m and m.group(1) in MONTHS:
                    month_cols.append((c, int(m.group(2)), MONTHS[m.group(1)]))
                elif "total" in v.lower():
                    total_col = c
        if not 6 <= len(month_cols) <= 12:  # the first fiscal year, 2018/19, runs from November
            raise LayoutChanged(f"{raw.path.name}: expected 6 to 12 month columns, found {len(month_cols)}: {[v for v in rows[hdr_i] if v]}")
        gt = next((i for i, r in enumerate(rows) if _norm(r[0]) == "grand total"), None)
        if gt is None:
            raise LayoutChanged(f"{raw.path.name}: no GRAND TOTAL row; last labels: {[r[0] for r in rows[-30:] if r[0]]}")
        blocks: dict[str, dict[str, list]] = {}
        cur = None
        for r in rows[gt + 1: gt + 40]:
            lab = _norm(r[0])
            if lab in ("total sports wagering", "retail sports wagering", "online sports wagering"):
                cur = lab.split()[0]
                blocks[cur] = {}
                continue
            if cur and lab in LABELS.values():
                key = next(k for k, v in LABELS.items() if v == lab)
                blocks[cur][key] = r
            if len(blocks) == 3 and all(k in blocks[b] for b in blocks for k in ("handle", "taxable", "tax")) and cur == "online" and "lsa" in blocks["online"]:
                break
        for b in ("total", "retail", "online"):
            if b not in blocks or not all(k in blocks[b] for k in ("handle", "taxable", "tax")):
                raise LayoutChanged(f"{raw.path.name}: GRAND TOTAL block lacks the {b} sub-block rows; found {dict((k, list(v)) for k, v in blocks.items())}")
        out: list[dict[str, Any]] = []
        sums: dict[tuple[str, str], float] = {}
        for c, y, mo in month_cols:
            if not blocks["total"]["handle"][c] and not blocks["total"]["taxable"][c]:
                continue  # month not yet reported: the current workbook carries zeros, older ones blanks
            rec: dict[str, Any] = {"year": y, "month": mo, "column": c}
            for b in ("total", "retail", "online"):
                vals = {k: blocks[b][k][c] for k in blocks[b]}
                for k, v in vals.items():
                    if v is not None and not isinstance(v, (int, float)):
                        raise LayoutChanged(f"{raw.path.name}: {b} {k} for {y}-{mo:02d} is not numeric: {v!r}")
                    sums[(b, k)] = sums.get((b, k), 0.0) + float(v or 0)
                rec[b] = vals
            for k in ("handle", "taxable"):
                if abs(rec["retail"][k] + rec["online"][k] - rec["total"][k]) > 2:
                    raise LayoutChanged(f"{raw.path.name}: retail + online {k} differs from total for {y}-{mo:02d}")
            out.append(rec)
        # The fiscal year total column is the regulator's own sum. When it disagrees with the months (the
        # 2019/20 workbook carries the previous year's total), the months stand and every row says so.
        mismatches = []
        if total_col is not None:
            for b in ("total", "retail", "online"):
                for k in ("handle", "taxable"):
                    fy_total = blocks[b][k][total_col]
                    if fy_total is not None and abs(float(fy_total) - sums.get((b, k), 0.0)) > 2:
                        mismatches.append(f"{b} {k}: months sum to {sums.get((b, k)):,.0f} dollars, fiscal year total column shows {float(fy_total):,.0f}")
        self._fy_note = ("The workbook's fiscal year total column does not equal the sum of its months (" + "; ".join(mismatches) + "); the monthly figures are recorded as printed and the column is treated as the regulator's error") if mismatches else None
        if not out:
            raise LayoutChanged(f"{raw.path.name}: no reported months")
        self._sheet = ws.title
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        want = raw.doc.period
        if want is not None:
            records = [r for r in records if (r["year"], r["month"]) == (want.start.year, want.start.month)]
            if not records:
                raise LayoutChanged(f"{raw.path.name}: {want.start:%B %Y} is not reported in this workbook")
        sheet = getattr(self, "_sheet", "first sheet")
        rows: list[Row] = []
        for rec in records:
            p = Period.month(rec["year"], rec["month"])
            for ch, b in (("retail", "retail"), ("online", "online"), ("all", "total")):
                v = rec[b]
                # Early fiscal years print a zero Revenue row while taxable revenue is positive: revenue before
                # promotional credits was not reported then, so it is left empty rather than recorded as zero.
                rev = v.get("revenue")
                unreported = rev is not None and rev == 0 and (v.get("taxable") or 0) != 0
                gross = None if unreported else (rev if rev is not None else v.get("taxable"))
                prov = provenance.block(SOURCE_ID, raw, method="xlsx", entered_by="wpdc_ingest.pa_pgcb_sports_wagering",
                                        page_or_table=f"sheet {sheet!r}, GRAND TOTAL block, {b.capitalize()} Sports Wagering rows, column {p.start:%B %Y}",
                                        notes="; ".join(x for x in [("Retail has no promotional credit row in the report, so retail gross revenue equals its taxable revenue; the 2 percent local share assessment is omitted from state tax" if b == "retail" else None), getattr(self, "_fy_note", None)] if x) or None)
                vals = {"fips": "42", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": ch, "market_segment": "regulated_sportsbook",
                        "handle_usd": round(v["handle"]), "gross_revenue_usd": round(gross) if gross is not None else None, "adjusted_revenue_usd": round(v["taxable"]),
                        "promo_deductions_usd": None if unreported else (round(v["promo"]) if v.get("promo") is not None else (0 if b == "retail" else None)),
                        "state_tax_usd": round(v["tax"]), "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
                rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=["GRAND TOTAL block row for the month", "dollars and cents rounded to whole dollars"]))
        return rows
