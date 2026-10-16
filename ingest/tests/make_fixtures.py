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
    ws.append(["AR \u00b2", 100, 60, 1, 39, 0, 2, 1, 0, 1, 0, 98, 59, 1, 38])  # footnote superscript as in the published sheet
    ws.append(["3rd", 300, 202, 1, 97, 0, 5, 2, 1, 2, 0, 295, 200, 0, 95])
    ws.append(["NJ", 300, 202, 1, 97, 0, 5, 2, 1, 2, 0, 295, 200, 0, 95])
    ws.append(["     2nd", 7000, 5000, 200, 1800, 0, 600, 300, 250, 50, 0, 6400, 4700, 20, 1680])
    ws.append(["ND", 268, 228, 3, 36, 1, 14, 10, 3, 0, 1, 254, 218, 0, 36])
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
            "26 Total Sports Wagering Tax Payment (sum lines 9 and 21) $ 1,000",
            "FORM MAY NOT FOOT DUE TO ROUNDING", "02/26 DGE-107",
        ]
    skin = ["LICENSEE A", "ONLINE SPORTSBOOK SKIN DETAIL REPORT", "FOR THE MONTH OF AUGUST 2026", "ONLINE SPORTSBOOK DETAIL BY SKIN",
            "16 Monthly Online Sportsbook Gross Revenue 4,000,000 1,000,000 5,000,000", "02/26 DGE-107 Skin Detail"]
    pages = [form("LICENSEE A", "74,088", "70,420", "3,668", "-", "312", "58,638,116", "53,638,116", "5,000,000", "987,500"), skin,
             form("LICENSEE B", "1,000,000", "900,000", "100,000", "(2,000)", "8,330", "20,000,000", "17,000,000", "3,000,000", "592,500")]
    _multi_page_pdf(path, pages)


def nj_tax_returns_2018_pdf(path: Path) -> None:
    """Family A (6/18 form): 16 lines, monthly gross on lines 1 and 8, tax on 7 and 14, comma after the month."""
    def form(name, r_gross, r_tax, o_gross, o_tax, month="SEPTEMBER, 2018"):
        return [
            name, "MONTHLY SPORTS WAGERING TAX RETURN", f"FOR THE MONTH OF {month}", "SPORTS WAGERING - CASINO OR RACETRACK",
            f"1 Current Month Sports Wagering Gross Revenue $ {r_gross}",
            "2 Year-to-Date Sports Wagering Gross Revenue 679,631",
            "3 Adjustments to Sports Wagering Gross Revenue -",
            "4 Year-to-Date Sports Wagering Taxable Revenue 679,631",
            "5 Year-to-Date 8.5% Tax on Sports Wagering 57,769",
            "6 Less: Total 8.5% Tax on Sports Wagering in Prior Months 24,275",
            f"7 Total Sports Wagering Tax Required for this Month $ {r_tax}",
            "SPORTS WAGERING - INTERNET",
            f"8 Current Month Internet Sports Wagering Gross Revenue $ {o_gross}",
            "9 Year-to-Date Internet Sports Wagering Gross Revenue 106,463",
            "10 Adjustments to Internet Sports Wagering Gross Revenue -",
            "11 Year-to-Date Internet Sports Wagering Taxable Revenue 106,463",
            "12 Year-to-Date 13% Tax on Internet Sports Wagering 13,840",
            "13 Less: Total 13% Tax on Internet Sports Wagering in Prior Month -",
            f"14 Total Internet Sports Wagering Tax Required for this Month $ {o_tax}",
            "15 Total Sports Wagering Tax for the Month (add lines 7 and 14) $ 47,334",
            "16 Sports Wagering Promotional Gaming Credits for the month $ -",
            "WEB SITES REPORTING SPORTS WAGERING GROSS REVENUE:", "6/18 DGE-107",
        ]
    pages = [form("LICENSEE A", "394,046", "33,494", "106,463", "13,840"),
             form("LICENSEE B", "(40,848)", "1,611", "223,339", "29,035", month="SEPTMEBER, 2018")]  # misspelt month tolerated
    _multi_page_pdf(path, pages)


def nj_tax_returns_2019_pdf(path: Path) -> None:
    """Family B (6/19 form): 26 lines; amounts with split digits as pdfplumber sometimes renders them."""
    def form(name, r_ytd, r_prior, r_gross, r_tax, o_ytd, o_prior, o_gross, o_tax):
        return [
            name, "MONTHLY SPORTS WAGERING TAX RETURN", "FOR THE MONTH OF DECEMBER, 2019", "SPORTS WAGERING - CASINO OR RACETRACK",
            f"1 Year-to-Date Retail Sports Wagering Gross Revenue $ {r_ytd}",
            f"2 Less: Last Month's Year-to-Date Retail Sports Wagering Gross Revenue {r_prior}",
            f"3 Monthly Retail Sports Wagering Gross Revenue $ {r_gross}",
            "4 Monthly Adjustments -",
            f"5 Monthly Taxable Retail Sports Wagering Gross Revenue {r_gross}",
            f"6 Monthly 8.5% Tax on Retail Sports Wagering Gross Revenue {r_tax}",
            "7 Less: Retail Sports Wagering Loss Carryforward Applied (if applicable) -",
            f"8 Total Retail Sports Wagering Tax Payment for this Month $ {r_tax}",
            "SPORTS WAGERING - INTERNET",
            f"13 Year-to-Date Internet Sports Wagering Gross Revenue $ {o_ytd}",
            f"14 Less: Last Month's Year-to-Date Internet Sports Wagering Gross Revenue {o_prior}",
            f"15 Monthly Internet Sports Wagering Gross Revenue $ {o_gross}",
            "16 Monthly Adjustments -",
            f"17 Monthly Taxable Internet Sports Wagering Gross Revenue {o_gross}",
            f"18 Monthly 13% Tax on Internet Sports Wagering Gross Revenue {o_tax}",
            "19 Less: Internet Sports Wagering Loss Applied from Prior Month (if applicable) -",
            f"20 Total Internet Sports Wagering Tax Payment for this Month $ {o_tax}",
            "25 Total Sports Wagering Tax Payment (sum lines 8 and 20) $ 9,217",
            "26 Sports Wagering Promotional Gaming Credits for the month $ -",
            "WEB SITES REPORTING SPORTS WAGERING GROSS REVENUE:", "6/19 DGE-107",
        ]
    pages = [form("LICENSEE A", "2,038,707", "1,930,270", "108,437", "9,217", "-", "-", "-", "-"),
             form("LICENSEE B", "-", "-", "-", "-", "1 ,356,345", "1 ,329,593", "2 6,752", "3 ,478")]
    _multi_page_pdf(path, pages)


def nj_tax_returns_misfoot_pdf(path: Path) -> None:
    """Family B form whose year-to-date lines do not foot to the monthly line (a misread amount)."""
    pages = [["LICENSEE A", "MONTHLY SPORTS WAGERING TAX RETURN", "FOR THE MONTH OF DECEMBER, 2019", "SPORTS WAGERING - CASINO OR RACETRACK",
              "1 Year-to-Date Retail Sports Wagering Gross Revenue $ 2,038,707", "2 Less: Last Month's Year-to-Date Retail Sports Wagering Gross Revenue 1,930,270",
              "3 Monthly Retail Sports Wagering Gross Revenue $ 8,437", "5 Monthly Taxable Retail Sports Wagering Gross Revenue 8,437",
              "6 Monthly 8.5% Tax on Retail Sports Wagering Gross Revenue 717", "SPORTS WAGERING - INTERNET",
              "13 Year-to-Date Internet Sports Wagering Gross Revenue $ -", "14 Less: Last Month's Year-to-Date Internet Sports Wagering Gross Revenue -",
              "15 Monthly Internet Sports Wagering Gross Revenue $ -", "17 Monthly Taxable Internet Sports Wagering Gross Revenue -", "18 Monthly 13% Tax on Internet Sports Wagering Gross Revenue -",
              "25 Total Sports Wagering Tax Payment (sum lines 8 and 20) $ 717", "6/19 DGE-107"]]
    _multi_page_pdf(path, pages)


def f2_pdf_2022(path: Path) -> None:
    pages = [["Table F-2 Quarterly.", "U.S. Bankruptcy Courts - Business and Nonbusiness Cases Commenced, by Chapter of the Bankruptcy Code,",
              "During the Three-Month Period Ending December 31, 2022, Based on Data Current as of December 31, 2022",
              "Predominant Nature of Debt", "Business Nonbusiness", "Circuit Total Total Total Total Total",
              "and All Chapter Chapter Chapter Other All Chapter Chapter Chapter Other All Chapter Chapter Chapter",
              "District Chapters 7 11 13 Chapters ¹ Chapters 7 11 13 Chapters ¹ Chapters 7 11 13",
              "Total 95,416 53,195 1,227 40,939 55 3,519 2,031 1,147 286 55 91,897 51,164 80 40,653",
              "2nd 4,595 2,888 149 1,542 16 322 155 136 15 16 4,273 2,733 13 1,527",
              "NJ 2,557 1,397 89 1,071 0 142 48 86 8 0 2,415 1,349 3 1,063",
              "VI 2 2 0 0 0 2 2 0 0 0 0 - - -",
              "AR ² 1,408 517 4 887 0 19 9 2 8 0 1,389 508 2 879",
              "ND 99 88 0 11 0 2 1 0 1 0 97 87 0 10",
              "OK,N 319 284 0 35 0 15 14 0 1 0 304 270 0 34", "Page 1 of 4"]]
    _multi_page_pdf(path, pages)


def f2_pdf_2018(path: Path) -> None:
    pages = [["Table F-2.", "U.S. Bankruptcy Courts - Business and Nonbusiness Cases Commenced, by Chapter of the Bankruptcy Code,",
              "During the Three-Month Period Ending March 31, 2018, Based on Data Current as of March 31, 2018",
              "Predominant Nature of Debt ¹", "Circuit Total Total Total Total Business Filings Nonbusiness Filings",
              "and Total Chapter Chapter Chapter Chapter Chapter Chapter Chapter Chapter Chapter Chapter Chapter",
              "District Filings 7 11 12 13 Total 7 11 12 13 Total 7 11 13 S", "0",
              "TOTAL 192,079 118,877 1,998 116 71,068 5,669 3,355 1,718 116 460 186,410 115,522 280 70,608",
              "2ND 9,967 6,679 234 7 3,035 502 250 208 7 25 9,465 6,429 26 3,010",
              "NJ 6,635 4,052 77 0 2,506 150 85 48 0 17 6,485 3,967 29 2,4890",
              "AR, E 1,879 921 4 1 953 22 14 3 1 4 1,857 907 1 9490",
              "AR, W 880 465 3 1 411 24 14 1 1 8 856 451 2 4030",
              "ND 180 165 1 0 14 7 4 0 0 3 173 161 1 110",
              "OK, N 644 577 0 0 67 12 12 0 0 0 632 565 0 671",
              "\u00b9 The nature of debt is business if the debtor is a corporation or partnership.",
              "Note: These figures include the following cases not reflected elsewhere:", "Chapter 9 Chapter 15", "MO, E 1085 NY, S 12023"]]
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
    nj_tax_returns_2018_pdf(HERE / "nj_dge107_2018_synthetic.pdf")
    nj_tax_returns_2019_pdf(HERE / "nj_dge107_2019_synthetic.pdf")
    nj_tax_returns_misfoot_pdf(HERE / "nj_dge107_misfoot_synthetic.pdf")
    f2_pdf_2022(HERE / "uscourts_f2_2022_synthetic.pdf")
    f2_pdf_2018(HERE / "uscourts_f2_2018_synthetic.pdf")
    print("fixtures written")
