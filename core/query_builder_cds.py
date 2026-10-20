"""
query_builder_cds.py
Cypher query templates for CDS (General Commons / Genomic Data Commons).

All queries verified against live Memgraph schema.

Real node labels (lowercase): participant, sample, file, study
Real relationships:
  participant -[:of_study]->  study
  sample      -[:of_participant]-> participant
  file        -[:of_participant]-> participant
  file        -[:from_sample]->   sample

HOW TO ADD A NEW FILTER
-----------------------
1. Find which UI facet section the checkbox lives in (e.g. "Genomic Facet")
2. That facet maps to a node (see Facet→Node table in NODE_PREFIX below)
3. The checkbox label in snake_case IS the Memgraph property name
4. Add the property name to that node's list in NODE_PREFIX — done.

If the TC filter key differs from the Memgraph property name (e.g. short alias),
add it to FIELD_ALIASES instead.

Other apps: core/query_builder_<app>.py, registered in core/query_builders.py.
"""

NODE_PREFIX = {
    "s": [
        "phs_accession", "study_data_types", "study_name", "study_acronym",
    ],
    "p": [
        "sex", "gender", "race", "ethnicity", "sex_at_birth",
    ],
    "f": [
        "file_type", "experimental_strategy_and_data_subtypes",
    ],
    "samp": [
        "sample_type", "sample_tumor_status", "sample_anatomic_site",
    ],
    "diag": [
        "primary_diagnosis", "disease_type", "primary_site",
        "tissue_or_organ_of_origin", "morphology", "vital_status",
    ],
    "gi": [
        "platform", "instrument_model", "library_strategy",
        "library_source_molecule", "library_source_material", "library_source",
        "library_layout", "library_selection", "reference_genome_assembly",
        "methylation_platform",
    ],
}

FIELD_ALIASES = {
    "phs":              "s.phs_accession",
    "strategy":         "f.experimental_strategy_and_data_subtypes",
    "tumor_status":     "samp.sample_tumor_status",
    "library_source":   "gi.library_source",
    "reference_genome": "gi.reference_genome_assembly",
}

_FIELD_TO_NODE: dict[str, str] = {
    prop: node_var
    for node_var, props in NODE_PREFIX.items()
    for prop in props
}

_CONTAINS_FIELDS = {
    "f.experimental_strategy_and_data_subtypes",
    "s.study_data_types",
}

_EXTRA_MATCH = {
    "f.":    "MATCH (f:file)-[:of_participant]->(p)",
    "samp.": "MATCH (samp:sample)-[:of_participant]->(p)",
    "diag.": "MATCH (diag:diagnosis)-[:of_participant]->(p)",
    "gi.":   "MATCH (gi:genomic_info)-[:of_file]->(f)",
}

_EXTRA_MATCH_DEPS = {
    "gi.": "f.",
}

_ALREADY_BOUND = {
    "ParticipantsTab": {"p", "s"},
    "SamplesTab":      {"samp", "p", "s"},
    "FilesTab":        {"f", "p", "s"},
    "StatBar":         {"p", "s"},
}

_ALIAS_VAR = {
    "f.": "f", "samp.": "samp", "gi.": "gi", "diag.": "diag",
}

_CROSS_GI_TABS = {"ParticipantsTab", "SamplesTab", "StatBar"}

_CROSS_GI_EXISTS_ANCHOR = {
    "ParticipantsTab": ("p",    "of_participant"),
    "SamplesTab":      ("samp", "from_sample"),
    "StatBar":         ("p",    "of_participant"),
}

_VALUE_ALIAS = {
    "gi.library_source": {
        "Transcriptomic": "Transcriptome",
    },
    "gi.library_strategy": {
        "OTHER": "Other",
    },
    "gi.library_selection": {
        "PolyA": "Poly-A Enriched Genomic Library",
    },
}

_EXTRA_MATCH_TAB_OVERRIDE = {
    "FilesTab": {
        "samp.": "MATCH (f)-[:from_sample]->(samp:sample)",
    },
    "SamplesTab": {
        "f.": "MATCH (f:file)-[:from_sample]->(samp)",
    },
}

CYPHER_TEMPLATES = {
    "ParticipantsTab": """
MATCH (p:participant)-[:of_study]->(s:study)
{extra_match}
{where}
WITH DISTINCT p, s
OPTIONAL MATCH (samp_all:sample)-[:of_participant]->(p)
WITH p, s, samp_all
ORDER BY samp_all.sample_id ASC
WITH p, s, [x IN collect(samp_all.sample_id) WHERE x IS NOT NULL] AS sample_ids
WITH p, s, sample_ids,
  CASE
    WHEN size(sample_ids) > 5
    THEN reduce(acc = "", id IN sample_ids[0..5] | CASE WHEN acc = "" THEN id ELSE acc + ", " + id END) + ", ..."
    ELSE reduce(acc = "", id IN sample_ids | CASE WHEN acc = "" THEN id ELSE acc + ", " + id END)
  END AS samples
RETURN
  p.participant_id AS participant_id,
  s.study_name     AS study_name,
  s.phs_accession  AS accession,
  p.sex            AS sex,
  samples
ORDER BY p.participant_id ASC
        """,

    "SamplesTab": """
MATCH (samp:sample)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
{extra_match}
{where}
WITH DISTINCT samp, p, s
RETURN
  s.study_name                                          AS study_name,
  s.phs_accession                                       AS accession,
  samp.sample_id                                        AS sample_id,
  COALESCE(samp.sample_name, samp.sample_id)            AS sample_name,
  COALESCE(samp.Organization_Name, "Not specified in data") AS organization_name
ORDER BY samp.sample_id ASC
        """,

    "FilesTab": """
MATCH (f:file)-[:of_participant]->(p:participant)-[:of_study]->(s:study)
{extra_match}
{where}
WITH DISTINCT f, s
OPTIONAL MATCH (f)-[:from_sample]->(samp:sample)
WITH f, s, min(samp.sample_id) AS samp_id
RETURN
  s.study_name                          AS study_name,
  s.phs_accession                       AS accession,
  f.file_name                           AS file_name,
  f.file_id                             AS file_id,
  f.file_type                           AS file_type,
  COALESCE(samp_id, "Not Applicable")   AS sample_id
{union_study_files}
        """,

    "StatBar": """
MATCH (p:participant)-[:of_study]->(s:study)
{extra_match}
{where}
OPTIONAL MATCH (samp:sample)-[:of_participant]->(p)
OPTIONAL MATCH (f:file)-[:of_participant]->(p)
RETURN
  count(DISTINCT s)    AS Studies,
  count(DISTINCT p)    AS Participants,
  count(DISTINCT samp) AS Samples,
  count(DISTINCT f)    AS Files
        """,
}


def _resolve_field(key: str) -> str:
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    if key in _FIELD_TO_NODE:
        return f"{_FIELD_TO_NODE[key]}.{key}"
    valid = sorted(list(FIELD_ALIASES.keys()) + list(_FIELD_TO_NODE.keys()))
    raise ValueError(
        f"Unknown filter key '{key}' for CDS. "
        f"Add it to NODE_PREFIX or FIELD_ALIASES in core/query_builder_cds.py. "
        f"Valid keys: {valid}"
    )


def _build_direct_file_where(filters: dict) -> str:
    conditions = []
    for key, values in filters.items():
        field = _resolve_field(key)
        if not (field.startswith("s.") or field.startswith("f.")):
            continue
        field_aliases = _VALUE_ALIAS.get(field, {})
        resolved = [field_aliases.get(v, v) for v in values]
        if field in _CONTAINS_FIELDS:
            parts = [f"{field} CONTAINS '{v}'" for v in resolved]
            conditions.append("(" + " OR ".join(parts) + ")")
        elif len(resolved) == 1:
            conditions.append(f"{field} = '{resolved[0]}'")
        else:
            vals = ", ".join(f"'{v}'" for v in resolved)
            conditions.append(f"{field} IN [{vals}]")
    return "\n  AND ".join(conditions) if conditions else ""


def build_query(tab_name: str, filters: dict, custom_query: str = None) -> str:
    """
    Build the final Cypher query for a CDS tab and filter values.

    Args:
        tab_name:     e.g. 'ParticipantsTab', 'SamplesTab', 'FilesTab'
        filters:      dict of {key: [value, ...]} from TC Excel Filter column
        custom_query: full Cypher from TC Queries sheet (overrides template)
    """
    if custom_query:
        return custom_query.strip()

    if tab_name not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No CDS template for tab='{tab_name}'. "
            f"Add it to CYPHER_TEMPLATES in core/query_builder_cds.py."
        )

    template = CYPHER_TEMPLATES[tab_name]
    extra_match, where_clause, samp_via_from_sample = _build_clauses(tab_name, filters)

    _PARTICIPANT_PREFIXES = {"p.", "samp.", "diag.", "gi."}
    has_participant_filters = any(
        _resolve_field(k).split(".")[0] + "." in _PARTICIPANT_PREFIXES
        for k in (filters or {})
    )
    union_study_files = ""
    if tab_name == "FilesTab" and not custom_query and not has_participant_filters:
        direct_where = _build_direct_file_where(filters)
        union_where = "WHERE NOT (f)-[:of_participant]->(:participant)"
        if direct_where:
            union_where += f"\n  AND {direct_where}"
        union_study_files = f"""UNION
MATCH (f:file)-[:of_study]->(s:study)
{union_where}
WITH DISTINCT f, s
OPTIONAL MATCH (f)-[:from_sample]->(samp:sample)
WITH f, s, min(samp.sample_id) AS samp_id
RETURN
  s.study_name                          AS study_name,
  s.phs_accession                       AS accession,
  f.file_name                           AS file_name,
  f.file_id                             AS file_id,
  f.file_type                           AS file_type,
  COALESCE(samp_id, "Not Applicable")   AS sample_id"""

    query = (
        template
        .replace("{extra_match}", extra_match)
        .replace("{where}", where_clause)
        .replace("{union_study_files}", union_study_files)
        .strip()
    )
    if samp_via_from_sample and tab_name == "FilesTab":
        query = query.replace(
            "WITH DISTINCT f, s\nOPTIONAL MATCH (f)-[:from_sample]->(samp:sample)\nWITH f, s, min(samp.sample_id) AS samp_id",
            "WITH DISTINCT f, s, samp\nWITH f, s, min(samp.sample_id) AS samp_id",
            1,
        )
    return query


def _build_clauses(tab_name: str, filters: dict) -> tuple[str, str, bool]:
    if not filters:
        return "", "", False

    tab_override = _EXTRA_MATCH_TAB_OVERRIDE.get(tab_name, {})
    already_bound = _ALREADY_BOUND.get(tab_name, set())
    cross_gi_mode = tab_name in _CROSS_GI_TABS
    cross_gi_anchor = _CROSS_GI_EXISTS_ANCHOR.get(tab_name, ("p", "of_participant"))

    extra_matches_needed: set[str] = set()
    conditions: list[str] = []
    exists_conditions: list[str] = []
    samp_via_from_sample = False

    for key, values in filters.items():
        field = _resolve_field(key)
        field_aliases = _VALUE_ALIAS.get(field, {})
        resolved = [field_aliases.get(v, v) for v in values]

        if cross_gi_mode and (field.startswith("f.") or field.startswith("gi.")):
            anchor_var, anchor_rel = cross_gi_anchor
            if field.startswith("gi."):
                prop = field[3:]
                inner_match = (
                    f"MATCH ({anchor_var})<-[:{anchor_rel}]-(fe:file)"
                    f"<-[:of_file]-(gie:genomic_info)"
                )
                cond_field = f"gie.{prop}"
            else:
                prop = field[2:]
                inner_match = f"MATCH ({anchor_var})<-[:{anchor_rel}]-(fe:file)"
                cond_field = f"fe.{prop}"

            if field in _CONTAINS_FIELDS:
                inner_where = " OR ".join(f"{cond_field} CONTAINS '{v}'" for v in resolved)
            elif len(resolved) == 1:
                inner_where = f"{cond_field} = '{resolved[0]}'"
            else:
                vals = ", ".join(f"'{v}'" for v in resolved)
                inner_where = f"{cond_field} IN [{vals}]"

            exists_conditions.append(f"EXISTS {{ {inner_match} WHERE {inner_where} }}")
            continue

        for alias_prefix in _EXTRA_MATCH:
            if not field.startswith(alias_prefix):
                continue
            if _ALIAS_VAR.get(alias_prefix) in already_bound:
                continue
            extra_matches_needed.add(alias_prefix)
            if alias_prefix == "samp." and alias_prefix in tab_override:
                samp_via_from_sample = True
            dep_prefix = _EXTRA_MATCH_DEPS.get(alias_prefix)
            if dep_prefix and dep_prefix in _EXTRA_MATCH:
                dep_var = _ALIAS_VAR.get(dep_prefix)
                if dep_var not in already_bound:
                    extra_matches_needed.add(dep_prefix)
        cond_field = field

        if field in _CONTAINS_FIELDS:
            parts = [f"{cond_field} CONTAINS '{v}'" for v in resolved]
            conditions.append("(" + " OR ".join(parts) + ")")
        elif len(resolved) == 1:
            conditions.append(f"{cond_field} = '{resolved[0]}'")
        else:
            vals = ", ".join(f"'{v}'" for v in resolved)
            conditions.append(f"{cond_field} IN [{vals}]")

    _order = ["f.", "samp.", "diag.", "gi."]
    ordered = sorted(extra_matches_needed, key=lambda p: _order.index(p) if p in _order else 99)

    def _get_match_clause(pfx):
        return tab_override.get(pfx, _EXTRA_MATCH[pfx])

    std_lines = [_get_match_clause(pfx) for pfx in ordered]
    extra_match_str = "\n".join(std_lines)
    all_conditions = conditions + exists_conditions
    where_str = "WHERE " + "\n  AND ".join(all_conditions) if all_conditions else ""
    return extra_match_str, where_str, samp_via_from_sample
