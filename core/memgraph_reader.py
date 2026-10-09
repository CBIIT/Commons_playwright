"""
memgraph_reader.py
Connects to Memgraph via Bolt protocol and executes Cypher queries.

Credentials are read from environment variables — never hardcoded:
  MEMGRAPH_HOST      bolt:// URL of the Memgraph NLB endpoint
  MEMGRAPH_PORT      default 7687
  MEMGRAPH_USERNAME  default memgraph
  MEMGRAPH_PASSWORD

Usage:
  from core.memgraph_reader import query_memgraph
  rows = query_memgraph(cypher_string)
  # returns list of dicts, one per row
"""

import atexit
import threading

from config.settings import MEMGRAPH_HOST, MEMGRAPH_PORT, MEMGRAPH_USERNAME, MEMGRAPH_PASSWORD

# Global lock — serializes all queries so only one runs at a time.
# Memgraph silently returns 0 rows under concurrent load, so one-at-a-time is essential.
_QUERY_LOCK = threading.Lock()

# Single persistent connection — opened once on first query, reused for all subsequent queries.
_conn = None
_conn_lock = threading.Lock()


def _get_conn():
    """Return the shared persistent neo4j driver session, creating it on first call."""
    global _conn
    if _conn is not None:
        return _conn
    with _conn_lock:
        if _conn is not None:
            return _conn
        try:
            from neo4j import GraphDatabase
        except ImportError:
            raise ImportError("neo4j driver not installed. Run: pip install neo4j")

        if not MEMGRAPH_HOST:
            raise ValueError("MEMGRAPH_HOST is not set. Export it as an environment variable before running.")

        host = MEMGRAPH_HOST.rstrip("/")
        if not host.startswith("bolt://"):
            host = f"bolt://{host}"
        uri = f"{host}:{MEMGRAPH_PORT}"

        _conn = GraphDatabase.driver(
            uri,
            auth=(MEMGRAPH_USERNAME, MEMGRAPH_PASSWORD),
            connection_timeout=30,
            max_transaction_retry_time=0,
        )
        atexit.register(_close_conn)
        print(f"[memgraph_reader] Connected to {uri}")
        return _conn


def _close_conn():
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


_MAX_RETRIES = 3
_RETRY_DELAY_S = 5


def query_memgraph(cypher: str) -> list[dict]:
    """
    Execute a Cypher query and return results as a list of dicts.

    Uses a global lock (one query at a time) and a single persistent connection
    opened once with credentials — same pattern as a global SQL con.execute().
    Retries up to 3 times on transient errors or DB=0 returns.
    """
    import time

    def _execute() -> list[dict]:
        driver = _get_conn()
        with driver.session() as session:
            result = session.run(cypher)
            return [dict(record) for record in result]

    with _QUERY_LOCK:
        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                rows = _execute()
                if rows or attempt == _MAX_RETRIES:
                    return rows
                # DB returned 0 rows — retry before accepting
                print(f"[memgraph_reader] DB=0 on attempt {attempt}/{_MAX_RETRIES}, retrying in {_RETRY_DELAY_S}s")
                time.sleep(_RETRY_DELAY_S)
            except Exception as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    print(f"[memgraph_reader] Error attempt {attempt}/{_MAX_RETRIES}, retrying in {_RETRY_DELAY_S}s: {e}")
                    time.sleep(_RETRY_DELAY_S)
                else:
                    print(f"[memgraph_reader] All {_MAX_RETRIES} attempts failed: {e}")

        if last_exc:
            raise last_exc
        return []


def test_connection() -> bool:
    try:
        rows = query_memgraph("RETURN 1 AS ok")
        return len(rows) > 0 and rows[0].get("ok") == 1
    except Exception as e:
        print(f"[memgraph_reader] Connection failed: {e}")
        return False
