"""The reviewed concept mapping. Module-private by specification section 12.

An authored expression names a concept — `EGFR_TKI`, `ECOG_SCORE` — and a patient
record carries source codes. Something has to connect the two, and this is it: a
versioned table, reviewed by hand, with no inference in it.

The model never does this step. Deciding that a source code carries a concept is
a clinical judgement, and it is the one judgement in this system that a
deterministic verifier cannot check: whether an ALK fusion result answers a
criterion about ALK rearrangement is not something you can confirm by resolving a
JSON path. A model asked to make that call would produce a citation that resolves
perfectly and an answer nobody can audit. So the mapping is authored, and a
concept it does not cover reports that fact rather than guessing.

Codes here were checked against RxNav and a FHIR terminology server rather than
recalled. A mapping that names the wrong code is worse than a missing one: it
produces a confident answer about the wrong test.
"""

from __future__ import annotations

from typing import NamedTuple

from ctma.domain.enums import CriterionCategory

TERMINOLOGY_VERSION = "terminology-v1"
"""Recorded with a run, so a mapping change is visible as a different
configuration rather than as a behaviour change nobody can explain."""


class _Concept(NamedTuple):
    category: CriterionCategory
    codes: frozenset[str]


_MAPPING: dict[str, _Concept] = {
    "NSCLC": _Concept(CriterionCategory.DISEASE, frozenset({"254637007"})),
    "BRAIN_METASTASIS": _Concept(CriterionCategory.DISEASE, frozenset({"94225005"})),
    "PD_L1_EXPRESSION": _Concept(CriterionCategory.BIOMARKER, frozenset({"83052-1"})),
    "EGFR_L858R": _Concept(CriterionCategory.BIOMARKER, frozenset({"55766-0"})),
    "ALK_REARRANGEMENT": _Concept(CriterionCategory.BIOMARKER, frozenset({"78205-2"})),
    "ECOG_SCORE": _Concept(CriterionCategory.PERFORMANCE_STATUS, frozenset({"89247-1"})),
    "NEUTROPHIL_COUNT": _Concept(CriterionCategory.PERFORMANCE_STATUS, frozenset({"751-8"})),
    "EGFR_TKI": _Concept(CriterionCategory.PRIOR_THERAPY, frozenset({"1721581"})),
    "THIRD_GENERATION_EGFR_TKI": _Concept(CriterionCategory.PRIOR_THERAPY, frozenset({"1721581"})),
}
"""Concept to source codes, with the category the concept belongs to.

A code here means "a fact with this code may carry this concept", not "a fact
with this code establishes it". `EGFR_L858R` maps to the code for the *test*; the
result is in the value, and reading the value is the model's job, with a citation
the verifier can check."""


def codes_for_concept(concept: str) -> frozenset[str] | None:
    """The source codes for a concept, whatever category it belongs to.

    `get_latest_observation` takes a code and a time and no category, so it asks
    this way. The category check exists for the tool that is given one.
    """
    entry = _MAPPING.get(concept)
    return None if entry is None else entry.codes


def codes_for(concept: str, category: CriterionCategory) -> frozenset[str] | None:
    """The source codes for a concept, or None if the mapping does not cover it.

    A category that disagrees with the mapping is also None. Asking for
    `ECOG_SCORE` as a `demographic` is an authoring mistake, and answering it
    with the performance-status facts would hide the mistake behind a plausible
    result.
    """
    entry = _MAPPING.get(concept)
    if entry is None or entry.category is not category:
        return None
    return entry.codes
