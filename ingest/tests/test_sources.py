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
    assert ok_all["notes"] and "F-2" in ok_all["notes"]  # the table reference leads the CSV notes
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
    html = '''<table><tr><td>F-2 Three Months Ended June 30, 2026</td><td><a href="/sites/default/files/data_tables/bf_f2.3_0630.2026.xlsx">Download</a></td></tr>
    <tr><td>F-2 Twelve Months</td><td><a href="https://www.uscourts.gov/sites/default/files/data_tables/bf_f2_0630.2026.xlsx">Download</a></td></tr>
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


def test_nj_tax_returns_2018_form_family_a():
    src = NJDGESportsWagering()
    raw = raw_for(FIX / "nj_dge107_2018_synthetic.pdf", Period.month(2018, 9), "pdf")
    recs = {r["channel"]: r for r in src.parse(raw)}
    assert recs["retail"]["gross_revenue_usd"] == 394_046 - 40_848  # line 1, parentheses negative
    assert recs["online"]["gross_revenue_usd"] == 106_463 + 223_339  # line 8
    assert recs["retail"]["state_tax_usd"] == 33_494 + 1_611 and recs["online"]["state_tax_usd"] == 13_840 + 29_035
    assert recs["retail"]["adjusted_revenue_usd"] is None and recs["all"]["promo_deductions_usd"] is None  # not on this form
    assert "SEPTMEBER" in recs["all"]["notes"]  # misspelt month tolerated and recorded
    rows = [r.finalize() for r in src.normalize(list(recs.values()), raw)]
    assert "2018 to May 2019 form" in rows[0]["notes"] and "SEPTMEBER" in rows[0]["notes"]


def test_nj_tax_returns_2019_form_family_b_split_digits():
    src = NJDGESportsWagering()
    raw = raw_for(FIX / "nj_dge107_2019_synthetic.pdf", Period.month(2019, 12), "pdf")
    recs = {r["channel"]: r for r in src.parse(raw)}
    assert recs["retail"]["gross_revenue_usd"] == 108_437 and recs["retail"]["adjusted_revenue_usd"] == 108_437
    assert recs["online"]["gross_revenue_usd"] == 26_752  # "2 6,752" read as one number; footed against year to date
    assert recs["online"]["state_tax_usd"] == 3_478
    assert recs["all"]["gross_revenue_usd"] == 108_437 + 26_752


def test_nj_tax_returns_misfooting_form_raises():
    with pytest.raises(LayoutChanged):
        NJDGESportsWagering().parse(raw_for(FIX / "nj_dge107_misfoot_synthetic.pdf", Period.month(2019, 12), "pdf"))


def test_uscourts_f2_pdf_2022_layout():
    src = USCourtsBankruptcyF2()
    recs = {r["district_code"]: r for r in src.parse(raw_for(FIX / "uscourts_f2_2022_synthetic.pdf", Period.quarter_ending(2022, 12), "pdf"))}
    assert set(recs) == {"NJ", "ARE", "ND", "OKN"}  # Total, circuit and Virgin Islands rows skipped
    assert recs["NJ"] == {"district_code": "NJ", "all_nonbusiness": 2415, "7": 1349, "11": 3, "13": 1063}
    assert recs["ND"]["all_nonbusiness"] == 97 and recs["ARE"]["13"] == 879


def test_uscourts_f2_pdf_2018_layout_repairs_glued_last_column():
    src = USCourtsBankruptcyF2()
    recs = {r["district_code"]: r for r in src.parse(raw_for(FIX / "uscourts_f2_2018_synthetic.pdf", Period.quarter_ending(2018, 3), "pdf"))}
    assert set(recs) == {"NJ", "ARE", "ARW", "ND", "OKN"}
    assert recs["NJ"] == {"district_code": "NJ", "all_nonbusiness": 6485, "7": 3967, "11": 29, "13": 2489}  # "2,4890" repaired
    assert recs["OKN"]["13"] == 67 and recs["ND"]["13"] == 11 and recs["ARW"]["13"] == 403
    rows = [r.finalize() for r in src.normalize(list(recs.values()), raw_for(FIX / "uscourts_f2_2018_synthetic.pdf", Period.quarter_ending(2018, 3), "pdf"))]
    ar = next(r for r in rows if r["fips"] == "05" and r["chapter"] == "13")
    assert ar["filings"] == 949 + 403 and "PDF edition" in ar["notes"]


def test_uscourts_resolve_takes_real_links_and_prefers_xlsx():
    src = USCourtsBankruptcyF2()
    page = Document(url="u", period=Period.quarter_ending(2022, 12), kind="html")
    html = '<a href="/sites/default/files/data_tables/bf_f2.3_1231.2022.pdf">x</a><a href="/sites/default/files/data_tables/bf_f2_1231.2022.pdf">y</a><a href="/sites/default/files/data_tables/bf_f2_1231.2022.xlsx">z</a>'
    docs = {d.get("measure"): d for d in src.resolve(page, html)}
    assert docs["quarter"].url.endswith("bf_f2.3_1231.2022.pdf") and docs["quarter"].kind == "pdf"
    assert docs["twelve_months_ending"].url.endswith("bf_f2_1231.2022.xlsx")


def test_uscourts_f2_pdf_doubled_header_page_is_read():
    src = USCourtsBankruptcyF2()
    recs = {r["district_code"]: r for r in src.parse(raw_for(FIX / "uscourts_f2_doubled_synthetic.pdf", Period.quarter_ending(2021, 12), "pdf"))}
    assert set(recs) == {"DC", "ME"} and recs["ME"]["all_nonbusiness"] == 147 and recs["DC"]["13"] == 11


def test_uscourts_resolve_accepts_reuploaded_file_suffix():
    src = USCourtsBankruptcyF2()
    page = Document(url="u", period=Period.quarter_ending(2018, 6), kind="html")
    html = '<a href="/data-news/data-tables/2018/06/30/bankruptcy-filings/f-2-three-months">x</a><a href="/sites/default/files/bf_f2.3_0630.2018_0.pdf">y</a><a href="/sites/default/files/bf_f2_0630.2018.pdf">z</a>'
    docs = {d.get("measure"): d for d in src.resolve(page, html)}
    assert docs["quarter"].url.endswith("/bf_f2.3_0630.2018_0.pdf") and docs["twelve_months_ending"].url.endswith("/bf_f2_0630.2018.pdf")


def test_archive_docs_extension_from_type_url_or_bytes():
    from wpdc_ingest.archive_docs import extension
    assert extension("https://x/a.xlsx", "application/octet-stream", b"PK\x03\x04xl/workbook.xml") == "xlsx"
    assert extension("https://x/report?id=1", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", b"PK") == "xlsx"
    assert extension("https://x/page?f=1", "text/html; charset=utf-8", b"<!DOCTYPE html>") == "html"
    assert extension("https://x/r.pdf", "", b"%PDF-1.7") == "pdf"
    assert extension("https://x/d", "text/csv", b"a,b") == "csv"
    assert extension("https://x/d", "", b"\x00\x01") == "bin"


def test_ny_statewide_monthly_report_parses_every_month_and_crosschecks_totals():
    from wpdc_ingest.sources.ny_gaming_commission_mobile_sports import NYGamingCommissionMobileSports, REVENUE_DEFINITION
    src = NYGamingCommissionMobileSports()
    raw = raw_for(FIX / "ny_monthly_mobile_statewide_2026-09.pdf", None, "pdf")
    recs = src.parse(raw)
    assert len(recs) == 56  # January 2022 to August 2026
    aug26 = next(r for r in recs if (r["year"], r["month"]) == (2026, 8))
    assert (aug26["handle_usd"], aug26["gross_revenue_usd"], aug26["state_tax_usd"]) == (1_731_302_503, 168_476_334, 85_934_232)
    apr23 = next(r for r in recs if (r["year"], r["month"]) == (2023, 4))  # row with a blank adjustments cell
    assert (apr23["handle_usd"], apr23["gross_revenue_usd"], apr23["state_tax_usd"]) == (1_544_465_378, 138_820_564, 70_798_487)
    jan22 = next(r for r in recs if (r["year"], r["month"]) == (2022, 1))  # first month, on the page with Unclaimed Funds
    assert jan22["handle_usd"] == 1_669_719_034 and jan22["state_tax_usd"] == 63_310_867
    rows = [r.finalize() for r in src.normalize(recs, raw)]
    assert len(rows) == 56 and all(r["channel"] == "online" and r["fips"] == "36" for r in rows)
    first = min(rows, key=lambda r: r["period_start"])
    assert first["period_start"] == "2022-01-01" and first["period_end"] == "2022-01-31"
    assert rows[0]["revenue_definition"] == REVENUE_DEFINITION and rows[0]["adjusted_revenue_usd"] == rows[0]["gross_revenue_usd"]
    assert "page" in rows[0]["notes"]
    # a single requested month filters to that month; a month not in the edition fails loudly
    one = src.normalize(recs, raw_for(FIX / "ny_monthly_mobile_statewide_2026-09.pdf", Period.month(2025, 11), "pdf"))
    assert len(one) == 1 and one[0].values["handle_usd"] == 2_606_597_963
    with pytest.raises(LayoutChanged):
        src.normalize(recs, raw_for(FIX / "ny_monthly_mobile_statewide_2026-09.pdf", Period.month(2026, 9), "pdf"))


def test_ny_report_layout_change_raises(tmp_path):
    from wpdc_ingest.sources.ny_gaming_commission_mobile_sports import NYGamingCommissionMobileSports
    with pytest.raises(LayoutChanged):
        NYGamingCommissionMobileSports().parse(raw_for(FIX / "nj_dge_synthetic.pdf", None, "pdf"))
