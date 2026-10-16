"""New Jersey Division of Gaming Enforcement monthly sports wagering report.

The DGE publishes a PDF each month with, per licensee, retail ("Casino" or
"Racetrack" sports pool) and internet sports wagering handle and gross
revenue, plus a statewide total line. The layout has changed several times
since June 2018, so each known layout has a fingerprint and a fixture.

Layout L1 (fingerprint): a page whose text contains "SPORTS WAGERING" and a
table with column headers containing "Handle" and "Gross Revenue", and rows
split into "Retail" and "Internet" sections ending in a "TOTAL" row.

parse() extracts the TOTAL row for retail and internet. It cross-checks that
retail + internet equals the all-channel total within rounding and raises
LayoutChanged otherwise. Per-licensee rows are intentionally not published in
Phase 1; they can be added without changing the dataset schema by using a
licensee column in a separate table.

Revenue definition recorded verbatim: "Gross revenue, before deductions for
promotional gaming credits" per the DGE report footnote.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import pdfplumber

from ..core import provenance
from ..core.source import Document, LayoutChanged, Period, RawDocument, Row

SOURCE_ID = "nj-dge-sports-wagering-monthly"
LANDING = "https://www.njoag.gov/about/divisions-and-offices/division-of-gaming-enforcement-home/financial-and-statistical-information/monthly-sports-wagering-revenue-reports/"
LANDING_CANDIDATES = [
    LANDING,
    "https://www.njoag.gov/about/divisions-and-offices/division-of-gaming-enforcement-home/financial-and-statistical-information/",
    "https://www.nj.gov/oag/ge/sportswageringrevenue.html",
]
# Historic pattern for the monthly PDF; the CLI confirms the link exists on the landing page before fetching.
PDF_PATTERN = "https://www.nj.gov/oag/ge/docs/Financials/SWRTaxReturns/{y}/{Month}{y}.pdf"
REVENUE_DEFINITION = "Gross revenue before deductions for promotional gaming credits, summed across licensees from the DGE-107 monthly sports wagering tax returns; adjusted revenue is taxable gross revenue after the promotional gaming credit deduction and adjustments"
PRESS_RELEASE_PATTERN = "https://www.nj.gov/oag/ge/docs/Financials/PressRelease{y}/{Month}{y}.pdf"
TAX_RETURN_LINES = {
    # line number -> (channel, field). Lines 3, 5, 6, 7 are the retail (Sportsbook Lounge) block; 16, 18, 19 the online block.
    3: ("retail", "gross_revenue_usd"), 5: ("retail", "promo_deductions_usd"), 6: ("retail", "adjusted_revenue_usd"), 7: ("retail", "state_tax_usd"),
    16: ("online", "gross_revenue_usd"), 18: ("online", "adjusted_revenue_usd"), 19: ("online", "state_tax_usd"),
}
MONEY = re.compile(r"\(?-?\$?\s*([\d,]+(?:\.\d+)?)\)?")


def _money(s: str) -> int:
    s = s.strip()
    neg = s.startswith("(") or s.startswith("-")
    m = MONEY.search(s)
    if not m:
        raise ValueError(f"not money: {s!r}")
    v = round(float(m.group(1).replace(",", "")))
    return -v if neg else v


class NJDGESportsWagering:
    source_id = SOURCE_ID
    dataset = "outcomes/handle_revenue.csv"

    def discover(self, period: Period | None) -> list[Document]:
        if period is None:
            t = date.today()
            y, m = (t.year, t.month - 1) if t.month > 1 else (t.year - 1, 12)
            period = Period.month(y, m)
        month_name = period.start.strftime("%B")
        docs = [Document(url=u, period=period, kind="html", label=f"NJ DGE revenue page candidate, looking for {month_name} {period.start.year}") for u in LANDING_CANDIDATES]
        docs.append(Document(url=PDF_PATTERN.format(y=period.start.year, Month=month_name), period=period, kind="pdf", label=f"NJ DGE sports wagering {month_name} {period.start.year} (historic URL pattern)"))
        return docs

    def resolve(self, doc: Document, html: str) -> list[Document]:
        """Find the monthly PDF for the period on the DGE landing page; fall back to the historic URL pattern."""
        assert doc.period is not None
        y = doc.period.start.year
        month = doc.period.start.strftime("%B")
        cands: list[str] = []
        for m in re.finditer(r'href="([^"]+\.pdf)"', html, re.I):
            href = m.group(1)
            low = href.lower()
            compact = low.replace(" ", "").replace("%20", "")
            if ("swrtaxreturns" in compact or "sportswagering" in compact) and f"{month.lower()}{y}" in compact and "amendment" not in compact:
                cands.append(href if href.startswith("http") else "https://www.nj.gov" + (href if href.startswith("/") else "/oag/ge/" + href))
        if not cands:
            raise LayoutChanged(f"No PDF link for {month} {y} on {doc.url}; pdf links seen: {re.findall(r'href=\"([^\"]+\\.pdf)\"', html, re.I)[:15]}")
        return [Document(url=cands[0], period=doc.period, kind="pdf", label=f"NJ DGE sports wagering {month} {y}")]

    def parse(self, raw: RawDocument) -> list[dict[str, Any]]:
        with pdfplumber.open(raw.path) as pdf:
            pages = [(p.extract_text() or "") for p in pdf.pages]
        text = "\n".join(pages)
        if "MONTHLY SPORTS WAGERING TAX RETURN" in text.upper():
            return self._parse_tax_returns(pages, raw)
        return self._parse_press_release(text, raw)

    # ---- DGE-107 monthly tax returns, one form per licensee, compiled into one PDF ----
    def _parse_tax_returns(self, pages: list[str], raw: RawDocument) -> list[dict[str, Any]]:
        """Sum the DGE-107 line items across licensees.

        Each licensee's return has a Sportsbook Lounge (retail) block, lines 1 to 13, and an Online
        Sportsbook block, lines 14 to 25. Skin detail pages repeat lines 14 to 16 per online partner and
        are skipped so nothing is double counted. Amounts in parentheses are negative; a dash is zero.
        """
        totals: dict[tuple[str, str], int] = {}
        licensees: list[str] = []
        month_seen: set[str] = set()
        line_re = re.compile(r"^(\d{1,2})\s+(.+?)\s+\$?\s*(\(?-?[\d,]+\)?|-)\s*$")
        for page in pages:
            up = page.upper()
            if "MONTHLY SPORTS WAGERING TAX RETURN" not in up or "SKIN DETAIL" in up:
                continue
            first = page.strip().splitlines()[0].strip() if page.strip() else ""
            licensees.append(first)
            m = re.search(r"FOR THE MONTH OF ([A-Z]+ \d{4})", up)
            if m:
                month_seen.add(m.group(1))
            for line in page.splitlines():
                mm = line_re.match(line.strip())
                if not mm:
                    continue
                n = int(mm.group(1))
                if n not in TAX_RETURN_LINES:
                    continue
                tok = mm.group(3)
                val = 0 if tok == "-" else _money(tok)
                key = TAX_RETURN_LINES[n]
                totals[key] = totals.get(key, 0) + val
        if not licensees:
            raise LayoutChanged(f"{raw.path.name}: no DGE-107 tax return pages found")
        if len(month_seen) != 1:
            raise LayoutChanged(f"{raw.path.name}: expected one reporting month across forms, saw {sorted(month_seen)}")
        if raw.doc.period:
            want = raw.doc.period.start.strftime("%B %Y").upper()
            if want not in month_seen:
                raise LayoutChanged(f"{raw.path.name}: forms are for {sorted(month_seen)}, requested {want}")
        out = []
        for ch in ("retail", "online"):
            rec = {"channel": ch, "handle_usd": None, "gross_revenue_usd": totals.get((ch, "gross_revenue_usd")), "adjusted_revenue_usd": totals.get((ch, "adjusted_revenue_usd")), "promo_deductions_usd": totals.get((ch, "promo_deductions_usd"), 0 if ch == "retail" else None), "state_tax_usd": totals.get((ch, "state_tax_usd")), "licensees": len(licensees), "document": "dge-107"}
            out.append(rec)
        allrec = {"channel": "all", "handle_usd": None, "document": "dge-107", "licensees": len(licensees)}
        for f in ("gross_revenue_usd", "adjusted_revenue_usd", "state_tax_usd"):
            vals = [r[f] for r in out if r[f] is not None]
            allrec[f] = sum(vals) if vals else None
        allrec["promo_deductions_usd"] = out[0]["promo_deductions_usd"]
        out.append(allrec)
        return out

    # ---- Monthly press release: handle and gross revenue by licensee and channel ----
    def _parse_press_release(self, text: str, raw: RawDocument) -> list[dict[str, Any]]:
        if "SPORTS WAGERING" not in text.upper():
            raise LayoutChanged(f"{raw.path.name}: 'SPORTS WAGERING' not found in text; first 200 chars: {text[:200]!r}")
        if "HANDLE" not in text.upper():
            raise LayoutChanged(f"{raw.path.name}: expected a Handle column in the press release; got headers: {text.splitlines()[:6]}")
        section = None
        found: dict[str, dict[str, int]] = {}
        for line in text.splitlines():
            u = line.strip().upper()
            if u.startswith("RETAIL") or u.startswith("CASINO AND RACETRACK"):
                section = "retail"
            elif u.startswith("INTERNET") or u.startswith("ONLINE"):
                section = "online"
            elif u.startswith("TOTAL") and section:
                nums = [t for t in re.findall(r"\(?-?\$?[\d,]+(?:\.\d+)?\)?", line) if any(ch.isdigit() for ch in t)]
                if len(nums) < 2:
                    raise LayoutChanged(f"{raw.path.name}: TOTAL row in {section} section has fewer than two numbers: {line!r}")
                found[section] = {"handle_usd": _money(nums[0]), "gross_revenue_usd": _money(nums[1])}
                if section == "online":
                    section = "all"
            elif u.startswith("GRAND TOTAL") or (u.startswith("TOTAL") and section == "all"):
                nums = [t for t in re.findall(r"\(?-?\$?[\d,]+(?:\.\d+)?\)?", line) if any(ch.isdigit() for ch in t)]
                if len(nums) >= 2:
                    found["all"] = {"handle_usd": _money(nums[0]), "gross_revenue_usd": _money(nums[1])}
        missing = [k for k in ("retail", "online") if k not in found]
        if missing:
            raise LayoutChanged(f"{raw.path.name}: could not find TOTAL rows for {missing}; sections seen: {list(found)}")
        if "all" in found:
            for k in ("handle_usd", "gross_revenue_usd"):
                if abs(found["retail"][k] + found["online"][k] - found["all"][k]) > 2:
                    raise LayoutChanged(f"{raw.path.name}: retail + internet {k} does not equal grand total")
        return [{"channel": ch, "document": "press-release", **vals} for ch, vals in found.items()]

    def normalize(self, records: list[dict[str, Any]], raw: RawDocument) -> list[Row]:
        period = raw.doc.period
        assert period is not None
        rows: list[Row] = []
        for rec in records:
            doc = rec.get("document", "press-release")
            page = "DGE-107 monthly sports wagering tax returns, lines 3, 5, 6, 7 (Sportsbook Lounge) and 16, 18, 19 (Online Sportsbook), summed across licensees" if doc == "dge-107" else "Monthly press release, sports wagering TOTAL rows"
            prov = provenance.block(SOURCE_ID, raw, method="pdf", entered_by="wpdc_ingest.nj_dge_sports_wagering", page_or_table=page)
            vals = {"fips": "34", "period_start": period.start.isoformat(), "period_end": period.end.isoformat(), "channel": rec["channel"], "market_segment": "regulated_sportsbook",
                    "handle_usd": rec.get("handle_usd"), "gross_revenue_usd": rec.get("gross_revenue_usd"), "adjusted_revenue_usd": rec.get("adjusted_revenue_usd"), "promo_deductions_usd": rec.get("promo_deductions_usd"), "state_tax_usd": rec.get("state_tax_usd"),
                    "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            steps = [f"summed across {rec.get('licensees', '?')} licensee returns" if doc == "dge-107" else f"TOTAL row of the {rec['channel']} section", "dollars rounded to integer"]
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=steps))
        return rows
