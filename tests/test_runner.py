"""
test_runner.py
Master test orchestrator — equivalent of a Katalon test script.
Reads the input Excel (study config), drives the browser, runs the full test.

Katalon flow replicated exactly:
  1. load_study_config(input_excel)            ← RunKatalon() + ReadExcel.initialLoad()
  2. launch_browser() + navigate_to(url)       ← WebUI.openBrowser()
  3. dismiss_popup()                            ← clickTab('Bento/Banner/Bento_Warning_Continue_Btn')
  4. click_and_wait(nav_btn)                   ← clickTabCDSStat('CDS/NavBar/CDS_Data-Btn')
  5. apply_filters(filters)                    ← clickTabCDSStat(Ddn) + clickTabCDSStat(Chkbx)
  6. read_stat_bar(program)                    ← readStatBarCDS(...)
  7. For each result tab:
       click_element(tab_btn)                  ← clickTab('CDS/Data_page/CDSResults_..._Tab')
       multi_function(...)                     ← multiFunction(...)
         → collect_all_rows()                  ← ReadCasesTableKatalon()
         → write_web_data()                    ← Utils.writeToExcel()
         → run_result_tabs()                   ← PythonReader.readFile('ResultTabs.py')
         → run_statbar_script()                ← PythonReader.readFile('Statbar.py')
         → compare_sheets()                    ← Utils.compareSheets()
         → validate_stat_bar()                 ← validateStatBar()
  8. close_browser()                           ← WebUI.closeBrowser()
"""
import os
import openpyxl
from core.object_repo   import find_test_object
from core.browser       import launch_browser, navigate_to, close_browser
from core.actions       import dismiss_popup, click_element, click_and_wait
from core.stat_bar      import read_stat_bar, validate_stat_bar
from core.table_reader  import collect_all_rows, write_web_data
from core.python_runner import run_result_tabs, run_statbar as run_statbar_script
from core.excel_reader  import load_study_config, compare_sheets
from config.settings    import get_url, OUTPUT_FILES_ROOT

# ── Per-program result tab definitions ────────────────────────────────────────
# Maps program → list of tabs, each with Object Repo keys for tab btn / table / header / next btn
# and the sheet name in the output Excel.
PROGRAM_TABS = {
    "CDS": [
        {
            "tab_name":    "ParticipantsTab",
            "tab_btn":     "CDS/Data_page/CDSResults_Participants_Tab",
            "table_body":  "CDS/Data_page/CDS_ParticipantsTable",
            "table_hdr":   "CDS/Data_page/CDS_ParticipantsTableHeader",
            "next_btn":    "CDS/Data_page/CDS_ParticipantsTabNextBtn",
            "web_sheet":   "WebDataParticipants",
            "tsv_sheet":   "TsvDataParticipants",
        },
        {
            "tab_name":    "SamplesTab",
            "tab_btn":     "CDS/Data_page/CDSResults_Samples_Tab",
            "table_body":  "CDS/Data_page/CDS_SamplesTable",
            "table_hdr":   "CDS/Data_page/CDS_SamplesTableHeader",
            "next_btn":    "CDS/Data_page/CDS_SamplesTabNextBtn",
            "web_sheet":   "WebDataSamples",
            "tsv_sheet":   "TsvDataSamples",
        },
        {
            "tab_name":    "FilesTab",
            "tab_btn":     "CDS/Data_page/CDSResults_Files_Tab",
            "table_body":  "CDS/Data_page/CDS_FilesTable",
            "table_hdr":   "CDS/Data_page/CDS_FilesTableHeader",
            "next_btn":    "CDS/Data_page/CDS_FilesTabNextBtn",
            "web_sheet":   "WebDataFiles",
            "tsv_sheet":   "TsvDataFiles",
        },
    ],
    # Add CCDI, C3DC, CTDC, INS, Bento, Canine tabs here as they are implemented
}

# ── Per-program nav button Object Repo key ─────────────────────────────────────
PROGRAM_NAV_BTN = {
    "CDS":    "CDS/NavBar/CDS_Data-Btn",
    "CCDI":   "CCDI/NavBar/CCDI_Data-Btn",
    "C3DC":   "C3DC/NavBar/C3DC_Data-Btn",
    "CTDC":   "CTDC/NavBar/CTDC_Data-Btn",
    "INS":    "INS/NavBar/INS_Data-Btn",
    "Bento":  "Bento/NavBar/Bento_Data-Btn",
    "Canine": "Canine/NavBar/Canine_Data-Btn",
}


def run_test(input_excel_path: str, program: str, url: str = "",
             filters: list = None, max_pages: int = None, max_rows: int = None):
    """
    Run one complete test for a study.
    Entry point — equivalent of one Katalon test script.

    Args:
        input_excel_path: Full path to input Excel e.g. InputFiles/CDS/TC01_CDS_phs001234_*.xlsx
        program:          Program name e.g. 'CDS', 'CCDI', 'Canine'
        url:              Override URL — if empty uses BASE_URLS[program]
        filters:          List of filter dicts [ { 'expand_obj': '...', 'checkbox_obj': '...' } ]
                          If None, no filters are applied
        max_pages:        Max pages to paginate per tab (None = all pages)
        max_rows:         Max rows to collect per tab (None = all rows)

    Returns:
        dict: Test result {
            'passed': bool,
            'tabs':   { tab_name: { 'passed': bool, 'mismatches': list } },
            'errors': list of error strings
        }
    """
    result  = {"passed": True, "tabs": {}, "errors": []}
    nav_url = url or BASE_URLS.get(program, "")

    if not nav_url:
        raise ValueError(
            f"No URL provided for program '{program}'. "
            f"Set BASE_URLS['{program}'] in settings.py or pass url= to run_test()."
        )

    # ── 1. Load study config from input Excel ─────────────────────────────────
    print(f"\n{'='*60}")
    print(f"[test_runner] Starting test: {os.path.basename(input_excel_path)}")
    print(f"[test_runner] Program: {program}  |  URL: {nav_url}")
    print(f"{'='*60}")

    config = load_study_config(input_excel_path)
    output_excel = config["web_excel"] or os.path.join(
        OUTPUT_FILES_ROOT,
        os.path.splitext(os.path.basename(input_excel_path))[0] + "_WebData.xlsx"
    )

    playwright, browser, page = None, None, None
    try:
        # ── 2. Launch browser and navigate ────────────────────────────────────
        playwright, browser, page = launch_browser()
        navigate_to(page, nav_url)

        # ── 3. Dismiss popup (FIRST action — same as every Katalon script) ────
        dismiss_popup(page)

        # ── 4. Click nav button to go to data page ────────────────────────────
        nav_btn = PROGRAM_NAV_BTN.get(program)
        if nav_btn:
            click_and_wait(page, find_test_object(nav_btn))

        # ── 5. Apply filters ──────────────────────────────────────────────────
        if filters:
            apply_filters(page, filters)

        # ── 6. Read stat bar after filters applied ────────────────────────────
        stat_counts = read_stat_bar(page, program)

        # ── 7. Run multiFunction for each result tab ──────────────────────────
        tabs_def = PROGRAM_TABS.get(program, [])
        for tab_def in tabs_def:
            tab_name = tab_def["tab_name"]

            # Skip tab if not in the input Excel
            if tab_name not in config["tabs"]:
                print(f"[test_runner] Skipping tab '{tab_name}' — not in input Excel")
                continue

            print(f"\n[test_runner] --- Tab: {tab_name} ---")

            # Click the result tab button
            click_element(page, find_test_object(tab_def["tab_btn"]))

            # Run multi_function for this tab
            tab_result = multi_function(
                page       = page,
                program    = program,
                config     = config,
                tab_def    = tab_def,
                output_excel = output_excel,
                stat_counts  = stat_counts,
                max_pages    = max_pages,
                max_rows     = max_rows,
            )

            result["tabs"][tab_name] = tab_result
            if not tab_result["passed"]:
                result["passed"] = False

    except Exception as e:
        result["passed"] = False
        result["errors"].append(str(e))
        print(f"[test_runner] ERROR: {e}")
        raise

    finally:
        if browser and playwright:
            close_browser(playwright, browser)

    # ── Summary ───────────────────────────────────────────────────────────────
    status = "PASS" if result["passed"] else "FAIL"
    print(f"\n{'='*60}")
    print(f"[test_runner] Result: {status}")
    for tab_name, tab_res in result["tabs"].items():
        tab_status = "PASS" if tab_res["passed"] else "FAIL"
        mismatches = len(tab_res.get("mismatches", []))
        print(f"  {tab_name}: {tab_status}"
              f"{f'  ({mismatches} mismatches)' if mismatches else ''}")
    print(f"{'='*60}\n")

    return result


def multi_function(page, program: str, config: dict, tab_def: dict,
                   output_excel: str, stat_counts: dict,
                   max_pages: int = None, max_rows: int = None) -> dict:
    """
    Master comparison function for one result tab.
    Replaces: multiFunction() in TestRunner.groovy.

    Steps:
      1. collect_all_rows()      — paginate table, collect all UI rows
      2. write_web_data()        — write rows to WebData sheet in output Excel
      3. run_result_tabs()       — run ResultTabs.py → writes TsvData sheet
      4. run_statbar_script()    — run Statbar.py → writes StatOutput sheet
      5. compare_sheets()        — compare WebData vs TsvData row by row
      6. validate_stat_bar()     — validate stat bar counts vs StatOutput

    Args:
        page:         Playwright Page object
        program:      Program name e.g. 'CDS'
        config:       Study config from load_study_config()
        tab_def:      Tab definition dict from PROGRAM_TABS
        output_excel: Full path to output Excel file
        stat_counts:  Stat bar counts already read from screen
        max_pages:    Max pages to paginate (None = all)
        max_rows:     Max rows to collect (None = all)

    Returns:
        dict: { 'passed': bool, 'mismatches': list, 'web_count': int, 'tsv_count': int }
    """
    tab_name  = tab_def["tab_name"]
    web_sheet = tab_def["web_sheet"]
    tsv_sheet = tab_def["tsv_sheet"]

    # Stat value for this tab — skip collection if 0 (same logic as Katalon)
    stat_key   = _tab_name_to_stat_key(tab_name)
    stat_value = stat_counts.get(stat_key, 0)

    if stat_value == 0:
        print(f"[test_runner] Skipping '{tab_name}' — stat bar count is 0")
        return {"passed": True, "mismatches": [], "web_count": 0, "tsv_count": 0, "skipped": True}

    # ── Step 1 & 2: Paginate table → write WebData ────────────────────────────
    table_result = collect_all_rows(
        page             = page,
        table_body_xpath = find_test_object(tab_def["table_body"]) + "//tbody//tr",
        next_btn_xpath   = find_test_object(tab_def["next_btn"]),
        header_xpath     = find_test_object(tab_def["table_hdr"]) + "//th",
        expected_total   = stat_value,
        max_pages        = max_pages,
        max_rows         = max_rows,
    )
    write_web_data(table_result, output_excel, web_sheet)

    # ── Step 3: Run ResultTabs.py → writes TsvData sheet ─────────────────────
    # ResultTabs.py expects sys.argv[4] = tsv_sheet name e.g. "TsvDataParticipants"
    run_result_tabs(
        program      = program,
        input_excel  = config["input_excel"],
        output_dir   = os.path.dirname(output_excel),
        tab_name     = tsv_sheet,
    )

    # ── Step 4: Run Statbar.py → writes StatOutput sheet ─────────────────────
    run_statbar_script(
        program      = program,
        input_excel  = config["input_excel"],
        output_dir   = os.path.dirname(output_excel),
        tab_name     = tsv_sheet,
    )

    # ── Step 5: Compare WebData vs TsvData ───────────────────────────────────
    # WebData rows are in WebData Excel; TsvData rows are in TSVData Excel
    tsv_excel = config.get("tsv_excel") or output_excel.replace("_WebData.xlsx", "_TSVData.xlsx")
    from core.excel_reader import read_excel_sheet, compare_two_lists
    web_rows = read_excel_sheet(output_excel, web_sheet)
    tsv_rows = read_excel_sheet(tsv_excel,    tsv_sheet)
    web_headers = web_rows[0] if web_rows else []
    import re as _re
    from core.excel_reader import normalize_semicolon_list, strip_cpi_badge
    def _norm(row): return [strip_cpi_badge(normalize_semicolon_list(str(v))) for v in row]
    web_data = sorted([_norm(r) for r in web_rows[1:]])
    tsv_data = sorted([_norm(r) for r in tsv_rows[1:]])
    mismatches = compare_two_lists(web_data, tsv_data, web_headers)
    comparison = {
        "passed":     len(mismatches) == 0 and len(web_data) == len(tsv_data),
        "mismatches": mismatches,
        "web_count":  len(web_data),
        "tsv_count":  len(tsv_data),
    }

    # ── Step 6: Validate stat bar counts ─────────────────────────────────────
    stat_valid = validate_stat_bar(page, program, stat_counts)

    passed = comparison["passed"] and stat_valid
    print(f"[test_runner] '{tab_name}': {'PASS' if passed else 'FAIL'} "
          f"| web={comparison['web_count']} tsv={comparison['tsv_count']} "
          f"| mismatches={len(comparison['mismatches'])}")

    return {
        "passed":     passed,
        "mismatches": comparison["mismatches"],
        "web_count":  comparison["web_count"],
        "tsv_count":  comparison["tsv_count"],
    }


def apply_filters(page, filters: list):
    """
    Apply a list of filters in sequence — expand dropdown then check checkbox.
    Replaces: the sequence of clickTabCDSStat(Ddn) + clickTabCDSStat(Chkbx) calls in Katalon.

    Args:
        page:    Playwright Page object
        filters: List of filter dicts e.g.
                 [ { 'expand_obj': 'CDS/Data_page/Filter/.../PHS_Accession_Ddn',
                     'checkbox_obj': 'CDS/Data_page/Filter/.../phs001234_Chkbx' } ]
    """
    for f in filters:
        expand_xpath   = find_test_object(f["expand_obj"])
        checkbox_xpath = find_test_object(f["checkbox_obj"])
        print(f"[test_runner] Expanding filter: {f['expand_obj']}")
        click_and_wait(page, expand_xpath)
        print(f"[test_runner] Checking: {f['checkbox_obj']}")
        click_and_wait(page, checkbox_xpath)


def login(page, credentials: dict):
    """
    Log into the application via SSO email/password flow.
    Replaces: Login() in TestRunner.groovy.

    Args:
        page:        Playwright Page object
        credentials: { 'email': str, 'password': str }
    """
    email    = credentials.get("email", "")
    password = credentials.get("password", "")

    # Click Sign In button
    signin_btn = page.locator("xpath=//button[contains(text(),'Sign In') or contains(text(),'Login')]").first
    signin_btn.wait_for(state="visible")
    signin_btn.click()

    # Enter email
    email_field = page.locator("xpath=//input[@type='email' or @name='email']").first
    email_field.wait_for(state="visible")
    email_field.fill(email)
    page.keyboard.press("Enter")

    # Enter password
    pass_field = page.locator("xpath=//input[@type='password']").first
    pass_field.wait_for(state="visible")
    pass_field.fill(password)
    page.keyboard.press("Enter")

    page.wait_for_load_state("networkidle")


def verify_static_page(page, program: str, expected_texts: list) -> bool:
    """
    Verify static page content against a list of expected text strings.
    Replaces: verifyStaticData() in TestRunner.groovy.

    Args:
        page:           Playwright Page object
        program:        Program name (for logging)
        expected_texts: List of strings that must appear on the page

    Returns:
        bool: True if all expected texts found
    """
    content = page.content()
    missing = [t for t in expected_texts if t not in content]
    if missing:
        print(f"[test_runner] Static page FAIL for {program} — missing texts:")
        for t in missing:
            print(f"  - {t!r}")
        return False
    print(f"[test_runner] Static page PASS for {program}")
    return True


# ── Internal helpers ──────────────────────────────────────────────────────────

def run_test_from_excel(testcase_excel: str):
    """
    Read a test case Excel (Config + Steps sheets) and execute it.
    This is the main entry point when tests are driven from Excel.

    Args:
        testcase_excel: Full path to the test case Excel file
                        e.g. TestCases/TC01_CDS_phs001437_*.xlsx
    """
    wb = openpyxl.load_workbook(testcase_excel, data_only=True)

    # ── Read Config sheet ─────────────────────────────────────────────────────
    ws_cfg = wb["Config"]
    cfg = {}
    for row in ws_cfg.iter_rows(min_row=2, values_only=True):
        if row[0] and row[1]:
            cfg[str(row[0]).strip()] = str(row[1]).strip()

    program    = cfg.get("Program", "")
    input_excel = cfg.get("Input Excel", "")
    max_pages  = int(cfg["Max Pages"]) if cfg.get("Max Pages", "").strip() else None
    max_rows   = int(cfg["Max Rows"])  if cfg.get("Max Rows",  "").strip() else None

    # Resolve input excel relative to COMMONS_ROOT if not absolute
    from config.settings import COMMONS_ROOT, OUTPUT_FILES_ROOT
    if not os.path.isabs(input_excel):
        input_excel = os.path.join(COMMONS_ROOT, input_excel)

    # ── Read Steps sheet ──────────────────────────────────────────────────────
    # Columns: # | Action | Page | Object Name | Params | Notes
    ws_steps = wb["Steps"]
    steps = []
    for row in ws_steps.iter_rows(min_row=2, values_only=True):
        if not row[1]:   # skip empty action rows
            continue
        steps.append({
            "action":      str(row[1]).strip(),
            "page":        str(row[2]).strip() if row[2] else "",
            "object_name": str(row[3]).strip() if row[3] else "",
            "params":      str(row[4]).strip() if row[4] else "",
            "notes":       str(row[5]).strip() if row[5] else "",
        })
    wb.close()

    print(f"\n{'='*60}")
    print(f"[test_runner] Test Case: {os.path.basename(testcase_excel)}")
    from config.settings import ENV
    url = get_url(program)
    print(f"[test_runner] Program={program}  ENV={ENV}  URL={url}")
    print(f"[test_runner] Steps: {len(steps)}")
    print(f"{'='*60}")

    # Load study config from input Excel
    config      = load_study_config(input_excel)
    output_excel = config["web_excel"] or os.path.join(
        OUTPUT_FILES_ROOT,
        os.path.splitext(os.path.basename(input_excel))[0] + "_WebData.xlsx"
    )

    playwright, browser, page = None, None, None
    stat_counts = {}
    result      = {"passed": True, "tabs": {}, "errors": []}

    try:
        playwright, browser, page = launch_browser()
        navigate_to(page, url)

        # Execute each step from the Excel
        for step in steps:
            action     = step["action"]
            page_name  = step["page"]
            obj_name   = step["object_name"]
            params     = step["params"]

            # Build lookup key from program/page/object_name when both are provided
            def _xpath():
                if not page_name or not obj_name:
                    raise ValueError(
                        f"Step '{action}' needs Page + Object Name but one is empty."
                    )
                lookup_key = f"{program}/{page_name}/{obj_name}"
                return find_test_object(lookup_key)

            print(f"[test_runner] Step: {action}"
                  f"{f' | {page_name}/{obj_name}' if obj_name else ''}"
                  f"{f' | {params}'               if params   else ''}")

            if action == "dismiss_popup":
                dismiss_popup(page)

            elif action == "navigate_to":
                from config.settings import get_page_url
                nav_target = get_page_url(program, page_name)
                navigate_to(page, nav_target)

            elif action == "click_element":
                click_element(page, _xpath())

            elif action == "click_and_wait":
                click_and_wait(page, _xpath())

            elif action == "js_click_and_wait":
                # JavaScript click bypasses MUI overlay — use for checkboxes
                from core.actions import js_click
                js_click(page, _xpath())
                page.wait_for_load_state("networkidle", timeout=15000)

            elif action in ("js_click", "scroll_into_view"):
                from core.actions import js_click, scroll_into_view
                fn = js_click if action == "js_click" else scroll_into_view
                fn(page, _xpath())

            elif action == "wait_for_element_hidden":
                page.locator(f"xpath={_xpath()}").wait_for(state="hidden")

            elif action in ("is_element_visible", "is_element_enabled"):
                loc = page.locator(f"xpath={_xpath()}")
                visible = loc.is_visible()
                enabled = loc.is_enabled() if action == "is_element_enabled" else None
                val = enabled if action == "is_element_enabled" else visible
                print(f"[test_runner] {action} => {val}")

            elif action == "clear_input":
                page.locator(f"xpath={_xpath()}").clear()

            elif action == "find_filter_by_search":
                from core.actions import find_filter_by_search
                find_filter_by_search(page, _xpath(), params)

            elif action == "read_stat_bar":
                stat_counts = read_stat_bar(page, params or program)

            elif action == "multi_function":
                tab_name = params
                tab_def  = next((t for t in PROGRAM_TABS.get(program, [])
                                  if t["tab_name"] == tab_name), None)
                if not tab_def:
                    print(f"[test_runner] Warning: no tab definition for '{tab_name}' — skipping")
                    continue
                # Click the result tab button first
                click_element(page, find_test_object(tab_def["tab_btn"]))
                tab_result = multi_function(
                    page=page, program=program, config=config,
                    tab_def=tab_def, output_excel=output_excel,
                    stat_counts=stat_counts, max_pages=max_pages, max_rows=max_rows,
                )
                result["tabs"][tab_name] = tab_result
                if not tab_result["passed"]:
                    result["passed"] = False

            elif action == "login":
                parts = params.split(",")
                login(page, {"email": parts[0].strip(), "password": parts[1].strip() if len(parts) > 1 else ""})

            elif action == "verify_static_page":
                verify_static_page(page, program, [params])

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
        mismatches = len(tab_res.get("mismatches", []))
        print(f"  {tab_name}: {tab_status}"
              f"{f'  ({mismatches} mismatches)' if mismatches else ''}")
    print(f"{'='*60}\n")
    return result


def _tab_name_to_stat_key(tab_name: str) -> str:
    """Map a tab name like 'ParticipantsTab' to the stat bar dict key 'participants'."""
    mapping = {
        "ParticipantsTab": "participants",
        "SamplesTab":      "samples",
        "FilesTab":        "files",
        "StudiesTab":      "studies",
        "DiagnosesTab":    "diagnoses",
        "GrantsTab":       "grants",
        "ProjectsTab":     "projects",
        "PublicationsTab": "publications",
        "DatasetsTab":     "datasets",
    }
    return mapping.get(tab_name, tab_name.lower().replace("tab", "").strip())
