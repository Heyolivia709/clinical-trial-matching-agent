"""Unknown Reason assignment: one test per row, plus the precedence between them.

Specification section 8.0. The rows overlap on purpose, so "the first matching
row wins" is a behaviour with its own tests rather than an implementation note.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.agent.unknown_reason import (
    STAGE_2,
    AgentOutcome,
    EvidenceSituation,
    ExpressionStatus,
    UnassignableReasonError,
    assign_unknown_reason,
)
from ctma.domain.enums import EVIDENCE_DERIVED_REASONS, CriterionCategory, UnknownReason
from ctma.evaluation.manifest import EXPECTED_REASON_BY_DISTRACTOR

BIOMARKER = CriterionCategory.BIOMARKER


def situation(**overrides: object) -> EvidenceSituation:
    """A situation that explains nothing on its own, plus one finding."""
    return EvidenceSituation.model_validate({"category": BIOMARKER} | overrides)


# --- Stage 1 -----------------------------------------------------------------


def test_a_trial_without_an_expression_yields_expression_unavailable() -> None:
    """Every criterion of that trial, regardless of what the timeline holds."""
    assert (
        assign_unknown_reason(expression=ExpressionStatus.UNAVAILABLE)
        is UnknownReason.EXPRESSION_UNAVAILABLE
    )


def test_stage_1_does_not_need_a_situation() -> None:
    """Nothing was looked up, because the criterion was never assessed."""
    assert assign_unknown_reason(None, expression=ExpressionStatus.UNAVAILABLE) is (
        UnknownReason.EXPRESSION_UNAVAILABLE
    )


# --- Stage 2, one test per row -----------------------------------------------


def test_row_1_an_unsupported_proposition() -> None:
    unsupported = EvidenceSituation(category=CriterionCategory.UNSUPPORTED)
    assert assign_unknown_reason(unsupported) is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE


def test_row_1_the_only_candidate_sits_outside_the_evidence_boundary() -> None:
    """A `MedicationRequest` is an order, and an order is not exposure."""
    outside = situation(only_candidate_facts_are_outside_the_boundary=True)
    assert assign_unknown_reason(outside) is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE


def test_row_2_an_anchor_the_expression_could_not_operationalize() -> None:
    """An anchor like the first dose of study drug, with no authored substitution."""
    ambiguous = situation(anchor_was_not_operationalized=True)
    assert assign_unknown_reason(ambiguous) is UnknownReason.AMBIGUOUS_CRITERION


def test_row_3_no_fact_for_the_concept() -> None:
    assert assign_unknown_reason(situation()) is UnknownReason.MISSING_EVIDENCE


def test_row_4_the_only_fact_has_a_disqualifying_status() -> None:
    """A disqualified fact and no fact at all are different diagnoses."""
    disqualified = situation(facts_with_disqualifying_status=1)
    assert assign_unknown_reason(disqualified) is UnknownReason.UNUSABLE_STATUS


def test_row_5_two_qualifying_facts_disagree() -> None:
    conflicting = situation(qualifying_facts=2, qualifying_facts_conflict=True)
    assert assign_unknown_reason(conflicting) is UnknownReason.CONFLICTING_EVIDENCE


def test_row_6_the_date_is_coarser_than_the_comparison_needs() -> None:
    """A year-only date against a 14-day window."""
    imprecise = situation(qualifying_facts=1, precision_is_coarser_than_required=True)
    assert assign_unknown_reason(imprecise) is UnknownReason.INSUFFICIENT_PRECISION


def test_row_7_every_qualifying_fact_falls_outside_the_window() -> None:
    stale = situation(qualifying_facts=1, qualifying_facts_are_all_out_of_window=True)
    assert assign_unknown_reason(stale) is UnknownReason.STALE_EVIDENCE


# --- Stage 2 precedence ------------------------------------------------------


MISSING_EVIDENCE_ROW = next(row for row in STAGE_2 if row.reason is UnknownReason.MISSING_EVIDENCE)
"""Found by reason rather than by index, so inserting a row above it is not a
change every overlap test has to be edited for."""


def test_an_unsupported_proposition_outranks_having_no_facts() -> None:
    """Both rows match: an unsupported proposition is never looked up."""
    unsupported = EvidenceSituation(category=CriterionCategory.UNSUPPORTED)
    assert MISSING_EVIDENCE_ROW.applies(unsupported), "that row matches too: a real overlap"
    assert assign_unknown_reason(unsupported) is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE


def test_an_unoperationalized_anchor_outranks_having_no_facts() -> None:
    """The criterion could not be read, which is prior to what the record holds."""
    ambiguous = situation(anchor_was_not_operationalized=True)
    assert MISSING_EVIDENCE_ROW.applies(ambiguous)
    assert assign_unknown_reason(ambiguous) is UnknownReason.AMBIGUOUS_CRITERION


def test_a_boundary_violation_outranks_an_unoperationalized_anchor() -> None:
    both = situation(
        only_candidate_facts_are_outside_the_boundary=True,
        anchor_was_not_operationalized=True,
    )
    assert assign_unknown_reason(both) is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE


def test_a_conflict_outranks_a_precision_problem() -> None:
    both = situation(
        qualifying_facts=2,
        qualifying_facts_conflict=True,
        precision_is_coarser_than_required=True,
    )
    assert assign_unknown_reason(both) is UnknownReason.CONFLICTING_EVIDENCE


def test_a_precision_problem_outranks_a_stale_fact() -> None:
    both = situation(
        qualifying_facts=1,
        precision_is_coarser_than_required=True,
        qualifying_facts_are_all_out_of_window=True,
    )
    assert assign_unknown_reason(both) is UnknownReason.INSUFFICIENT_PRECISION


def test_a_usable_fact_beside_a_disqualified_one_is_not_unusable_status() -> None:
    """The disqualified fact explains nothing once a usable one exists."""
    mixed = situation(
        qualifying_facts=1,
        facts_with_disqualifying_status=1,
        precision_is_coarser_than_required=True,
    )
    assert assign_unknown_reason(mixed) is UnknownReason.INSUFFICIENT_PRECISION


# --- Stage 3 -----------------------------------------------------------------


def test_a_second_verification_failure_replaces_whatever_the_evidence_said() -> None:
    """Section 8.0: the reason regardless of what the evidence looked like."""
    conflicting = situation(qualifying_facts=2, qualifying_facts_conflict=True)
    assert assign_unknown_reason(conflicting) is UnknownReason.CONFLICTING_EVIDENCE
    assert (
        assign_unknown_reason(conflicting, outcome=AgentOutcome.VERIFICATION_FAILED_TWICE)
        is UnknownReason.VERIFICATION_FAILED
    )


def test_deterministic_disagreement_replaces_whatever_the_evidence_said() -> None:
    imprecise = situation(qualifying_facts=1, precision_is_coarser_than_required=True)
    assert (
        assign_unknown_reason(imprecise, outcome=AgentOutcome.DETERMINISTIC_DISAGREEMENT)
        is UnknownReason.REASONING_CONFLICT
    )


def test_stage_3_outranks_stage_1_as_well() -> None:
    """Defensive: a verification failure is not an authoring gap."""
    assert (
        assign_unknown_reason(
            expression=ExpressionStatus.UNAVAILABLE,
            outcome=AgentOutcome.VERIFICATION_FAILED_TWICE,
        )
        is UnknownReason.VERIFICATION_FAILED
    )


def test_a_completed_assessment_leaves_stage_2_standing() -> None:
    assert (
        assign_unknown_reason(situation(), outcome=AgentOutcome.ASSESSED)
        is UnknownReason.MISSING_EVIDENCE
    )


# --- Coverage of the vocabulary ----------------------------------------------


def test_stage_2_produces_the_authorable_reasons_and_one_that_is_not() -> None:
    """`enums.EVIDENCE_DERIVED_REASONS` names the seven a scenario can author.

    `concept_not_in_mapping` is the one row no scenario can produce: it depends
    on what this system covers, not on what an author wrote into a record. It
    belongs in the table and outside that set, and keeping the two apart is what
    stops the benchmark plan's balance requirement from demanding a scenario
    that would have to be authored against the mapping itself.
    """
    assert {row.reason for row in STAGE_2} == EVIDENCE_DERIVED_REASONS | {
        UnknownReason.CONCEPT_NOT_IN_MAPPING
    }


def test_every_unknown_reason_is_reachable() -> None:
    """A reason nothing can assign would be a diagnosis that never fires."""
    reachable = {row.reason for row in STAGE_2} | {
        UnknownReason.EXPRESSION_UNAVAILABLE,
        UnknownReason.VERIFICATION_FAILED,
        UnknownReason.REASONING_CONFLICT,
    }
    assert reachable == set(UnknownReason)


def test_the_table_has_the_seven_rows_of_section_8_point_0_and_the_coverage_row() -> None:
    assert len(STAGE_2) == 8
    assert MISSING_EVIDENCE_ROW is STAGE_2[3]


def test_an_unmapped_concept_outranks_having_no_facts() -> None:
    """Both match, and the order is the whole point.

    An unmapped concept has no facts *because nothing looked*. Letting
    `missing_evidence` match first reports the consequence and hides the cause,
    which is how a coordinator ends up searching a chart nothing searched.
    """
    unmapped = situation(concept_is_not_in_the_mapping=True)
    assert MISSING_EVIDENCE_ROW.applies(unmapped)
    assert assign_unknown_reason(unmapped) is UnknownReason.CONCEPT_NOT_IN_MAPPING


def test_every_reason_a_planted_distractor_expects_is_reachable() -> None:
    """Gate 2 asserts the mapping per hazard; this checks the table can serve it."""
    assert set(EXPECTED_REASON_BY_DISTRACTOR.values()) <= {row.reason for row in STAGE_2}


# --- Refusals ----------------------------------------------------------------


def test_a_situation_that_explains_nothing_is_refused() -> None:
    """A usable fact and no finding should have produced a state, not an unknown."""
    explained = situation(qualifying_facts=1)
    with pytest.raises(UnassignableReasonError, match="no row"):
        assign_unknown_reason(explained)


def test_stage_2_without_a_situation_is_refused() -> None:
    with pytest.raises(UnassignableReasonError, match="needs an EvidenceSituation"):
        assign_unknown_reason(None)


def test_an_unsupported_proposition_reporting_facts_is_refused() -> None:
    """It is never assessed, so a lookup result implies a lookup that never ran."""
    with pytest.raises(ValidationError, match="not assessed"):
        EvidenceSituation(category=CriterionCategory.UNSUPPORTED, qualifying_facts=1)


def test_a_conflict_between_fewer_than_two_facts_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least two qualifying facts"):
        situation(qualifying_facts=1, qualifying_facts_conflict=True)


@pytest.mark.parametrize(
    "finding",
    ["precision_is_coarser_than_required", "qualifying_facts_are_all_out_of_window"],
)
def test_a_finding_about_a_qualifying_fact_requires_one(finding: str) -> None:
    """Both rows are phrased "a qualifying fact exists but..." — so one must."""
    with pytest.raises(ValidationError, match="requires at least one qualifying fact"):
        situation(**{finding: True})


def test_facts_inside_the_boundary_contradict_only_candidates_being_outside() -> None:
    with pytest.raises(ValidationError, match="means no fact inside it"):
        situation(only_candidate_facts_are_outside_the_boundary=True, qualifying_facts=1)


def test_situations_are_immutable() -> None:
    with pytest.raises(ValidationError):
        situation().qualifying_facts = 3  # type: ignore[misc]


def test_the_same_situation_always_gives_the_same_reason() -> None:
    """Assignment is a pure function, which is what makes a taxonomy publishable."""
    disqualified = situation(facts_with_disqualifying_status=2)
    assert len({assign_unknown_reason(disqualified) for _ in range(20)}) == 1
