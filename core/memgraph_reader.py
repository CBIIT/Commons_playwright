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

from config.settings import MEMGRAPH_HOST, MEMGRAPH_PORT, MEMGRAPH_USERNAME, MEMGRAPH_PASSWORD


def _get_connection():
    try:
        from neo4j import GraphDatabase
    except ImportError:
        raise ImportError(
            "neo4j driver not installed. Run: pip install neo4j"
        )

    if not MEMGRAPH_HOST:
        raise ValueError(
            "MEMGRAPH_HOST is not set. "
            "Export it as an environment variable before running."
        )

    # Build bolt URI — strip trailing slash if present
    host = MEMGRAPH_HOST.rstrip("/")
    if not host.startswith("bolt://"):
        host = f"bolt://{host}"
    uri = f"{host}:{MEMGRAPH_PORT}"

    driver = GraphDatabase.driver(
        uri,
        auth=(MEMGRAPH_USERNAME, MEMGRAPH_PASSWORD),
    )
    return driver


def query_memgraph(cypher: str) -> list[dict]:
    """
    Execute a Cypher query against Memgraph and return results as a list of dicts.

    Args:
        cypher: Cypher query string (built by query_builder.build_query)

    Returns:
        list of dicts, one per row — keys are the RETURN field names from the query

    Raises:
        ImportError:  if neo4j driver is not installed
        ValueError:   if MEMGRAPH_HOST env var is not set
        Exception:    if query fails (connection error, Cypher syntax, etc.)
    """
    driver = _get_connection()
    rows = []
    try:
        with driver.session() as session:
            result = session.run(cypher)
            for record in result:
                rows.append(dict(record))
    finally:
        driver.close()
    return rows


def test_connection() -> bool:
    """
    Quick connectivity check — returns True if Memgraph is reachable, False otherwise.
    Useful for pre-flight check before a suite run.
    """
    try:
        rows = query_memgraph("RETURN 1 AS ok")
        return len(rows) > 0 and rows[0].get("ok") == 1
    except Exception as e:
        print(f"[memgraph_reader] Connection failed: {e}")
        return False
