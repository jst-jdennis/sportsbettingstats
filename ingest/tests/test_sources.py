from datetime import date
from pathlib import Path

import pytest

from wpdc_ingest.core.source import Document, LayoutChanged, Period, RawDocument
from wpdc_ingest.sources.nj_dge_sports_wagering import NJDGESportsWagering, REVENUE_DEFINITION
from wpdc_ingest.sources.uscourts_bankruptcy import USCourtsBankruptcyF2

FIX = Path(__file__).parent / "fixtures"


def raw_for(path: Path, period: Period, kind: str) -> RawDocument:
    return RawDocument(doc=Document(url="https://example.invalid/" + path.name, period=period, kind=kind, label=path.name), path=path, sha256="0" * 64, retrieved_at=date(2026, 10, 16), archive_url=None)


def test_uscourts_f2_parse_and_sum_by_state():
    src = USCourtsBankruptcyF2()
    raw = raw_for(FIX / "uscourts_f2_synthetic.xlsx", Period.quarter_ending(2026, 6), "xlsx")
    recs = src.parse(raw)
    codes = {r["district_code"] for r in recs}
    assert codes == {"OKN", "OKE", "OKW", "KS", "NJ", "ARE", "ND"}  # totals and circuit rows skipped; "OK,N" normalized; "AR \u00b2" footnote stripped and mapped
    nd = next(r for r in recs if r["district_code"] == "ND")
    assert nd["all_nonbusiness"] == 254  # the "2nd" circuit row must not be read as ND
    rows = [r.finalize() for r in src.normalize(recs, raw)]
    ok_all = next(r for r in rows if r["fips"] == "40" and r["chapter"] == "all_nonbusiness")
    assert ok_all["filings"] == 118 + 79 + 196
    ok_13 = next(r for r in rows if r["fips"] == "40" and r["chapter"] == "13")
    assert ok_13["filings"] == 48 + 29 + 75
    assert ok_all["status"] == "pending_review" and ok_all["source_id"] == "uscourts-bankruptcy-f2"
    assert "OKN" in ok_all["notes"] if ok_all.get("notes") else True
    assert ok_all["period_start"] == "2026-04-01" and ok_all["period_end"] == "2026-06-30"
    ar = next(r for r in rows if r["fips"] == "05" and r["chapter"] == "all_nonbusiness")
    assert ar["filings"] == 98
    # Twelve-month table: the period is the year ending on the quarter end.
    raw12 = RawDocument(doc=Document(url="u", period=Period.quarter_ending(2026, 6), kind="xlsx", label="12m", meta=(("measure", "twelve_months_ending"),)), path=FIX / "uscourts_f2_synthetic.xlsx", sha256="0" * 64, retrieved_at=date(2026, 10, 16), archive_url=None)
    rows12 = [r.finalize() for r in src.normalize(src.parse(raw12), raw12)]
    assert rows12[0]["period_start"] == "2025-07-01" and rows12[0]["period_end"] == "2026-06-30" and rows12[0]["measure"] == "twelve_months_ending"


def test_uscourts_f2_layout_change_raises(tmp_path):
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Something else entirely"]); ws.append(["District", "Count"])
    p = tmp_path / "bad.xlsx"; wb.save(p)
    with pytest.raises(LayoutChanged):
        USCourtsBankruptcyF2().parse(raw_for(p, Period.quarter_ending(2026, 6), "xlsx"))


def test_nj_dge_parse_totals_and_crosscheck():
    src = NJDGESportsWagering()
    raw = raw_for(FIX / "nj_dge_synthetic.pdf", Period.month(2026, 9), "pdf")
    recs = src.parse(raw)
    by = {r["channel"]: r for r in recs}
    assert by["retail"]["handle_usd"] == 15_000_000 and by["retail"]["gross_revenue_usd"] == 800_000
    assert by["online"]["handle_usd"] == 150_000_000 and by["online"]["gross_revenue_usd"] == 12_500_000
    assert by["all"]["handle_usd"] == 165_000_000
    rows = [r.finalize() for r in src.normalize(recs, raw)]
    assert all(r["revenue_definition"] == REVENUE_DEFINITION for r in rows)
    assert all(r["market_segment"] == "regulated_sportsbook" for r in rows)
    assert {r["channel"] for r in rows} == {"retail", "online", "all"}


def test_nj_dge_wrong_document_raises(tmp_path):
    from tests.make_fixtures import nj_pdf  # reuse writer, then corrupt the text
    p = tmp_path / "x.pdf"; nj_pdf(p)
    data = p.read_bytes().replace(b"SPORTS WAGERING", b"SLOT MACHINES"); p.write_bytes(data)
    with pytest.raises(LayoutChanged):
        NJDGESportsWagering().parse(raw_for(p, Period.month(2026, 9), "pdf"))


def test_writer_upsert_supersedes(tmp_path, monkeypatch):
    from wpdc_ingest.core import writers
    path = tmp_path / "bankruptcy.csv"
    base = {"fips": "40", "period_start": "2026-04-01", "period_end": "2026-06-30", "measure": "quarter", "chapter": "7", "source_id": "uscourts-bankruptcy-f2", "source_url": "u", "archive_url": "", "retrieved_at": "2026-10-16", "status": "pending_review", "entered_by": "t", "reviewed_by": "", "notes": ""}
    key = ("fips", "period_start", "period_end", "measure", "chapter"); sort = ("fips", "period_start", "chapter")
    assert writers.upsert_csv(path, "bankruptcy", [{**base, "filings": 100}], key, sort) == (1, 0)
    assert writers.upsert_csv(path, "bankruptcy", [{**base, "filings": 100}], key, sort) == (0, 0)  # identical: skipped
    assert writers.upsert_csv(path, "bankruptcy", [{**base, "filings": 101}], key, sort) == (1, 1)  # restated: old superseded
    rows = writers.read_csv(path)
    assert sorted(r["status"] for r in rows) == ["pending_review", "superseded"]


def test_uscourts_resolve_finds_f2_tables():
    html = '''<table><tr><td>F-2 Three Months Ended June 30, 2026</td><td><a href="/sites/default/files/data_tables/bf_f2_0630.2026.xlsx">Download</a></td></tr>
    <tr><td>F-2 Twelve Months</td><td><a href="https://www.uscourts.gov/sites/default/files/data_tables/bf_f2_twelve_0630.2026.xlsx">Download</a></td></tr>
    <tr><td>F-2A Three Months</td><td><a href="/x/bf_f2a_0630.2026.xlsx">Download</a></td></tr>
    <tr><td>F-5A</td><td><a href="/x/bf_f5a_0630.2026.xlsx">Download</a></td></tr></table>'''
    src = USCourtsBankruptcyF2()
    discovered = src.discover(Period.quarter_ending(2026, 6))
    assert discovered[0].url.endswith("/document/bf_f2.3_0630.2026.xlsx") and discovered[0].get("measure") == "quarter"
    assert discovered[1].url.endswith("/document/bf_f2_0630.2026.xlsx") and discovered[1].get("measure") == "twelve_months_ending"
    page = discovered[2]
    assert page.kind == "html" and page.url.endswith("/june-2026-quarterly-bankruptcy-filings")
    docs = src.resolve(page, html)
    assert [d.get("measure") for d in docs] == ["quarter", "twelve_months_ending"]
    assert docs[0].url.startswith("https://www.uscourts.gov/") and docs[0].kind == "xlsx"
    # The real quarter page links to per-table pages rather than files; those map to the file convention.
    docs2 = src.resolve(page, '<a href="/data-news/data-tables/2026/06/30/bankruptcy-filings/f-2">F-2</a><a href="/data-news/data-tables/2026/06/30/bankruptcy-filings/f-2-three-months">F-2 Three Months</a>')
    assert {d.url.rsplit("/", 1)[1] for d in docs2} == {"bf_f2.3_0630.2026.xlsx", "bf_f2_0630.2026.xlsx"}


def test_uscourts_resolve_raises_without_f2():
    with pytest.raises(LayoutChanged):
        USCourtsBankruptcyF2().resolve(Document(url="u", period=Period.quarter_ending(2026, 6), kind="html"), "<a href='/a.pdf'>F-5A</a>")


def test_nj_discover_candidates_and_resolve():
    src = NJDGESportsWagering()
    docs = src.discover(Period.month(2026, 8))
    assert [d.kind for d in docs] == ["html", "html", "html", "pdf"]  # landing candidates, then the historic PDF pattern
    assert docs[-1].url.endswith("SWRTaxReturns/2026/August2026.pdf")
    page = docs[0]
    found = src.resolve(page, '<a href="https://www.nj.gov/oag/ge/docs/Financials/SWRTaxReturns/2026/August2026.pdf">August</a><a href="https://www.nj.gov/oag/ge/docs/Financials/SWRTaxReturns/2026/107AmendmentsList2026.pdf">x</a>')
    assert found[0].url == "https://www.nj.gov/oag/ge/docs/Financials/SWRTaxReturns/2026/August2026.pdf"
    with pytest.raises(LayoutChanged):
        src.resolve(page, "<p>nothing</p>")


def test_census_csv_parse(tmp_path):
    from wpdc_ingest.sources.census_population import CensusPopulation
    csv_text = "SUMLEV,REGION,DIVISION,STATE,NAME,ESTIMATESBASE2020,POPESTIMATE042020,POPESTIMATE2020,POPESTIMATE2021\n010,0,0,00,United States,1,1,2,3\n040,3,6,40,Oklahoma,3959353,3959353,3964912,3986639\n040,X,X,72,Puerto Rico,1,1,2,3\n"
    p = tmp_path / "nst.csv"; p.write_text(csv_text)
    src = CensusPopulation()
    doc = src.discover(None)[0]
    raw = RawDocument(doc=Document(url=doc.url, kind="csv", label=doc.label, meta=(("vintage", 2025),)), path=p, sha256="0" * 64, retrieved_at=date(2026, 10, 16), archive_url=None)
    recs = src.parse(raw)
    assert [(r["fips"], r["year"], r["population"]) for r in recs] == [("40", 2020, 3964912), ("40", 2021, 3986639)]
    assert all(r["vintage"] == 2025 for r in recs)


def test_census_api_html_error_raises(tmp_path):
    from wpdc_ingest.sources.census_population import CensusPopulation
    p = tmp_path / "x.json"; p.write_text("<html>missing key</html>")
    src = CensusPopulation()
    doc = [d for d in src.discover(None) if d.kind == "json"][0]
    with pytest.raises(LayoutChanged):
        src.parse(RawDocument(doc=doc, path=p, sha256="0" * 64, retrieved_at=date(2026, 10, 16), archive_url=None))


def test_nj_tax_returns_sum_across_licensees_and_skip_skin_pages():
    src = NJDGESportsWagering()
    raw = raw_for(FIX / "nj_dge107_synthetic.pdf", Period.month(2026, 8), "pdf")
    recs = {r["channel"]: r for r in src.parse(raw)}
    assert recs["retail"]["gross_revenue_usd"] == 3_668 + 100_000
    assert recs["retail"]["promo_deductions_usd"] == -2_000  # parentheses are negative, dash is zero
    assert recs["retail"]["state_tax_usd"] == 312 + 8_330
    assert recs["online"]["gross_revenue_usd"] == 5_000_000 + 3_000_000  # skin detail page not double counted
    assert recs["online"]["state_tax_usd"] == 987_500 + 592_500
    assert recs["all"]["gross_revenue_usd"] == 3_668 + 100_000 + 8_000_000
    assert recs["retail"]["handle_usd"] is None
    rows = [r.finalize() for r in src.normalize(list(recs.values()), raw)]
    assert all(r["revenue_definition"].startswith("Gross revenue before deductions") for r in rows)


def test_nj_tax_returns_wrong_month_raises(tmp_path):
    src = NJDGESportsWagering()
    with pytest.raises(LayoutChanged):
        src.parse(raw_for(FIX / "nj_dge107_synthetic.pdf", Period.month(2026, 9), "pdf"))
