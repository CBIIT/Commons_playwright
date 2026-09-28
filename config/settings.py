"""
settings.py
Global configuration — base URLs per program, file paths, environment settings.

On your local machine  : defaults below are used automatically (ENV=qa).
On CI/CD (Jenkins etc) : set environment variables to override — no code change needed.

To run against prod:  export ENV=prod
To run against stage: export ENV=stage
"""
import os

# ── Active environment ────────────────────────────────────────────────────────
# Set ENV=prod or ENV=stage on CI/CD. Default is qa.
ENV = os.environ.get("ENV", "qa")

# ── Base directory ────────────────────────────────────────────────────────────
COMMONS_ROOT = os.environ.get(
    "COMMONS_ROOT",
    "/Users/lollal/New_Framework/Commons_Automation"
)

# ── File paths (all derived from COMMONS_ROOT) ────────────────────────────────
INPUT_FILES_ROOT = os.environ.get(
    "INPUT_FILES_ROOT",
    os.path.join(COMMONS_ROOT, "InputFiles")
)

OUTPUT_FILES_ROOT = os.environ.get(
    "OUTPUT_FILES_ROOT",
    os.path.join(COMMONS_ROOT, "OutputFiles")
)

PYTHON_FILES_ROOT = os.environ.get(
    "PYTHON_FILES_ROOT",
    os.path.join(COMMONS_ROOT, "PythonFiles")
)

OBJECT_REPO_EXCEL = os.environ.get(
    "OBJECT_REPO_EXCEL",
    "/Users/lollal/New_Framework/Playwright_Framework/Object_Repository.xlsx"
)

# ── Program URLs per environment ──────────────────────────────────────────────
# TC Excel has NO URLs. All URLs live here.
# To add a new environment: add a key under each program (e.g. "stage").
# To override a URL on CI/CD: set the env var (e.g. URL_CDS_PROD=https://...).
_BASE_URLS = {
    "CDS": {
        "qa":   os.environ.get("URL_CDS_QA",    "https://general-qa.datacommons.cancer.gov"),
        "prod": os.environ.get("URL_CDS_PROD",   "https://datacommons.cancer.gov"),
        "stage":os.environ.get("URL_CDS_STAGE",  ""),
    },
    "CCDI": {
        "qa":   os.environ.get("URL_CCDI_QA",   ""),
        "prod": os.environ.get("URL_CCDI_PROD",  ""),
        "stage":os.environ.get("URL_CCDI_STAGE", ""),
    },
    "C3DC": {
        "qa":   os.environ.get("URL_C3DC_QA",   ""),
        "prod": os.environ.get("URL_C3DC_PROD",  ""),
        "stage":os.environ.get("URL_C3DC_STAGE", ""),
    },
    "CTDC": {
        "qa":   os.environ.get("URL_CTDC_QA",   "https://clinical.datacommons.cancer.gov"),
        "prod": os.environ.get("URL_CTDC_PROD",  "https://clinical.datacommons.cancer.gov"),
        "stage":os.environ.get("URL_CTDC_STAGE", ""),
    },
    "INS": {
        "qa":   os.environ.get("URL_INS_QA",    ""),
        "prod": os.environ.get("URL_INS_PROD",   ""),
        "stage":os.environ.get("URL_INS_STAGE",  ""),
    },
    "Bento": {
        "qa":   os.environ.get("URL_BENTO_QA",   ""),
        "prod": os.environ.get("URL_BENTO_PROD",  ""),
        "stage":os.environ.get("URL_BENTO_STAGE", ""),
    },
    "Canine": {
        "qa":   os.environ.get("URL_CANINE_QA",   "https://caninecommons.cancer.gov"),
        "prod": os.environ.get("URL_CANINE_PROD",  "https://caninecommons.cancer.gov"),
        "stage":os.environ.get("URL_CANINE_STAGE", ""),
    },
    "CCDC": {
        "qa":   os.environ.get("URL_CCDC_QA",   ""),
        "prod": os.environ.get("URL_CCDC_PROD",  ""),
        "stage":os.environ.get("URL_CCDC_STAGE", ""),
    },
    "MTP": {
        "qa":   os.environ.get("URL_MTP_QA",    ""),
        "prod": os.environ.get("URL_MTP_PROD",   ""),
        "stage":os.environ.get("URL_MTP_STAGE",  ""),
    },
}


def get_url(program: str) -> str:
    """
    Return the URL for the given program in the active environment (ENV).
    Raises ValueError if no URL is configured.
    """
    url = _BASE_URLS.get(program, {}).get(ENV, "")
    if not url:
        raise ValueError(
            f"No URL configured for program='{program}' env='{ENV}'. "
            f"Set URL_{program.upper()}_{ENV.upper()} environment variable."
        )
    return url


# ── Page paths per program ────────────────────────────────────────────────────
# Maps page name (= sheet name in Object Repository) → URL hash fragment.
# Used by navigate_to action in TC Excel: get_page_url(program, page) returns
# the full URL for that page in the active environment.
# NavBar, StatBar, Popup, Footer are global — no standalone URL.
_PAGE_PATHS = {
    "CDS": {
        "Home":       "/",
        "Data":       "/#/data",
        "About":      "/#/cancerDataService",
        "Resources":  "/#/resources",
    },
    "Canine": {
        "Home":       "/#/",
        "Explore":    "/#/explore",
        "Programs":   "/#/programs",
        "Studies":    "/#/studies",
        "Cart":       "/#/fileCentricCart",
    },
    "CTDC": {
        "Home":             "/#/",
        "Explore":          "/#/explore",
        "RequestAccess":    "/#/request-access",
        "DataModel":        "/#/data-model",
        "DataHarmonization":"/#/data-harmonization",
        "DataSubmission":   "/#/submit",
        "DataUse":          "/#/data-use",
        "CloudComputing":   "/#/cloud-computing",
        "Login":            "/#/user/login",
        "Cart":             "/#/fileCentricCart",
        "About_Purpose":    "/#/purpose",
    },
}


def get_page_url(program: str, page: str) -> str:
    """
    Return the full URL for a page within a program.
    Combines get_url(program) base with the page's hash path.

    Args:
        program: e.g. 'CDS', 'Canine', 'CTDC'
        page:    Page name matching Object Repository sheet name e.g. 'Data', 'Explore'

    Returns:
        str: Full URL e.g. 'https://general-qa.datacommons.cancer.gov/#/data'

    Raises:
        ValueError: If page not found in PAGE_PATHS for that program
    """
    path = _PAGE_PATHS.get(program, {}).get(page, "")
    if not path:
        raise ValueError(
            f"No page path configured for program='{program}' page='{page}'. "
            f"Add it to _PAGE_PATHS in settings.py."
        )
    base = get_url(program).rstrip("/")
    return base + path


# ── Browser settings ─────────────────────────────────────────────────────────
BROWSER         = os.environ.get("BROWSER", "chromium")
HEADLESS        = os.environ.get("HEADLESS", "false").lower() == "true"
DEFAULT_TIMEOUT = int(os.environ.get("DEFAULT_TIMEOUT", "30000"))
