"""
table_reader.py
Paginate the results table and collect all rows into memory.
Replaces ReadCasesTableKatalon() and changePaginationResultsPerPage100() in TestRunner.groovy.

Pagination controls (all optional — set per test or via env variables):
  max_pages     : stop after N pages regardless of total rows  (default: unlimited)
  max_rows      : stop once this many rows are collected       (default: unlimited)
  expected_total: from stat bar — used for progress logging    (default: None)
  page_size     : rows per page to request from UI             (default: 100)
"""
import os
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config.settings import DEFAULT_TIMEOUT

# Default page size — matches Katalon's changePaginationResultsPerPage100()
DEFAULT_PAGE_SIZE = int(os.environ.get("TABLE_PAGE_SIZE", "100"))

# Hard cap — safety valve so a runaway test never loops forever
MAX_PAGES_HARD_CAP = int(os.environ.get("TABLE_MAX_PAGES", "500"))


def set_page_size(page: Page, size: int = DEFAULT_PAGE_SIZE):
    """
    Set the results table to show N rows per page.
    Replaces: changePaginationResultsPerPage100() in Utils.groovy.

    Looks for a rows-per-page dropdown and selects the requested size.
    If the dropdown is not found (some programs don't have it), silently skips.

    Args:
        page: Playwright Page object
        size: Number of rows per page (default 100)
    """
    try:
        # Common pattern across CDS/CCDI/Canine etc.
        dropdown = page.locator(
            "xpath=//select[contains(@class,'pagination') or contains(@aria-label,'rows per page')"
            " or contains(@aria-label,'Rows per page')]"
        ).first
        dropdown.wait_for(state="visible", timeout=5000)
        dropdown.select_option(str(size))
        page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
    except PlaywrightTimeoutError:
        # Some program pages don't have a rows-per-page selector — skip silently
        pass


def get_table_headers(page: Page, header_xpath: str) -> list:
    """
    Read column headers from the results table header row.

    Args:
        page:        Playwright Page object
        header_xpath: XPath for the header row (th elements)

    Returns:
        list: Column header strings e.g. ['Study', 'Participants', 'Files']
    """
    headers = []
    cells = page.locator(f"xpath={header_xpath}").all()
    for cell in cells:
        text = cell.inner_text().strip()
        if text:
            headers.append(text)
    return headers


def get_current_page_rows(page: Page, table_body_xpath: str) -> list:
    """
    Read all visible rows from the current page of the results table.

    Args:
        page:             Playwright Page object
        table_body_xpath: XPath that selects all <tr> elements in the table body

    Returns:
        list: List of row lists e.g. [['phs001234', '100', '50'], ...]
    """
    rows = []
    loc = page.locator(f"xpath={table_body_xpath}")
    # Wait for at least one row to be visible (not just attached) before reading
    try:
        loc.first.wait_for(state="visible", timeout=15000)
    except Exception:
        return rows
    # Small settle wait so React finishes rendering all rows on the current page
    page.wait_for_timeout(500)
    row_count = loc.count()
    for i in range(row_count):
        # Re-locate each row by index to avoid stale handles after React re-renders
        row_el = loc.nth(i)
        try:
            row_el.wait_for(state="visible", timeout=5000)
        except Exception:
            continue
        cell_count = row_el.locator("xpath=.//td").count()
        row_data = []
        for j in range(cell_count):
            try:
                text = row_el.locator("xpath=.//td").nth(j).inner_text(timeout=10000).strip()
            except Exception:
                text = ""
            row_data.append(text)
        if any(row_data):  # skip completely empty rows
            rows.append(row_data)
    return rows


def get_pagination_total(page: Page, pagination_xpath: str) -> int:
    """
    Read total row count from pagination text e.g. '1-100 of 1,234' → 1234.
    Replaces: CountRowsfromPagination() in DataValidation.groovy.

    Args:
        page:             Playwright Page object
        pagination_xpath: XPath for the pagination text element

    Returns:
        int: Total number of rows, or 0 if not found
    """
    try:
        text = page.locator(f"xpath={pagination_xpath}").first.inner_text().strip()
        # Pattern: "1-100 of 1,234"  or  "Showing 1 to 100 of 1234"
        import re
        match = re.search(r'of\s+([\d,]+)', text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))
    except Exception:
        pass
    return 0


def is_next_button_enabled(page: Page, next_btn_xpath: str) -> bool:
    """
    Check if the Next page button is enabled (not on last page).

    Args:
        page:           Playwright Page object
        next_btn_xpath: XPath for the Next button

    Returns:
        bool: True if Next button is clickable
    """
    try:
        btn = page.locator(f"xpath={next_btn_xpath}").first
        return btn.is_visible() and btn.is_enabled()
    except Exception:
        return False


def click_next_page(page: Page, next_btn_xpath: str) -> bool:
    """
    Click the Next page button and wait for the table to reload.
    Returns False if Next button is disabled (last page reached).

    Args:
        page:           Playwright Page object
        next_btn_xpath: XPath for the Next button

    Returns:
        bool: True if clicked, False if last page
    """
    if not is_next_button_enabled(page, next_btn_xpath):
        return False

    page.locator(f"xpath={next_btn_xpath}").first.click()
    page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
    return True


def collect_all_rows(page: Page,
                     table_body_xpath: str,
                     next_btn_xpath: str,
                     header_xpath: str = None,
                     expected_total: int = None,
                     max_pages: int = None,
                     max_rows: int = None,
                     page_size: int = DEFAULT_PAGE_SIZE) -> dict:
    """
    Paginate through all pages of the results table and collect every row.
    Replaces: ReadCasesTableKatalon() in TestRunner.groovy.

    Controls (all optional):
      expected_total : total from stat bar — used for progress logging only
      max_pages      : stop after N pages  (env: TABLE_MAX_PAGES, hard cap: 500)
      max_rows       : stop once this many rows collected
      page_size      : rows per page to request (default 100)

    Args:
        page:             Playwright Page object
        table_body_xpath: XPath selecting all <tr> rows in the table body
        next_btn_xpath:   XPath for the Next page button
        header_xpath:     XPath for table header cells (optional)
        expected_total:   Expected total rows from stat bar (for logging)
        max_pages:        Stop after this many pages
        max_rows:         Stop after collecting this many rows
        page_size:        Rows per page to set in the UI

    Returns:
        dict: {
            'headers':  list of column header strings,
            'rows':     list of all collected row lists,
            'pages':    number of pages visited,
            'truncated': bool — True if stopped early due to max_pages/max_rows
        }
    """
    # Apply hard cap — max_pages cannot exceed the env/config hard cap
    effective_max_pages = min(
        max_pages if max_pages is not None else MAX_PAGES_HARD_CAP,
        MAX_PAGES_HARD_CAP
    )

    # Set rows per page in the UI
    set_page_size(page, page_size)

    # Read headers if xpath provided
    headers = get_table_headers(page, header_xpath) if header_xpath else []

    all_rows  = []
    page_num  = 0
    truncated = False

    print(f"[table_reader] Starting pagination"
          f"{f' (expected {expected_total} rows)' if expected_total else ''}"
          f"{f', max {effective_max_pages} pages' if effective_max_pages < MAX_PAGES_HARD_CAP else ''}"
          f"{f', max {max_rows} rows' if max_rows else ''}")

    while True:
        page_num += 1

        # Wait for the table to settle before reading
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Collect rows from current page
        page_rows = get_current_page_rows(page, table_body_xpath)
        all_rows.extend(page_rows)

        print(f"[table_reader] Page {page_num}: {len(page_rows)} rows"
              f" (total so far: {len(all_rows)}"
              f"{f'/{expected_total}' if expected_total else ''})")

        # Check max_rows limit
        if max_rows and len(all_rows) >= max_rows:
            all_rows = all_rows[:max_rows]
            truncated = True
            print(f"[table_reader] Stopped at max_rows={max_rows}")
            break

        # Check max_pages limit
        if page_num >= effective_max_pages:
            truncated = True
            print(f"[table_reader] Stopped at max_pages={effective_max_pages}")
            break

        # Try to go to next page
        if not click_next_page(page, next_btn_xpath):
            print(f"[table_reader] Last page reached.")
            break

        # Wait for page to reload after pagination click
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

    print(f"[table_reader] Done — {len(all_rows)} rows across {page_num} pages"
          f"{' (TRUNCATED)' if truncated else ''}")

    return {
        "headers":   headers,
        "rows":      all_rows,
        "pages":     page_num,
        "truncated": truncated,
    }


def write_web_data(result: dict, output_excel_path: str, sheet_name: str):
    """
    Write collected table rows to the WebData sheet in the output Excel file.
    Replaces: Utils.writeToExcel() in Katalon.

    Args:
        result:            Return value from collect_all_rows()
        output_excel_path: Full path to output Excel file
        sheet_name:        Sheet name to write to (e.g. 'WebData')
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    # Load existing workbook or create new one
    try:
        wb = openpyxl.load_workbook(output_excel_path)
    except FileNotFoundError:
        wb = openpyxl.Workbook()
        # Remove default empty sheet
        if "Sheet" in wb.sheetnames:
            del wb["Sheet"]

    # Remove existing sheet if present so we write fresh
    if sheet_name in wb.sheetnames:
        del wb[sheet_name]

    ws = wb.create_sheet(sheet_name)

    # Write headers
    if result["headers"]:
        for ci, header in enumerate(result["headers"], 1):
            cell = ws.cell(row=1, column=ci, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="1F4E79")
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center")

    # Write data rows
    start_row = 2 if result["headers"] else 1
    for ri, row in enumerate(result["rows"], start_row):
        for ci, value in enumerate(row, 1):
            ws.cell(row=ri, column=ci, value=value)

    wb.save(output_excel_path)
    print(f"[table_reader] Written {len(result['rows'])} rows to '{sheet_name}' in {output_excel_path}")
