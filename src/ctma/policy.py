"""The Matching Policy: what is retained, presented, assessed, and in what order.

Specification section 9. Pure functions over the retrieval order, so the rules
that decide what a reader sees can be tested without retrieval, a model, or a
timeline.

Two orderings live here and never merge. Retrieval Rank is where retrieval put a
trial. Review Priority is where the reader should look first, which is decided
after assessment. A single sorted list holding both would be an "AI match score"
by another name, and section 15.3 forbids one.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from enum import StrEnum

from pydantic import Field

from ctma.domain.assessment import TrialAssessment
from ctma.domain.base import Frozen
from ctma.domain.enums import CandidateStatus, MatchConclusion
from ctma.domain.run import CandidateSet, CandidateTrial, ChannelRank

RETAINED_LIMIT = 20
"""Retrieval returns an immutable top 20. Ranks 6-20 stay visible as Unassessed
Candidates rather than disappearing."""

PRESENTED_LIMIT = 5
"""The top five by Retrieval Rank are shown to the reader."""

ASSESSED_LIMIT = 3
"""At most three trials are assessed, which is the authoring budget rather than
a claim about how many trials matter."""


class AssessmentShortfall(StrEnum):
    """Why fewer than three trials were assessed.

    Section 9 requires the report to say how many and why, because both causes
    are properties of this project rather than findings about the patient, and an
    unexplained short list reads like one.
    """

    FEWER_CANDIDATES_PRESENTED = "fewer_candidates_presented"
    FEWER_EXPRESSIONS_AUTHORED = "fewer_expressions_authored"


class RetrievedTrial(Frozen):
    """One trial in retrieval order, before the policy gives it a status.

    Retrieval decides the order; the policy numbers it. `has_authored_expression`
    comes from the trial record, not from retrieval, and is the only reason a
    presented trial can go unassessed.
    """

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    snapshot_record_id: str = Field(min_length=1)
    has_authored_expression: bool
    fused_score: float | None = None
    channel_ranks: tuple[ChannelRank, ...] = ()


class MatchingPlan(Frozen):
    """The Candidate Set with statuses assigned, and what the report must say.

    `expression_unavailable` names the presented trials that have no authored
    expression. Their Retrieval Rank is not repeated here: it is already on the
    candidate, and a second copy could disagree with the first.
    """

    candidates: CandidateSet
    expression_unavailable: tuple[str, ...] = ()
    shortfall: AssessmentShortfall | None = None


def plan(retrieved: Sequence[RetrievedTrial]) -> MatchingPlan:
    """Retain the top 20, present the top 5, assess up to 3 of the presented.

    The assessed set is the three highest-ranked presented candidates with an
    authored expression. Section 9 describes that as backfill — a candidate
    without an expression is reported at its own rank and the next presented one
    takes its place — but there is nothing to shift: filtering the five
    presented candidates and taking three produces exactly that, and stops at
    rank 5 because nothing past rank 5 is in the list being filtered.

    Raises `ValidationError` if `retrieved` is empty: a run compares a patient
    against at least one candidate.
    """
    retained = tuple(retrieved[:RETAINED_LIMIT])
    presented = retained[:PRESENTED_LIMIT]
    assessable = tuple(trial for trial in presented if trial.has_authored_expression)
    assessed = {trial.nct_id for trial in assessable[:ASSESSED_LIMIT]}

    candidates = tuple(
        CandidateTrial(
            nct_id=trial.nct_id,
            snapshot_record_id=trial.snapshot_record_id,
            retrieval_rank=rank,
            status=_status_of(trial, rank, assessed),
            fused_score=trial.fused_score,
            channel_ranks=trial.channel_ranks,
        )
        for rank, trial in enumerate(retained, start=1)
    )
    return MatchingPlan(
        candidates=CandidateSet(candidates=candidates),
        expression_unavailable=tuple(
            trial.nct_id for trial in presented if not trial.has_authored_expression
        ),
        shortfall=_shortfall(len(presented), len(assessed)),
    )


def _status_of(trial: RetrievedTrial, rank: int, assessed: set[str]) -> CandidateStatus:
    if trial.nct_id in assessed:
        return CandidateStatus.ASSESSED
    if rank <= PRESENTED_LIMIT:
        return CandidateStatus.PRESENTED
    return CandidateStatus.RETAINED


def _shortfall(presented: int, assessed: int) -> AssessmentShortfall | None:
    """Which of the two causes bound, when fewer than three were assessed.

    Retrieval returning fewer than three candidates is reported ahead of missing
    expressions, because it is the one that would still hold if every trial in
    the corpus had an authored expression.
    """
    if assessed >= ASSESSED_LIMIT:
        return None
    if presented < ASSESSED_LIMIT:
        return AssessmentShortfall.FEWER_CANDIDATES_PRESENTED
    return AssessmentShortfall.FEWER_EXPRESSIONS_AUTHORED


_CONCLUSION_ORDER: dict[MatchConclusion, int] = {
    MatchConclusion.POTENTIAL_MATCH: 0,
    MatchConclusion.INSUFFICIENT_INFORMATION: 1,
    MatchConclusion.UNLIKELY_MATCH: 2,
}
"""Section 9 orders Review Priority by Match Conclusion without saying which
conclusion leads. A coordinator's next action decides it: a potential match is
worth reading now, an unresolved trial is worth a look at the chart, and a
confirmed blocker needs nothing. Ordering it the other way would put the trials
requiring no work at the top of the page."""


def review_priority(assessments: Iterable[TrialAssessment]) -> tuple[TrialAssessment, ...]:
    """Order assessed trials by Match Conclusion, then by Retrieval Rank.

    The rank is untouched: it stays on each assessment and only the position in
    this tuple changes. That is what keeps the report able to show both.
    """
    return tuple(
        sorted(
            assessments,
            key=lambda assessment: (
                _CONCLUSION_ORDER[assessment.conclusion],
                assessment.retrieval_rank,
            ),
        )
    )
