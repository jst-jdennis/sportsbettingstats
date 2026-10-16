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
    ws.append(["Predominant Nature of Debt"])
    ws.append(["Circuit and District", "Total", None, None, None, None, "Business", None, None, None, None, "Nonbusiness", None, None, None])
    ws.append([None, "All Chapters", "Chapter 7", "Chapter 11", "Chapter 13", "Other Chapters", "All Chapters", "Chapter 7", "Chapter 11", "Chapter 13", "Other Chapters", "All Chapters", "Chapter 7", "Chapter 11", "Chapter 13"])
    ws.append(["Total", 9999, 6100, 29, 3920, 0, 100, 50, 20, 30, 0, 9899, 6000, 9, 3890])
    ws.append(["10th", 500, 310, 3, 192, 0, 10, 5, 2, 3, 0, 490, 300, 1, 189])
    ws.append(["OK,N", 120, 71, 0, 49, 0, 2, 1, 0, 1, 0, 118, 70, 0, 48])
    ws.append(["OK,E", 80, 51, 0, 29, 0, 1, 1, 0, 0, 0, 79, 50, 0, 29])
    ws.append(["OK,W", 200, 122, 2, 76, 0, 4, 2, 1, 1, 0, 196, 120, 1, 75])
    ws.append(["KS", 150, 91, 1, 58, 0, 3, 1, 1, 1, 0, 147, 90, 0, 57])
    ws.append(["AR", 100, 60, 1, 39, 0, 2, 1, 0, 1, 0, 98, 59, 1, 38])
    ws.append(["3rd", 300, 202, 1, 97, 0, 5, 2, 1, 2, 0, 295, 200, 0, 95])
    ws.append(["NJ", 300, 202, 1, 97, 0, 5, 2, 1, 2, 0, 295, 200, 0, 95])
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


def nj_tax_returns_pdf(path: Path) -> None:
    def form(name, r_ytd, r_prior, r_gross, r_promo, r_tax, o_ytd, o_prior, o_gross, o_tax):
        return [
            name, "MONTHLY SPORTS WAGERING TAX RETURN", "FOR THE MONTH OF AUGUST 2026", "SPORTSBOOK LOUNGE",
            "Line Description Gross Revenue/Tax", "(a) (b) (c)",
            f"1 Year-to-Date Sportsbook Lounge Gross Revenue $ {r_ytd}",
            f"2 Less: Prior Month's Year-to-Date Sportsbook Lounge Gross Revenue {r_prior}",
            f"3 Monthly Sportsbook Lounge Gross Revenue {r_gross}",
            "4 Monthly Adjustments -",
            f"5 Monthly Sports Wagering Promotional Gaming Credit Deduction {r_promo}",
            f"6 Monthly Taxable Sportsbook Lounge Gross Revenue {r_gross}",
            f"7 Monthly Tax on Sportsbook Lounge Gross Revenue {r_tax}",
            "8 Less: Sportsbook Lounge Loss Carryforward Applied (if applicable) -",
            f"9 Total Sportsbook Lounge Tax Payment for this Month {r_tax}",
            "ONLINE SPORTSBOOK", "Line Description Gross Revenue/Tax", "(a) (b) (c)",
            f"14 Year-to-Date Online Sportsbook Gross Revenue $ {o_ytd}",
            f"15 Less: Prior Month's Year-to-Date Online Sportsbook Gross Revenue {o_prior}",
            f"16 Monthly Online Sportsbook Gross Revenue {o_gross}",
            "17 Monthly Adjustments -",
            f"18 Monthly Taxable Online Sportsbook Gross Revenue {o_gross}",
            f"19 Monthly Tax on Online Sportsbook Gross Revenue {o_tax}",
            "20 Less: Online Sportsbook Loss Carryforward Applied (if applicable) -",
            f"21 Total Online Sportsbook Tax Payment for this Month {o_tax}",
            "FORM MAY NOT FOOT DUE TO ROUNDING", "02/26 DGE-107",
        ]
    skin = ["LICENSEE A", "ONLINE SPORTSBOOK SKIN DETAIL REPORT", "FOR THE MONTH OF AUGUST 2026", "ONLINE SPORTSBOOK DETAIL BY SKIN",
            "16 Monthly Online Sportsbook Gross Revenue 4,000,000 1,000,000 5,000,000", "02/26 DGE-107 Skin Detail"]
    pages = [form("LICENSEE A", "74,088", "70,420", "3,668", "-", "312", "58,638,116", "53,560,337", "5,000,000", "987,500"), skin,
             form("LICENSEE B", "1,000,000", "900,000", "100,000", "(2,000)", "8,330", "20,000,000", "17,000,000", "3,000,000", "592,500")]
    _multi_page_pdf(path, pages)


def _multi_page_pdf(path: Path, pages: list[list[str]]) -> None:
    objs: list[bytes] = []
    # 1 catalog, 2 pages, 3 font, then per page: page obj + content obj
    kids = []
    page_objs = []
    n = 4
    for lines in pages:
        content_lines = ["BT", "/F1 10 Tf", "40 760 Td", "13 TL"]
        for ln in lines:
            esc = ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content_lines.append(f"({esc}) Tj T*")
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1")
        page_objs.append((n, n + 1, stream))
        kids.append(f"{n} 0 R")
        n += 2
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for pn, cn, stream in page_objs:
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {cn} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
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
    nj_tax_returns_pdf(HERE / "nj_dge107_synthetic.pdf")
    print("fixtures written")
