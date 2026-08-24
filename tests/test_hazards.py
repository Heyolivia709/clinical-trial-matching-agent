"""Every planted hazard resolves to the Unknown Reason it was planted for.

Gate 2, specification sections 5.1, 8.0 and 8.3. This is where the table meets
real timelines. A hazard that resolves to some other reason is a defect in the
timeline or in the table, so these tests run the actual tools over the actual
frozen Bundles rather than constructing an `EvidenceSituation` by hand.

Only development scenarios appear here. A held-out scenario used to debug a
table is no longer held out, and nothing else in the repository would say so.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import NamedTuple

import pytest

from ctma.adapters.scenario_bundles import load_scenario_inputs
from ctma.agent.situation import ToolResult, situation_from
from ctma.agent.unknown_reason import assign_unknown_reason
from ctma.domain.enums import CriterionCategory, Partition, UnknownReason
from ctma.domain.expression import AnchorSubstitution, TemporalWindow
from ctma.evaluation.manifest import EXPECTED_REASON_BY_DISTRACTOR, DistractorKind
from ctma.evaluation.scenarios import load_scenario_manifests
from ctma.timeline.build import build
from ctma.timeline.tools import (
    ExposureQuery,
    FactQuery,
    LatestObservation,
    Refusal,
    Verdict,
    check_temporal_window,
    find_medication_exposure,
    find_patient_facts,
    get_latest_observation,
)

MANIFESTS = {manifest.scenario_id: manifest for manifest in load_scenario_manifests()}
TIMELINES = {
    scenario.scenario_id: build(
        scenario.bundle_json,
        scenario_id=scenario.scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )
    for scenario in load_scenario_inputs()
}

TWELVE_MONTHS = TemporalWindow(duration=dt.timedelta(days=365))
FIRST_DOSE = "the first dose of study drug"


class Tool(StrEnum):
    """Which Timeline Tool a criterion about this hazard would reach for."""

    FACTS = "find_patient_facts"
    LATEST = "get_latest_observation"
    EXPOSURE = "find_medication_exposure"


class Hazard(NamedTuple):
    """One planted hazard, and the lookup a criterion about it would perform."""

    scenario_id: str
    category: CriterionCategory
    concept: str
    tool: Tool
    window: TemporalWindow | None = None


HAZARDS: dict[DistractorKind, Hazard] = {
    DistractorKind.ERROR_STATUS_RESULT: Hazard(
        "SCN-02", CriterionCategory.BIOMARKER, "PD_L1_EXPRESSION", Tool.FACTS
    ),
    DistractorKind.ORDER_WITHOUT_ADMINISTRATION: Hazard(
        "SCN-04", CriterionCategory.PRIOR_THERAPY, "EGFR_TKI", Tool.EXPOSURE
    ),
    DistractorKind.POST_ASSESSMENT_OBSERVATION: Hazard(
        "SCN-04", CriterionCategory.PERFORMANCE_STATUS, "ECOG_SCORE", Tool.LATEST
    ),
    DistractorKind.CONFLICTING_RESULTS: Hazard(
        "SCN-02", CriterionCategory.PERFORMANCE_STATUS, "ECOG_SCORE", Tool.LATEST
    ),
    DistractorKind.INSUFFICIENT_DATE_PRECISION: Hazard(
        "SCN-03", CriterionCategory.PRIOR_THERAPY, "EGFR_TKI", Tool.EXPOSURE, TWELVE_MONTHS
    ),
    DistractorKind.PRELIMINARY_RESULT: Hazard(
        "SCN-03", CriterionCategory.PERFORMANCE_STATUS, "ECOG_SCORE", Tool.LATEST
    ),
    DistractorKind.NEAR_MISS_CONCEPT: Hazard(
        "SCN-04", CriterionCategory.BIOMARKER, "ALK_REARRANGEMENT", Tool.FACTS
    ),
}


def look_up(hazard: Hazard) -> ToolResult:
    timeline = TIMELINES[hazard.scenario_id]
    match hazard.tool:
        case Tool.FACTS:
            return find_patient_facts(timeline, category=hazard.category, concept=hazard.concept)
        case Tool.LATEST:
            return get_latest_observation(timeline, concept=hazard.concept)
        case Tool.EXPOSURE:
            return find_medication_exposure(timeline, concept=hazard.concept, window=hazard.window)


def undecided(result: ToolResult) -> bool:
    """Whether the tool declined to hand back an answer to cite.

    Not the same as finding nothing. Two conflicting ECOG scores are two facts,
    and the tool still has no single reading to give a `met` a citation.
    """
    match result:
        case FactQuery():
            return not result.qualifying
        case LatestObservation():
            return result.latest is None
        case ExposureQuery():
            return not result.matched


def test_every_hazard_kind_has_a_check_here() -> None:
    """Section 8.3's right-hand column is a test obligation, so it is one."""
    assert set(HAZARDS) == set(DistractorKind)


@pytest.mark.parametrize("kind", list(DistractorKind), ids=[kind.value for kind in DistractorKind])
def test_a_planted_hazard_produces_no_confident_answer_and_the_named_reason(
    kind: DistractorKind,
) -> None:
    hazard = HAZARDS[kind]
    manifest = MANIFESTS[hazard.scenario_id]
    assert manifest.partition is Partition.DEVELOPMENT
    assert kind in manifest.distractor_kinds(), (
        f"{hazard.scenario_id} no longer plants {kind.value}, so this check proves nothing"
    )

    result = look_up(hazard)
    assert undecided(result), f"{kind.value} produced an answer a confident state could cite"
    situation = situation_from(result, category=hazard.category)
    assert assign_unknown_reason(situation) is EXPECTED_REASON_BY_DISTRACTOR[kind]


@pytest.mark.parametrize(
    "kind",
    [
        DistractorKind.ERROR_STATUS_RESULT,
        DistractorKind.PRELIMINARY_RESULT,
        DistractorKind.POST_ASSESSMENT_OBSERVATION,
        DistractorKind.NEAR_MISS_CONCEPT,
    ],
    ids=lambda kind: kind.value,
)
def test_a_disqualified_or_absent_fact_leaves_nothing_to_cite(kind: DistractorKind) -> None:
    """Section 8: `met` and `not_met` cite verified patient evidence.

    These four hazards leave no qualifying fact at all, so there is nothing for
    a confident state to be built on. The other three do leave facts, and are
    refused for a different reason — which is the distinction the reasons carry.
    """
    result = look_up(HAZARDS[kind])
    match result:
        case FactQuery():
            assert result.qualifying == ()
        case LatestObservation():
            assert result.latest is None
            assert result.conflicting == ()
        case ExposureQuery():
            assert result.matched == ()


def test_a_retracted_result_is_unusable_status_and_not_missing_evidence() -> None:
    """SCN-02 was tested for PD-L1 and the result was withdrawn.

    The two answers send a coordinator to different places: order the test, or
    go and read the pathology report that is already in the chart. Collapsing
    them into `missing_evidence` would report the first about the second.
    """
    result = find_patient_facts(
        TIMELINES["SCN-02"], category=CriterionCategory.BIOMARKER, concept="PD_L1_EXPRESSION"
    )
    assert result.qualifying == ()
    assert [fact.status for fact in result.disqualified] == ["entered-in-error"]
    situation = situation_from(result, category=CriterionCategory.BIOMARKER)
    assert assign_unknown_reason(situation) is UnknownReason.UNUSABLE_STATUS


def test_a_near_miss_concept_is_missing_evidence_and_not_the_neighbouring_answer() -> None:
    """SCN-04 holds an ALK protein stain, and a criterion asks about the fusion.

    The stain is a real, final, in-window result, which is what makes it
    dangerous: a model reading "ALK" and "Present" has everything it needs to
    answer confidently about a test the patient never had.
    """
    timeline = TIMELINES["SCN-04"]
    assert any(fact.code.code == "47303-3" for fact in timeline.facts)
    result = find_patient_facts(
        timeline, category=CriterionCategory.BIOMARKER, concept="ALK_REARRANGEMENT"
    )
    assert result.mapped
    assert result.qualifying == ()
    assert result.disqualified == ()
    situation = situation_from(result, category=CriterionCategory.BIOMARKER)
    assert assign_unknown_reason(situation) is UnknownReason.MISSING_EVIDENCE


def test_an_exposure_outside_the_window_is_stale_evidence() -> None:
    """SCN-01's EGFR TKI ended in 2024, which answers a twelve-month window.

    Not one of the seven hazards, and the seventh Unknown Reason an authored
    scenario has to be able to produce.
    """
    result = find_medication_exposure(TIMELINES["SCN-01"], concept="EGFR_TKI", window=TWELVE_MONTHS)
    assert result.matched == ()
    assert len(result.outside_window) == 1
    situation = situation_from(result, category=CriterionCategory.PRIOR_THERAPY)
    assert assign_unknown_reason(situation) is UnknownReason.STALE_EVIDENCE


# --- prospective anchors, covered twice (specification section 5.1) ----------


def substituted_window() -> TemporalWindow:
    return TemporalWindow(
        duration=dt.timedelta(days=365),
        source_anchor_text=FIRST_DOSE,
        anchor_substitution=AnchorSubstitution(
            rationale=(
                "Screening happens before the first dose, so Assessment Time is the "
                "proxy a coordinator uses."
            )
        ),
    )


def unsubstituted_window() -> TemporalWindow:
    return TemporalWindow(duration=dt.timedelta(days=365), source_anchor_text=FIRST_DOSE)


def test_a_prospective_anchor_with_a_declared_substitution_is_assessed() -> None:
    """The window is placed, and the result says which anchor placed it.

    The substitution rides on the tool result rather than being recovered from
    the expression later, so a trace cannot show a window whose anchor nobody
    can account for.
    """
    window = substituted_window()
    exposure = TIMELINES["SCN-01"].exposures[0]
    check = check_temporal_window(
        exposure.time, anchor=TIMELINES["SCN-01"].assessment_as_of, window=window
    )
    assert check.verdict is Verdict.FAILS
    assert check.refusal is None
    assert check.anchor_substitution is not None
    assert check.anchor_substitution.substituted_with == "assessment_as_of"
    assert check.window_end == dt.date(2026, 8, 4)

    result = find_medication_exposure(TIMELINES["SCN-01"], concept="EGFR_TKI", window=window)
    situation = situation_from(result, category=CriterionCategory.PRIOR_THERAPY, window=window)
    assert assign_unknown_reason(situation) is UnknownReason.STALE_EVIDENCE


def test_the_same_anchor_without_a_substitution_is_ambiguous_criterion() -> None:
    """Nothing about the patient changed; the authored expression did.

    Section 5.1 prohibits substituting the Assessment Time silently, so an
    expression that declares no substitution reports that it could not
    operationalize the criterion, whatever the record happens to contain.
    """
    window = unsubstituted_window()
    assert not window.anchor_is_resolvable
    result = find_medication_exposure(TIMELINES["SCN-01"], concept="EGFR_TKI", window=window)
    situation = situation_from(result, category=CriterionCategory.PRIOR_THERAPY, window=window)
    assert assign_unknown_reason(situation) is UnknownReason.AMBIGUOUS_CRITERION


def test_a_substitution_cannot_be_declared_without_the_anchor_it_replaces() -> None:
    with pytest.raises(ValueError, match="requires the source_anchor_text"):
        TemporalWindow(
            duration=dt.timedelta(days=365),
            anchor_substitution=AnchorSubstitution(rationale="no anchor named"),
        )


def test_a_window_with_no_named_anchor_counts_back_from_the_assessment_time() -> None:
    """The default rule of section 5.1, which most criteria rely on."""
    assert TWELVE_MONTHS.anchor_is_resolvable
    check = check_temporal_window(
        TIMELINES["SCN-01"].exposures[0].time,
        anchor=TIMELINES["SCN-01"].assessment_as_of,
        window=TWELVE_MONTHS,
    )
    assert check.anchor_substitution is None
    assert check.window_end == TIMELINES["SCN-01"].assessment_as_of


def test_a_coarse_date_that_straddles_the_boundary_refuses_rather_than_guesses() -> None:
    """SCN-03's osimertinib is dated to 2025, and the window starts inside it."""
    exposure = next(
        item for item in TIMELINES["SCN-03"].exposures if item.medication.code == "1721581"
    )
    check = check_temporal_window(
        exposure.time, anchor=TIMELINES["SCN-03"].assessment_as_of, window=TWELVE_MONTHS
    )
    assert check.verdict is Verdict.REFUSED
    assert check.refusal is Refusal.PRECISION_TOO_COARSE
