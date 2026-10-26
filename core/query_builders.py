"""
Dispatch Cypher query building to per-app modules (query_builder_cds.py, query_builder_c3dc.py, …).
"""
from __future__ import annotations

_BUILDERS = {
    "CDS": "core.query_builder_cds",
    "C3DC": "core.query_builder_c3dc",
    "ICDC": "core.query_builder_icdc",
    "Canine": "core.query_builder_icdc",
}


def build_query(program: str, tab_name: str, filters: dict, custom_query: str = None) -> str:
    if custom_query:
        return custom_query.strip()
    mod_path = _BUILDERS.get(program)
    if not mod_path:
        known = ", ".join(sorted(_BUILDERS))
        raise KeyError(
            f"No query builder for program='{program}'. "
            f"Known programs: {known}. Add core/query_builder_<app>.py and register here."
        )
    import importlib

    mod = importlib.import_module(mod_path)
    return mod.build_query(tab_name, filters, custom_query=custom_query)
