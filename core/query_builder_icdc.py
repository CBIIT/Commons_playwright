"""
query_builder_icdc.py
Cypher templates for ICDC (Integrated Canine Data Commons).

Graph (icdc-fe-be/icdc-dataloader-master/examples/icdc/data-model/icdc-model.yml):
  (program)<-[:member_of]-(study)<-[:member_of]-(case)
  (demographic|diagnosis|sample|file|registration)-[:of_case]->(case)
  (file)-[:of_sample]->(sample)
  (file)-[:of_study]->(study)

Explore filters (dashboardData.jsx / es_indices_icdc.yml) map to:
  study.clinical_study_designation, study.clinical_study_type
  demographic.breed / sex / neutered_indicator
  diagnosis.disease_term / primary_disease_site / stage_of_disease / best_response
  registration.registration_origin  (biobank)
  sample.sample_site / summarized_sample_type / specific_sample_pathology
  file.file_type / file_format / file association via parent label

Registered as ICDC (Canine is a backward-compatible alias) in query_builders.py.
"""
from __future__ import annotations

NODE_PREFIX = {
    "s": [
        "clinical_study_designation", "clinical_study_type", "clinical_study_name",
    ],
    "demo": [
        "breed", "sex", "neutered_indicator",
    ],
    "diag": [
        "disease_term", "primary_disease_site", "stage_of_disease", "best_response",
    ],
    "samp": [
        "sample_site", "summarized_sample_type", "specific_sample_pathology",
    ],
    "f": [
        "file_type", "file_format",
    ],
}

FIELD_ALIASES = {
    "study": "s.clinical_study_designation",
    "study_code": "s.clinical_study_designation",
    "study_type": "s.clinical_study_type",
    "diagnosis": "diag.disease_term",
    "primary_disease_site": "diag.primary_disease_site",
    "disease_site": "diag.primary_disease_site",
    "response_to_treatment": "diag.best_response",
    "neutered_status": "demo.neutered_indicator",
    "sample_type": "samp.summarized_sample_type",
    "sample_pathology": "samp.specific_sample_pathology",
    "biobank": "__biobank__",
    "file_association": "__file_association__",
}

_FIELD_TO_NODE: dict[str, str] = {
    prop: node_var
    for node_var, props in NODE_PREFIX.items()
    for prop in props
}

_VALUE_ALIAS = {
    "diag.disease_term": {
        "Osteosacroma": "Osteosarcoma",
        "UrothelCarcinoma": "Urothelial Carcinoma",
        "UrothelialCarcinoma": "Urothelial Carcinoma",
        "BCellLymphoma": "B-Cell Lymphoma",
        "B Cell Lymphoma": "B-Cell Lymphoma",
        "MammaryCancer": "Mammary Cancer",
        "BladderCancer": "Bladder Cancer",
        "HealthyControl": "Healthy Control",
        "PulmonaryNeoplasms": "Pulmonary Neoplasms",
    },
    "diag.primary_disease_site": {
        "UrogenitalTract": "Urogenital Tract",
        "BoneAppend": "Bone - Appendicular",
        "BoneAppendicular": "Bone - Appendicular",
        "Bone (Appendicular)": "Bone - Appendicular",
        "BoneAxial": "Bone - Axial",
        "Bone (Axial)": "Bone - Axial",
        "LymphNode": "Lymph Node",
        "MammaryGland": "Mammary Gland",
    },
    "diag.best_response": {
        "NotDetermined": "Not Determined",
        "NotApplicable": "Not Applicable",
        "ProgressiveDisease": "Progressive Disease",
        "ProgresDisease": "Progressive Disease",
        "CompleteResponce": "Complete Response",
        "CompleteResponse": "Complete Response",
        "PartialResponse": "Partial Response",
        "StableDisease": "Stable Disease",
    },
    "diag.stage_of_disease": {
        "NotDetermined": "Not Determined",
        "NotApplicable": "Not Applicable",
    },
    "s.clinical_study_type": {
        "ClinicalTrial": "Clinical Trial",
        "TreatmentStudy": "Treatment Study",
        "GenomTranscrip": "Genomics/Transcriptomics",
        "GenomicsTranscriptomics": "Genomics/Transcriptomics",
        "TranscrpGenomics": "Transcriptomics/Genomics",
        "Transcrip": "Transcriptomics",
    },
    "demo.breed": {
        "BassetHound": "Basset Hound",
        "SaintBernard": "Saint Bernard",
        "DobermanPinscher": "Doberman Pinscher",
        "BostonTerrier": "Boston Terrier",
        "LabradorRetriever": "Labrador Retriever",
        "BouvierDesFlandres": "Bouvier des Flandres",
        "GermanShthrPntr": "German Shorthaired Pointer",
        "GermanShorthairedPointer": "German Shorthaired Pointer",
        "GermanShepherdDog": "German Shepherd Dog",
        "GermanShepDog": "German Shepherd Dog",
        "GoldenRetriever": "Golden Retriever",
        "GreatPyrenees": "Great Pyrenees",
        "MixedBreed": "Mixed Breed",
        "ScottishTerrier": "Scottish Terrier",
        "BelgianSheepdog": "Belgian Sheepdog",
        "AlaskanMalamute": "Alaskan Malamute",
        "AfghanHound": "Afghan Hound",
        "BerMountDog": "Bernese Mountain Dog",
        "BerneseMountainDog": "Bernese Mountain Dog",
    },
    "__biobank__": {
        "NotApplicable": "Not Applicable",
        "UCD-SVM": "UCD SVM",
        "UCD SVM": "UCD SVM",
    },
}

_CORE = """
MATCH (s:study{study_pred})
MATCH (c:case)-[:member_of]->(s)
MATCH (p:program)<-[:member_of]-(s)
MATCH (demo:demographic)-[:of_case]->(c)
MATCH (diag:diagnosis)-[:of_case]->(c)
{extra_match}
{where}"""

CYPHER_TEMPLATES = {
    "CasesTab": _CORE + """
RETURN DISTINCT c.case_id AS case_id
ORDER BY case_id
    """,
    "SamplesTab": _CORE + """
MATCH (samp:sample)-[:of_case]->(c)
RETURN DISTINCT samp.sample_id AS sample_id
ORDER BY sample_id
    """,
    "CaseFilesTab": _CORE + """
MATCH (samp:sample)-[:of_case]->(c)
MATCH (f:file)-[:of_sample]->(samp)
RETURN DISTINCT f.file_name AS file_name
ORDER BY file_name
    """,
    "StudyFilesTab": _CORE + """
WITH DISTINCT s
MATCH (sf:file)-[:of_study]->(s)
RETURN DISTINCT sf.file_name AS file_name
ORDER BY file_name
    """,
    "StatBar": _CORE + """
WITH DISTINCT c, s, p
OPTIONAL MATCH (samp:sample)-[:of_case]->(c)
OPTIONAL MATCH (f:file)-[:of_sample]->(samp)
OPTIONAL MATCH (sf:file)-[:of_study]->(s)
RETURN
  count(DISTINCT p.program_acronym) AS Programs,
  count(DISTINCT s.clinical_study_designation) AS Studies,
  count(DISTINCT c.case_id) AS Cases,
  count(DISTINCT samp) AS Samples,
  count(DISTINCT f) AS `Case Files`,
  count(DISTINCT sf) AS `Study Files`
    """,
}


def _esc(val: str) -> str:
    return (val or "").replace("\\", "\\\\").replace("'", "\\'")


def _resolve_field(key: str) -> str:
    if key in FIELD_ALIASES:
        return FIELD_ALIASES[key]
    if key in _FIELD_TO_NODE:
        return f"{_FIELD_TO_NODE[key]}.{key}"
    valid = sorted(list(FIELD_ALIASES.keys()) + list(_FIELD_TO_NODE.keys()))
    raise ValueError(
        f"Unknown filter key '{key}' for ICDC. "
        f"Add it to NODE_PREFIX or FIELD_ALIASES in core/query_builder_icdc.py. "
        f"Valid keys: {valid}"
    )


def _alias_values(field: str, values: list[str]) -> list[str]:
    table = _VALUE_ALIAS.get(field, {})
    return [table.get(v, v) for v in values]


def _eq_or_in(field: str, values: list[str]) -> str:
    resolved = _alias_values(field, values)
    if len(resolved) == 1:
        return f"{field} = '{_esc(resolved[0])}'"
    vals = ", ".join(f"'{_esc(v)}'" for v in resolved)
    return f"{field} IN [{vals}]"


def _biobank_clause(values: list[str]) -> str:
    resolved = _alias_values("__biobank__", values)
    parts = []
    for val in resolved:
        if val == "Not Applicable":
            parts.append(
                """NOT EXISTS {
  MATCH (r:registration)-[:of_case]->(c)
  WHERE r.registration_origin IS NOT NULL AND r.registration_origin <> s.clinical_study_designation
}"""
            )
        else:
            parts.append(
                f"""EXISTS {{
  MATCH (r:registration)-[:of_case]->(c)
  WHERE r.registration_origin = '{_esc(val)}'
}}"""
            )
    return "(" + " OR ".join(parts) + ")" if len(parts) > 1 else parts[0]


def _file_association_clause(values: list[str]) -> str:
    resolved = [v.lower() for v in values]
    parts = []
    for val in resolved:
        if val == "sample":
            parts.append(
                "EXISTS { MATCH (fe:file)-[:of_sample]->(samp2:sample)-[:of_case]->(c) }"
            )
        elif val == "case":
            parts.append("EXISTS { MATCH (fe:file)-[:of_case]->(c) }")
        elif val == "diagnosis":
            parts.append("EXISTS { MATCH (fe:file)-[:from_diagnosis]->(diag) }")
        elif val == "study":
            parts.append("EXISTS { MATCH (fe:file)-[:of_study]->(s) }")
        else:
            parts.append(
                f"EXISTS {{ MATCH (fe:file)-->(parent) WHERE toLower(head(labels(parent))) = '{_esc(val)}' "
                f"AND ((parent)-[:of_case]->(c) OR (parent)-[:of_study]->(s) OR parent = c OR parent = s) }}"
            )
    return "(" + " OR ".join(parts) + ")" if len(parts) > 1 else parts[0]


def _file_format_clause(values: list[str]) -> str:
    resolved = [v.lower().lstrip(".") for v in values]
    ors = []
    for val in resolved:
        ors.append(
            f"(toLower(coalesce(f.file_format, '')) = '{_esc(val)}' "
            f"OR toLower(coalesce(f.file_name, '')) ENDS WITH '.{_esc(val)}')"
        )
    inner = " OR ".join(ors)
    return (
        f"EXISTS {{ MATCH (f:file)-[:of_sample]->(samp2:sample)-[:of_case]->(c) WHERE {inner} }}"
    )


def build_query(tab_name: str, filters: dict, custom_query: str = None) -> str:
    if custom_query:
        return custom_query.strip()
    if tab_name not in CYPHER_TEMPLATES:
        raise KeyError(
            f"No ICDC template for tab='{tab_name}'. "
            f"Add it to CYPHER_TEMPLATES in core/query_builder_icdc.py."
        )
    study_pred, extra_match, where_clause = _build_clauses(tab_name, filters or {})
    return (
        CYPHER_TEMPLATES[tab_name]
        .replace("{study_pred}", study_pred)
        .replace("{extra_match}", extra_match)
        .replace("{where}", where_clause)
        .strip()
    )


def _build_clauses(tab_name: str, filters: dict) -> tuple[str, str, str]:
    study_vals: list[str] = []
    extra_matches: list[str] = []
    conditions: list[str] = []
    already_has_sample = tab_name in {"SamplesTab", "CaseFilesTab"}
    already_has_file = tab_name == "CaseFilesTab"

    for key, values in filters.items():
        if not values:
            continue
        field = _resolve_field(key)
        if field == "s.clinical_study_designation":
            study_vals = _alias_values(field, list(values))
            continue
        if field == "__biobank__":
            conditions.append(_biobank_clause(list(values)))
            continue
        if field == "__file_association__":
            conditions.append(_file_association_clause(list(values)))
            continue
        if field == "f.file_format":
            conditions.append(_file_format_clause(list(values)))
            continue
        if field.startswith("samp.") and not already_has_sample:
            extra_matches.append("MATCH (samp:sample)-[:of_case]->(c)")
            already_has_sample = True
        if field.startswith("f.") and not already_has_file:
            extra_matches.append("MATCH (samp_f:sample)-[:of_case]->(c)")
            extra_matches.append("MATCH (f:file)-[:of_sample]->(samp_f)")
            already_has_file = True
            if field == "f.file_type":
                conditions.append(_eq_or_in("f.file_type", list(values)))
                continue
        conditions.append(_eq_or_in(field, list(values)))

    if len(study_vals) == 1:
        study_pred = f" {{clinical_study_designation: '{_esc(study_vals[0])}'}}"
    elif study_vals:
        vals = ", ".join(f"'{_esc(v)}'" for v in study_vals)
        study_pred = ""
        conditions.insert(0, f"s.clinical_study_designation IN [{vals}]")
    else:
        study_pred = ""

    # Dedupe extra matches while keeping order
    seen = set()
    extra_uniq = []
    for line in extra_matches:
        if line not in seen:
            seen.add(line)
            extra_uniq.append(line)
    extra_match = "\n".join(extra_uniq)
    where_clause = "WHERE " + "\n  AND ".join(conditions) if conditions else ""
    return study_pred, extra_match, where_clause
