"""New York State Gaming Commission, statewide monthly mobile sports wagering report.

The Commission publishes one PDF, "Total Mobile Sports Wagering Gross Gaming
Revenue (GGR) and Taxes", with one page per state fiscal year (April to March)
from fiscal year 2021/2022, when mobile wagering began in January 2022. Each
page is a table of months with handle, GGR, the net revenue retained by the
platform providers, adjustments (prior period, unclaimed funds in early years,
fines and penalties) and the net revenue to education, which is the State's
share. The same file name is reused each month under a dated folder
(``/system/files/documents/<year>/<month>/``), so every edition is archived
and the edition's URL is the provenance for every month it carries.

Layout fingerprint: a page title matching "Total Mobile Sports Wagering Gross
Gaming Revenue (GGR) and Taxes - Fiscal Year YYYY/YYYY", a header line
containing "Handle" and "GGR", month rows "Mon-YY $handle $GGR ... $education"
and a "Total" row. The page's Total row must equal the sum of its month rows
for handle and GGR, which catches a misread column.

Output: one ``online`` row per month with handle, gross revenue (GGR, which
is also the taxable base in New York) and state tax (net revenue to
education). Retail sports wagering at the commercial casinos is reported
elsewhere and is not in this file.

With no period, every month in the current edition is written, which is how
the back series is loaded in one run; with ``--period YYYY-MM`` only that
month is written and a month missing from the edition is an error.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import pdfplumber

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "ny-gaming-commission-mobile-sports-monthly"
FILE = "monthly-mobile-sports-wagering-report-statewide.pdf"
DATED = "https://gaming.ny.gov/system/files/documents/{y}/{m:02d}/" + FILE
LANDING = ["https://gaming.ny.gov/revenue-reports", "https://gaming.ny.gov/state-revenue-reports", "https://gaming.ny.gov/sports-wagering"]
REVENUE_DEFINITION = ("Mobile sports wagering gross gaming revenue (GGR) reported on a cash basis, so wagers on future events count as current revenue "
                      "and payouts are recognized when redeemed; GGR is the taxable base and state tax is the net revenue to education, the State's "
                      "51 percent share after the platform providers' share and prior period adjustments; statewide, all platform providers combined")
TITLE_RE = re.compile(r"Total Mobile Sports Wagering Gross Gaming Revenue \(GGR\) and Taxes\s*-\s*Fiscal Year (\d{4})/(\d{4})")
MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
ROW_RE = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2})\b(.*)$")
MONEY_RE = re.compile(r"\(?-?\$[\d,]+\)?")


def _money(tok: str) -> int:
    neg = tok.startswith("(") or tok.startswith("-")
    v = int(tok.strip("()-$").replace(",", "").replace("$", ""))
    return -v if neg else v


class NYGamingCommissionMobileSports:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"

    def discover(self, period: Period | None) -> list[Document]:
        """The current edition: the dated folder of this month or the two before it, then the landing pages."""
        t = date.today()
        docs: list[Document] = []
        y, m = t.year, t.month
        for _ in range(3):
            docs.append(Document(url=DATED.format(y=y, m=m), period=period, kind="pdf", label=f"NY statewide monthly mobile sports wagering report, {y}-{m:02d} edition"))
            y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        for u in LANDING:
            docs.append(Document(url=u, period=period, kind="html", label="NY Gaming Commission revenue reports page"))
        return docs

    def resolve(self, doc: Document, html: str) -> list[Document]:
        m = re.search(r'href="([^"]*' + re.escape(FILE) + r')"', html)
        if not m:
            raise LayoutChanged(f"No link to {FILE} on {doc.url}")
        href = m.group(1)
        url = href if href.startswith("http") else "https://gaming.ny.gov" + href
        return [Document(url=url, period=doc.period, kind="pdf", label="NY statewide monthly mobile sports wagering report (linked edition)")]

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with pdfplumber.open(raw.path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        if not pages or not TITLE_RE.search(pages[0]):
            raise LayoutChanged(f"{raw.path.name}: first page title is not the statewide monthly mobile sports wagering table; first line: {pages[0].splitlines()[:1] if pages else []}")
        for n, text in enumerate(pages, start=1):
            tm = TITLE_RE.search(text)
            if not tm:
                continue
            fy_start = int(tm.group(1))
            lines = text.splitlines()
            header = next((l for l in lines if "Handle" in l and "GGR" in l), None)
            if header is None:
                raise LayoutChanged(f"{raw.path.name} page {n}: no header line with Handle and GGR")
            rows: list[dict[str, Any]] = []
            total: tuple[int, int] | None = None
            for l in lines:
                l = l.strip()
                rm = ROW_RE.match(l)
                if rm:
                    nums = [_money(t) for t in MONEY_RE.findall(rm.group(3))]
                    if len(nums) < 3:
                        continue  # a month not yet reported, or a pre-launch "$0 $0" row
                    mon = MONTHS[rm.group(1)]
                    yr = 2000 + int(rm.group(2))
                    if (mon >= 4 and yr != fy_start) or (mon < 4 and yr != fy_start + 1):
                        raise LayoutChanged(f"{raw.path.name} page {n}: month {l[:6]} does not belong to fiscal year {fy_start}/{fy_start + 1}")
                    rows.append({"year": yr, "month": mon, "handle_usd": nums[0], "gross_revenue_usd": nums[1], "state_tax_usd": nums[-1], "page": n, "fiscal_year": f"{fy_start}/{fy_start + 1}"})
                elif l.startswith("Total"):
                    nums = [_money(t) for t in MONEY_RE.findall(l)]
                    if len(nums) >= 2:
                        total = (nums[0], nums[1])
            if rows:
                if total is None:
                    raise LayoutChanged(f"{raw.path.name} page {n}: no Total row")
                if abs(sum(r["handle_usd"] for r in rows) - total[0]) > 2 or abs(sum(r["gross_revenue_usd"] for r in rows) - total[1]) > 2:
                    raise LayoutChanged(f"{raw.path.name} page {n}: month rows do not sum to the Total row (handle {sum(r['handle_usd'] for r in rows)} vs {total[0]}, GGR {sum(r['gross_revenue_usd'] for r in rows)} vs {total[1]})")
            out.extend(rows)
        if not out:
            raise LayoutChanged(f"{raw.path.name}: no month rows found")
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        want = raw.doc.period
        if want is not None:
            records = [r for r in records if r["year"] == want.start.year and r["month"] == want.start.month]
            if not records:
                raise LayoutChanged(f"{raw.path.name}: {want.start:%B %Y} is not in this edition of the report")
        rows: list[Row] = []
        for r in records:
            p = Period.month(r["year"], r["month"])
            prov = provenance.block(SOURCE_ID, raw, method="pdf", entered_by="wpdc_ingest.ny_gaming_commission_mobile_sports",
                                    page_or_table=f"Total Mobile Sports Wagering GGR and Taxes, fiscal year {r['fiscal_year']} page (page {r['page']} of the edition), row {p.start:%b-%y}",
                                    notes="Retail sports wagering at the commercial casinos is reported separately by the Commission and is not included; adjusted revenue equals GGR because New York allows no promotional deduction from the taxable base")
            vals = {"fips": "36", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": "online", "market_segment": "regulated_sportsbook",
                    "handle_usd": r["handle_usd"], "gross_revenue_usd": r["gross_revenue_usd"], "adjusted_revenue_usd": r["gross_revenue_usd"], "promo_deductions_usd": None,
                    "state_tax_usd": r["state_tax_usd"], "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=["Handle, GGR and Net Revenue to Education columns of the month row", "dollars as printed, no rounding needed"]))
        return rows
