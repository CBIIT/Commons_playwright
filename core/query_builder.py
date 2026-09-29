"""
query_builder.py
Cypher query templates per program/tab.
Framework developer writes templates here once — testers never touch this file.

Filter values come from the Filter column in TC Excel Steps sheet (e.g. sex=Unknown, phs=phs001437).
Runner calls build_query(program, tab_name, filters) to get the final Cypher string.

Filter key → Cypher field mapping is defined per program in FILTER_FIELD_MAP.
Tester must use the exact key names documented in FILTER_FIELD_MAP.

To add a new program:
  1. Add its templates to CYPHER_TEMPLATES
  2. Add its key→field mapping to FILTER_FIELD_MAP
"""

# ── Cypher templates ──────────────────────────────────────────────────────────
# Use {where} as the placeholder — runner replaces it with a WHERE clause
# built from the TC Excel Filter column values.
# If no filters are provided {where} is replaced with an empty string.

CYPHER_TEMPLATES = {
    "CDS": {
        "ParticipantsTab": """
            MATCH (p:Participant)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN p.participant_id, p.gender, p.race, p.ethnicity,
                   p.experimental_strategy, s.phs_accession
            ORDER BY p.participant_id
        """,
        "SamplesTab": """
            MATCH (sa:Sample)-[:FROM_PARTICIPANT]->(p:Participant)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN sa.sample_id, sa.sample_type, sa.anatomic_site,
                   p.participant_id, s.phs_accession
            ORDER BY sa.sample_id
        """,
        "FilesTab": """
            MATCH (f:File)-[:FROM_SAMPLE]->(sa:Sample)-[:FROM_PARTICIPANT]->(p:Participant)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN f.file_id, f.file_name, f.file_type, f.file_size,
                   f.experimental_strategy, s.phs_accession
            ORDER BY f.file_id
        """,
        "ProgramsTab": """
            MATCH (pr:Program)<-[:FROM_PROGRAM]-(s:Study)
            {where}
            RETURN pr.program_id, pr.program_name, count(s) AS study_count
            ORDER BY pr.program_id
        """,
        "StudiesTab": """
            MATCH (s:Study)-[:FROM_PROGRAM]->(pr:Program)
            {where}
            RETURN s.study_id, s.phs_accession, s.study_name,
                   s.study_type, pr.program_name
            ORDER BY s.phs_accession
        """,
    },
    "Canine": {
        "CasesTab": """
            MATCH (c:Case)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN c.case_id, c.breed, c.disease_term, c.sex,
                   s.clinical_study_designation
            ORDER BY c.case_id
        """,
        "SamplesTab": """
            MATCH (sa:Sample)-[:FROM_CASE]->(c:Case)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN sa.sample_id, sa.sample_type, sa.tissue_category,
                   c.case_id, s.clinical_study_designation
            ORDER BY sa.sample_id
        """,
        "FilesTab": """
            MATCH (f:File)-[:FROM_SAMPLE]->(sa:Sample)-[:FROM_CASE]->(c:Case)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN f.file_id, f.file_name, f.file_type, f.file_size,
                   s.clinical_study_designation
            ORDER BY f.file_id
        """,
    },
    "CTDC": {
        "CasesTab": """
            MATCH (c:Case)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN c.case_id, c.primary_diagnosis, c.disease_term,
                   c.gender, s.study_code
            ORDER BY c.case_id
        """,
        "FilesTab": """
            MATCH (f:File)-[:FROM_CASE]->(c:Case)-[:FROM_STUDY]->(s:Study)
            {where}
            RETURN f.file_id, f.file_name, f.file_type, f.file_size,
                   s.study_code
            ORDER BY f.file_id
        """,
    },
}

# ── Filter key → Cypher field mapping ─────────────────────────────────────────
# Tester writes Filter column as: sex=Unknown, phs=phs001437, strategy=RNA-Seq
# These keys must match exactly (case-sensitive).
# Framework developer updates this map when new filter types are needed.

FILTER_FIELD_MAP = {
    "CDS": {
        "phs":      "s.phs_accession",
        "sex":      "p.gender",
        "gender":   "p.gender",
        "race":     "p.race",
        "ethnicity":"p.ethnicity",
        "strategy": "f.experimental_strategy",
        "disease":  "p.disease_term",
        "program":  "pr.program_name",
    },
    "Canine": {
        "study":    "s.clinical_study_designation",
        "breed":    "c.breed",
        "sex":      "c.sex",
        "disease":  "c.disease_term",
        "tissue":   "sa.tissue_category",
    },
    "CTDC": {
        "study":    "s.study_code",
        "sex":      "c.gender",
        "gender":   "c.gender",
        "disease":  "c.disease_term",
        "diagnosis":"c.primary_diagnosis",
    },
}


def build_query(program: str, tab_name: str, filters: dict, custom_query: str = None) -> str:
    """
    Build the final Cypher query for a given program/tab and filter dict.

    Args:
        program:      e.g. 'CDS', 'Canine', 'CTDC'
        tab_name:     e.g. 'ParticipantsTab', 'FilesTab'
        filters:      dict of {key: value} pairs from TC Excel Filter column
                      e.g. {'phs': 'phs001437', 'sex': 'Unknown'}
        custom_query: full Cypher string from TC Queries sheet (one-off override).
                      If provided, filters are ignored and this query is returned as-is.

    Returns:
        str: final Cypher query ready to execute

    Raises:
        KeyError: if program or tab_name not found in CYPHER_TEMPLATES
        ValueError: if a filter key is not mapped in FILTER_FIELD_MAP for this program
    """
    if custom_query:
        return custom_query.strip()

    if program not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No Cypher templates defined for program='{program}'. "
            f"Add it to CYPHER_TEMPLATES in core/query_builder.py."
        )
    if tab_name not in CYPHER_TEMPLATES[program]:
        raise KeyError(
            f"No Cypher template for program='{program}' tab='{tab_name}'. "
            f"Add it to CYPHER_TEMPLATES['{program}'] in core/query_builder.py."
        )

    template = CYPHER_TEMPLATES[program][tab_name]
    where_clause = _build_where(program, filters)
    return template.replace("{where}", where_clause).strip()


def _build_where(program: str, filters: dict) -> str:
    if not filters:
        return ""

    field_map = FILTER_FIELD_MAP.get(program, {})
    conditions = []
    for key, value in filters.items():
        if key not in field_map:
            raise ValueError(
                f"Unknown filter key '{key}' for program='{program}'. "
                f"Allowed keys: {list(field_map.keys())}. "
                f"Update FILTER_FIELD_MAP in core/query_builder.py to add it."
            )
        field = field_map[key]
        conditions.append(f"{field} = '{value}'")

    return "WHERE " + " AND ".join(conditions)
