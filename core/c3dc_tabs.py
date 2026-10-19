"""
C3DC result tab selection (bar tabs + More menu).
Mirrors commons-automation Commons/apps/c3dc.py selectTab logic.
"""
import re
import time

from playwright.sync_api import Page

from core.object_repo import find_test_object
from core.actions import js_click
from config.settings import DEFAULT_TIMEOUT

RESULT_TAB_BUTTONS_XP = "//button[@role='tab']"
MORE_TABS_BTN_XP = (
    "(//button[@role='tab'])[last()]/following::button"
    "[contains(@class,'more-button') or contains(normalize-space(.),'More')][1]"
)
MORE_MENU_ITEM_XP = "//div[contains(@class,'popover-list-item')]"
_MENU_TEXT_JS = """
(el) => {
  const s = el.querySelector('span[class*="popover-tab-name"]');
  return (s ? s.textContent : el.textContent) || '';
}
"""

TAB_LABEL_ALIASES = {
    "GeneticAnalysisTab": ["Genetic Analyses", "Genetic Analysis"],
    "TreatmentTab": ["Treatments", "Treatment"],
    "TreatmentRespTab": ["Treatment Responses", "Treatment Response"],
    "ParticipantsTab": ["Participants"],
    "StudiesTab": ["Studies"],
    "DiagnosisTab": ["Diagnosis"],
    "SurvivalTab": ["Survival"],
    "SamplesTab": ["Samples"],
    "FilesTab": ["Files"],
}


def _normalize_label(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").replace("\u00a0", " ")).strip()


def _label_matches(raw: str, target: str) -> bool:
    label = _normalize_label(raw)
    core = re.sub(r"\s*\([\d,]+\)\s*$", "", label).strip()
    for lbl in (label, core):
        if not lbl or not target:
            continue
        if lbl.lower() == target.lower():
            return True
        if len(lbl) > len(target) and lbl[: len(target)].lower() == target.lower():
            if not lbl[len(target)].isalnum():
                return True
    return False


def _is_more_button(raw: str, class_name: str = "") -> bool:
    if "more-button" in (class_name or ""):
        return True
    return bool(re.match(r"^:?\s*More\b", (raw or "").strip(), re.I))


def select_c3dc_tab(page: Page, tab_name: str, timeout_s: int = 15) -> None:
    """
    Open a C3DC explore result tab by framework tab name (e.g. ParticipantsTab).
    """
    labels = TAB_LABEL_ALIASES.get(tab_name, [tab_name.replace("Tab", "")])
    deadline = time.time() + timeout_s
    last_err = None

    while time.time() < deadline:
        for label in labels:
            if _try_select_label(page, label, timeout_s=max(5, int(deadline - time.time()))):
                page.wait_for_load_state("networkidle", timeout=DEFAULT_TIMEOUT)
                return
        page.wait_for_timeout(400)
    raise RuntimeError(f"C3DC tab {tab_name!r} not found (tried labels {labels!r}). Last: {last_err}")


def _try_select_label(page: Page, label: str, timeout_s: int = 10) -> bool:
    tab_xp = RESULT_TAB_BUTTONS_XP
    loc = page.locator(f"xpath={tab_xp}")
    try:
        loc.first.wait_for(state="visible", timeout=int(timeout_s * 1000))
    except Exception:
        return False

    count = loc.count()
    for i in range(count):
        nth = loc.nth(i)
        raw = nth.evaluate("el => el.textContent") or ""
        cls = nth.evaluate("el => el.className") or ""
        if _is_more_button(raw, cls):
            continue
        if not _label_matches(raw, label):
            continue
        nth.scroll_into_view_if_needed()
        nth.evaluate("el => el.click()")
        return True

    try:
        more = page.locator(f"xpath={MORE_TABS_BTN_XP}").first
        more.wait_for(state="visible", timeout=5000)
        more.scroll_into_view_if_needed()
        js_click(page, MORE_TABS_BTN_XP)
        page.wait_for_timeout(400)
    except Exception:
        return False

    menu = page.locator(f"xpath={MORE_MENU_ITEM_XP}")
    for i in range(menu.count()):
        item = menu.nth(i)
        raw = item.evaluate(_MENU_TEXT_JS)
        if not _label_matches(raw, label):
            continue
        item.evaluate("el => el.click()")
        return True
    return False
