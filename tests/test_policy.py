"""The Matching Policy: retained, presented, assessed, and Review Priority.

The interesting cases are the ones where an authored expression is missing. The
trial is still shown at its own rank, and the assessed set is filled from the
presented five rather than being allowed to shrink.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.domain.enums import CandidateStatus, MatchConclusion
from ctma.policy import (
    ASSESSED_LIMIT,
    PRESENTED_LIMIT,
    RETAINED_LIMIT,
    AssessmentShortfall,
    plan,
    review_priority,
)
from tests.builders import (
    assessed_exc7,
    exc7_trial_assessment,
    met,
    not_met,
    retrieved,
    unknown,
)


def test_the_limits_are_the_ones_section_9_fixes() -> None:
    assert (RETAINED_LIMIT, PRESENTED_LIMIT, ASSESSED_LIMIT) == (20, 5, 3)


def test_retrieval_beyond_the_top_twenty_is_dropped() -> None:
    result = plan([retrieved(rank) for rank in range(1, 26)])
    assert len(result.candidates.candidates) == RETAINED_LIMIT
    assert [entry.retrieval_rank for entry in result.candidates.candidates] == list(range(1, 21))


def test_the_top_five_are_presented_and_the_rest_stay_visible() -> None:
    """Ranks 6-20 are Unassessed Candidates, not discarded ones."""
    result = plan([retrieved(rank) for rank in range(1, 21)])
    assert len(result.candidates.presented) == PRESENTED_LIMIT
    assert [entry.status for entry in result.candidates.candidates[5:]] == [
        CandidateStatus.RETAINED
    ] * 15


def test_the_three_highest_ranked_presented_candidates_are_assessed() -> None:
    result = plan([retrieved(rank) for rank in range(1, 21)])
    assert [entry.retrieval_rank for entry in result.candidates.assessed] == [1, 2, 3]
    assert result.expression_unavailable == ()
    assert result.shortfall is None


@pytest.mark.parametrize("missing_at", [1, 2, 3])
def test_a_top_three_candidate_without_an_expression_is_replaced_from_rank_four(
    missing_at: int,
) -> None:
    """It keeps its own rank and its own label; the next presented one takes its place."""
    hits = [True] * 5
    hits[missing_at - 1] = False
    result = plan([retrieved(rank, has_expression=has) for rank, has in enumerate(hits, start=1)])

    assessed_ranks = [entry.retrieval_rank for entry in result.candidates.assessed]
    assert assessed_ranks == sorted({1, 2, 3, 4} - {missing_at})
    assert result.expression_unavailable == (f"NCT0500{missing_at:04d}",)
    displaced = result.candidates.candidates[missing_at - 1]
    assert displaced.retrieval_rank == missing_at
    assert displaced.status is CandidateStatus.PRESENTED
    assert result.shortfall is None


def test_backfill_never_reaches_an_unpresented_candidate() -> None:
    """Only ranks 1 and 5 have expressions, so two are assessed and rank 6 is not."""
    result = plan(
        [retrieved(rank, has_expression=rank in (1, 5)) for rank in range(1, 11)],
    )
    assert [entry.retrieval_rank for entry in result.candidates.assessed] == [1, 5]
    assert result.candidates.candidates[5].status is CandidateStatus.RETAINED
    assert result.shortfall is AssessmentShortfall.FEWER_EXPRESSIONS_AUTHORED


def test_fewer_expressions_among_the_presented_five_yields_fewer_assessments() -> None:
    result = plan([retrieved(rank, has_expression=rank == 2) for rank in range(1, 6)])
    assert len(result.candidates.assessed) == 1
    assert len(result.expression_unavailable) == 4
    assert result.shortfall is AssessmentShortfall.FEWER_EXPRESSIONS_AUTHORED


def test_fewer_candidates_retrieved_is_reported_as_its_own_reason() -> None:
    """Two causes, and the report says which one bound."""
    result = plan([retrieved(1), retrieved(2)])
    assert len(result.candidates.assessed) == 2
    assert result.shortfall is AssessmentShortfall.FEWER_CANDIDATES_PRESENTED


def test_no_presented_candidate_has_an_expression() -> None:
    """Nothing is assessed, and the five are still presented at their own ranks."""
    result = plan([retrieved(rank, has_expression=False) for rank in range(1, 8)])
    assert result.candidates.assessed == ()
    assert result.shortfall is AssessmentShortfall.FEWER_EXPRESSIONS_AUTHORED
    assert [entry.status for entry in result.candidates.presented] == (
        [CandidateStatus.PRESENTED] * 5
    )


def test_the_assessed_set_stays_inside_what_was_presented() -> None:
    """The invariant the whole rule exists to protect."""
    result = plan([retrieved(rank, has_expression=rank % 2 == 0) for rank in range(1, 21)])
    presented = {entry.nct_id for entry in result.candidates.presented}
    assert {entry.nct_id for entry in result.candidates.assessed} <= presented


def test_a_run_needs_at_least_one_candidate() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        plan([])


def test_review_priority_orders_by_conclusion_then_rank() -> None:
    potential = exc7_trial_assessment(
        criteria=(assessed_exc7((not_met("P1"), unknown("P2"))),),
        retrieval_rank=3,
        nct_id="NCT05000003",
    )
    insufficient = exc7_trial_assessment(retrieval_rank=1, nct_id="NCT05000001")
    blocked = exc7_trial_assessment(
        criteria=(assessed_exc7((met("P1"), met("P2"))),),
        retrieval_rank=2,
        nct_id="NCT05000002",
    )
    assert (potential.conclusion, insufficient.conclusion, blocked.conclusion) == (
        MatchConclusion.POTENTIAL_MATCH,
        MatchConclusion.INSUFFICIENT_INFORMATION,
        MatchConclusion.UNLIKELY_MATCH,
    )

    ordered = review_priority((insufficient, blocked, potential))
    assert [entry.nct_id for entry in ordered] == [
        "NCT05000003",
        "NCT05000001",
        "NCT05000002",
    ]


def test_retrieval_rank_breaks_ties_within_one_conclusion() -> None:
    first = exc7_trial_assessment(retrieval_rank=2, nct_id="NCT05000002")
    second = exc7_trial_assessment(retrieval_rank=4, nct_id="NCT05000004")
    assert review_priority((second, first)) == (first, second)


def test_review_priority_never_overwrites_retrieval_rank() -> None:
    """Both orderings are shown in the report, so neither may consume the other."""
    assessments = (
        exc7_trial_assessment(retrieval_rank=1, nct_id="NCT05000001"),
        exc7_trial_assessment(
            criteria=(assessed_exc7((not_met("P1"), unknown("P2"))),),
            retrieval_rank=5,
            nct_id="NCT05000005",
        ),
    )
    ordered = review_priority(assessments)
    assert [entry.retrieval_rank for entry in ordered] == [5, 1]
