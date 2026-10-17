"""Kansas Lottery, Sports Wagering Revenues monthly summary.

The Lottery is the statutory operator of sports wagering and publishes a
two page PDF for each month on its publications page (Sports Wagering
Monthly Revenues), under a media path that cannot be guessed, so the
publications page is read to find the month's link. Page one is the monthly
summary: one row per casino and provider with Settled Wagers, Revenues and
State Share, a "Subtotal - Retail" row, a "Subtotal - Online" row (the label
is split across lines in the text layer) and a Totals row. Page two repeats
the table for the fiscal year to date and is not used. The reports are
marked unaudited; an operator whose revenue is negative for the month prints
as zero, as the May 2023 report notes for BetMGM.

Layout fingerprint: "Sports Wagering Revenues", "Monthly Summary", a month
heading, a header with Settled Wagers, Revenues and State Share, the two
subtotal rows and a Totals row. Cross-checks: operator rows sum to their
subtotal within rounding (one dollar per row) and the subtotals sum to Totals,
for all three columns.

Output per month: retail, online and all rows with handle (settled wagers),
adjusted revenue (the Lottery's Revenues figure, which is the base of the
10 percent state share) and state tax (State Share). Gross revenue before
deductions is not reported and is left empty. The page lists months from
January 2023; the launch months of September to December 2022 are not on it.
"""
from __future__ import annotations

import re
from typing import Any

import pdfplumber

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "ks-lottery-sports-wagering"
PUBLICATIONS = "https://www.kslottery.gov/publications/sports-monthly-revenues/"
LINK_RE = re.compile(r'href="(/media/[a-z0-9]+/sports-wagering-monthly-revenue-(\d{4})-(\d{2})\.pdf)"', re.I)
REVENUE_DEFINITION = ("Settled Wagers, Revenues and State Share as printed in the Kansas Lottery's unaudited monthly summary; Revenues are the "
                      "Lottery's sports wagering revenues, the base of the 10 percent state share; an operator with negative revenue in a month is "
                      "printed as zero; statewide totals across casino managers and their platform providers")
MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}
ROW_RE = re.compile(r"^(.*?)\s*\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s*$")
NUMS_RE = re.compile(r"^\$([\d,]+)\s+\$([\d,]+)\s+\$([\d,]+)\s*$")


def _i(s: str) -> int:
    return int(s.replace(",", ""))


def _key(s: str) -> str:
    """A label with spaces and hyphens removed, so lines rebuilt from character positions compare equal."""
    return re.sub(r"[\s-]+", "", s).lower()


class KSLotterySportsWagering:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"
    fetch_all = False

    def discover(self, period: Period | None) -> list[Document]:
        self.fetch_all = period is None
        return [Document(url=PUBLICATIONS, period=period, kind="html", label="Kansas Lottery publications, sports wagering monthly revenues")]

    def resolve(self, doc: Document, html: str) -> list[Document]:
        found = {}
        for m in LINK_RE.finditer(html):
            found[(int(m.group(2)), int(m.group(3)))] = "https://www.kslottery.gov" + m.group(1)
        if not found:
            raise LayoutChanged(f"No sports-wagering-monthly-revenue links on {doc.url}")
        if doc.period is not None:
            key = (doc.period.start.year, doc.period.start.month)
            if key not in found:
                raise LayoutChanged(f"No report for {doc.period.start:%B %Y} on {doc.url}; months listed: {sorted(found)[-3:]}")
            keys = [key]
        else:
            keys = sorted(found)
        return [Document(url=found[k], period=Period.month(*k), kind="pdf", label=f"Kansas Lottery sports wagering revenues, {k[0]}-{k[1]:02d}") for k in keys]

    @staticmethod
    def _lines_from_chars(page) -> list[str]:
        """Rebuild text lines from character positions.

        Some editions (April 2025 onward) set each glyph with wide spacing, so pdfplumber's default word
        clustering yields one letter per word. Characters are grouped by their top coordinate and joined,
        with a space wherever the gap to the next character exceeds half the font size.
        """
        rows: dict[int, list] = {}
        for c in page.chars:
            if not c["text"].strip():
                continue
            rows.setdefault(round(c["top"] / 2), []).append(c)
        out = []
        for key in sorted(rows):
            cs = sorted(rows[key], key=lambda c: c["x0"])
            line = cs[0]["text"]
            for a, b in zip(cs, cs[1:]):
                line += (" " if b["x0"] - a["x1"] > a["size"] * 0.5 else "") + b["text"]
            out.append(line)
        return out

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        with pdfplumber.open(raw.path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            if not any("settledwagers" in _key(l) and "stateshare" in _key(l) for l in lines[:8]):
                lines = [l.strip() for l in self._lines_from_chars(page) if l.strip()]
        if not lines or "sportswageringrevenues" not in _key(lines[0]) or "monthlysummary" not in _key(" ".join(lines[:3])):
            raise LayoutChanged(f"{raw.path.name}: first page is not the monthly summary; first lines: {lines[:3]}")
        mh = next((m for m in (re.fullmatch(r"([A-Z][a-z]+) ?(\d{4})", l) for l in lines[:5]) if m), None)
        if not mh or mh.group(1) not in MONTHS:
            raise LayoutChanged(f"{raw.path.name}: no month heading in {lines[:5]}")
        year, month = int(mh.group(2)), MONTHS[mh.group(1)]
        if not any("settledwagers" in _key(l) and "revenues" in _key(l) and "stateshare" in _key(l) for l in lines[:8]):
            raise LayoutChanged(f"{raw.path.name}: header with Settled Wagers, Revenues and State Share not found")
        channel = "retail"
        ops: dict[str, list[tuple[int, int, int]]] = {"retail": [], "online": []}
        subs: dict[str, tuple[int, int, int]] = {}
        totals = None
        pending_sub = False
        for l in lines:
            k = _key(l)
            m = ROW_RE.match(l)
            if k.startswith("subtotalretail") and m:
                subs["retail"] = (_i(m.group(2)), _i(m.group(3)), _i(m.group(4))); channel = "online"; continue
            if k.startswith("subtotalonline") and m:
                subs["online"] = (_i(m.group(2)), _i(m.group(3)), _i(m.group(4))); continue
            if k.startswith("subtotal") and not m:
                pending_sub = True; continue
            if pending_sub:
                m2 = NUMS_RE.match(l)
                if m2:
                    subs["online"] = (_i(m2.group(1)), _i(m2.group(2)), _i(m2.group(3))); pending_sub = False; continue
            if k.startswith("totals") and m:
                totals = (_i(m.group(2)), _i(m.group(3)), _i(m.group(4))); continue
            if m and not k.startswith("casino"):
                ops[channel].append((_i(m.group(2)), _i(m.group(3)), _i(m.group(4))))
        if "retail" not in subs or "online" not in subs or totals is None:
            raise LayoutChanged(f"{raw.path.name}: subtotal or totals rows missing (found {sorted(subs)}, totals={totals})")
        # The Lottery prints rounded dollars, so a subtotal may differ from the sum of its rows by up to one dollar per row.
        for ch in ("retail", "online"):
            for k in range(3):
                if abs(sum(o[k] for o in ops[ch]) - subs[ch][k]) > len(ops[ch]) + 1:
                    raise LayoutChanged(f"{raw.path.name}: {ch} operator rows do not sum to the subtotal (column {k}: {sum(o[k] for o in ops[ch])} vs {subs[ch][k]})")
        for k in range(3):
            if abs(subs["retail"][k] + subs["online"][k] - totals[k]) > 3:
                raise LayoutChanged(f"{raw.path.name}: subtotals do not sum to Totals (column {k})")
        if raw.doc.period is not None and (raw.doc.period.start.year, raw.doc.period.start.month) != (year, month):
            raise LayoutChanged(f"{raw.path.name}: report is for {year}-{month:02d}, requested {raw.doc.period.start:%Y-%m}")
        out = []
        for ch, t in (("retail", subs["retail"]), ("online", subs["online"]), ("all", totals)):
            out.append({"year": year, "month": month, "channel": ch, "handle_usd": t[0], "adjusted_revenue_usd": t[1], "state_tax_usd": t[2], "operators": len(ops["retail"]) + len(ops["online"]) if ch == "all" else len(ops[ch])})
        return out

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        rows: list[Row] = []
        for r in records:
            p = Period.month(r["year"], r["month"])
            label = {"retail": "Subtotal - Retail", "online": "Subtotal - Online", "all": "Totals"}[r["channel"]]
            prov = provenance.block(SOURCE_ID, raw, method="pdf", entered_by="wpdc_ingest.ks_lottery_sports_wagering",
                                    page_or_table=f"page 1, Monthly Summary, {label} row",
                                    notes="Unaudited per the report; gross revenue before deductions is not reported, so only the Lottery's Revenues figure and the State Share are recorded")
            vals = {"fips": "20", "period_start": p.start.isoformat(), "period_end": p.end.isoformat(), "channel": r["channel"], "market_segment": "regulated_sportsbook",
                    "handle_usd": r["handle_usd"], "gross_revenue_usd": None, "adjusted_revenue_usd": r["adjusted_revenue_usd"], "promo_deductions_usd": None,
                    "state_tax_usd": r["state_tax_usd"], "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=[f"{label} row across {r['operators']} operator rows", "dollars as printed"]))
        return rows
