"""The Trial Supervisor: trial-level strategy, behind flags that default off.

Specification section 11. Two behaviours, both configuration, and both with a
hazard the specification requires to be measured rather than assumed away.

`early_termination` stops once a blocker is confirmed and marks the rest
`not_assessed`. What it costs is Criterion Coverage, and the record has to say
which criteria nobody looked at — a coordinator told "unresolved" goes to the
chart for an answer that was never sought there.

`order_criteria` assesses exclusion criteria first, which is how a blocker is
found sooner. What it costs is order independence, so the order the supervisor
chose is recorded rather than reconstructed.

With both flags off this returns exactly what assessing the criteria in
authored order returns, which is what makes the flags an ablation row rather
than a confound. Output is always in authored order, whatever order the
assessment ran in.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

from ctma.adapters.model import ModelClient
from ctma.agent.loop import assess_criterion
from ctma.domain.assessment import (
    AssessedCriterion,
    CriterionAssessment,
    SkippedCriterion,
    TrialAssessment,
)
from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionImpact, CriterionPolarity
from ctma.domain.evidence import TrialEvidence
from ctma.domain.expression import EligibilityCriterion
from ctma.domain.run import SupervisorConfiguration
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trace import Measurements, SupervisorAction, SupervisorDecision
from ctma.domain.trial import TrialRecord

FLAGS_OFF = SupervisorConfiguration()
"""Both flags off: the configuration correctness is measured under."""

MAX_CONCURRENT_CRITERIA = 8
"""Criterion assessments within a trial are independent, so they overlap. The
cap is about not opening one connection per criterion, not about correctness."""


class SupervisedTrial(Frozen):
    """One assessed trial, and the strategy decisions taken while assessing it."""

    assessment: TrialAssessment
    decisions: tuple[SupervisorDecision, ...] = ()


def assess_trial(
    trial: TrialRecord,
    *,
    timeline: PatientTimeline,
    model: ModelClient,
    retrieval_rank: int,
    configuration: SupervisorConfiguration = FLAGS_OFF,
    verifier_feedback: bool = True,
) -> SupervisedTrial:
    """Assess every criterion of one trial, under the supervisor's strategy."""
    order = _order(trial.criteria, configuration)
    started = time.monotonic()
    if configuration.early_termination:
        results, decisions = _sequential(order, trial, timeline, model, verifier_feedback, started)
    else:
        results = _concurrent(order, trial, timeline, model, verifier_feedback)
        decisions = ()

    if configuration.order_criteria:
        decisions = (*decisions, _ordering_decision(trial, order, results, started))

    by_id = {result.criterion_id: result for result in results}
    return SupervisedTrial(
        assessment=TrialAssessment(
            nct_id=trial.nct_id,
            snapshot_record_id=trial.snapshot_record_id,
            retrieval_rank=retrieval_rank,
            criteria=tuple(by_id[criterion.criterion_id] for criterion in trial.criteria),
            measurements=Measurements.summed(
                assessment.measurements
                for result in results
                if isinstance(result, AssessedCriterion)
                for assessment in result.propositions
            ),
        ),
        decisions=decisions,
    )


def _order(
    criteria: Sequence[EligibilityCriterion], configuration: SupervisorConfiguration
) -> tuple[EligibilityCriterion, ...]:
    """Authored order, or exclusion criteria first.

    Deterministic either way: a stable sort on polarity keeps the authored order
    within each half, so a fixed configuration produces one assessment order and
    the recorded one is reproducible.
    """
    if not configuration.order_criteria:
        return tuple(criteria)
    return tuple(
        sorted(criteria, key=lambda item: item.polarity is not CriterionPolarity.EXCLUSION)
    )


def _concurrent(
    order: Sequence[EligibilityCriterion],
    trial: TrialRecord,
    timeline: PatientTimeline,
    model: ModelClient,
    verifier_feedback: bool,
) -> tuple[CriterionAssessment, ...]:
    """Criteria are independent, so they run together (section 10)."""
    if len(order) == 1:
        return (_assess(order[0], trial, timeline, model, verifier_feedback),)

    def run(criterion: EligibilityCriterion) -> CriterionAssessment:
        return _assess(criterion, trial, timeline, model, verifier_feedback)

    with ThreadPoolExecutor(max_workers=min(MAX_CONCURRENT_CRITERIA, len(order))) as pool:
        return tuple(pool.map(run, order))


def _sequential(
    order: Sequence[EligibilityCriterion],
    trial: TrialRecord,
    timeline: PatientTimeline,
    model: ModelClient,
    verifier_feedback: bool,
    started: float,
) -> tuple[tuple[CriterionAssessment, ...], tuple[SupervisorDecision, ...]]:
    """Assess until a blocker is confirmed, then skip the rest.

    Skipped criteria are `not_assessed` and carry the criterion that stopped
    the run. They are never `unknown`: nobody looked, so there is no evidence to
    describe, and reporting the budget decision as uncertainty would send a
    coordinator to the chart for an answer that was never sought there.
    """
    results: list[CriterionAssessment] = []
    decisions: list[SupervisorDecision] = []
    blocker: str | None = None
    for criterion in order:
        if blocker is not None:
            results.append(_skipped(criterion, trial, blocker))
            continue
        assessed = _assess(criterion, trial, timeline, model, verifier_feedback)
        results.append(assessed)
        if _blocks(assessed):
            blocker = assessed.criterion_id
            decisions.append(
                SupervisorDecision(
                    nct_id=trial.nct_id,
                    action=SupervisorAction.EARLY_TERMINATION,
                    criterion_id=blocker,
                    detail=(
                        f"stopped after {blocker} was confirmed as a blocker, "
                        f"{int((time.monotonic() - started) * 1000)} ms in; "
                        f"{len(order) - len(results)} criteria not assessed"
                    ),
                )
            )
    return tuple(results), tuple(decisions)


def _ordering_decision(
    trial: TrialRecord,
    order: Sequence[EligibilityCriterion],
    results: Sequence[CriterionAssessment],
    started: float,
) -> SupervisorDecision:
    """What the ordering bought, as the number section 11 asks for.

    Time to first blocker is the measured effect, so it is recorded even when
    there is no blocker to find — "none" is the result in that case, and a
    missing record would look like a run that was never ordered.
    """
    by_id = {result.criterion_id: result for result in results}
    position = next(
        (
            index
            for index, criterion in enumerate(order, start=1)
            if _blocks(by_id.get(criterion.criterion_id))
        ),
        None,
    )
    found = (
        f"first blocker at position {position} of {len(order)}"
        if position is not None
        else "no blocker found"
    )
    return SupervisorDecision(
        nct_id=trial.nct_id,
        action=SupervisorAction.ORDER_CRITERIA,
        detail=(
            f"assessed exclusion criteria first; {found}, "
            f"{int((time.monotonic() - started) * 1000)} ms into the trial"
        ),
    )


def _blocks(result: CriterionAssessment | None) -> bool:
    return isinstance(result, AssessedCriterion) and result.impact is CriterionImpact.BLOCKING


def _assess(
    criterion: EligibilityCriterion,
    trial: TrialRecord,
    timeline: PatientTimeline,
    model: ModelClient,
    verifier_feedback: bool,
) -> CriterionAssessment:
    return assess_criterion(
        criterion,
        timeline=timeline,
        trial=trial,
        model=model,
        verifier_feedback=verifier_feedback,
    )


def _skipped(criterion: EligibilityCriterion, trial: TrialRecord, blocker: str) -> SkippedCriterion:
    """A criterion nobody looked at, quoted so the reader can see what it said."""
    return SkippedCriterion(
        criterion_id=criterion.criterion_id,
        polarity=criterion.polarity,
        trial_evidence=TrialEvidence(
            snapshot_id=trial.snapshot_record_id,
            nct_id=trial.nct_id,
            source_section=criterion.source_section,
            criterion_ordinal=criterion.ordinal,
            span_start=criterion.span_start,
            span_end=criterion.span_end,
            source_text=criterion.source_text,
        ),
        blocker_criterion_id=blocker,
    )
