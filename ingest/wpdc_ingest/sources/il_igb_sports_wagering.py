"""Illinois Gaming Board, sports wagering monthly reports.

The Board serves its monthly reports only through an ASP.NET form
(igbapps.illinois.gov/SportsReports_AEM.aspx): a start and end month, a
report type and a format. Two reports are posted for each month and stored
together as one archived file, each part preceded by a marker line:

  tax-summary      Completed Events Tax Summary (accrual basis), CSV: for
                   each licensee and location type (In-Person Wagering,
                   Online Wagering, Total) the State AGR, State Tax, Cook
                   County AGR and tax, Sports Wager Tax (the per-wager tax
                   from July 2025), Expired Tickets and Total Payment.
  activity-detail  All Wagering Activity Detail (cash basis), CSV: for each
                   sport level, location type and licensee the Tier 1 and
                   Tier 2 wager counts and handle, with a Total location row
                   per sport level and a further group for wagers with no
                   sport level (whose empty first field is dropped).

Adjusted gross sports wagering receipts (AGR) are gross receipts less
winnings paid, with no promotional deduction, for events completed in the
month; handle is all wagering activity placed in the month. The two are on
different bases and the module records both as the Board publishes them.

Layout fingerprint: the title line of each part, the month line, and the
header rows named above. Cross-checks: in the tax summary the per-licensee Total
rows equal the in-person plus online rows for AGR, and in the detail report
each sport level's Total rows equal its in-person plus online rows.

Output per month: retail (in-person), online and all rows with handle,
AGR as both gross and adjusted revenue, and state tax (State Tax plus
Sports Wager Tax; the Cook County tax is local and left out). The Board
says revenue is due the last day of the month after the month earned, so
the series runs two months behind. Sports wagering began in March 2020.
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

SOURCE_ID = "il-igb-sports-wagering-monthly"
FORM = "https://igbapps.illinois.gov/SportsReports_AEM.aspx"
FIRST = (2020, 3)
REVENUE_DEFINITION = ("Adjusted gross sports wagering receipts (AGR) for events completed in the month, accrual basis: gross receipts less winnings "
                      "paid, with no promotional deduction, so gross and taxable revenue are the same figure; handle is all wagering activity placed "
                      "in the month on a cash basis, a different basis from AGR; state tax is the AGR tax plus the per-wager tax levied from July "
                      "2025 and excludes the Cook County tax; statewide across master sports wagering licensees")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
LOC = {"In-Person Wagering": "retail", "Online Wagering": "online"}


def _forms(y: int, m: int) -> list[dict]:
    mon = MONTHS[m - 1]
    base = {"SearchStartMonth": mon, "SearchStartYear": str(y), "SearchEndMonth": mon, "SearchEndYear": str(y), "ViewType": "ViewCSV", "ButtonSearch.x": "10", "ButtonSearch.y": "10"}
    return [
        {"name": "tax-summary", "data": {"SearchType": "TypeAccrual", "SearchAccrual": "Tax Summary Report", **base}},
        {"name": "activity-detail", "data": {"SearchType": "TypeCash", "SearchCash": "Detail Report", **base}},
    ]


def _num(s: str) -> float:
    return float(s.replace(",", "") or 0)


def split_parts(text: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^==== wpdc part: (\S+) ====$", line.strip())
        if m:
            cur = m.group(1)
            parts[cur] = ""
            continue
        if cur is not None:
            parts[cur] += line + "\n"
    return parts


class ILIGBSportsWagering:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"
    fetch_all = False

    def discover(self, period: Period | None) -> list[Document]:
        if period is not None:
            months = [(period.start.year, period.start.month)]
            self.fetch_all = False
        else:
            t = date.today()
            y, m = (t.year, t.month - 2) if t.month > 2 else (t.year - 1, t.month + 10)
            months = []
            cy, cm = FIRST
            while (cy, cm) <= (y, m):
                months.append((cy, cm))
                cy, cm = (cy, cm + 1) if cm < 12 else (cy + 1, 1)
            self.fetch_all = True
        return [Document(url=FORM, period=Period.month(y, m), kind="txt", label=f"IGB sports wagering reports, {y}-{m:02d} (tax summary and activity detail)", meta=(("posts", json.dumps(_forms(y, m))), ("measure", f"{y}-{m:02d}"))) for y, m in months]

    def resolve(self, doc: Document, html: str) -> list[Document]:  # pragma: no cover - no html documents
        raise LayoutChanged("not used")

    @staticmethod
    def _table(part: str, title: str, header_first: str, name: str) -> tuple[str, list[list[str]]]:
        rows = list(csv.reader(io.StringIO(part)))
        rows = [r for r in rows if any(c.strip() for c in r)]
        if not rows or title not in rows[0][0]:
            raise LayoutChanged(f"{name} part does not open with '{title}': {rows[:1]}")
        month_line = rows[1][0].strip() if len(rows) > 1 else ""
        hi = next((i for i, r in enumerate(rows) if r and r[0].strip() == header_first), None)
        if hi is None:
            raise LayoutChanged(f"{name} part has no header row starting with {header_first!r}")
        return month_line, rows[hi + 1:]

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        parts = split_parts(raw.path.read_text(errors="replace"))
        if set(parts) != {"tax-summary", "activity-detail"}:
            raise LayoutChanged(f"{raw.path.name}: expected tax-summary and activity-detail parts, found {sorted(parts)}")
        month_a, tax_rows = self._table(parts["tax-summary"], "Completed Events Tax Summary", "Location Type", "tax-summary")
        month_b, det_rows = self._table(parts["activity-detail"], "All Wagering Activity Detail", "Sport Level", "activity-detail")
        mm = re.fullmatch(r"([A-Z][a-z]+) (\d{4})", month_a)
        if not mm or mm.group(1) not in MONTHS or month_b != month_a:
            raise LayoutChanged(f"{raw.path.name}: month lines are {month_a!r} and {month_b!r}; a single month was requested")
        year, month = int(mm.group(2)), MONTHS.index(mm.group(1)) + 1
        if raw.doc.period is not None and (year, month) != (raw.doc.period.start.year, raw.doc.period.start.month):
            raise LayoutChanged(f"{raw.path.name}: report is for {month_a}, requested {raw.doc.period.start:%B %Y}")
        # tax summary: Location Type, Licensee, State AGR, State Tax, Cook AGR, Cook Tax, Sports Wager Tax, Expired, Total Payment
        agr = {"retail": 0.0, "online": 0.0}
        tax = {"retail": 0.0, "online": 0.0}
        total_agr = 0.0
        n_lic = 0
        for r in tax_rows:
            if len(r) < 9:
                continue
            loc = r[0].strip()
            if loc in LOC:
                agr[LOC[loc]] += _num(r[2])
                tax[LOC[loc]] += _num(r[3]) + _num(r[6])
            elif loc == "Total":
                total_agr += _num(r[2])
                n_lic += 1
        if n_lic == 0:
            raise LayoutChanged(f"{raw.path.name}: tax summary has no Total rows")
        if abs(agr["retail"] + agr["online"] - total_agr) > 1:
            raise LayoutChanged(f"{raw.path.name}: tax summary location rows sum to {agr['retail'] + agr['online']:.2f} AGR but the licensee totals sum to {total_agr:.2f}")
        # detail: Sport Level, Location Type, Licensee, T1 wagers, T1 handle, T2 wagers, T2 handle. Each sport level has
        # In-Person, Online and Total location rows, the Total being that level's in-person plus online. Wagers with no
        # sport level (parlays across sports) form one more such group whose empty first field is dropped, so those
        # rows begin with the location type and their Total rows with "Total".
        handle = {"retail": 0.0, "online": 0.0}
        per_level: dict[str, dict[str, float]] = {}
        for r in det_rows:
            if not r:
                continue
            first = r[0].strip()
            if first in LOC and len(r) >= 6:
                level, loc, h = "(no sport level)", first, _num(r[3]) + _num(r[5])
            elif first == "Total" and len(r) >= 6:
                level, loc, h = "(no sport level)", "Total", _num(r[3]) + _num(r[5])
            elif len(r) >= 7 and r[1].strip() in LOC or (len(r) >= 7 and r[1].strip() == "Total"):
                level, loc, h = first, r[1].strip(), _num(r[4]) + _num(r[6])
            else:
                continue
            per_level.setdefault(level, {"retail": 0.0, "online": 0.0, "Total": 0.0})[LOC.get(loc, loc)] += h
            if loc in LOC:
                handle[LOC[loc]] += h
        if not per_level:
            raise LayoutChanged(f"{raw.path.name}: detail part has no sport level rows")
        for level, v in per_level.items():
            if abs(v["retail"] + v["online"] - v["Total"]) > 1:
                raise LayoutChanged(f"{raw.path.name}: detail {level} in-person plus online handle {v['retail'] + v['online']:.2f} differs from its Total rows {v['Total']:.2f}")
        out = []
        for ch in ("retail", "online"):
            out.append({"year": year, "month": month, "channel": ch, "handle_usd": handle[ch], "agr": agr[ch], "tax": tax[ch], "licensees": n_lic})
        out.append({"year": year, "month": month, "channel": "all", "handle_usd": handle["retail"] + handle["online"], "agr": agr["retail"] + agr["online"], "tax": tax["retail"] + tax["online"], "licensees": n_lic})
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        rows: list[Row] = []
        for r in records:
            p = Period.month(r["year"], r["month"])
            loc = {"retail": "In-Person Wagering rows", "online": "Online Wagering rows", "all": "In-Person plus Online Wagering rows"}[r["channel"]]
            prov = provenance.block(SOURCE_ID, raw, method="csv", entered_by="wpdc_ingest.il_igb_sports_wagering",
                                    page_or_table=f"Completed Events Tax Summary and All Wagering Activity Detail for {p.start:%B %Y}, {loc} summed across licensees",
                                    notes="Posted to the Board's report form (start and end month set to this month, CSV); the archived file holds both responses; AGR is on an accrual basis and handle on a cash basis, as the Board publishes them")
            vals = {"fips": "17", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": r["channel"], "market_segment": "regulated_sportsbook",
                    "handle_usd": round(r["handle_usd"]), "gross_revenue_usd": round(r["agr"]), "adjusted_revenue_usd": round(r["agr"]), "promo_deductions_usd": None,
                    "state_tax_usd": round(r["tax"]), "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=[f"summed across {r['licensees']} licensees: Tier 1 plus Tier 2 handle; State AGR; State Tax plus Sports Wager Tax", "dollars and cents rounded to whole dollars"]))
        return rows
