"""Builds synthetic fixture documents that imitate the real layouts.

These are NOT real data. They exist so parse() has a deterministic test. When
a real document is archived from a networked machine, add it under fixtures/
with its sha256 and point a test at it.
"""
from pathlib import Path
import openpyxl

HERE = Path(__file__).parent / "fixtures"
HERE.mkdir(exist_ok=True)


def f2_xlsx(path: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "F-2"
    ws.append(["Table F-2. U.S. Bankruptcy Courts, Business and Nonbusiness Cases Commenced, by Chapter of the Bankruptcy Code, During the 3-Month Period Ending (synthetic fixture)"])
    ws.append([])
    ws.append(["Circuit and District", "Total Filings", "Business", None, None, None, "Nonbusiness", None, None, None])
    ws.append([None, None, "Total", "Chapter 7", "Chapter 11", "Chapter 13", "Total", "Chapter 7", "Chapter 11", "Chapter 13"])
    ws.append(["TOTAL", 9999, 100, 50, 20, 30, 9899, 6000, 9, 3890])
    ws.append(["10TH", 500, 10, 5, 2, 3, 490, 300, 1, 189])
    ws.append(["OKN", 120, 2, 1, 0, 1, 118, 70, 0, 48])
    ws.append(["OKE", 80, 1, 1, 0, 0, 79, 50, 0, 29])
    ws.append(["OKW", 200, 4, 2, 1, 1, 196, 120, 1, 75])
    ws.append(["KS", 150, 3, 1, 1, 1, 147, 90, 0, 57])
    ws.append(["3RD", 300, 5, 2, 1, 2, 295, 200, 0, 95])
    ws.append(["NJ", 300, 5, 2, 1, 2, 295, 200, 0, 95])
    wb.save(path)


def nj_pdf(path: Path) -> None:
    # Minimal text-only PDF written by hand (no reportlab dependency).
    lines = [
        "NEW JERSEY DIVISION OF GAMING ENFORCEMENT",
        "SPORTS WAGERING REVENUE (synthetic fixture, not real data)",
        "Licensee  Handle  Gross Revenue",
        "RETAIL (CASINO AND RACETRACK SPORTS POOL)",
        "Licensee A  $10,000,000  $900,000",
        "Licensee B  $5,000,000  ($100,000)",
        "TOTAL  $15,000,000  $800,000",
        "INTERNET SPORTS WAGERING",
        "Licensee A  $100,000,000  $8,000,000",
        "Licensee B  $50,000,000  $4,500,000",
        "TOTAL  $150,000,000  $12,500,000",
        "GRAND TOTAL  $165,000,000  $13,300,000",
        "Gross revenue before deductions for promotional gaming credits.",
    ]
    content_lines = ["BT", "/F1 11 Tf", "40 760 Td", "14 TL"]
    for ln in lines:
        esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content_lines.append(f"({esc}) Tj T*")
    content_lines.append("ET")
    stream = "\n".join(content_lines).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


if __name__ == "__main__":
    f2_xlsx(HERE / "uscourts_f2_synthetic.xlsx")
    nj_pdf(HERE / "nj_dge_synthetic.pdf")
    print("fixtures written")
