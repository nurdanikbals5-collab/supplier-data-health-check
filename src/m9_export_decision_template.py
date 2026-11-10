"""M9 (input) - supplier decision template for a sourcing decision.

Scenario: a new project needs electronic sensors. Which suppliers of this commodity should get the
request for quotation (RFQ) and the main volume? The template lists the 6 largest suppliers of the
commodity with facts only (KPIs from M2, payment terms from M6, open data issues from M1).
Scores, weighted score, ranking and the recommendation are added by hand in Excel.
Unit prices are not used: in the synthetic data they are random and would give a fake comparison.

Run:  ./.venv/bin/python src/m9_export_decision_template.py
Out:  excel/Supplier_Decision_Template.xlsx  (refuses to overwrite an existing file)
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "excel" / "Supplier_Decision_Template.xlsx"
COMMODITY = "Electronic sensors"
N = 6
NET_DAYS = {"NT30": 30, "NT45": 45, "NT60": 60, "SK14": 30}

CRITERIA = [
    # criterion, weight, based on, 5 points, 3 points, 1 point
    ("Quality", 0.35, "PPM (defective parts per million)", "PPM ≤ 150", "PPM ≤ 500", "PPM > 1,000"),
    ("Delivery", 0.35, "On-time delivery %", "OTD ≥ 95%", "OTD ≥ 85%", "OTD < 75%"),
    ("Payment terms", 0.15, "Net days of the payment term", "60 days", "30–45 days", "missing"),
    ("Master data", 0.15, "Open data-quality issues (M1)", "0 issues", "1 issue", "2 or more issues"),
]

HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # yellow = to be filled by hand


def header(ws, row=1):
    for c in ws[row]:
        if c.value is not None:
            c.fill, c.font = HEAD_FILL, HEAD_FONT
            c.alignment = Alignment(wrap_text=True, vertical="top")


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT.name} already exists - not overwriting your work.")
    spend = pd.read_excel(ROOT / "excel" / "Spend_Analysis.xlsx", "Suppliers")
    golden = pd.read_csv(ROOT / "data" / "output" / "golden_suppliers.csv", dtype=str)
    issues = pd.read_csv(ROOT / "data" / "output" / "dq_issues.csv", dtype=str)

    rec_to_golden = {rec.split(":", 1)[1]: g.golden_id
                     for g in golden.itertuples() for rec in g.source_records.split("; ")}
    issues["golden_id"] = issues.record_id.map(rec_to_golden)
    open_issues = issues.groupby("golden_id").size()

    s = spend[spend["Commodity"] == COMMODITY].sort_values("Spend (EUR)", ascending=False).head(N).copy()
    s["Net days"] = s["Payment term"].map(NET_DAYS)
    s["Data issues"] = s["Golden ID"].map(open_issues).fillna(0).astype(int)

    wb = Workbook()
    ws = wb.active
    ws.title = "Shortlist"
    cols = ["Golden ID", "Supplier", "Country", "Segment (M2)", "Spend (EUR)", "OTD %", "PPM", "Payment term",
            "Net days", "Data issues", "Quality score", "Delivery score", "Terms score", "Data score",
            "Weighted score", "Rank"]
    ws.append(cols)
    for _, r in s.iterrows():
        ws.append([r["Golden ID"], r["Supplier"], r["Country"], r["Segment (M2)"], round(r["Spend (EUR)"]),
                   r["OTD %"], r["PPM"], r["Payment term"], None if pd.isna(r["Net days"]) else int(r["Net days"]),
                   int(r["Data issues"])] + [None] * 6)
    n = len(s) + 1
    for row in ws.iter_rows(min_row=2, max_row=n):
        row[4].number_format = "#,##0"
        row[6].number_format = "#,##0"
        for c in row[10:]:
            c.fill = INPUT_FILL
    for col, w in zip("ABCDEFGHIJKLMNOP", [9, 22, 8, 28, 12, 7, 7, 10, 8, 8, 9, 9, 9, 9, 10, 6]):
        ws.column_dimensions[col].width = w
    header(ws)
    t = Table(displayName="tblShortlist", ref=f"A1:P{n}")
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(t)
    ws.freeze_panes = "C2"

    cr = wb.create_sheet("Criteria")
    cr.append(["Criterion", "Weight", "Based on", "5 points", "3 points", "1 point"])
    for c in CRITERIA:
        cr.append(list(c))
    cr.append(["Total", "=SUM(B2:B5)"])
    for r in range(2, 7):
        cr.cell(row=r, column=2).number_format = "0%"
    for col, w in zip("ABCDEF", [15, 8, 32, 14, 14, 18]):
        cr.column_dimensions[col].width = w
    header(cr)
    cr["A8"] = "Scores in between (4 and 2) are allowed. The thresholds are my own assumption for this simulation."
    cr["A9"] = "Unit prices are not compared: in the synthetic data they are random."
    cr["A8"].font = cr["A9"].font = Font(italic=True)

    de = wb.create_sheet("Decision")
    de.column_dimensions["A"].width = 26
    de.column_dimensions["B"].width = 80
    rows = [
        ("Supplier decision – " + COMMODITY, None),
        ("Decision needed", "Which suppliers get the RFQ and the main volume for a new sensor project?"),
        ("Scope", f"The {N} largest suppliers of {COMMODITY} by spend (Jan – Sep 2026, synthetic data)"),
        ("Criteria", "Quality 35%, delivery 35%, payment terms 15%, master data 15% (see Criteria sheet)"),
        ("Recommendation", None),
        ("Why", None),
        ("Risks / next steps", None),
        ("Prepared by", "Nurdan İkbal Söyler"),
    ]
    for i, (k, v) in enumerate(rows, start=1):
        de.cell(row=i, column=1, value=k).font = Font(bold=True, size=14 if i == 1 else 11,
                                                      color="1F4E78" if i == 1 else None)
        c = de.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if k in ("Recommendation", "Why", "Risks / next steps"):
            c.fill = INPUT_FILL
            de.row_dimensions[i].height = 45

    wb.save(OUT)
    print(f"{len(s)} suppliers of {COMMODITY} -> {OUT}")
    print(s[["Golden ID", "Supplier", "OTD %", "PPM", "Payment term", "Net days", "Data issues"]].to_string())


if __name__ == "__main__":
    main()
