"""Running a variant over a partition, and totalling what came out.

Specification section 12's Evaluation Lab, at the size v7 left it: three
variants, one partition at a time, and counts over stated denominators.

Nothing here decides anything about a patient. It builds the timeline, runs the
variant, grades the output at the offline call site, and adds up. The two
things it is careful about are the two the measurement plan is careful about:
the held-out half is only ever run when a caller names it, and the verifier that
grades every variant is the same verifier with the same configuration.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import Field

from ctma.adapters.model import ModelClient
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.assessment import AssessedCriterion
from ctma.domain.base import Frozen
from ctma.domain.enums import Partition
from ctma.domain.run import MatchingRun, SupervisorConfiguration
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trace import Measurements
from ctma.domain.trial import TrialRecord
from ctma.evaluation.baseline import BaselineAnswers, one_shot
from ctma.evaluation.cases import EvalCase
from ctma.evaluation.counts import ReportedCounts, report_counts
from ctma.evaluation.grading import (
    GradedProposition,
    InvariantResult,
    Variant,
    grade_baseline,
    grade_run,
    track_one,
)
from ctma.match import match
from ctma.timeline.build import build


class VariantResult(Frozen):
    """One variant over one case: what it answered, and how it was scored."""

    case_id: str = Field(min_length=1)
    variant: Variant
    graded: tuple[GradedProposition, ...] = ()
    invariants: tuple[InvariantResult, ...] = ()
    cost: Measurements = Measurements()
    criterion_assessments: int = Field(default=0, ge=0)


def timeline_for(scenario_id: str) -> PatientTimeline:
    scenario = load_scenario_input(scenario_id)
    return build(
        scenario.bundle_json,
        scenario_id=scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )


def run_agent(
    case: EvalCase,
    *,
    model: ModelClient,
    verifier_feedback: bool = True,
    supervisor: SupervisorConfiguration | None = None,
) -> VariantResult:
    """Assess one case with the agent, then grade it offline."""
    scenario = load_scenario_input(case.scenario_id)
    trial = _trial(case.nct_id)
    variant = Variant.AGENT if verifier_feedback else Variant.AGENT_NO_VERIFIER
    run = match(
        scenario_id=case.scenario_id,
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=[trial],
        model=model,
        partition=case.partition,
        run_id=f"{case.case_id}|{variant.value}",
        supervisor=supervisor or SupervisorConfiguration(),
        verifier_feedback=verifier_feedback,
    )
    timeline = timeline_for(case.scenario_id)
    graded = grade_run(run, case=case, timeline=timeline, trial=trial, variant=variant)
    return VariantResult(
        case_id=case.case_id,
        variant=variant,
        graded=graded,
        invariants=track_one(run, graded, case=case, trial=trial, timeline=timeline),
        cost=run.measurements,
        criterion_assessments=_assessed(run),
    )


def run_one_shot(case: EvalCase, *, model: ModelClient) -> VariantResult:
    """Assess one case with the baseline: no tools, no verifier feedback."""
    trial = _trial(case.nct_id)
    timeline = timeline_for(case.scenario_id)
    answers: list[BaselineAnswers] = [
        one_shot(criterion, timeline=timeline, trial=trial, model=model)
        for criterion in trial.criteria
    ]
    return VariantResult(
        case_id=case.case_id,
        variant=Variant.BASELINE,
        graded=grade_baseline(answers, case=case, timeline=timeline, trial=trial),
        cost=Measurements.summed(answer.measurements for answer in answers),
        criterion_assessments=len(answers),
    )


def totals(
    results: Sequence[VariantResult], *, variant: Variant, partition: Partition
) -> ReportedCounts:
    """Add one variant's cases into the row the report prints."""
    graded = tuple(item for result in results for item in result.graded)
    scenarios = {result.case_id.split("|")[0] for result in results}
    trials = {result.case_id.split("|")[1] for result in results}
    _guard(partition)
    return report_counts(
        graded,
        variant=variant,
        scenarios=len(scenarios),
        trials=len(trials),
        cost=Measurements.summed(result.cost for result in results),
        criterion_assessments=sum(result.criterion_assessments for result in results),
    )


def _guard(partition: Partition) -> None:
    """A reminder in the one place both halves pass through.

    Held-out results are assessed once, at the end, and never used to tune. The
    code cannot enforce when a person looks at a number; what it can do is make
    the partition impossible to pass by accident, which `eval_cases` already
    does by having no default.
    """
    if partition not in Partition:
        msg = f"unknown partition {partition!r}"
        raise ValueError(msg)


def _trial(nct_id: str) -> TrialRecord:
    return next(trial for trial in load_trial_fixtures() if trial.nct_id == nct_id)


def _assessed(run: MatchingRun) -> int:
    return sum(
        1
        for assessment in run.trial_assessments
        for criterion in assessment.criteria
        if isinstance(criterion, AssessedCriterion)
    )
