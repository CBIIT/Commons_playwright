"""
query_builder.py
Cypher query templates for CDS per result tab.
All queries verified against live Memgraph schema.

Real node labels (lowercase): participant, sample, file, study
Real relationships:
  participant -[:of_study]->  study
  sample      -[:of_participant]-> participant
  file        -[:of_participant]-> participant
  file        -[:from_sample]->   sample

Filter keys tester writes in TC Excel Filter column (case-sensitive):
  phs          → s.phs_accession        e.g. phs=phs001437
  sex          → p.sex                  e.g. sex=Male
  gender       → p.gender               e.g. gender=Female
  race         → p.race                 e.g. race=White
  ethnicity    → p.ethnicity
  file_type    → f.file_type            e.g. file_type=CRAM
  strategy     → f.experimental_strategy_and_data_subtypes  e.g. strategy=RNA-Seq
  sample_type  → samp.sample_type       e.g. sample_type=DNA
  tumor_status → samp.sample_tumor_status

NOTE: strategy uses CONTAINS because the field is stored as a JSON array string e.g. ["RNA-Seq","WXS"]
NOTE: filters on file/sample fields inject an extra MATCH clause automatically — tester does not need to worry about this.

Framework developer updates templates and maps when new programs/tabs are needed.
Testers never touch this file.
"""

# ── Filter key → Cypher field ─────────────────────────────────────────────────
# Right side = exact Cypher node alias + property as used in templates below.

FILTER_FIELD_MAP = {
    "CDS": {
        "phs":          "s.phs_accession",
        "sex":          "p.sex",
        "gender":       "p.gender",
        "race":         "p.race",
        "ethnicity":    "p.ethnicity",
        "file_type":    "f.file_type",
        "strategy":     "f.experimental_strategy_and_data_subtypes",
        "sample_type":  "samp.sample_type",
        "tumor_status": "samp.sample_tumor_status",
    },
}

# Fields that need CONTAINS instead of = (stored as JSON array strings in Memgraph)
_CONTAINS_FIELDS = {"f.experimental_strategy_and_data_subtypes"}

# Extra MATCH clauses required when a filter references a node not in the base template.
# Key = Cypher node alias prefix used in FILTER_FIELD_MAP above.
_EXTRA_MATCH = {
    "CDS": {
        "f.":    "MATCH (f:file)-[:of_participant]->(p)",
        "samp.": "MATCH (samp:sample)-[:of_participant]->(p)",
    }
}

# ── Query templates ───────────────────────────────────────────────────────────
# {extra_match} → injected MATCH clauses for cross-node filters (may be empty)
# {where}       → WHERE clause built from Filter column values

CYPHER_TEMPLATES = {
    "CDS": {
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
OPTIONAL MATCH (f)-[:from_sample]->(samp:sample)
RETURN
  s.study_name                              AS study_name,
  s.phs_accession                           AS accession,
  f.file_name                               AS file_name,
  f.file_id                                 AS file_id,
  f.file_type                               AS file_type,
  COALESCE(samp.sample_id, "Not Applicable") AS sample_id
ORDER BY f.file_name ASC
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
    },
}


def build_query(program: str, tab_name: str, filters: dict, custom_query: str = None) -> str:
    """
    Build the final Cypher query for a given program/tab and filter values.

    Args:
        program:      e.g. 'CDS'
        tab_name:     e.g. 'ParticipantsTab', 'SamplesTab', 'FilesTab'
        filters:      dict of {key: [value, ...]} from TC Excel Filter column
                      e.g. {'phs': ['phs001437'], 'sex': ['Unknown', 'Male']}
        custom_query: full Cypher string from TC Queries sheet (one-off override).
                      If provided, filters are ignored.

    Returns:
        str: Cypher query ready to run against Memgraph

    Raises:
        KeyError:   if program or tab_name not in CYPHER_TEMPLATES
        ValueError: if a filter key is not in FILTER_FIELD_MAP for this program
    """
    if custom_query:
        return custom_query.strip()

    if program not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No templates for program='{program}'. "
            f"Add it to CYPHER_TEMPLATES in core/query_builder.py."
        )
    if tab_name not in CYPHER_TEMPLATES[program]:
        raise KeyError(
            f"No template for program='{program}' tab='{tab_name}'. "
            f"Add it to CYPHER_TEMPLATES['{program}'] in core/query_builder.py."
        )

    template = CYPHER_TEMPLATES[program][tab_name]
    extra_match, where_clause = _build_clauses(program, tab_name, filters)
    return (
        template
        .replace("{extra_match}", extra_match)
        .replace("{where}", where_clause)
        .strip()
    )


def _build_clauses(program: str, tab_name: str, filters: dict):
    """Return (extra_match_str, where_str) for the given filters."""
    if not filters:
        return "", ""

    field_map  = FILTER_FIELD_MAP.get(program, {})
    extra_map  = _EXTRA_MATCH.get(program, {})

    # Determine which base nodes are already in this tab's template
    # so we don't inject a duplicate MATCH
    template   = CYPHER_TEMPLATES[program][tab_name]
    conditions = []
    extra_matches_needed = set()

    for key, values in filters.items():
        if key not in field_map:
            raise ValueError(
                f"Unknown filter key '{key}' for program='{program}'. "
                f"Allowed: {list(field_map.keys())}. "
                f"Update FILTER_FIELD_MAP in core/query_builder.py."
            )
        field = field_map[key]

        # Check if this field's node alias needs an extra MATCH injected
        for alias_prefix, match_clause in extra_map.items():
            if field.startswith(alias_prefix) and match_clause not in template:
                extra_matches_needed.add(match_clause)

        # Build condition — single value uses = or CONTAINS, multiple uses IN
        if field in _CONTAINS_FIELDS:
            parts = [f"{field} CONTAINS '{v}'" for v in values]
            conditions.append("(" + " OR ".join(parts) + ")")
        elif len(values) == 1:
            conditions.append(f"{field} = '{values[0]}'")
        else:
            vals = ", ".join(f"'{v}'" for v in values)
            conditions.append(f"{field} IN [{vals}]")

    extra_match_str = "\n".join(sorted(extra_matches_needed))
    where_str = "WHERE " + "\n  AND ".join(conditions) if conditions else ""
    return extra_match_str, where_str
