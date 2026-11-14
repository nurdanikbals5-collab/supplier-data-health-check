"""M10 (input) - project management package for this portfolio project.

Three sheets:
  Milestones     finished modules with their real end date (date of the last commit of the module) and the
                 planned next modules with a planned end date and dependencies
  RAID_Log       risks, actions, issues and decisions of the project (real ones from the work so far)
  Status_Report  weekly status report (RAG) that reads from the two other sheets
Status, days late, risk scores, the RAG colours and the status report are added by hand in Excel.

Run:  ./.venv/bin/python src/m10_export_pm_template.py
Out:  excel/Project_Management.xlsx  (refuses to overwrite an existing file)
"""
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "excel" / "Project_Management.xlsx"

MILESTONES = [
    # ID, milestone, phase, depends on, planned end, actual end
    ("M1", "Data-quality checks and golden records", "1 Build", "", None, date(2026, 10, 5)),
    ("M2", "Supplier KPIs and segments", "1 Build", "M1", None, date(2026, 10, 5)),
    ("M3", "AI vs. human complaint labels", "1 Build", "", None, date(2026, 10, 5)),
    ("M4", "Ticket tracker with SLA (Excel)", "1 Build", "M1", None, date(2026, 10, 5)),
    ("M5", "AI use-case prioritization", "1 Build", "M3", None, date(2026, 10, 9)),
    ("P1", "BPMN as-is and to-be models", "1 Build", "M1, M4", None, date(2026, 10, 9)),
    ("M7", "Mapping to SAP S/4HANA", "1 Build", "M1", None, date(2026, 10, 16)),
    ("M6", "Spend analysis and payment terms", "1 Build", "M2", None, date(2026, 10, 25)),
    ("M9", "Supplier decision template", "1 Build", "M2, M6", None, date(2026, 11, 11)),
    ("M8", "Power BI ticket dashboard", "1 Build", "M4", None, date(2026, 11, 13)),
    ("P2", "BPMN modeling guide, to-be v1.1", "1 Build", "P1", None, date(2026, 11, 14)),
    ("M10", "Project management package", "2 Improve", "", date(2026, 11, 20), None),
    ("M11", "User feedback session and 2 changes", "2 Improve", "M8", date(2026, 11, 24), None),
    ("M12", "Management deck (PowerPoint)", "2 Improve", "M10, M11", date(2026, 11, 26), None),
    ("M13", "Jira Kanban board", "2 Improve", "M10", date(2026, 11, 26), None),
    ("M14", "Data model and SQL queries", "2 Improve", "M1", date(2026, 11, 30), None),
    ("M15", "Status e-mail with Power Automate (optional)", "2 Improve", "M10", date(2026, 12, 4), None),
]

RAID = [
    # ID, type, description, owner, action, due, status
    ("R1", "Risk", "Classmates have no time for the feedback session before 24 Nov, so M11 is late",
     "Nurdan", "Ask 3 classmates by 17 Nov; an online session is the backup", date(2026, 11, 17), "Open"),
    ("R2", "Risk", "Power Automate may not be part of the HFU Microsoft licence",
     "Nurdan", "Check in the HFU account; drop M15 if it is missing", date(2026, 11, 28), "Open"),
    ("R3", "Risk", "Application deadlines (20 Nov – 5 Dec) and exams take time away from the project",
     "Nurdan", "Weekly status check every Friday; move optional work (M15) first", date(2026, 11, 20), "Open"),
    ("R4", "Risk", "Results come from synthetic data and cannot be compared with a real company",
     "Nurdan", "Say it clearly in the README and in every application", None, "Open"),
    ("I1", "Issue", "Power BI Desktop does not run on a Mac",
     "Nurdan", "Used the Power BI service in the browser (HFU account)", date(2026, 11, 13), "Closed"),
    ("I2", "Issue", "'New measure' is not offered in the web report editor",
     "Nurdan", "Created the DAX measures in the semantic model (Editing)", date(2026, 11, 13), "Closed"),
    ("D1", "Decision", "Use only synthetic data, no real company data",
     "Nurdan", "", date(2026, 10, 5), "Closed"),
    ("D2", "Decision", "Python code is written by an AI coding assistant; Excel, Power BI and BPMN are built by me",
     "Nurdan", "", date(2026, 10, 5), "Closed"),
    ("D3", "Decision", "All process models follow the BPMN modeling guide",
     "Nurdan", "", date(2026, 11, 14), "Closed"),
]

HEAD_FILL = PatternFill("solid", fgColor="1F4E78")
HEAD_FONT = Font(bold=True, color="FFFFFF")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")  # yellow = to be filled by hand


def header(ws, row=1):
    for c in ws[row]:
        if c.value is not None:
            c.fill, c.font = HEAD_FILL, HEAD_FONT
            c.alignment = Alignment(wrap_text=True, vertical="top")


def add_table(ws, name, ref):
    t = Table(displayName=name, ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
    ws.add_table(t)


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT.name} already exists - not overwriting your work.")
    wb = Workbook()

    ms = wb.active
    ms.title = "Milestones"
    ms.append(["ID", "Milestone", "Phase", "Depends on", "Planned end", "Actual end", "Status", "Days late"])
    for m in MILESTONES:
        ms.append(list(m) + [None, None])
    n = len(MILESTONES) + 1
    for row in ms.iter_rows(min_row=2, max_row=n):
        row[4].number_format = row[5].number_format = "DD.MM.YYYY"
        row[6].fill = row[7].fill = INPUT_FILL
    for col, w in zip("ABCDEFGH", [6, 42, 10, 11, 12, 12, 9, 9]):
        ms.column_dimensions[col].width = w
    header(ms)
    add_table(ms, "tblMilestones", f"A1:H{n}")
    ms.freeze_panes = "C2"
    ms[f"A{n + 2}"] = "Actual end of phase 1 = date of the last commit of the module on GitHub."
    ms[f"A{n + 2}"].font = Font(italic=True)

    rl = wb.create_sheet("RAID_Log")
    rl.append(["ID", "Type", "Description", "Probability (1-3)", "Impact (1-3)", "Score", "Owner",
               "Action / mitigation", "Due", "Status"])
    for r in RAID:
        rid, typ, desc, owner, action, due, status = r
        rl.append([rid, typ, desc, None, None, None, owner, action, due, status])
    n = len(RAID) + 1
    for i, row in enumerate(rl.iter_rows(min_row=2, max_row=n)):
        row[8].number_format = "DD.MM.YYYY"
        for c in (row[2], row[7]):
            c.alignment = Alignment(wrap_text=True, vertical="top")
        if RAID[i][1] == "Risk":
            row[3].fill = row[4].fill = row[5].fill = INPUT_FILL
    for col, w in zip("ABCDEFGHIJ", [5, 9, 45, 11, 9, 7, 9, 42, 11, 8]):
        rl.column_dimensions[col].width = w
    header(rl)
    add_table(rl, "tblRAID", f"A1:J{n}")
    rl.freeze_panes = "C2"
    rl[f"A{n + 2}"] = "RAID = Risks, Actions, Issues, Decisions. Probability and impact only for risks."
    rl[f"A{n + 2}"].font = Font(italic=True)

    st = wb.create_sheet("Status_Report")
    st.column_dimensions["A"].width = 26
    st.column_dimensions["B"].width = 70
    rows = [
        ("Weekly status report", None),
        ("Project", "Supplier Data Health Check for an SAP S/4HANA Migration"),
        ("Week", None),
        ("Overall status (RAG)", None),
        ("Milestones done", None),
        ("Milestones open", None),
        ("Milestones late", None),
        ("Open risks", None),
        ("Done this week", None),
        ("Next week", None),
        ("Top risk and action", None),
        ("Decision needed", None),
        ("Prepared by", "Nurdan İkbal Söyler"),
    ]
    for i, (k, v) in enumerate(rows, start=1):
        st.cell(row=i, column=1, value=k).font = Font(bold=True, size=14 if i == 1 else 11,
                                                      color="1F4E78" if i == 1 else None)
        c = st.cell(row=i, column=2, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        if v is None and i > 1:
            c.fill = INPUT_FILL

    wb.save(OUT)
    print(f"{len(MILESTONES)} milestones, {len(RAID)} RAID entries -> {OUT}")


if __name__ == "__main__":
    main()
