"""Michigan Gaming Control Board, internet sports betting revenue and tax workbooks.

The Board publishes one workbook per calendar year ("<year> Internet Sports
Betting Revenues and Taxes", linked from the Detroit casinos revenue page)
whose first sheet lists each operator in a group of four columns (Total
Handle, Gross Sports Betting Receipts, Adjusted Gross Sports Betting
Receipts, state tax or payment) with months in rows and a Total row, and a
group headed "All Internet Sports Betting Operators" with the statewide
totals. Internet sports betting began on 22 January 2021. The Board's notes
say the figures are as reported by operators and that recent months may not
yet be audited.

Retail sports betting at the three Detroit casinos is published in a
separate workbook that is encrypted, and tribal retail sports betting is not
reported, so this module writes the online channel only.

Layout fingerprint: row 2 operator names, row 6 column labels beginning
"Total Handle", month names in column A from row 7, a Total row, and the
"All Internet Sports Betting Operators" group. Cross-checks: the operator
groups sum to the statewide group for handle and adjusted receipts in every
month, and the months sum to the Total row.

Output per month: one online row with handle, gross receipts, adjusted
gross receipts (after the promotional deductions the Lawful Sports Betting
Act allows) and the state's tax or payment (8.4 percent of adjusted
receipts; commercial operators' 30 percent share to Detroit is not state
tax and is excluded by the Board's column).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import openpyxl

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "mi-mgcb-sports-betting-monthly"
PAGE = "https://www.michigan.gov/mgcb/detroit-casinos/resources/revenues-and-wagering-tax-information"
FIRST_YEAR = 2021
REVENUE_DEFINITION = ("Internet sports betting only, as reported by operators to the Gaming Control Board: handle; gross sports betting receipts; "
                      "adjusted gross sports betting receipts after the deductions the Lawful Sports Betting Act allows (free play and promotional "
                      "credits within statutory limits); state tax is the 8.4 percent internet sports betting tax or tribal payment on adjusted "
                      "receipts, excluding the City of Detroit's share; retail sports betting at the Detroit casinos is reported separately and "
                      "tribal retail is not reported")
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}


class MIMGCBInternetSportsBetting:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"
    fetch_all = False

    def discover(self, period: Period | None) -> list[Document]:
        self.fetch_all = period is None
        return [Document(url=PAGE, period=period, kind="html", label="MGCB revenues and wagering tax information page")]

    def resolve(self, doc: Document, html: str) -> list[Document]:
        years = list(range(FIRST_YEAR, date.today().year + 1)) if doc.period is None else [doc.period.start.year]
        out: list[Document] = []
        for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
            href, text = m.group(1), re.sub(r"<[^>]+>|&nbsp;", " ", m.group(2))
            tm = re.search(r"(\d{4}) Internet Sports Betting Revenues and Taxes\s*Excel", text)
            if tm and int(tm.group(1)) in years:
                url = href.replace("&amp;", "&")
                url = url if url.startswith("http") else "https://www.michigan.gov" + url
                out.append(Document(url=url, period=doc.period, kind="xlsx", label=f"MGCB internet sports betting revenues and taxes, {tm.group(1)}", meta=(("year", int(tm.group(1))),)))
        if not out:
            raise LayoutChanged(f"No 'Internet Sports Betting Revenues and Taxes Excel' link for {years} on {doc.url}")
        return out

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        wb = openpyxl.load_workbook(raw.path, data_only=True)
        ws = wb.worksheets[0]
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        title = str(rows[0][1] or "") if rows else ""
        ym = re.match(r"(\d{4}) Internet Sports Betting Revenue", title)
        if not ym:
            raise LayoutChanged(f"{raw.path.name}: sheet {ws.title!r} title is {title!r}")
        year = int(ym.group(1))
        ops_row, hdr_row = rows[1], rows[5]
        groups = [(c, str(v).strip()) for c, v in enumerate(ops_row) if v and c > 0]
        if not groups or not str(hdr_row[1] or "").startswith("Total Handle"):
            raise LayoutChanged(f"{raw.path.name}: operator groups or Total Handle header not where expected (row 2 and row 6)")
        allc = next((c for c, name in groups if name.startswith("All Internet Sports Betting Operators")), None)
        if allc is None:
            raise LayoutChanged(f"{raw.path.name}: no 'All Internet Sports Betting Operators' group; groups: {[n for _, n in groups][:20]}")
        op_cols = [c for c, name in groups if c < allc]
        out: list[dict[str, Any]] = []
        sums = [0.0] * 4
        total_row = None
        for r in rows[6:]:
            lab = str(r[0] or "").strip()
            if lab == "Total":
                total_row = r
                break
            if lab not in MONTHS:
                continue
            vals = r[allc:allc + 4]
            if vals[0] is None:
                continue
            if any(not isinstance(v, (int, float)) for v in vals):
                raise LayoutChanged(f"{raw.path.name}: {lab} {year} statewide cells are not numeric: {vals}")
            op_handle = sum(float(r[c] or 0) for c in op_cols)
            op_adj = sum(float(r[c + 2] or 0) for c in op_cols)
            if abs(op_handle - float(vals[0])) > 2 or abs(op_adj - float(vals[2])) > 2:
                raise LayoutChanged(f"{raw.path.name}: operator groups do not sum to the statewide group for {lab} {year} (handle {op_handle:.2f} vs {vals[0]}, adjusted {op_adj:.2f} vs {vals[2]})")
            for i in range(4):
                sums[i] += float(vals[i])
            out.append({"year": year, "month": MONTHS[lab], "handle_usd": vals[0], "gross_revenue_usd": vals[1], "adjusted_revenue_usd": vals[2], "state_tax_usd": vals[3], "operators": len(op_cols)})
        if total_row is None:
            raise LayoutChanged(f"{raw.path.name}: no Total row")
        for i in range(4):
            t = total_row[allc + i]
            if t is not None and abs(float(t) - sums[i]) > 2:
                raise LayoutChanged(f"{raw.path.name}: months do not sum to the Total row in statewide column {i} ({sums[i]:.2f} vs {t})")
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
        rows: list[Row] = []
        for r in records:
            p = Period.month(r["year"], r["month"])
            prov = provenance.block(SOURCE_ID, raw, method="xlsx", entered_by="wpdc_ingest.mi_mgcb_internet_sports_betting",
                                    page_or_table=f"sheet {getattr(self, '_sheet', 'first sheet')!r}, All Internet Sports Betting Operators columns, row {p.start:%B}",
                                    notes="Online channel only: the Board's retail sports betting workbook for the Detroit casinos is encrypted and tribal retail is not reported; the Board notes that recent months may not yet be audited")
            vals = {"fips": "26", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": "online", "market_segment": "regulated_sportsbook",
                    "handle_usd": round(r["handle_usd"]), "gross_revenue_usd": round(r["gross_revenue_usd"]), "adjusted_revenue_usd": round(r["adjusted_revenue_usd"]), "promo_deductions_usd": None,
                    "state_tax_usd": round(r["state_tax_usd"]), "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=[f"statewide group row, checked against {r['operators']} operator groups", "dollars and cents rounded to whole dollars"]))
        return rows
