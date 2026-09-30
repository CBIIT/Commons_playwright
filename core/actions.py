"""
actions.py
Core browser interaction functions.
Replaces clickTab(), clickTabCDSStat(), scrolltoViewjs(), clickElement() from TestRunner.groovy.

Every function takes an XPath (already resolved via find_test_object) and a Playwright page.
"""
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from config.settings import DEFAULT_TIMEOUT

# XPath for the popup that appears on every page load — same across all programs
_POPUP_CONTINUE_XPATH = "//span[contains(text(),'Continue')]"

# Wait for network idle after a filter click — same behaviour as Katalon's waitForAngular
_NETWORK_IDLE_TIMEOUT = 15000  # ms


def dismiss_popup(page: Page):
    """
    Dismiss the warning/continue popup that appears on every page load.
    Uses JS click to bypass the MuiDialog overlay that intercepts regular pointer events.
    Must be called FIRST before any navigation — mirrors the first line of every Katalon test.

    Args:
        page: Playwright Page object
    """
    try:
        locator = page.locator(f"xpath={_POPUP_CONTINUE_XPATH}")
        locator.wait_for(state="visible", timeout=10000)
        # JS click bypasses the MuiDialog overlay that intercepts regular pointer events
        locator.evaluate("el => el.click()")
        # Wait for all MuiDialog containers to disappear before any subsequent click
        page.wait_for_function(
            "() => document.querySelectorAll('[class*=\"MuiDialog-container\"]').length === 0",
            timeout=10000,
        )
    except PlaywrightTimeoutError:
        # Popup not present on this page load — that is fine, continue
        pass


def click_element(page: Page, xpath: str):
    """
    Click an element by XPath. Scrolls into view and waits for it to be visible first.
    Replaces: clickTab() in Katalon.

    Args:
        page:  Playwright Page object
        xpath: XPath string from find_test_object()
    """
    locator = page.locator(f"xpath={xpath}")
    locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    locator.scroll_into_view_if_needed()
    locator.click()


def click_and_wait(page: Page, xpath: str):
    """
    Click an element then wait for the network to go idle — used for filter
    dropdowns and checkboxes where clicking triggers a data reload.
    Replaces: clickTabCDSStat() / clickTabINSStat() / clickTabCanineStat() in Katalon.

    Args:
        page:  Playwright Page object
        xpath: XPath string from find_test_object()
    """
    # Wait for network to settle first so React has finished re-rendering
    page.wait_for_load_state("networkidle", timeout=_NETWORK_IDLE_TIMEOUT)
    # Re-locate fresh — stale handles from before networkidle are discarded
    loc = page.locator(f"xpath={xpath}").first
    loc.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    # JS scroll avoids "not attached" errors when React re-renders mid-action
    loc.evaluate("el => el.scrollIntoView({block: 'center'})")
    loc.click()
    # Wait for React to re-render after the click
    page.wait_for_load_state("networkidle", timeout=_NETWORK_IDLE_TIMEOUT)


def _scroll_virtual_list_to_reveal(page: Page, xpath: str, max_attempts: int = 20) -> bool:
    """
    For virtualized filter lists (e.g. PHS Accession), scroll the list container
    incrementally until the target element appears in the DOM.
    Returns True if the element was found, False if not found after scrolling.
    """
    # Find the scrollable container that holds filter checkboxes
    # These are divs with overflow scroll/auto that contain the checkbox items
    script = """
    (xpath) => {
        const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
        const el = result.singleNodeValue;
        if (el) return { found: true };
        // Not in DOM — find and scroll the virtualized list containers
        const containers = Array.from(document.querySelectorAll('div')).filter(d => {
            const style = window.getComputedStyle(d);
            return (style.overflow === 'auto' || style.overflow === 'scroll' ||
                    style.overflowY === 'auto' || style.overflowY === 'scroll') &&
                   d.scrollHeight > d.clientHeight + 10 &&
                   d.clientHeight > 50 &&
                   d.querySelectorAll('input[type="checkbox"]').length > 0;
        });
        if (containers.length === 0) return { found: false, scrolled: false };
        // Scroll all matching containers by one step
        containers.forEach(c => { c.scrollTop += 200; });
        return { found: false, scrolled: true, containers: containers.length };
    }
    """
    for _ in range(max_attempts):
        result = page.evaluate(script, xpath)
        if result.get("found"):
            return True
        if not result.get("scrolled"):
            break
        page.wait_for_timeout(150)
    return False


def js_click(page: Page, xpath: str):
    """
    Click element using JavaScript — bypasses overlays and interceptors.
    If the element is in a virtualized list (not in DOM initially), scrolls
    the list container to reveal it before clicking.
    Replaces: clickElement() in Katalon (which used JavascriptExecutor).

    Args:
        page:  Playwright Page object
        xpath: XPath string
    """
    locator = page.locator(f"xpath={xpath}")
    # Quick check if already in DOM
    try:
        locator.wait_for(state="attached", timeout=2000)
    except Exception:
        # Element not in DOM yet — try scrolling the virtualized list to reveal it
        _scroll_virtual_list_to_reveal(page, xpath)
        locator.wait_for(state="attached", timeout=DEFAULT_TIMEOUT)
    locator.evaluate("el => el.click()")


def scroll_into_view(page: Page, xpath: str):
    """
    Scroll an element into the viewport.
    Replaces: scrolltoViewjs() in Katalon.

    Args:
        page:  Playwright Page object
        xpath: XPath string
    """
    locator = page.locator(f"xpath={xpath}")
    locator.wait_for(state="attached", timeout=DEFAULT_TIMEOUT)
    locator.scroll_into_view_if_needed()


def wait_for_element_hidden(page: Page, xpath: str, timeout: int = DEFAULT_TIMEOUT):
    """
    Wait until an element is no longer visible on page.
    Replaces: waitForElementToDisappear() in Utils.groovy.

    Args:
        page:    Playwright Page object
        xpath:   XPath string
        timeout: Max wait time in milliseconds
    """
    page.locator(f"xpath={xpath}").wait_for(state="hidden", timeout=timeout)


def is_element_visible(page: Page, xpath: str) -> bool:
    """
    Return True if element is currently visible on page — no waiting.
    Replaces: isObjPresent() in DataValidation.groovy.

    Args:
        page:  Playwright Page object
        xpath: XPath string

    Returns:
        bool
    """
    return page.locator(f"xpath={xpath}").is_visible()


def is_element_enabled(page: Page, xpath: str) -> bool:
    """
    Return True if element is enabled and clickable.
    Replaces: isObjClickablet() in DataValidation.groovy.

    Args:
        page:  Playwright Page object
        xpath: XPath string

    Returns:
        bool
    """
    return page.locator(f"xpath={xpath}").is_enabled()


def clear_input(page: Page, xpath: str):
    """
    Clear a text input field using keyboard shortcut (Ctrl+A → Delete).
    Replaces: clearTextfieldByOs() in Katalon.

    Args:
        page:  Playwright Page object
        xpath: XPath string
    """
    locator = page.locator(f"xpath={xpath}")
    locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    locator.click()
    locator.select_text()
    page.keyboard.press("Delete")


def find_filter_by_search(page: Page, filter_name: str):
    """
    Type a filter name into the filter search box to locate a filter facet.
    Replaces: findFilterBySearch() in Utils.groovy.

    Args:
        page:        Playwright Page object
        filter_name: Text to type into the filter search box

    Returns:
        Locator: Playwright locator for the matching filter element
    """
    search_box = page.locator("xpath=//input[@placeholder='Search' or @type='search']").first
    search_box.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    search_box.fill(filter_name)
    page.wait_for_load_state("networkidle", timeout=_NETWORK_IDLE_TIMEOUT)
    return page.locator(f"xpath=//*[contains(text(), '{filter_name}')]").first
