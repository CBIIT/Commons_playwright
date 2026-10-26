"""
settings.py
Global configuration — base URLs per program, file paths, environment settings.

On your local machine  : defaults below are used automatically (ENV=qa).
On CI/CD (Jenkins etc) : set environment variables to override — no code change needed.

To run against prod:  export ENV=prod
To run against stage: export ENV=stage
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

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
        "qa":   os.environ.get("URL_C3DC_QA",   "https://clinicalcommons-qa.ccdi.cancer.gov"),
        "prod": os.environ.get("URL_C3DC_PROD",  "https://clinicalcommons.ccdi.cancer.gov"),
        "stage":os.environ.get("URL_C3DC_STAGE", "https://clinicalcommons-stage.ccdi.cancer.gov"),
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
        "qa":   os.environ.get("URL_CANINE_QA",   "https://caninecommons-qa.cancer.gov"),
        "prod": os.environ.get("URL_CANINE_PROD",  "https://caninecommons.cancer.gov"),
        "stage":os.environ.get("URL_CANINE_STAGE", "https://caninecommons-stage.cancer.gov"),
    },
    "ICDC": {
        "qa":   os.environ.get("URL_ICDC_QA",    os.environ.get("URL_CANINE_QA",   "https://caninecommons-qa.cancer.gov")),
        "prod": os.environ.get("URL_ICDC_PROD",  os.environ.get("URL_CANINE_PROD",  "https://caninecommons.cancer.gov")),
        "stage":os.environ.get("URL_ICDC_STAGE", os.environ.get("URL_CANINE_STAGE", "https://caninecommons-stage.cancer.gov")),
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
    "C3DC": {
        "Home":    "/",
        "Explore": "/#/exploreParticipants",
    },
    "ICDC": {
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


# ── Memgraph connection ───────────────────────────────────────────────────────
# Global (CDS / default). Per-app: MEMGRAPH_HOST_C3DC, MEMGRAPH_PASSWORD_C3DC, …
MEMGRAPH_HOST     = os.environ.get("MEMGRAPH_HOST",     "")
MEMGRAPH_PORT     = int(os.environ.get("MEMGRAPH_PORT", "7687"))
MEMGRAPH_USERNAME = os.environ.get("MEMGRAPH_USERNAME", "")
MEMGRAPH_PASSWORD = os.environ.get("MEMGRAPH_PASSWORD", "")

_C3DC_QA_HOST = "bolt://ccdi-dcc-qa-99d933a8c11c2ea3.elb.us-east-1.amazonaws.com"
_ICDC_QA_HOST = "bolt://ncidb-q600-c.nci.nih.gov"


def get_memgraph_config(program: str | None = None) -> dict:
    """Bolt settings for one commons app. C3DC and ICDC/Canine use their own clusters."""
    prog = (program or "").upper()

    def _first(*names: str, default: str = "") -> str:
        for name in names:
            val = os.environ.get(name)
            if val:
                return val
        return default

    if prog == "C3DC":
        host = _first(
            "MEMGRAPH_HOST_C3DC",
            "MEMGRAPH_ENDPOINT_C3DC",
            "memgraph_endpoint",
            default=_C3DC_QA_HOST,
        )
        user = _first("MEMGRAPH_USERNAME_C3DC", "memgraph_username", default="memgraph")
        password = _first("MEMGRAPH_PASSWORD_C3DC", "memgraph_password", default="")
        port = int(_first("MEMGRAPH_PORT_C3DC", default=str(MEMGRAPH_PORT)))
    elif prog in ("CANINE", "ICDC"):
        host = _first(
            "NEO4J_ENDPOINT_ICDC",
            "NEO4J_HOST_ICDC",
            "MEMGRAPH_HOST_CANINE",
            "MEMGRAPH_HOST_ICDC",
            default=_ICDC_QA_HOST,
        )
        user = _first(
            "NEO4J_USERNAME_ICDC",
            "MEMGRAPH_USERNAME_CANINE",
            "MEMGRAPH_USERNAME_ICDC",
            default="neo4j",
        )
        password = _first(
            "NEO4J_PASSWORD_ICDC",
            "MEMGRAPH_PASSWORD_CANINE",
            "MEMGRAPH_PASSWORD_ICDC",
            default="",
        )
        port = int(_first("NEO4J_PORT_ICDC", "MEMGRAPH_PORT_CANINE", default=str(MEMGRAPH_PORT)))
    else:
        suffix = f"_{prog}" if prog else ""
        host = _first(f"MEMGRAPH_HOST{suffix}", "MEMGRAPH_HOST", default=MEMGRAPH_HOST)
        user = _first(f"MEMGRAPH_USERNAME{suffix}", "MEMGRAPH_USERNAME", default=MEMGRAPH_USERNAME)
        password = _first(f"MEMGRAPH_PASSWORD{suffix}", "MEMGRAPH_PASSWORD", default=MEMGRAPH_PASSWORD)
        port = int(_first(f"MEMGRAPH_PORT{suffix}", default=str(MEMGRAPH_PORT)))

    return {"host": host, "port": port, "username": user, "password": password}

# ── Browser settings ─────────────────────────────────────────────────────────
BROWSER         = os.environ.get("BROWSER", "chromium")
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
DEFAULT_TIMEOUT = int(os.environ.get("DEFAULT_TIMEOUT", "30000"))
