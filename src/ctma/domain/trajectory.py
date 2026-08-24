"""The Evidence Trajectory: what a coordinator reads instead of the trace.

Specification section 14. The Reasoning Trace is a diagnostic artifact for
whoever is debugging the system. This is the other audience: someone deciding
whether to go and look at a patient's chart, who needs to know which criterion,
which evidence, which tools, and what the verifier said — and nothing else.

It is derived from the assessments rather than stored beside them, and that is
also what makes two of its guarantees structural. It cannot expose hidden
reasoning or Scenario Manifest content because it has none to draw on: the
records it reads never held either.
"""

from __future__ import annotations

from pydantic import Field

from ctma.domain.assessment import (
    CriterionAssessment,
    SkippedCriterion,
    TrialAssessment,
    UnexpressedCriterion,
)
from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionImpact, CriterionState, ReportingStatus, UnknownReason
from ctma.domain.trace import VerifierOutcome, VerifierVerdict


class TrajectoryStep(Frozen):
    """One criterion, as a coordinator needs to read it."""

    criterion_id: str = Field(min_length=1)
    reporting_status: ReportingStatus
    state: CriterionState | None = None
    """Absent for a criterion the supervisor skipped. `not_assessed` is a
    reporting status and never a state, so there is nothing to read here."""

    impact: CriterionImpact | None = None
    unknown_reason: UnknownReason | None = None
    tools_called: tuple[str, ...] = ()
    citations: tuple[str, ...] = ()
    """Cited facts as `ResourceType/id at json.path`, so the reader can open the
    record rather than take the assessment's word for it."""

    verification: tuple[str, ...] = ()
    rationale: tuple[str, ...] = ()
    """The model's explanatory sentences. Never evidence, and never the
    reasoning behind them: an assessment records one sentence about its answer,
    not how it got there."""

    detail: str | None = None
    """Why a criterion was skipped, where it was."""


def evidence_trajectory(assessment: TrialAssessment) -> tuple[TrajectoryStep, ...]:
    """The trajectory for one assessed trial, in the order it was assessed."""
    return tuple(_step(criterion) for criterion in assessment.criteria)


def _step(criterion: CriterionAssessment) -> TrajectoryStep:
    if isinstance(criterion, SkippedCriterion):
        return TrajectoryStep(
            criterion_id=criterion.criterion_id,
            reporting_status=ReportingStatus.NOT_ASSESSED,
            detail=(
                f"skipped after {criterion.blocker_criterion_id} was confirmed as a blocker"
                if criterion.blocker_criterion_id is not None
                else "skipped by the supervisor"
            ),
        )
    if isinstance(criterion, UnexpressedCriterion):
        return TrajectoryStep(
            criterion_id=criterion.criterion_id,
            reporting_status=ReportingStatus.ASSESSED,
            state=criterion.state,
            impact=criterion.impact,
            unknown_reason=criterion.unknown_reason,
            detail="no Criterion Expression was authored for this trial",
        )
    return TrajectoryStep(
        criterion_id=criterion.criterion_id,
        reporting_status=ReportingStatus.ASSESSED,
        state=criterion.state,
        impact=criterion.impact,
        unknown_reason=criterion.unknown_reason,
        tools_called=tuple(
            call.tool for assessment in criterion.propositions for call in assessment.tool_calls
        ),
        citations=tuple(
            f"{fact.resource_type}/{fact.resource_id} at {fact.json_path}"
            for assessment in criterion.propositions
            for evidence in assessment.patient_evidence
            for fact in evidence.facts
        ),
        verification=tuple(
            _verdict_line(outcome)
            for assessment in criterion.propositions
            for outcome in assessment.verification
        ),
        rationale=tuple(
            assessment.rationale
            for assessment in criterion.propositions
            if assessment.rationale is not None
        ),
    )


def _verdict_line(outcome: VerifierOutcome) -> str:
    if outcome.verdict is VerifierVerdict.ACCEPTED:
        return "verifier accepted the citation"
    named = ", ".join(rejection.value for rejection in outcome.rejections)
    return f"verifier rejected the citation: {named}"
