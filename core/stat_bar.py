"""
stat_bar.py
Read and validate stat bar counts per program.
Replaces readStatBarCDS/CCDI/C3DC/CTDC/INS/Bento/Canine() and validateStatBar() in TestRunner.groovy.

All XPaths come from Object_Repository.xlsx via find_test_object() — no hardcoded selectors.
"""
import re
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from core.object_repo import find_test_object
from config.settings import DEFAULT_TIMEOUT


def parse_count(text: str) -> int:
    """
    Convert a stat bar display string to integer.
    e.g. '1,234' → 1234  |  '12.5K' → 12500  |  '0' → 0
    Replaces: convStringtoInt() in Katalon.

    Args:
        text: Raw string from stat bar element

    Returns:
        int: Numeric count
    """
    if not text:
        return 0
    text = text.strip().replace(",", "")
    # Handle K suffix e.g. '12.5K'
    if text.upper().endswith("K"):
        return int(float(text[:-1]) * 1000)
    # Handle M suffix
    if text.upper().endswith("M"):
        return int(float(text[:-1]) * 1_000_000)
    # Extract first number found in string
    match = re.search(r"[\d.]+", text)
    return int(float(match.group())) if match else 0


def _read_stat(page: Page, lookup_key: str) -> int:
    """
    Read a single stat bar element by Object Repo lookup key and return its integer value.

    Args:
        page:       Playwright Page object
        lookup_key: Object Repo path e.g. 'CDS/StatBar/CDS_StatBar-Studies'

    Returns:
        int: Parsed count value
    """
    xpath = find_test_object(lookup_key)
    try:
        locator = page.locator(f"xpath={xpath}").first
        locator.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
        return parse_count(locator.inner_text())
    except PlaywrightTimeoutError:
        print(f"[stat_bar] Warning: could not read '{lookup_key}' — returning 0")
        return 0


def read_stat_bar_cds(page: Page) -> dict:
    """
    Read Studies, Participants, Samples, Files counts from the CDS stat bar.
    Replaces: readStatBarCDS() in TestRunner.groovy.

    Returns:
        dict: { 'studies': int, 'participants': int, 'samples': int, 'files': int }
    """
    return {
        "studies":      _read_stat(page, "CDS/StatBar/CDS_StatBar-Studies"),
        "participants": _read_stat(page, "CDS/StatBar/CDS_StatBar-Participants"),
        "samples":      _read_stat(page, "CDS/StatBar/CDS_StatBar-Samples"),
        "files":        _read_stat(page, "CDS/StatBar/CDS_StatBar-Files"),
    }


def read_stat_bar_ccdi(page: Page) -> dict:
    """
    Read stat bar counts for CCDI program.
    Replaces: readStatBarCCDIhub() in TestRunner.groovy.

    Returns:
        dict: { 'studies': int, 'participants': int, 'samples': int, 'files': int }
    """
    return {
        "studies":      _read_stat(page, "CCDI/StatBar/CCDI_StatBar-Studies"),
        "participants": _read_stat(page, "CCDI/StatBar/CCDI_StatBar-Participants"),
        "samples":      _read_stat(page, "CCDI/StatBar/CCDI_StatBar-Samples"),
        "files":        _read_stat(page, "CCDI/StatBar/CCDI_StatBar-Files"),
    }


def read_stat_bar_c3dc(page: Page) -> dict:
    """
    Read stat bar counts for C3DC program.
    Replaces: readStatBarC3DC() in TestRunner.groovy.

    Returns:
        dict: { 'diagnoses': int, 'participants': int, 'studies': int }
    """
    return {
        "diagnoses":    _read_stat(page, "C3DC/Statbar/Diagnosis-Count"),
        "participants": _read_stat(page, "C3DC/Statbar/Participants-Count"),
        "studies":      _read_stat(page, "C3DC/Statbar/Studies-Count"),
    }


def read_stat_bar_ctdc(page: Page) -> dict:
    """
    Read stat bar counts for CTDC program.
    Replaces: readStatBarCTDC() in TestRunner.groovy.

    Returns:
        dict: { 'studies': int, 'participants': int, 'diagnoses': int,
                'targeted_therapies': int, 'biospecimens': int, 'files': int }
    """
    return {
        "studies":             _read_stat(page, "CTDC/Statbar/Studies-Count"),
        "participants":        _read_stat(page, "CTDC/Statbar/Participants-Count"),
        "diagnoses":           _read_stat(page, "CTDC/Statbar/Diagnoses-Count"),
        "targeted_therapies":  _read_stat(page, "CTDC/Statbar/TargetedTherapies-Count"),
        "biospecimens":        _read_stat(page, "CTDC/Statbar/Biospecimens-Count"),
        "files":               _read_stat(page, "CTDC/Statbar/Files-Count"),
    }


def read_stat_bar_ins(page: Page) -> dict:
    """
    Read stat bar counts for INS program.
    Replaces: readStatBarINS() in TestRunner.groovy.

    Returns:
        dict: { 'programs': int, 'projects': int, 'grants': int, 'publications': int }
    """
    return {
        "programs":     _read_stat(page, "INS/Statbar/Statbar-Programs"),
        "projects":     _read_stat(page, "INS/Statbar/Statbar-Projects"),
        "grants":       _read_stat(page, "INS/Statbar/Statbar-Grants"),
        "publications": _read_stat(page, "INS/Statbar/Statbar-Publications"),
    }


def read_stat_bar_bento(page: Page) -> dict:
    """
    Read stat bar counts for Bento program.
    Replaces: readStatBarBento() in TestRunner.groovy.

    Returns:
        dict: { 'programs': int, 'arms': int, 'cases': int,
                'samples': int, 'assays': int, 'files': int }
    """
    return {
        "programs": _read_stat(page, "Bento/StatBar/Bento_StatBar-Programs"),
        "arms":     _read_stat(page, "Bento/StatBar/Bento_StatBar-Arms"),
        "cases":    _read_stat(page, "Bento/StatBar/Bento_StatBar-Cases"),
        "samples":  _read_stat(page, "Bento/StatBar/Bento_StatBar-Samples"),
        "assays":   _read_stat(page, "Bento/StatBar/Bento_StatBar-Assays"),
        "files":    _read_stat(page, "Bento/StatBar/Bento_StatBar-Files"),
    }


def read_stat_bar_canine(page: Page) -> dict:
    """
    Read stat bar counts for Canine program.
    Replaces: readStatBarCanine() in TestRunner.groovy.

    Returns:
        dict: { 'programs': int, 'studies': int, 'cases': int,
                'samples': int, 'files': int, 'study_files': int }
    """
    return {
        "programs":    _read_stat(page, "Canine/StatBar/Canine_StatBar-Programs"),
        "studies":     _read_stat(page, "Canine/StatBar/Canine_StatBar-Studies"),
        "cases":       _read_stat(page, "Canine/StatBar/Canine_StatBar-Cases"),
        "samples":     _read_stat(page, "Canine/StatBar/Canine_StatBar-Samples"),
        "files":       _read_stat(page, "Canine/StatBar/Canine_StatBar-CaseFiles"),
        "study_files": _read_stat(page, "Canine/StatBar/Canine_StatBar-StudyFiles"),
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

_READERS = {
    "CDS":    read_stat_bar_cds,
    "CCDI":   read_stat_bar_ccdi,
    "C3DC":   read_stat_bar_c3dc,
    "CTDC":   read_stat_bar_ctdc,
    "INS":    read_stat_bar_ins,
    "Bento":  read_stat_bar_bento,
    "Canine": read_stat_bar_canine,
}


def read_stat_bar(page: Page, program: str) -> dict:
    """
    Dispatcher — calls the correct read_stat_bar_* for the given program.
    Replaces: the if/else program switch in TestRunner.groovy.

    Args:
        page:    Playwright Page object
        program: Program name e.g. 'CDS', 'CCDI', 'Canine'

    Returns:
        dict: Stat bar counts for that program

    Raises:
        ValueError: If program is not supported
    """
    reader = _READERS.get(program)
    if not reader:
        raise ValueError(
            f"No stat bar reader for program '{program}'. "
            f"Supported: {list(_READERS.keys())}"
        )
    counts = reader(page)
    print(f"[stat_bar] {program} counts: {counts}")
    return counts


def validate_stat_bar(page: Page, program: str, expected: dict) -> bool:
    """
    Validate that stat bar counts on screen match expected values from TSV/StatOutput.
    Replaces: validateStatBar() in TestRunner.groovy.

    Args:
        page:     Playwright Page object
        program:  Program name
        expected: Dict of expected counts from StatOutput Excel sheet

    Returns:
        bool: True if all counts match, False if any mismatch found
    """
    actual   = read_stat_bar(page, program)
    passed   = True
    mismatches = []

    for key, exp_val in expected.items():
        act_val = actual.get(key, 0)
        if act_val != exp_val:
            mismatches.append(f"  {key}: screen={act_val}, expected={exp_val}")
            passed = False

    if passed:
        print(f"[stat_bar] PASS — all {program} stat bar counts match.")
    else:
        print(f"[stat_bar] FAIL — {program} stat bar mismatches:")
        for m in mismatches:
            print(m)

    return passed
