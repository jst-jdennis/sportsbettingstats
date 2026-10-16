"""New Jersey Division of Gaming Enforcement monthly sports wagering tax returns.

The DGE publishes, for each month since June 2018, a PDF compiling every
licensee's DGE-107 Monthly Sports Wagering Tax Return. Handle is not on
these forms; only gross revenue, deductions and tax. The form has been
revised several times, and the line numbers moved, so the parser detects
the form family from the form's own total line and reads each family by
its own line map. Three families exist (fingerprints are the total line):

  A  June 2018 to May 2019 ("6/18", "1/19"): 16 lines; "Total Sports Wagering
     Tax for the Month (add|sum lines 7 and 14)". Monthly gross revenue is
     line 1 (retail) and 8 (internet); the taxable amounts are year to date
     only, so monthly adjusted revenue is not reported. Line 16 promotional
     credits are informational, not a deduction.
  B  June 2019 to December 2021 ("4/19", "6/19"): 26 lines; "Total Sports
     Wagering Tax Payment (sum lines 8 and 20)". Monthly gross 3 and 15,
     taxable 5 and 17, tax 6 and 18. Line 26 promotional credits informational.
  C  January 2022 onward ("1/22", "07/22", "03/24", "07/25", "02/26"): 28
     lines; "Total Sports Wagering Tax Payment (sum lines 9 and 21)". Monthly
     gross 3 and 16, retail promotional credit deduction 5, taxable 6 and 18,
     tax 7 and 19. Later revisions rename retail to "Sportsbook Lounge" and
     internet to "Online Sportsbook" without moving lines.

state_tax_usd is the tax computed on the month's taxable revenue (before loss
carryforward is applied), which is the only tax figure present in every
family. Each family B or C form is checked against itself: year-to-date
minus prior year-to-date must equal the monthly gross revenue, which catches
the split digits ("4 ,192,270") that pdfplumber sometimes produces.
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
REVENUE_DEFINITION = "Gross revenue before deductions for promotional gaming credits, summed across licensees from the DGE-107 monthly sports wagering tax returns; adjusted revenue is the month's taxable gross revenue after adjustments and, from 2022, the promotional gaming credit deduction; state tax is the tax computed on that taxable revenue before loss carryforward"
PRESS_RELEASE_PATTERN = "https://www.nj.gov/oag/ge/docs/Financials/PressRelease{y}/{Month}{y}.pdf"
# Form families, detected from the layout of the numbered lines (the wording of the total line varies
# within a family, and some licensees file retail-only pages). line number -> (channel, field).
def _family_of(desc: dict[int, str]) -> str | None:
    d = {n: t.upper() for n, t in desc.items()}
    if d.get(1, "").startswith("CURRENT MONTH"):
        return "A"
    if ("MONTHLY" in d.get(16, "") and "GROSS REVENUE" in d.get(16, "")) or "PROMOTIONAL" in d.get(5, ""):
        return "C"
    if ("MONTHLY" in d.get(15, "") and "GROSS REVENUE" in d.get(15, "")) or ("MONTHLY" in d.get(3, "") and "TAXABLE" in d.get(5, "")):
        return "B"
    return None


FAMILIES = {
    "A": {"lines": {1: ("retail", "gross_revenue_usd"), 7: ("retail", "state_tax_usd"), 8: ("online", "gross_revenue_usd"), 14: ("online", "state_tax_usd")},
          "ytd_check": None,
          "page": "DGE-107 (2018 to May 2019 form), lines 1 and 7 (casino or racetrack) and 8 and 14 (internet), summed across licensees; monthly taxable revenue is not on this form"},
    "B": {"lines": {3: ("retail", "gross_revenue_usd"), 5: ("retail", "adjusted_revenue_usd"), 6: ("retail", "state_tax_usd"), 15: ("online", "gross_revenue_usd"), 17: ("online", "adjusted_revenue_usd"), 18: ("online", "state_tax_usd")},
          "ytd_check": ((1, 2, 3), (13, 14, 15)),
          "page": "DGE-107 (June 2019 to 2021 form), lines 3, 5, 6 (retail) and 15, 17, 18 (internet), summed across licensees"},
    "C": {"lines": {3: ("retail", "gross_revenue_usd"), 5: ("retail", "promo_deductions_usd"), 6: ("retail", "adjusted_revenue_usd"), 7: ("retail", "state_tax_usd"), 16: ("online", "gross_revenue_usd"), 18: ("online", "adjusted_revenue_usd"), 19: ("online", "state_tax_usd")},
          "ytd_check": ((1, 2, 3), (14, 15, 16)),
          "page": "DGE-107 (2022 onward form), lines 3, 5, 6, 7 (retail or Sportsbook Lounge) and 16, 18, 19 (online), summed across licensees"},
}
MONTH_NAMES = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
MONTH_RE = re.compile(r"FOR THE MONTH OF\s+([A-Z]+),?\s+(\d{4})")
# A numbered line: number, description, then the amount. pdfplumber sometimes splits digits ("4 ,192,270",
# "2 6,752"), so the amount may contain spaces; it is the trailing run of digit, comma, space, parenthesis
# and minus characters, preceded by a space or a dollar sign.
LINE_RE = re.compile(r"^(\d{1,2})\s+(.*?)(?<=\s)(-?\s*\$?\s*\(?\s*-?\d[\d,\s]*\)?|\$?\s*-)\s*$")
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
    @staticmethod
    def _month_key(text_upper: str) -> str | None:
        """Return 'MONTH YYYY' from the form heading, tolerating a comma and a misspelt month ("JANAURY")."""
        m = MONTH_RE.search(text_upper)
        if not m:
            return None
        name, year = m.group(1), m.group(2)
        if name not in MONTH_NAMES:
            import difflib
            close = difflib.get_close_matches(name, MONTH_NAMES, n=1, cutoff=0.75)
            if not close:
                return f"{name} {year}"
            name = close[0]
        return f"{name} {year}"

    def _parse_tax_returns(self, pages: list[str], raw: RawDocument) -> list[dict[str, Any]]:
        """Sum the DGE-107 line items across licensees, reading each form by its detected family.

        Skin detail pages repeat the online block per partner and are skipped so nothing is double
        counted. Amounts in parentheses are negative; a dash or a blank is zero.
        """
        totals: dict[tuple[str, str], int] = {}
        licensees: list[str] = []
        month_seen: set[str] = set()
        families_seen: set[str] = set()
        typo_notes: set[str] = set()
        for page in pages:
            up = page.upper()
            if "MONTHLY SPORTS WAGERING TAX RETURN" not in up or "SKIN DETAIL" in up:
                continue
            first = page.strip().splitlines()[0].strip() if page.strip() else ""
            values: dict[int, int] = {}
            desc: dict[int, str] = {}
            for line in page.splitlines():
                st = line.strip()
                mm = LINE_RE.match(st)
                if mm:
                    n = int(mm.group(1))
                    tok = mm.group(3).replace(" ", "").replace("$", "")
                    values[n] = 0 if tok in ("-", "") else _money(tok)
                    desc[n] = mm.group(2)
                    continue
                mm2 = re.match(r"^(\d{1,2})\s+([A-Za-z].*)$", st)
                if mm2:
                    values.setdefault(int(mm2.group(1)), 0)  # a numbered line with no amount is blank, that is zero
                    desc.setdefault(int(mm2.group(1)), mm2.group(2))
            fam_key = _family_of(desc)
            if fam_key is None:
                raise LayoutChanged(f"{raw.path.name}: {first}: tax return page matches no known DGE-107 form family; numbered lines: {[f'{n} {t[:40]}' for n, t in sorted(desc.items())][:8]}")
            fam = FAMILIES[fam_key]
            families_seen.add(fam_key)
            licensees.append(first)
            mk = self._month_key(up)
            if mk:
                month_seen.add(mk)
                raw_name = MONTH_RE.search(up).group(1)
                if raw_name not in MONTH_NAMES:
                    typo_notes.add(f"{first}: month printed as {raw_name!r}")
            if fam["ytd_check"]:
                for ytd, prior, monthly in fam["ytd_check"]:
                    if abs(values.get(ytd, 0) - values.get(prior, 0) - values.get(monthly, 0)) > 2:
                        raise LayoutChanged(f"{raw.path.name}: {first}: line {ytd} minus line {prior} is not line {monthly} ({values.get(ytd)} - {values.get(prior)} vs {values.get(monthly)}); amounts may have been misread")
            for n, key in fam["lines"].items():
                totals[key] = totals.get(key, 0) + values.get(n, 0)
        if not licensees:
            raise LayoutChanged(f"{raw.path.name}: no DGE-107 tax return pages found")
        if len(month_seen) != 1:
            raise LayoutChanged(f"{raw.path.name}: expected one reporting month across forms, saw {sorted(month_seen)}")
        if raw.doc.period:
            want = raw.doc.period.start.strftime("%B %Y").upper()
            if want not in month_seen:
                raise LayoutChanged(f"{raw.path.name}: forms are for {sorted(month_seen)}, requested {want}")
        # In transition months some licensees file the previous form, so a month may mix families.
        # A field is reported only when every form in the month carries it.
        fam_keys = sorted(families_seen)
        fam_key = fam_keys[-1] if len(fam_keys) == 1 else "+".join(fam_keys)
        has = set.intersection(*[{f for (_, f) in FAMILIES[k]["lines"].values()} for k in fam_keys])
        notes = []
        if "A" in families_seen:
            notes.append("2018 to May 2019 form: monthly taxable revenue is not reported, only year to date, so adjusted revenue is left empty; promotional credits on this form are informational and not a deduction")
        if "B" in families_seen:
            notes.append("June 2019 to 2021 form: promotional gaming credits are informational on this form and not deducted from taxable revenue")
        if len(fam_keys) > 1:
            notes.append(f"licensees filed more than one form revision this month ({', '.join(fam_keys)}); only fields present on every revision are reported")
        notes.extend(sorted(typo_notes))
        out = []
        for ch in ("retail", "online"):
            rec = {"channel": ch, "handle_usd": None, "document": "dge-107", "licensees": len(licensees), "family": fam_key, "notes": "; ".join(notes) or None}
            for f in ("gross_revenue_usd", "adjusted_revenue_usd", "promo_deductions_usd", "state_tax_usd"):
                if f in has and (ch, f) in totals:
                    rec[f] = totals[(ch, f)]
                elif f == "promo_deductions_usd" and fam_key == "C" and ch == "retail":
                    rec[f] = 0
                else:
                    rec[f] = None
            out.append(rec)
        allrec = {"channel": "all", "handle_usd": None, "document": "dge-107", "licensees": len(licensees), "family": fam_key, "notes": "; ".join(notes) or None}
        for f in ("gross_revenue_usd", "adjusted_revenue_usd", "state_tax_usd", "promo_deductions_usd"):
            vals = [r[f] for r in out if r[f] is not None]
            allrec[f] = sum(vals) if vals else None
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
            page = ("; ".join(FAMILIES[k]["page"] for k in rec["family"].split("+")) if doc == "dge-107" else "Monthly press release, sports wagering TOTAL rows")
            prov = provenance.block(SOURCE_ID, raw, method="pdf", entered_by="wpdc_ingest.nj_dge_sports_wagering", page_or_table=page, notes=rec.get("notes"))
            vals = {"fips": "34", "period_start": period.start.isoformat(), "period_end": period.end.isoformat(), "channel": rec["channel"], "market_segment": "regulated_sportsbook",
                    "handle_usd": rec.get("handle_usd"), "gross_revenue_usd": rec.get("gross_revenue_usd"), "adjusted_revenue_usd": rec.get("adjusted_revenue_usd"), "promo_deductions_usd": rec.get("promo_deductions_usd"), "state_tax_usd": rec.get("state_tax_usd"),
                    "revenue_definition": REVENUE_DEFINITION, "is_revised": False}
            steps = [f"summed across {rec.get('licensees', '?')} licensee returns" if doc == "dge-107" else f"TOTAL row of the {rec['channel']} section", "dollars rounded to integer"]
            rows.append(Row(values=vals, provenance=provenance.csv_columns(prov), transform_steps=steps))
        return rows
