#!/usr/bin/env python3
"""
Generate C3DC Playwright TC Excel files (Steps sheet) from Katalon-style scenarios.
"""
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "TestCases" / "C3DC"

HEADER = ["#", "Program", "Input Excel", "Max Pages", "Max Rows",
          "Action", "Page", "Object Name", "Params", "Filter", "Notes"]

# (filename_stem, phs, sex_at_birth, sex_chkbx_object_suffix)
SCENARIOS = [
    (
        "TC01_C3DC_phs000463_SexAtBirth-Female",
        "phs000463",
        "Female",
        "Female-Chkbx",
    ),
    (
        "TC01_C3DC_phs002431_SexAtBirth-Male",
        "phs002431",
        "Male",
        "Male-Chkbx",
    ),
    (
        "TC01_C3DC_phs000720_SexAtBirth-Unknown",
        "phs000720",
        "Unknown",
        "Unknown-Chkbx",
    ),
]


def _steps(phs: str, sex: str, sex_chkbx: str) -> list[list]:
    # UI order matches Commons_Automation Scripts/C3DC_TestCases/.../Script*.groovy
    return [
        [1, None, None, None, None, "dismiss_popup", None, None, None, None, "Dismiss banner"],
        [2, None, None, None, None, "click_and_wait", "Navbar", "Explore-Tab", None, None, "Open Explore Participants"],
        [3, None, None, None, None, "click_and_wait", "Filters", "Study/Study_Facet", None, None, "Open Study filter panel"],
        [4, None, None, None, None, "click_and_wait", "Filters", "Study/dbGaP_Accession/dbGaP_Accession-Ddn", None, None, "Open dbGaP Accession list"],
        [5, None, None, None, None, "js_click_and_wait", "Filters", f"Study/dbGaP_Accession/{phs}-Chkbx", None, f"phs={phs}", f"Select {phs}"],
        [6, None, None, None, None, "click_and_wait", "Filters", "Demographics/Demographics_Facet", None, None, "Open Demographics filter panel"],
        [7, None, None, None, None, "click_and_wait", "Filters", "Demographics/SexAtBirth/SexAtBirth-Ddn", None, None, "Open Sex at Birth list"],
        [8, None, None, None, None, "js_click_and_wait", "Filters", f"Demographics/SexAtBirth/{sex_chkbx}", None, f"sex_at_birth={sex}", f"Select {sex}"],
        [9, None, None, None, None, "read_stat_bar", None, None, "C3DC", None, "Read stat bar"],
        # Result tabs — same order as Commons_Automation InputFiles C3DC TabName rows
        [10, None, None, None, None, "multi_function", None, None, "ParticipantsTab", None, "Compare Participants"],
        [11, None, None, None, None, "multi_function", None, None, "StudiesTab", None, "Compare Studies"],
        [12, None, None, None, None, "multi_function", None, None, "DiagnosisTab", None, "Compare Diagnosis"],
        [13, None, None, None, None, "multi_function", None, None, "GeneticAnalysisTab", None, "Compare Genetic Analysis"],
        [14, None, None, None, None, "multi_function", None, None, "TreatmentTab", None, "Compare Treatments"],
        [15, None, None, None, None, "multi_function", None, None, "TreatmentRespTab", None, "Compare Treatment Response"],
        [16, None, None, None, None, "multi_function", None, None, "SurvivalTab", None, "Compare Survival"],
        [17, None, None, None, None, "multi_function", None, None, "SamplesTab", None, "Compare Samples"],
        [18, None, None, None, None, "multi_function", None, None, "FilesTab", None, "Compare Files (Explore Files)"],
    ]


def write_tc(stem: str, phs: str, sex: str, sex_chkbx: str, input_excel: str):
    path = OUT / f"{stem}.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Steps"
    ws.append(HEADER)
    ws.append([None, "C3DC", input_excel, 2, None, None, None, None, None, None, None])
    for row in _steps(phs, sex, sex_chkbx):
        ws.append(row)
    wb.save(path)
    print(f"Wrote {path}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for stem, phs, sex, chkbx in SCENARIOS:
        inp = f"InputFiles/C3DC/{stem}.xlsx"
        write_tc(stem, phs, sex, chkbx, inp)


if __name__ == "__main__":
    main()
