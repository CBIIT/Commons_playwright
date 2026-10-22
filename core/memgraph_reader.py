"""
memgraph_reader.py
Connects to Memgraph via Bolt and executes Cypher.

Per-app credentials come from get_memgraph_config(program):
  C3DC → MEMGRAPH_HOST_C3DC / MEMGRAPH_PASSWORD_C3DC (QA ccdi-dcc cluster)
  CDS  → MEMGRAPH_HOST / MEMGRAPH_PASSWORD (gen-dev NLB)
"""
import atexit
import re
import threading
import time

from config.settings import get_memgraph_config

_QUERY_LOCK = threading.Lock()
_drivers: dict[str, object] = {}
_conn_lock = threading.Lock()

_MAX_RETRIES = 3
_RETRY_DELAY_S = 5


def _bolt_uri(host: str, port: int) -> str:
    host = (host or "").rstrip("/")
    if not host:
        raise ValueError("Memgraph host is empty. Set MEMGRAPH_HOST or MEMGRAPH_HOST_<APP>.")
    if not host.startswith("bolt://"):
        host = f"bolt://{host}"
    if re.search(r":\d+$", host):
        return host
    return f"{host}:{port}"


def _get_conn(program: str | None = None):
    key = (program or "default").upper()
    if key in _drivers:
        return _drivers[key]
    with _conn_lock:
        if key in _drivers:
            return _drivers[key]
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError("neo4j driver not installed. Run: pip install neo4j")

        cfg = get_memgraph_config(program)
        uri = _bolt_uri(cfg["host"], cfg["port"])
        if not cfg["password"]:
            raise ValueError(
                f"Memgraph password is empty for {key}. "
                f"Set MEMGRAPH_PASSWORD_{key} (or MEMGRAPH_PASSWORD) in .env."
            )
        driver = GraphDatabase.driver(
            uri,
            auth=(cfg["username"], cfg["password"]),
            connection_timeout=30,
            max_transaction_retry_time=0,
        )
        _drivers[key] = driver
        atexit.register(_close_all)
        print(f"[memgraph_reader] Connected ({key}) {uri}")
        return driver


def _close_all():
    for driver in list(_drivers.values()):
        try:
            driver.close()
        except Exception:
            pass
    _drivers.clear()


def query_memgraph(cypher: str, program: str | None = None) -> list[dict]:
    """
    Run Cypher against the Memgraph cluster for `program` (C3DC vs CDS).
    """

    def _execute() -> list[dict]:
        driver = _get_conn(program)
        with driver.session() as session:
            return [dict(record) for record in session.run(cypher)]

    with _QUERY_LOCK:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                rows = _execute()
                if rows or attempt == _MAX_RETRIES:
                    return rows
                print(
                    f"[memgraph_reader] DB=0 on attempt {attempt}/{_MAX_RETRIES}, "
                    f"retrying in {_RETRY_DELAY_S}s"
                )
                time.sleep(_RETRY_DELAY_S)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    print(
                        f"[memgraph_reader] Error attempt {attempt}/{_MAX_RETRIES}, "
                        f"retrying in {_RETRY_DELAY_S}s: {e}"
                    )
                    time.sleep(_RETRY_DELAY_S)
                else:
                    print(f"[memgraph_reader] All {_MAX_RETRIES} attempts failed: {e}")
        if last_exc:
            raise last_exc
        return []


def test_connection(program: str | None = None) -> bool:
    try:
        rows = query_memgraph("RETURN 1 AS ok", program=program)
        return len(rows) > 0 and rows[0].get("ok") == 1
    except Exception as e:
        print(f"[memgraph_reader] Connection failed: {e}")
        return False
