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
    assert codes == {"OKN", "OKE", "OKW", "KS", "NJ"}  # totals and circuit rows skipped
    rows = [r.finalize() for r in src.normalize(recs, raw)]
    ok_all = next(r for r in rows if r["fips"] == "40" and r["chapter"] == "all_nonbusiness")
    assert ok_all["filings"] == 118 + 79 + 196
    ok_13 = next(r for r in rows if r["fips"] == "40" and r["chapter"] == "13")
    assert ok_13["filings"] == 48 + 29 + 75
    assert ok_all["status"] == "pending_review" and ok_all["source_id"] == "uscourts-bankruptcy-f2"
    assert "OKN" in ok_all["notes"] if ok_all.get("notes") else True
    assert ok_all["period_start"] == "2026-04-01" and ok_all["period_end"] == "2026-06-30"


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
