"""
browser.py
Playwright browser lifecycle — launch, new page, close.
Replaces WebUI.openBrowser() / WebUI.closeBrowser() from Katalon.
"""
from playwright.sync_api import sync_playwright, Playwright, Browser, Page
from config.settings import BROWSER, HEADLESS, DEFAULT_TIMEOUT


def launch_browser(headless: bool = HEADLESS,
                   browser_type: str = BROWSER) -> tuple:
    """
    Launch a Playwright browser instance.
    Replaces: WebUI.openBrowser() in Katalon.

    Args:
        headless:     Run without UI — False locally, True on CI/CD
        browser_type: 'chromium', 'firefox', or 'webkit'

    Returns:
        tuple: (playwright, browser, page)
    """
    playwright = sync_playwright().start()

    if browser_type == "firefox":
        browser = playwright.firefox.launch(headless=headless)
    elif browser_type == "webkit":
        browser = playwright.webkit.launch(headless=headless)
    else:
        browser = playwright.chromium.launch(headless=headless)

    page = browser.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)

    return playwright, browser, page


def new_page(browser: Browser) -> Page:
    """
    Open a new browser page/tab.

    Args:
        browser: Playwright Browser instance

    Returns:
        Page: Playwright Page object with default timeout set
    """
    page = browser.new_page()
    page.set_default_timeout(DEFAULT_TIMEOUT)
    return page


def close_browser(playwright: Playwright, browser: Browser):
    """
    Close the browser and stop Playwright.
    Replaces: WebUI.closeBrowser() in Katalon.

    Args:
        playwright: Playwright instance
        browser:    Browser instance
    """
    browser.close()
    playwright.stop()


def navigate_to(page: Page, url: str):
    """
    Navigate to a URL and wait until the network is idle.
    Replaces: WebUI.navigateToUrl() in Katalon.

    Args:
        page: Playwright Page object
        url:  Full URL to navigate to
    """
    page.goto(url, wait_until="networkidle")
