"""
test_runner.py
Excel-driven test orchestrator. Reads TC Excel Steps sheet and executes each action.

Steps sheet columns:
  # | Program | Input Excel | Max Pages | Max Rows | Action | Page | Object Name | Params | Filter | Notes

Filter column: tester writes key=value on checkbox steps e.g. sex=Male, phs=phs001437
Runner collects all Filter values during execution, then uses them to:
  - Build Cypher WHERE clause via query_builder.py
  - Query Memgraph via memgraph_reader.py
  - Compare UI rows vs Memgraph rows on multi_function steps
  - Compare UI stat bar counts vs Memgraph StatBar query on read_stat_bar steps

If a Queries sheet exists in the TC Excel, its Cypher is used instead of the template (one-off override).
"""
import os
import openpyxl
from core.object_repo   import find_test_object
from core.browser       import launch_browser, navigate_to, close_browser
from core.actions       import dismiss_popup, click_element, click_and_wait
from core.stat_bar      import read_stat_bar, validate_stat_bar
from core.table_reader  import collect_all_rows, write_web_data
from core.excel_reader  import load_study_config, compare_sheets
from config.settings    import get_url, OUTPUT_FILES_ROOT

# ── Per-program result tab definitions ────────────────────────────────────────
PROGRAM_TABS = {
    "CDS": [
        {
            "tab_name":   "ParticipantsTab",
            "tab_btn":    "CDS/Data_page/CDSResults_Participants_Tab",
            "table_body": "CDS/Data_page/CDS_ParticipantsTable",
            "table_hdr":  "CDS/Data_page/CDS_ParticipantsTableHeader",
            "next_btn":   "CDS/Data_page/CDS_ParticipantsTabNextBtn",
        },
        {
            "tab_name":   "SamplesTab",
            "tab_btn":    "CDS/Data_page/CDSResults_Samples_Tab",
            "table_body": "CDS/Data_page/CDS_SamplesTable",
            "table_hdr":  "CDS/Data_page/CDS_SamplesTableHeader",
            "next_btn":   "CDS/Data_page/CDS_SamplesTabNextBtn",
        },
        {
            "tab_name":   "FilesTab",
            "tab_btn":    "CDS/Data_page/CDSResults_Files_Tab",
            "table_body": "CDS/Data_page/CDS_FilesTable",
            "table_hdr":  "CDS/Data_page/CDS_FilesTableHeader",
            "next_btn":   "CDS/Data_page/CDS_FilesTabNextBtn",
        },
    ],
}

PROGRAM_NAV_BTN = {
    "CDS":    "CDS/NavBar/CDS_Data-Btn",
    "Canine": "Canine/NavBar/Canine_Data-Btn",
    "CTDC":   "CTDC/NavBar/CTDC_Data-Btn",
}


def run_test_from_excel(testcase_excel: str):
    """
    Read a TC Excel (Steps sheet) and execute every step.
    Main entry point for single TC runs.

    Args:
        testcase_excel: path to TC Excel e.g. TestCases/TC01_CDS_phs001437.xlsx
    """
    wb = openpyxl.load_workbook(testcase_excel, data_only=True)
    sheet_names = wb.sheetnames

    # ── Read Steps sheet ──────────────────────────────────────────────────────
    # Row 1 = config values in cols B-E: Program | Input Excel | Max Pages | Max Rows
    # Row 2+ = steps: # | Program | Input Excel | Max Pages | Max Rows | Action | Page | Object Name | Params | Filter | Notes
    ws = wb["Steps"]
    rows = list(ws.iter_rows(min_row=1, values_only=True))

    cfg_row   = rows[0]
    program   = str(cfg_row[1]).strip()  if cfg_row[1] else ""
    input_excel = str(cfg_row[2]).strip() if cfg_row[2] else ""
    max_pages = int(cfg_row[3]) if cfg_row[3] else None
    max_rows  = int(cfg_row[4]) if cfg_row[4] else None

    steps = []
    for row in rows[1:]:
        if not row[5]:
            continue
        steps.append({
            "action":      str(row[5]).strip(),
            "page":        str(row[6]).strip() if row[6] else "",
            "object_name": str(row[7]).strip() if row[7] else "",
            "params":      str(row[8]).strip() if row[8] else "",
            "filter":      str(row[9]).strip() if row[9] else "",
            "notes":       str(row[10]).strip() if row[10] else "",
        })

    # ── Read Queries sheet if present (one-off Cypher override) ──────────────
    # Format: Tab | Cypher Query
    custom_queries = {}
    if "Queries" in sheet_names:
        ws_q = wb["Queries"]
        for qrow in ws_q.iter_rows(min_row=2, values_only=True):
            if qrow[0] and qrow[1]:
                custom_queries[str(qrow[0]).strip()] = str(qrow[1]).strip()
        print(f"[test_runner] Queries sheet found — custom queries for: {list(custom_queries.keys())}")

    wb.close()

    from config.settings import ENV
    url = get_url(program)
    print(f"\n{'='*60}")
    print(f"[test_runner] TC: {os.path.basename(testcase_excel)}")
    print(f"[test_runner] Program={program}  ENV={ENV}  URL={url}")
    print(f"[test_runner] Steps={len(steps)}  Custom queries={len(custom_queries)}")
    print(f"{'='*60}")

    # Resolve input excel path
    from config.settings import COMMONS_ROOT
    if input_excel and not os.path.isabs(input_excel):
        input_excel = os.path.join(COMMONS_ROOT, input_excel)

    playwright, browser, page = None, None, None
    stat_counts  = {}
    collected_filters: dict = {}   # {key: [value, ...]} — accumulated from Filter column
    result = {"passed": True, "tabs": {}, "errors": []}

    try:
        playwright, browser, page = launch_browser()
        navigate_to(page, url)

        for step in steps:
            action   = step["action"]
            page_name = step["page"]
            obj_name  = step["object_name"]
            params    = step["params"]
            flt       = step["filter"]

            def _xpath():
                if not page_name or not obj_name:
                    raise ValueError(f"Step '{action}' needs Page + Object Name but one is empty.")
                return find_test_object(f"{program}/{page_name}/{obj_name}")

            print(f"[test_runner] {action}"
                  f"{f' | {page_name}/{obj_name}' if obj_name else ''}"
                  f"{f' | params={params}' if params else ''}"
                  f"{f' | filter={flt}' if flt else ''}")

            # ── Collect filter value from this step ───────────────────────────
            if flt and "=" in flt:
                key, val = flt.split("=", 1)
                key = key.strip()
                val = val.strip()
                collected_filters.setdefault(key, [])
                if val not in collected_filters[key]:
                    collected_filters[key].append(val)

            # ── Execute action ────────────────────────────────────────────────
            if action == "dismiss_popup":
                dismiss_popup(page)

            elif action == "navigate_to":
                from config.settings import get_page_url
                navigate_to(page, get_page_url(program, page_name))

            elif action == "click_element":
                click_element(page, _xpath())

            elif action == "click_and_wait":
                click_and_wait(page, _xpath())

            elif action == "js_click_and_wait":
                from core.actions import js_click
                js_click(page, _xpath())
                page.wait_for_load_state("networkidle", timeout=15000)

            elif action == "js_click":
                from core.actions import js_click
                js_click(page, _xpath())

            elif action == "scroll_into_view":
                from core.actions import scroll_into_view
                scroll_into_view(page, _xpath())

            elif action == "wait_for_element_hidden":
                page.locator(f"xpath={_xpath()}").wait_for(state="hidden")

            elif action in ("is_element_visible", "is_element_enabled"):
                loc = page.locator(f"xpath={_xpath()}")
                val = loc.is_enabled() if action == "is_element_enabled" else loc.is_visible()
                print(f"[test_runner]   => {val}")

            elif action == "clear_input":
                page.locator(f"xpath={_xpath()}").clear()

            elif action == "find_filter_by_search":
                from core.actions import find_filter_by_search
                find_filter_by_search(page, _xpath(), params)

            elif action == "read_stat_bar":
                # Read UI stat bar
                stat_counts = read_stat_bar(page, params or program)
                print(f"[test_runner]   UI stat bar: {stat_counts}")

                # Compare with Memgraph StatBar query if filters collected
                if collected_filters:
                    _compare_stat_bar(program, collected_filters, stat_counts, custom_queries)

            elif action == "multi_function":
                tab_name = params
                tab_def  = next((t for t in PROGRAM_TABS.get(program, [])
                                  if t["tab_name"] == tab_name), None)
                if not tab_def:
                    print(f"[test_runner] Warning: no tab definition for '{tab_name}' — skipping")
                    continue

                click_element(page, find_test_object(tab_def["tab_btn"]))

                tab_result = _run_multi_function(
                    page=page,
                    program=program,
                    tab_def=tab_def,
                    stat_counts=stat_counts,
                    filters=collected_filters,
                    custom_query=custom_queries.get(tab_name),
                    max_pages=max_pages,
                    max_rows=max_rows,
                )
                result["tabs"][tab_name] = tab_result
                if not tab_result["passed"]:
                    result["passed"] = False

            elif action == "login":
                parts = params.split(",")
                _login(page, parts[0].strip(), parts[1].strip() if len(parts) > 1 else "")

            elif action == "verify_static_page":
                ok = _verify_static(page, program, [params])
                if not ok:
                    result["passed"] = False

            else:
                print(f"[test_runner] Warning: unknown action '{action}' — skipping")

    except Exception as e:
        result["passed"] = False
        result["errors"].append(str(e))
        print(f"[test_runner] ERROR: {e}")
        raise
    finally:
        if browser and playwright:
            close_browser(playwright, browser)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"\n{'='*60}")
    print(f"[test_runner] Result: {status}")
    for tab_name, tab_res in result["tabs"].items():
        tab_status = "PASS" if tab_res["passed"] else "FAIL"
        mm = len(tab_res.get("mismatches", []))
        print(f"  {tab_name}: {tab_status}{f'  ({mm} mismatches)' if mm else ''}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  ERROR: {e}")
    print(f"{'='*60}\n")
    return result


def _run_multi_function(page, program: str, tab_def: dict, stat_counts: dict,
                         filters: dict, custom_query: str = None,
                         max_pages: int = None, max_rows: int = None) -> dict:
    """
    Paginate UI result tab, query Memgraph with same filters, compare row counts.

    Returns:
        dict: { passed, mismatches, ui_count, db_count }
    """
    from core.query_builder  import build_query
    from core.memgraph_reader import query_memgraph

    tab_name  = tab_def["tab_name"]
    stat_key  = _tab_to_stat_key(tab_name)
    stat_value = stat_counts.get(stat_key, 0)

    if stat_value == 0:
        print(f"[test_runner]   Skipping '{tab_name}' — stat bar count is 0")
        return {"passed": True, "mismatches": [], "ui_count": 0, "db_count": 0, "skipped": True}

    # ── Collect UI rows ───────────────────────────────────────────────────────
    ui_rows = collect_all_rows(
        page             = page,
        table_body_xpath = find_test_object(tab_def["table_body"]) + "//tbody//tr",
        next_btn_xpath   = find_test_object(tab_def["next_btn"]),
        header_xpath     = find_test_object(tab_def["table_hdr"]) + "//th",
        expected_total   = stat_value,
        max_pages        = max_pages,
        max_rows         = max_rows,
    )
    ui_count = len(ui_rows)
    print(f"[test_runner]   UI rows collected: {ui_count}")

    # ── Query Memgraph ────────────────────────────────────────────────────────
    try:
        cypher   = build_query(program, tab_name, filters, custom_query=custom_query)
        db_rows  = query_memgraph(cypher)
        db_count = len(db_rows)
        print(f"[test_runner]   Memgraph rows returned: {db_count}")
    except Exception as e:
        print(f"[test_runner]   Memgraph query failed: {e}")
        return {"passed": False, "mismatches": [str(e)], "ui_count": ui_count, "db_count": 0}

    # ── Compare row counts ────────────────────────────────────────────────────
    # Primary check: counts must match
    count_match = (ui_count == db_count)
    mismatches  = []
    if not count_match:
        mismatches.append(
            f"Row count mismatch: UI={ui_count} Memgraph={db_count}"
        )

    passed = count_match
    status = "PASS" if passed else "FAIL"
    print(f"[test_runner]   {tab_name}: {status} | UI={ui_count} DB={db_count}")
    if mismatches:
        for m in mismatches:
            print(f"[test_runner]     MISMATCH: {m}")

    return {
        "passed":    passed,
        "mismatches": mismatches,
        "ui_count":  ui_count,
        "db_count":  db_count,
    }


def _compare_stat_bar(program: str, filters: dict, ui_counts: dict, custom_queries: dict):
    """Query Memgraph StatBar and compare counts against UI stat bar."""
    from core.query_builder  import build_query
    from core.memgraph_reader import query_memgraph

    try:
        custom = custom_queries.get("StatBar")
        cypher = build_query(program, "StatBar", filters, custom_query=custom)
        rows   = query_memgraph(cypher)
        if not rows:
            print("[test_runner]   StatBar: no rows returned from Memgraph")
            return
        db = rows[0]
        print(f"[test_runner]   Memgraph stat bar: {dict(db)}")

        # Compare each count
        mapping = {
            "Studies":      "studies",
            "Participants": "participants",
            "Samples":      "samples",
            "Files":        "files",
        }
        for db_key, ui_key in mapping.items():
            db_val = db.get(db_key)
            ui_val = ui_counts.get(ui_key)
            if db_val is not None and ui_val is not None:
                match = "✓" if db_val == ui_val else "✗ MISMATCH"
                print(f"[test_runner]   {db_key}: UI={ui_val} DB={db_val} {match}")
    except Exception as e:
        print(f"[test_runner]   StatBar Memgraph query failed: {e}")


def _tab_to_stat_key(tab_name: str) -> str:
    mapping = {
        "ParticipantsTab": "participants",
        "SamplesTab":      "samples",
        "FilesTab":        "files",
        "StudiesTab":      "studies",
    }
    return mapping.get(tab_name, tab_name.lower().replace("tab", "").strip())


def _login(page, email: str, password: str):
    btn = page.locator("xpath=//button[contains(text(),'Sign In') or contains(text(),'Login')]").first
    btn.wait_for(state="visible")
    btn.click()
    page.locator("xpath=//input[@type='email' or @name='email']").first.fill(email)
    page.keyboard.press("Enter")
    page.locator("xpath=//input[@type='password']").first.fill(password)
    page.keyboard.press("Enter")
    page.wait_for_load_state("networkidle")


def _verify_static(page, program: str, expected_texts: list) -> bool:
    content = page.content()
    missing = [t for t in expected_texts if t not in content]
    if missing:
        print(f"[test_runner] Static page FAIL — missing: {missing}")
        return False
    print(f"[test_runner] Static page PASS")
    return True
