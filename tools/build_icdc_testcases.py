#!/usr/bin/env python3
"""
Generate Playwright ICDC TC Excel files from Katalon groovy scripts.

For each study under Commons_Automation/Scripts/Canine_TestCases/Studies,
writes TC01–TC07 (whatever exists) to TestCases/ICDC/<study>/.

Program column is ICDC so Object Repository lookups are ICDC/...
Filter values come from Katalon InputFiles SQL when present, else checkbox XPath labels.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
KATALON = REPO_ROOT.parent / "Commons_Automation"
SCRIPTS = KATALON / "Scripts" / "Canine_TestCases" / "Studies"
INPUTS = KATALON / "InputFiles" / "ICDC"
OR_XLSX = REPO_ROOT / "ObjectRepository" / "ICDC_ObjectRepository.xlsx"
OUT = REPO_ROOT / "TestCases" / "ICDC"

SKIP_FOLDERS = {"StaticData", "UBC01"}  # UBC01 scripts are COTC021 copies
MAX_TC = 7

# Katalon folder typos → study code used in output path
FOLDER_ALIAS = {
    "COTCO21": "COTC021",
    "COTCO22": "COTC022",
    "PRICINCT01": "PRECINCT01",
    "PRICINCT02": "PRECINCT02",
    "TLC01": "TCL01",
    "NCATS-COP01": "NCATSCOP01",
}

HEADER = [
    "#", "Program", "Input Excel", "Max Pages", "Max Rows",
    "Action", "Page", "Object Name", "Params", "Filter", "Notes",
]

CLICK_RE = re.compile(
    r"TestRunner\.(?:clickTab|clickTabCanineStat)'\(\s*'([^']+)'\s*\)"
)
RUN_RE = re.compile(r"RunKatalon'\('([^']+\.xlsx)'\)")
TC_DIR_RE = re.compile(r"^(TC(\d+))_ICDC_", re.I)

FACET_FILTER_KEY = {
    "Study": "study",
    "StudyType": "study_type",
    "Biobank": "biobank",
    "Breed": "breed",
    "Diagnosis": "diagnosis",
    "PrimDiseaseSite": "primary_disease_site",
    "StageOfDisease": "stage_of_disease",
    "ResponseToTreatment": "response_to_treatment",
    "Sex": "sex",
    "NeuteredStatus": "neutered_status",
    "SampleSite": "sample_site",
    "SampleType": "sample_type",
    "SamplePathology": "sample_pathology",
    "FileAssociation": "file_association",
    "FileType": "file_type",
    "FileFormat": "file_format",
}

SQL_COL_TO_FILTER = {
    ("st", "clinical_study_designation"): "study",
    ("st", "clinical_study_type"): "study_type",
    ("dmg", "breed"): "breed",
    ("diag", "disease_term"): "diagnosis",
    ("diag", "primary_disease_site"): "primary_disease_site",
    ("diag", "stage_of_disease"): "stage_of_disease",
    ("diag", "best_response"): "response_to_treatment",
    ("reg", "registration_origin"): "biobank",
}

EXPANDER_HINTS = ("_Ddn", "Canine_Filter_Study", "Canine_Filter_StudyType", "FilterBy")


def _load_or() -> dict[str, str]:
    if not OR_XLSX.is_file():
        return {}
    wb = openpyxl.load_workbook(OR_XLSX, read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
        try:
            lk_i, xp_i = headers.index("Lookup Key"), headers.index("XPath")
        except ValueError:
            continue
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[lk_i] and row[xp_i]:
                out[str(row[lk_i]).strip()] = str(row[xp_i]).strip()
    wb.close()
    return out


def _xpath_label(xp: str) -> str | None:
    m = re.search(r"checkbox_(.+?)['\"]", xp or "")
    if not m:
        return None
    raw = re.sub(r"\s*\(\d+\)\s*$", "", m.group(1)).strip()
    if "_" not in raw:
        return raw
    return raw.split("_", 1)[1].strip()


def _parse_sql_filters(sql: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not sql:
        return out
    for m in re.finditer(
        r"(?:^|[\s(])([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\s*=\s*'((?:[^']|'')*)'",
        sql,
    ):
        alias, col, val = m.group(1), m.group(2), m.group(3).replace("''", "'")
        key = SQL_COL_TO_FILTER.get((alias, col))
        if key:
            out[key] = val
    # Cypher already converted
    m = re.search(r"clinical_study_designation:\s*'([^']+)'", sql)
    if m:
        out.setdefault("study", m.group(1))
    for cy_key, filt in (
        (r"s\.clinical_study_type\s*=\s*'([^']+)'", "study_type"),
        (r"demo\.breed\s*=\s*'([^']+)'", "breed"),
        (r"diag\.disease_term\s*=\s*'([^']+)'", "diagnosis"),
        (r"diag\.primary_disease_site\s*=\s*'([^']+)'", "primary_disease_site"),
        (r"diag\.stage_of_disease\s*=\s*'([^']+)'", "stage_of_disease"),
        (r"diag\.best_response\s*=\s*'([^']+)'", "response_to_treatment"),
        (r"registration_origin\s*=\s*'([^']+)'", "biobank"),
    ):
        m = re.search(cy_key, sql)
        if m:
            out.setdefault(filt, m.group(1))
    if "Not Applicable" in sql and "registration_origin" in sql:
        out.setdefault("biobank", "Not Applicable")
    return out


def _input_filters(xlsx_name: str | None) -> dict[str, str]:
    if not xlsx_name:
        return {}
    path = INPUTS / xlsx_name
    if not path.is_file():
        hits = list(INPUTS.rglob(xlsx_name))
        path = hits[0] if hits else None
    if not path or not path.is_file():
        return {}
    try:
        wb = openpyxl.load_workbook(path, data_only=True)
    except Exception:
        return {}
    ws = wb.active
    headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    # Prefer CasesTab / TabQuery / StatQuery
    tab_i = headers.index("TabName") if "TabName" in headers else None
    q_i = None
    for col in ("TabQuery", "StatQuery", "Query"):
        if col in headers:
            q_i = headers.index(col)
            break
    text = ""
    if tab_i is not None and q_i is not None:
        for row in ws.iter_rows(min_row=2, values_only=True):
            tab = str(row[tab_i] or "")
            q = str(row[q_i] or "")
            if tab in ("CasesTab", "StatQuery", "StatBar") and q:
                text = q
                break
            if not text and q:
                text = q
    elif q_i is not None:
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[q_i]:
                text = str(row[q_i])
                break
    wb.close()
    return _parse_sql_filters(text)


def _parse_groovy(script_dir: Path) -> tuple[str | None, list[str]]:
    clicks: list[str] = []
    xlsx = None
    for g in script_dir.glob("Script*.groovy"):
        text = g.read_text(encoding="utf-8", errors="replace")
        m = RUN_RE.search(text)
        if m:
            xlsx = m.group(1)
        clicks.extend(CLICK_RE.findall(text))
    return xlsx, clicks


def _lookup_parts(katalon_path: str) -> tuple[str, str]:
    """Canine/Filter/Study/UC01_Chkbx or ICDC/Filter/... → (Filter, Study/UC01_Chkbx)."""
    parts = katalon_path.split("/")
    if parts[0] == "Object Repository":
        parts = parts[1:]
    if parts and parts[0] in ("Canine", "ICDC"):
        parts = parts[1:]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return parts[0], "/".join(parts[1:])


def _is_checkbox(obj: str) -> bool:
    return obj.endswith("_Chkbx") or obj.endswith("Chkbx")


def _is_expander(obj: str) -> bool:
    return any(h in obj for h in EXPANDER_HINTS) and not _is_checkbox(obj)


def _write_tc(path: Path, input_excel: str, steps: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Steps"
    ws.append(HEADER)
    ws.append([None, "ICDC", input_excel, 2, None, None, None, None, None, None, None])
    for row in steps:
        ws.append(row)
    wb.save(path)


def _build_steps(
    clicks: list[str],
    filters: dict[str, str],
    or_map: dict[str, str],
) -> tuple[list[list], list[str]]:
    missing: list[str] = []
    steps: list[list] = []
    n = 1
    steps.append([n, None, None, None, None, "dismiss_popup", None, None, None, None, "Dismiss banner"])
    n += 1

    used_filter_keys: set[str] = set()
    for raw in clicks:
        if raw.endswith("Canine_PopUp_Continue_Btn"):
            continue
        page, obj = _lookup_parts(raw)
        lookup = f"ICDC/{page}/{obj}" if page else f"ICDC/{obj}"
        if lookup not in or_map and f"ICDC/{obj}" not in or_map:
            # Root objects (result tabs) are not step xpaths — skip tab clicks
            if "Results_" in obj or obj.endswith("_Tab"):
                continue
            missing.append(lookup)
        if not page:
            continue
        action = "js_click_and_wait" if _is_checkbox(obj) else "click_and_wait"
        flt = None
        note = obj
        if _is_checkbox(obj):
            folder = obj.split("/")[0] if "/" in obj else page
            key = FACET_FILTER_KEY.get(folder)
            if key and key not in used_filter_keys:
                # Checkbox XPath label is what the UI actually selects.
                # InputFiles SQL is fallback only (some Katalon workbooks are copies).
                val = _xpath_label(or_map.get(lookup, "") or or_map.get(f"ICDC/{obj}", ""))
                if not val:
                    val = filters.get(key)
                if val:
                    flt = f"{key}={val}"
                    used_filter_keys.add(key)
        steps.append([n, None, None, None, None, action, page, obj, None, flt, note])
        n += 1

    # Always pin study filter from SQL even if groovy checkbox label parse failed
    if "study" in filters and "study" not in used_filter_keys:
        # already clicked; just ensure Filter column exists on the study checkbox step
        for row in steps:
            obj = str(row[7] or "")
            if "Study/" in obj and _is_checkbox(obj) and not row[9]:
                row[9] = f"study={filters['study']}"
                used_filter_keys.add("study")
                break

    steps.append([n, None, None, None, None, "read_stat_bar", None, None, "ICDC", None, "Read stat bar"])
    n += 1
    for tab, note in (
        ("CasesTab", "Compare Cases"),
        ("SamplesTab", "Compare Samples"),
        ("CaseFilesTab", "Compare Case Files"),
        ("StudyFilesTab", "Compare Study Files"),
    ):
        steps.append([n, None, None, None, None, "multi_function", None, None, tab, None, note])
        n += 1
    return steps, missing


def main() -> int:
    if not SCRIPTS.is_dir():
        print(f"Katalon scripts not found: {SCRIPTS}", file=sys.stderr)
        return 1
    or_map = _load_or()
    if not or_map:
        print("Run tools/import_icdc_or.py first — ICDC OR is empty.", file=sys.stderr)
        return 1

    written = 0
    missing_all: list[str] = []
    studies = 0
    for study_dir in sorted(p for p in SCRIPTS.iterdir() if p.is_dir()):
        if study_dir.name in SKIP_FOLDERS:
            continue
        tcs = []
        for tc_dir in sorted(p for p in study_dir.iterdir() if p.is_dir()):
            m = TC_DIR_RE.match(tc_dir.name)
            if not m:
                continue
            num = int(m.group(2))
            if num < 1 or num > MAX_TC:
                continue
            tcs.append((num, tc_dir))
        if not tcs:
            continue
        studies += 1
        out_dir = OUT / FOLDER_ALIAS.get(study_dir.name, study_dir.name)
        for num, tc_dir in tcs:
            xlsx, clicks = _parse_groovy(tc_dir)
            filters = _input_filters(xlsx)
            steps, missing = _build_steps(clicks, filters, or_map)
            if missing:
                missing_all.extend(f"{tc_dir.name}: {lk}" for lk in missing)
            stem = tc_dir.name
            input_rel = f"InputFiles/ICDC/{xlsx or (stem + '.xlsx')}"
            _write_tc(out_dir / f"{stem}.xlsx", input_rel, steps)
            written += 1
            print(f"Wrote TestCases/ICDC/{study_dir.name}/{stem}.xlsx  filters={filters}")

    print(f"\n[build_icdc_testcases] {written} TCs across {studies} studies -> {OUT}")
    if missing_all:
        print(f"[build_icdc_testcases] {len(missing_all)} missing OR keys:")
        for line in missing_all:
            print(f"  {line}")
        return 1
    print("[build_icdc_testcases] All step object keys resolved in ICDC OR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
