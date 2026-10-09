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

HOW TO ADD A NEW FILTER
-----------------------
1. Find which UI facet section the checkbox lives in (e.g. "Genomic Facet")
2. That facet maps to a node (see Facet→Node table in NODE_PREFIX below)
3. The checkbox label in snake_case IS the Memgraph property name
   (e.g. "Library Source Molecule" → library_source_molecule)
4. Add the property name to that node's list in NODE_PREFIX — done.

If the TC filter key differs from the Memgraph property name (e.g. short alias),
add it to FIELD_ALIASES instead.

Framework developer updates templates and maps when new programs/tabs are needed.
Testers never touch this file.
"""

# ── Node prefix mapping ───────────────────────────────────────────────────────
# Maps Cypher node alias → list of Memgraph property names on that node.
# Property names verified against live Memgraph schema.
#
# Facet → Node:
#   Study Facet        → s    (study)
#   Demographics Facet → p    (participant)
#   Files Facet        → f    (file)
#   Samples Facet      → samp (sample)
#   Diagnosis Facet    → diag (diagnosis)
#   Genomic Facet      → gi   (genomic_info)
NODE_PREFIX = {
    "CDS": {
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
}

# ── Short aliases — TC filter key → Cypher field ──────────────────────────────
# Only needed when the TC filter key differs from the actual Memgraph property name.
# Right side = "node_alias.property" exactly as used in Cypher.
#
FIELD_ALIASES = {
    "CDS": {
        "phs":              "s.phs_accession",
        "strategy":         "f.experimental_strategy_and_data_subtypes",
        "tumor_status":     "samp.sample_tumor_status",
        "library_source":   "gi.library_source",
        "reference_genome": "gi.reference_genome_assembly",
    }
}

# Build reverse lookup: property_name → node_alias  (built once at import time)
_FIELD_TO_NODE: dict[str, dict[str, str]] = {
    prog: {
        prop: node_var
        for node_var, props in nodes.items()
        for prop in props
    }
    for prog, nodes in NODE_PREFIX.items()
}


def _resolve_field(program: str, key: str) -> str:
    """Resolve a TC filter key to 'node_alias.property' for Cypher."""
    aliases = FIELD_ALIASES.get(program, {})
    if key in aliases:
        return aliases[key]
    node_map = _FIELD_TO_NODE.get(program, {})
    if key in node_map:
        return f"{node_map[key]}.{key}"
    valid = sorted(list(aliases.keys()) + list(node_map.keys()))
    raise ValueError(
        f"Unknown filter key '{key}' for program='{program}'. "
        f"Add it to NODE_PREFIX or FIELD_ALIASES in core/query_builder.py. "
        f"Valid keys: {valid}"
    )

# Fields that need CONTAINS instead of = (stored as JSON array strings in Memgraph)
_CONTAINS_FIELDS = {
    "f.experimental_strategy_and_data_subtypes",
    "s.study_data_types",
}

# Extra MATCH clauses required when a filter references a node not in the base template.
# Key = Cypher node alias prefix used in FILTER_FIELD_MAP above.
_EXTRA_MATCH = {
    "CDS": {
        "f.":    "MATCH (f:file)-[:of_participant]->(p)",
        "samp.": "MATCH (samp:sample)-[:of_participant]->(p)",
        "diag.": "MATCH (diag:diagnosis)-[:of_participant]->(p)",
        "gi.":   "MATCH (gi:genomic_info)-[:of_file]->(f)",
    }
}

# Some extra MATCH clauses depend on another node being in scope first.
# e.g. gi requires f; if f is not in the template either, f's MATCH must also be injected.
_EXTRA_MATCH_DEPS = {
    "CDS": {
        "gi.": "f.",   # gi-[:of_file]->(f) requires f to be bound
    }
}

# Variables already bound by the base template for each tab — never inject a MATCH
# for these even if the standalone-check heuristic would otherwise fire.
_ALREADY_BOUND = {
    "CDS": {
        "ParticipantsTab": {"p", "s"},
        "SamplesTab":      {"samp", "p", "s"},
        "FilesTab":        {"f", "p", "s"},
        "StatBar":         {"p", "s"},
    }
}

# Maps alias prefix → the variable name it binds (used with _ALREADY_BOUND).
_ALIAS_VAR = {"f.": "f", "samp.": "samp", "gi.": "gi", "diag.": "diag"}

# Tabs where each gi.* (and f.*) filter condition is evaluated on SEPARATE file/gi nodes
# rather than requiring all conditions to match the SAME genomic_info node.
# This mirrors the CDS portal's cross-file filter semantics.
_CROSS_GI_TABS = {
    "CDS": {"ParticipantsTab", "SamplesTab", "StatBar"}
}

# EXISTS subquery anchor for cross-gi mode.
# Each genomic condition becomes an EXISTS { MATCH ... WHERE ... } clause,
# so Memgraph short-circuits after finding the FIRST matching file rather than
# enumerating ALL (f1,gi1)×(f2,gi2)×… combinations (which is O(N^K) in files).
# Template vars: {anchor} = node already in scope (p or samp), {rel} = relationship.
_CROSS_GI_EXISTS_ANCHOR = {
    "CDS": {
        "ParticipantsTab": ("p",    "of_participant"),
        "SamplesTab":      ("samp", "from_sample"),
        "StatBar":         ("p",    "of_participant"),
    }
}

# Keep for backward-compat reference — no longer used for MATCH generation.
_CROSS_GI_FILE_MATCH = {
    "CDS": {
        "ParticipantsTab": "MATCH (f{n}:file)-[:of_participant]->(p)",
        "SamplesTab":      "MATCH (f{n}:file)-[:from_sample]->(samp)",
        "StatBar":         "MATCH (f{n}:file)-[:of_participant]->(p)",
    }
}

# Tab-specific overrides for extra MATCH clauses.
# Used when the standard participant-based join is incorrect for a specific tab.
# FilesTab: when sample filters are applied, join file→sample directly (from_sample)
# so we only return files actually linked to the matching samples, not all files
# of any participant who has a matching sample.
# Value aliases: map UI-displayed filter values to the actual stored Memgraph values.
# Used when the UI shows a different label than the stored property value.
_VALUE_ALIAS = {
    "CDS": {
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
}

_EXTRA_MATCH_TAB_OVERRIDE = {
    "CDS": {
        # FilesTab: sample filters must join file→sample directly so we only return
        # files actually linked to the matching samples.
        "FilesTab": {
            "samp.": "MATCH (f)-[:from_sample]->(samp:sample)",
        },
        # SamplesTab: file/genomic filters must join file→sample directly so we only
        # return samples that are directly linked to matching files.
        "SamplesTab": {
            "f.": "MATCH (f:file)-[:from_sample]->(samp)",
        },
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
    },
}


def _build_direct_file_where(program: str, filters: dict) -> str:
    """Return WHERE conditions applicable to study-level files (s.* and f.* fields only).

    Study-level files have no participant/sample/genomic nodes, so only study and
    file property filters can be applied to them in the UNION branch.
    """
    alias_map = _VALUE_ALIAS.get(program, {})
    conditions = []
    for key, values in filters.items():
        field = _resolve_field(program, key)
        if not (field.startswith("s.") or field.startswith("f.")):
            continue
        field_aliases = alias_map.get(field, {})
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
    extra_match, where_clause, samp_via_from_sample = _build_clauses(program, tab_name, filters)

    # Build UNION branch for study-level files (no participant link) — FilesTab only.
    # Some files are attached directly to a study (e.g. reference BED files) with only
    # (f)-[:of_study]->(s) and no [:of_participant] edge. The main branch misses them.
    union_study_files = ""
    if tab_name == "FilesTab" and not custom_query:
        direct_where = _build_direct_file_where(program, filters)
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
    # When FilesTab joins samp via from_sample, the template's OPTIONAL MATCH for samp
    # is no longer needed (samp is already bound and deduped). Replace the two-line
    # "WITH DISTINCT f, p, s\nOPTIONAL MATCH (f)-[:from_sample]->(samp:sample)" block
    # with "WITH DISTINCT f, p, s, samp" to preserve samp and avoid re-expansion.
    if samp_via_from_sample and tab_name == "FilesTab":
        # samp is already bound by the injected MATCH (f)-[:from_sample]->(samp:sample).
        # Replace the OPTIONAL MATCH + min() aggregation block with a direct carry-through.
        query = query.replace(
            "WITH DISTINCT f, s\nOPTIONAL MATCH (f)-[:from_sample]->(samp:sample)\nWITH f, s, min(samp.sample_id) AS samp_id",
            "WITH DISTINCT f, s, samp\nWITH f, s, min(samp.sample_id) AS samp_id",
            1  # replace only the first occurrence (main branch, not the UNION branch)
        )
    return query


def _build_clauses(program: str, tab_name: str, filters: dict):
    """Return (extra_match_str, where_str, samp_via_from_sample) for the given filters.

    samp_via_from_sample is True when FilesTab samp. filters are injected via the
    from_sample relationship override — callers must adjust the template accordingly.

    For tabs in _CROSS_GI_TABS, each f.* and gi.* filter condition gets its own
    numbered file+gi MATCH pair (f1+gi1, f2+gi2, …) so conditions on different
    genomic_info nodes are satisfied independently, matching CDS portal semantics.
    """
    if not filters:
        return "", "", False

    extra_map        = _EXTRA_MATCH.get(program, {})
    dep_map          = _EXTRA_MATCH_DEPS.get(program, {})
    tab_override     = _EXTRA_MATCH_TAB_OVERRIDE.get(program, {}).get(tab_name, {})
    already_bound    = _ALREADY_BOUND.get(program, {}).get(tab_name, set())
    alias_map        = _VALUE_ALIAS.get(program, {})
    cross_gi_mode    = tab_name in _CROSS_GI_TABS.get(program, set())
    cross_gi_anchor  = _CROSS_GI_EXISTS_ANCHOR.get(program, {}).get(tab_name, ("p", "of_participant"))

    extra_matches_needed = set()
    conditions           = []   # plain WHERE conditions (non-cross-gi)
    exists_conditions    = []   # EXISTS { } subqueries (cross-gi)
    samp_via_from_sample = False

    for key, values in filters.items():
        field = _resolve_field(program, key)

        # Apply value aliases (UI label → stored Memgraph value)
        field_aliases = alias_map.get(field, {})
        resolved = [field_aliases.get(v, v) for v in values]

        # Cross-gi mode: f.* and gi.* each become an EXISTS { } subquery so that
        # Memgraph short-circuits on the first match rather than enumerating all
        # (f1,gi1)×(f2,gi2)×… combinations (which grows as O(files_per_node^K)).
        if cross_gi_mode and (field.startswith("f.") or field.startswith("gi.")):
            anchor_var, anchor_rel = cross_gi_anchor
            if field.startswith("gi."):
                prop = field[3:]
                # Single chained path — Memgraph rejects comma-separated patterns
                # and multiple MATCHes inside EXISTS { }.
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

            exists_conditions.append(
                f"EXISTS {{ {inner_match} WHERE {inner_where} }}"
            )
            continue
        else:
            # Standard injection: look up which extra MATCH clauses are needed.
            for alias_prefix in extra_map:
                if not field.startswith(alias_prefix):
                    continue
                if _ALIAS_VAR.get(alias_prefix) in already_bound:
                    continue
                extra_matches_needed.add(alias_prefix)
                if alias_prefix == "samp." and alias_prefix in tab_override:
                    samp_via_from_sample = True
                dep_prefix = dep_map.get(alias_prefix)
                if dep_prefix and dep_prefix in extra_map:
                    dep_var = _ALIAS_VAR.get(dep_prefix)
                    if dep_var not in already_bound:
                        extra_matches_needed.add(dep_prefix)
            cond_field = field

        # Build WHERE condition — check _CONTAINS_FIELDS by original field name.
        if field in _CONTAINS_FIELDS:
            parts = [f"{cond_field} CONTAINS '{v}'" for v in resolved]
            conditions.append("(" + " OR ".join(parts) + ")")
        elif len(resolved) == 1:
            conditions.append(f"{cond_field} = '{resolved[0]}'")
        else:
            vals = ", ".join(f"'{v}'" for v in resolved)
            conditions.append(f"{cond_field} IN [{vals}]")

    # Standard injection order: f. and samp. and diag. bind to p; gi. binds to f.
    _ORDER = ["f.", "samp.", "diag.", "gi."]
    ordered = sorted(extra_matches_needed, key=lambda p: _ORDER.index(p) if p in _ORDER else 99)

    def _get_match_clause(pfx):
        return tab_override.get(pfx, extra_map[pfx])

    std_lines = [_get_match_clause(pfx) for pfx in ordered]
    extra_match_str = "\n".join(std_lines)
    all_conditions = conditions + exists_conditions
    where_str = "WHERE " + "\n  AND ".join(all_conditions) if all_conditions else ""
    return extra_match_str, where_str, samp_via_from_sample
