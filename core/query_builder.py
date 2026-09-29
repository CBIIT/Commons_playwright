"""
query_builder.py
Cypher query templates for CDS per result tab — built from live Memgraph schema.

Real node labels (lowercase): participant, sample, file, study, program, diagnosis, treatment
Real relationships: participant-[:of_study]->study, sample-[:of_participant]->participant,
                    file-[:of_participant]->participant, file-[:from_sample]->sample,
                    file-[:of_study]->study, study-[:of_program]->program (tbc)

Filter key names tester uses in TC Excel Filter column (case-sensitive):
  phs       → study phs_accession   e.g.  phs=phs001437
  sex       → participant gender     e.g.  sex=Male
  gender    → participant gender     e.g.  gender=Female
  race      → participant race       e.g.  race=White
  ethnicity → participant ethnicity  e.g.  ethnicity=Hispanic
  strategy  → file experimental_strategy_and_data_subtypes  e.g.  strategy=RNA-Seq
  file_type → file file_type         e.g.  file_type=CRAM
  disease   → diagnosis disease_type e.g.  disease=Sarcoma

Framework developer updates CYPHER_TEMPLATES and FILTER_FIELD_MAP when
new programs or tabs are needed. Testers never touch this file.
"""

# ── Cypher templates ──────────────────────────────────────────────────────────
# {where} is replaced at runtime with a WHERE clause built from Filter column values.
# If no filters are provided, {where} becomes an empty string.

CYPHER_TEMPLATES = {
    "CDS": {
        "ParticipantsTab": """
            MATCH (p:participant)-[:of_study]->(s:study)
            {where}
            RETURN p.participant_id, p.gender, p.race, p.ethnicity,
                   p.sex_at_birth, s.phs_accession, s.study_name
            ORDER BY p.participant_id
        """,

        "SamplesTab": """
            MATCH (sa:sample)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
            {where}
            RETURN sa.sample_id, sa.sample_type, sa.sample_type_category,
                   sa.sample_anatomic_site, sa.sample_tumor_status,
                   p.participant_id, s.phs_accession
            ORDER BY sa.sample_id
        """,

        "FilesTab": """
            MATCH (f:file)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
            {where}
            RETURN f.file_id, f.file_name, f.file_type,
                   f.file_size, f.experimental_strategy_and_data_subtypes,
                   p.participant_id, s.phs_accession
            ORDER BY f.file_id
        """,

        "DiagnosesTab": """
            MATCH (d:diagnosis)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
            {where}
            RETURN d.diagnosis_id, d.primary_diagnosis, d.disease_type,
                   d.primary_site, d.tumor_grade, d.vital_status,
                   p.participant_id, s.phs_accession
            ORDER BY d.diagnosis_id
        """,

        "TreatmentsTab": """
            MATCH (t:treatment)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
            {where}
            RETURN t.treatment_id, t.treatment_type, t.therapeutic_agents,
                   t.treatment_outcome, p.participant_id, s.phs_accession
            ORDER BY t.treatment_id
        """,
    },
}

# ── Filter key → Cypher field mapping ─────────────────────────────────────────
# Left side  = key tester writes in Filter column of TC Excel
# Right side = actual Cypher field (node alias + property)
#
# Node aliases used above:
#   p  = participant
#   sa = sample
#   f  = file
#   s  = study
#   d  = diagnosis
#   t  = treatment

FILTER_FIELD_MAP = {
    "CDS": {
        "phs":        "s.phs_accession",
        "sex":        "p.gender",
        "gender":     "p.gender",
        "race":       "p.race",
        "ethnicity":  "p.ethnicity",
        "strategy":   "f.experimental_strategy_and_data_subtypes",
        "file_type":  "f.file_type",
        "disease":    "d.disease_type",
        "diagnosis":  "d.primary_diagnosis",
        "sample_type":"sa.sample_type",
        "tumor_status":"sa.sample_tumor_status",
    },
}


def build_query(program: str, tab_name: str, filters: dict, custom_query: str = None) -> str:
    """
    Build the final Cypher query for a given program/tab and filter values.

    Args:
        program:      e.g. 'CDS'
        tab_name:     e.g. 'ParticipantsTab', 'FilesTab'
        filters:      dict of {key: value} from TC Excel Filter column
                      e.g. {'phs': 'phs001437', 'sex': 'Unknown'}
        custom_query: full Cypher string from TC Queries sheet (one-off override).
                      If provided, filters are ignored and this is returned as-is.

    Returns:
        str: Cypher query ready to execute against Memgraph

    Raises:
        KeyError:   if program or tab_name not in CYPHER_TEMPLATES
        ValueError: if a filter key is not in FILTER_FIELD_MAP for this program
    """
    if custom_query:
        return custom_query.strip()

    if program not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No Cypher templates for program='{program}'. "
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


# Fields stored as JSON array strings — use CONTAINS instead of =
_CONTAINS_FIELDS = {"f.experimental_strategy_and_data_subtypes"}


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
                f"Add it to FILTER_FIELD_MAP in core/query_builder.py."
            )
        field = field_map[key]
        if field in _CONTAINS_FIELDS:
            conditions.append(f"{field} CONTAINS '{value}'")
        else:
            conditions.append(f"{field} = '{value}'")

    return "WHERE " + " AND ".join(conditions)
