# Commons Playwright Framework

Python + Playwright test automation framework for CBIIT NCI Data Commons programs.  
Migrated from Katalon Studio — Excel-driven, environment-agnostic, zero hardcoding.

---

## Programs Supported

| Program | URL (QA) |
|---------|----------|
| CDS     | https://general-qa.datacommons.cancer.gov |
| Canine  | https://caninecommons.cancer.gov |
| CTDC    | https://clinical.datacommons.cancer.gov |

---

## Repository Structure

```
Commons_playwright/
├── config/
│   └── settings.py              # All URLs and environment config — one place
├── core/
│   ├── object_repo.py           # XPath lookup from Object Repository Excel files
│   ├── actions.py               # Playwright actions (click, js_click, scroll, etc.)
│   ├── browser.py               # Browser launch / close
│   ├── table_reader.py          # Paginate result tables, collect rows
│   ├── stat_bar.py              # Read and validate stat bar counts
│   ├── excel_reader.py          # Read study input Excel, compare web vs TSV data
│   └── python_runner.py         # Run ResultTabs.py and Statbar.py as subprocesses
├── tests/
│   └── test_runner.py           # Excel-driven test orchestrator — main entry point
├── ObjectRepository/
│   ├── CDS_ObjectRepository.xlsx
│   ├── Canine_ObjectRepository.xlsx
│   └── CTDC_ObjectRepository.xlsx
├── TestCases/
│   └── TC01_CDS_phs001437_*.xlsx   # Sample test case Excel
└── Object_Repository.xlsx       # Original Katalon source (reference)
```

---

## How It Works

### Excel is the only driver

Every test is defined in a **Test Case Excel** with two sheets:

**Config sheet**

| Key | Value |
|-----|-------|
| Test Case ID | TC01_CDS_phs001437_... |
| Program | CDS |
| Input Excel | InputFiles/CDS/TC01_... .xlsx |
| Max Pages | 5 |

**Steps sheet** — one row per action

| # | Action | Page | Object Name | Params | Notes |
|---|--------|------|-------------|--------|-------|
| 1 | dismiss_popup | | | | |
| 2 | click_and_wait | NavBar | CDS_Data-Btn | | Click Data nav |
| 3 | click_and_wait | Data_page | Filter/StudyFacet/PHS_Accession/PHS_Accession_Ddn | | Expand filter |
| 4 | js_click_and_wait | Data_page | Filter/StudyFacet/PHS_Accession/phs001437_Chkbx | | Select study |
| 9 | read_stat_bar | | | CDS | Read counts |
| 10 | multi_function | | | ParticipantsTab | Paginate + compare |

The runner builds the XPath lookup key as `{Program}/{Page}/{Object Name}` and looks it up in the Object Repository.

---

## Object Repository

Each program has its own Excel file in `ObjectRepository/`, with **one sheet per app page**.

| Column | Description |
|--------|-------------|
| Lookup Key | Full Katalon-style path e.g. `CDS/NavBar/CDS_Data-Btn` |
| Object Name | Short name e.g. `CDS_Data-Btn` |
| XPath | XPath expression used by Playwright |

---

## Environment Configuration

All URLs live in `config/settings.py` — **no URLs in Test Case Excel files**.

```python
# Run against QA (default)
python3 -c "from tests.test_runner import run_test_from_excel; run_test_from_excel('TestCases/TC01_CDS_phs001437_*.xlsx')"

# Run against prod
ENV=prod python3 -c "..."

# Run headless (for CI/CD)
HEADLESS=true ENV=prod python3 -c "..."
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `qa` | Target environment: `qa`, `prod`, `stage` |
| `HEADLESS` | `false` | Run browser headless |
| `BROWSER` | `chromium` | Browser: `chromium`, `firefox`, `webkit` |
| `URL_CDS_QA` | (set in settings.py) | Override any URL per program+env |
| `COMMONS_ROOT` | `/Users/lollal/New_Framework/Commons_Automation` | Root for InputFiles / OutputFiles |

---

## Available Actions

| Action | Description |
|--------|-------------|
| `dismiss_popup` | Dismiss warning popup — always first step |
| `navigate_to` | Navigate to a page by name (uses `get_page_url`) |
| `click_and_wait` | Click element + wait for networkidle |
| `js_click_and_wait` | JavaScript click + wait — for MUI checkboxes |
| `click_element` | Click element, no wait |
| `js_click` | JavaScript click only |
| `scroll_into_view` | Scroll element into viewport |
| `wait_for_element_hidden` | Wait until element disappears |
| `is_element_visible` | Assert element is visible |
| `is_element_enabled` | Assert element is enabled |
| `clear_input` | Clear a text input |
| `find_filter_by_search` | Type into a filter search box |
| `read_stat_bar` | Read stat bar counts (Params = program name) |
| `multi_function` | Paginate table + run SQL scripts + compare results |
| `login` | SSO login (Params = `email,password`) |
| `verify_static_page` | Verify static page text |

---

## Running a Test

```bash
cd /path/to/Commons_playwright

# Install dependencies (first time)
pip install playwright openpyxl
playwright install chromium

# Run a test case
python3 -c "
from tests.test_runner import run_test_from_excel
run_test_from_excel('TestCases/TC01_CDS_phs001437_Sex-Unknown_ExperimentalStrategy-RNASeq.xlsx')
"
```

---

## Adding a New Program

1. Browse the program's app, note all page URLs
2. Create `ObjectRepository/<Program>_ObjectRepository.xlsx` — one sheet per page
3. Add the program's URLs to `config/settings.py` under `_BASE_URLS` and page paths under `_PAGE_PATHS`
4. Add tab definitions to `PROGRAM_TABS` in `tests/test_runner.py`
5. Create a Test Case Excel in `TestCases/`
