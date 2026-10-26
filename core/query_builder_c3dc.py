"""
query_builder_c3dc.py
Cypher query templates for C3DC (Childhood Cancer Clinical Data Commons).

Graph path (Explore Participants filters):
  participant -[:of_participant]-> consent_group -[:of_consent_group]-> study

Framework developer updates templates and maps when new tabs/filters are needed.
Testers use TC Filter column + optional Queries sheet override in test_runner.
"""

NODE_PREFIX = {
    "s": [
        "dbgap_accession", "study_name", "study_id", "study_phase",
    ],
    "p": [
        "sex_at_birth", "race", "ethnicity", "occupation",
    ],
    "d": [
        "diagnosis", "diagnosis_id", "disease_phase", "anatomic_site",
        "primary_diagnosis", "age_at_diagnosis",
    ],
    "sm": [
        "sample_id", "sample_type", "sample_tumor_status", "sample_anatomic_site",
    ],
    "surv": [
        "last_known_survival_status", "first_event", "cause_of_death",
    ],
}

FIELD_ALIASES = {
    "phs": "s.dbgap_accession",
}

_FIELD_TO_NODE: dict[str, str] = {
    prop: node_var
    for node_var, props in NODE_PREFIX.items()
    for prop in props
}

_EXTRA_MATCH = {
    "d.":    "MATCH (d:diagnosis)-[:of_diagnosis]->(p)",
    "sm.":   "MATCH (sm:sample)-[:of_sample]->(p)",
    "surv.": "MATCH (surv:survival)-[:of_survival]->(p)",
}

_ALREADY_BOUND = {
    "ParticipantsTab":      {"p", "s"},
    "StudiesTab":           {"p", "s"},
    "DiagnosisTab":         {"d", "p", "s"},
    "GeneticAnalysisTab":   {"g", "p", "s"},
    "TreatmentTab":         {"p", "s"},
    "TreatmentRespTab":     {"tr", "p", "s"},
    "SurvivalTab":          {"sv", "p", "s"},
    "SamplesTab":           {"sm", "p", "s"},
    "FilesTab":             {"p", "s"},
    "StatBar":              {"p", "s"},
}

# Repeated anchor for UNION tab queries (same filters on each branch).
_PARTICIPANT_STUDY_MATCH = """
MATCH (p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}"""

_ALIAS_VAR = {
    "d.": "d", "sm.": "sm", "surv.": "surv",
}

CYPHER_TEMPLATES = {
    "ParticipantsTab": """
MATCH (p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT p.participant_id AS participant_id
ORDER BY participant_id
    """,
    "StudiesTab": """
MATCH (p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT s.study_id AS study_id
ORDER BY study_id
    """,
    "DiagnosisTab": """
MATCH (d:diagnosis)-[:of_diagnosis]->(p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT d.diagnosis_id AS diagnosis_id
ORDER BY diagnosis_id
    """,
    "SamplesTab": """
MATCH (sm:sample)-[:of_sample]->(p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT sm.sample_id AS sample_id
ORDER BY sample_id
    """,
    "GeneticAnalysisTab": """
MATCH (g:genetic_analysis)-[:of_genetic_analysis]->(:sample)-[:of_sample]->(p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT g.genetic_analysis_id AS genetic_analysis_id
ORDER BY genetic_analysis_id
    """,
    "TreatmentTab": (
        _PARTICIPANT_STUDY_MATCH
        + """
MATCH (t:treatment_chemotherapy)-[:of_treatment_chemotherapy]->(p)
RETURN DISTINCT t.treatment_chemotherapy_id AS treatment_id
UNION
"""
        + _PARTICIPANT_STUDY_MATCH
        + """
MATCH (t:treatment_radiation)-[:of_treatment_radiation]->(p)
RETURN DISTINCT t.treatment_radiation_id AS treatment_id
UNION
"""
        + _PARTICIPANT_STUDY_MATCH
        + """
MATCH (t:treatment_surgery)-[:of_treatment_surgery]->(p)
RETURN DISTINCT t.treatment_surgery_id AS treatment_id
UNION
"""
        + _PARTICIPANT_STUDY_MATCH
        + """
MATCH (t:treatment_other)-[:of_treatment_other]->(p)
RETURN DISTINCT t.treatment_other_id AS treatment_id
ORDER BY treatment_id
    """
    ),
    "TreatmentRespTab": """
MATCH (tr:treatment_response)-[:of_treatment_response]->(p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT tr.treatment_response_id AS treatment_response_id
ORDER BY treatment_response_id
    """,
    "SurvivalTab": """
MATCH (sv:survival)-[:of_survival]->(p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
RETURN DISTINCT sv.survival_id AS survival_id
ORDER BY survival_id
    """,
    "FilesTab": (
        _PARTICIPANT_STUDY_MATCH
        + """
MATCH (sm:sample)-[:of_sample]->(p)
MATCH (f)-[:of_sequencing_file|of_clinical_measure_file|of_cytogenomic_file|of_generic_file|of_methylation_array_file|of_pathology_file|of_radiology_file]->(sm)
RETURN DISTINCT f.file_name AS file_name
UNION
"""
        + _PARTICIPANT_STUDY_MATCH
        + """
MATCH (fp)-[:of_clinical_measure_file|of_generic_file|of_radiology_file]->(p)
RETURN DISTINCT fp.file_name AS file_name
ORDER BY file_name
    """
    ),
    "StatBar": """
MATCH (p:participant)-[:of_participant]->(:consent_group)-[:of_consent_group]->(s:study)
{extra_match}
{where}
OPTIONAL MATCH (sm:sample)-[:of_sample]->(p)
OPTIONAL MATCH (f)-[:of_sequencing_file|of_clinical_measure_file|of_cytogenomic_file|of_generic_file|of_methylation_array_file|of_pathology_file|of_radiology_file]->(sm)
OPTIONAL MATCH (fp)-[:of_clinical_measure_file|of_generic_file|of_radiology_file]->(p)
RETURN
  count(DISTINCT s)  AS Studies,
  count(DISTINCT p)  AS Participants,
  count(DISTINCT sm) AS Samples,
  count(DISTINCT f) + count(DISTINCT fp) AS Files
    """,
}


def _resolve_field(key: str) -> str:
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    if key in _FIELD_TO_NODE:
        return f"{_FIELD_TO_NODE[key]}.{key}"
    valid = sorted(list(FIELD_ALIASES.keys()) + list(_FIELD_TO_NODE.keys()))
    raise ValueError(
        f"Unknown filter key '{key}' for C3DC. "
        f"Add it to NODE_PREFIX or FIELD_ALIASES in core/query_builder_c3dc.py. "
        f"Valid keys: {valid}"
    )


def build_query(tab_name: str, filters: dict, custom_query: str = None) -> str:
    if custom_query:
        return custom_query.strip()
    if tab_name not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No C3DC template for tab='{tab_name}'. "
            f"Add it to CYPHER_TEMPLATES in core/query_builder_c3dc.py."
        )
    template = CYPHER_TEMPLATES[tab_name]
    extra_match, where_clause = _build_clauses(tab_name, filters)
    return (
        template
        .replace("{extra_match}", extra_match)
        .replace("{where}", where_clause)
        .strip()
    )


def _build_clauses(tab_name: str, filters: dict) -> tuple[str, str]:
    if not filters:
        return "", ""

    already_bound = _ALREADY_BOUND.get(tab_name, set())
    extra_matches_needed: set[str] = set()
    conditions: list[str] = []

    for key, values in filters.items():
        field = _resolve_field(key)
        for alias_prefix in _EXTRA_MATCH:
            if not field.startswith(alias_prefix):
                continue
            if _ALIAS_VAR.get(alias_prefix) in already_bound:
                continue
            extra_matches_needed.add(alias_prefix)

        resolved = list(values)
        if len(resolved) == 1:
            conditions.append(f"{field} = '{resolved[0]}'")
        else:
            vals = ", ".join(f"'{v}'" for v in resolved)
            conditions.append(f"{field} IN [{vals}]")

    _order = ["d.", "sm.", "surv."]
    ordered = sorted(extra_matches_needed, key=lambda p: _order.index(p) if p in _order else 99)
    extra_match_str = "\n".join(_EXTRA_MATCH[pfx] for pfx in ordered)
    where_str = "WHERE " + "\n  AND ".join(conditions) if conditions else ""
    return extra_match_str, where_str
