"""The entry point: one patient, four trials, one Matching Run.

Specification section 12 keeps this thin, and thin is a claim about where the
work lives rather than about how long the file is. Everything here is wiring:
the policy decides what is presented and assessed, the supervisor assesses it,
the timeline and the trials come from adapters, and nothing in this module
decides anything a reader would want to argue with.

Two things it does own.

**Infrastructure Failures stay separate.** A model that cannot be reached takes
its trial out of the run — the failure is recorded, and the criteria it would
have produced are absent rather than `unknown`. A run that hit an outage has
fewer assessments and a failure to show for it, never more uncertainty, and
that separation is a release gate.

**The partition is passed in, not read.** Which half a scenario belongs to is
recorded in its hidden manifest, and the matching system may not read one. The
Evaluation Lab knows the partition and hands it over.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import time
from collections.abc import Sequence
from pathlib import Path

from ctma.adapters.model import ModelClient, ModelUnavailableError
from ctma.domain.assessment import TrialAssessment
from ctma.domain.enums import CandidateStatus, Partition
from ctma.domain.run import (
    CandidateSet,
    MatchingRun,
    RunConfiguration,
    RunIdentities,
    RunWarning,
    SupervisorConfiguration,
)
from ctma.domain.trace import (
    InfrastructureFailure,
    Measurements,
    ReasoningTrace,
    SupervisorDecision,
)
from ctma.domain.trial import TrialRecord
from ctma.policy import AssessmentShortfall, CandidateInput, plan, review_priority
from ctma.supervisor.strategy import FLAGS_OFF, assess_trial
from ctma.timeline._terminology import TERMINOLOGY_VERSION
from ctma.timeline.build import NORMALIZATION_VERSION, build

EVALUATOR_VERSION = "gate3-match-v1"
"""Bumped when anything that grades or aggregates changes. Recorded on the run,
because a grading change between two runs is otherwise indistinguishable from a
behaviour change."""


def match(
    *,
    scenario_id: str,
    bundle_json: str,
    assessment_as_of: dt.date,
    trials: Sequence[TrialRecord],
    model: ModelClient,
    partition: Partition,
    run_id: str,
    supervisor: SupervisorConfiguration = FLAGS_OFF,
    verifier_feedback: bool = True,
    hardware_profile: str = "unrecorded",
    seed: int = 0,
) -> MatchingRun:
    """Assess one patient against the frozen candidate trials."""
    started = time.monotonic()
    timeline = build(bundle_json, scenario_id=scenario_id, assessment_as_of=assessment_as_of)
    matching = plan(
        [
            CandidateInput(
                nct_id=trial.nct_id,
                snapshot_record_id=trial.snapshot_record_id,
                has_authored_expression=bool(trial.criteria),
            )
            for trial in trials
        ]
    )
    by_id = {trial.nct_id: trial for trial in trials}

    assessments: list[TrialAssessment] = []
    decisions: list[SupervisorDecision] = []
    failures: list[InfrastructureFailure] = []
    for candidate in matching.candidates.assessed:
        try:
            supervised = assess_trial(
                by_id[candidate.nct_id],
                timeline=timeline,
                model=model,
                retrieval_rank=candidate.retrieval_rank,
                configuration=supervisor,
                verifier_feedback=verifier_feedback,
            )
        except ModelUnavailableError as error:
            failures.append(error.failure)
            continue
        assessments.append(supervised.assessment)
        decisions.extend(supervised.decisions)

    candidates = matching.candidates
    if failures:
        candidates = _demote(candidates, {assessment.nct_id for assessment in assessments})

    return MatchingRun(
        run_id=run_id,
        identities=RunIdentities(
            scenario_id=scenario_id,
            bundle_sha256=timeline.bundle_sha256,
            snapshot_id=_snapshot_id(trials),
            snapshot_sha256=_snapshot_hash(trials),
            assessment_as_of=assessment_as_of,
            partition=partition,
        ),
        configuration=RunConfiguration(
            tool_version=f"{NORMALIZATION_VERSION}+{TERMINOLOGY_VERSION}",
            evaluator_version=EVALUATOR_VERSION,
            hardware_profile=hardware_profile,
            seed=seed,
            model=model.configuration,
            supervisor=supervisor,
        ),
        candidates=candidates,
        trial_assessments=review_priority(assessments),
        trace=ReasoningTrace(supervisor_decisions=tuple(decisions)),
        warnings=_warnings(matching.shortfall, matching.expression_unavailable, failures),
        failures=tuple(failures),
        measurements=Measurements.summed(
            (
                *(assessment.measurements for assessment in assessments),
                Measurements(latency_ms=int((time.monotonic() - started) * 1000)),
            )
        ),
    )


def write_run(run: MatchingRun, path: Path) -> Path:
    """Freeze a run to disk. Traces are re-read and re-graded offline."""
    path.write_text(run.model_dump_json(indent=1), encoding="utf-8")
    return path


def read_run(path: Path) -> MatchingRun:
    return MatchingRun.model_validate_json(path.read_text(encoding="utf-8"))


def _demote(candidates: CandidateSet, assessed: set[str]) -> CandidateSet:
    """A candidate whose assessment failed is presented, not assessed.

    Leaving it marked assessed would make the run claim a result it does not
    carry, which is the trial-scale version of silently dropping a criterion.
    """
    return CandidateSet(
        candidates=tuple(
            candidate
            if candidate.status is not CandidateStatus.ASSESSED or candidate.nct_id in assessed
            else candidate.model_copy(update={"status": CandidateStatus.PRESENTED})
            for candidate in candidates.candidates
        )
    )


def _warnings(
    shortfall: AssessmentShortfall | None,
    unexpressed: Sequence[str],
    failures: Sequence[InfrastructureFailure],
) -> tuple[RunWarning, ...]:
    """What the reader is told about the run that is not a result of it."""
    warnings: list[RunWarning] = []
    if shortfall is not None:
        warnings.append(
            RunWarning(
                code="assessment_shortfall",
                detail=f"fewer than three trials were assessed: {shortfall.value}",
            )
        )
    for nct_id in unexpressed:
        warnings.append(
            RunWarning(
                code="expression_unavailable",
                detail=f"{nct_id} was presented with no authored Criterion Expression",
            )
        )
    for failure in failures:
        warnings.append(
            RunWarning(
                code="trial_not_assessed",
                detail=f"a trial was dropped from the run: {failure.detail}",
            )
        )
    return tuple(warnings)


def _snapshot_id(trials: Sequence[TrialRecord]) -> str:
    """The candidate set's identity, which is the set of records it read."""
    return trials[0].snapshot_record_id.split(":")[0] if trials else "empty"


def _snapshot_hash(trials: Sequence[TrialRecord]) -> str:
    """One hash over the eligibility hashes the run compared against.

    Per-record hashes already exist and are checked when a record loads. This
    is the identity of the *set*, so a run made against three trials and one
    made against four are visibly different runs.
    """
    digest = hashlib.sha256()
    for trial in sorted(trials, key=lambda item: item.nct_id):
        digest.update(f"{trial.nct_id}:{trial.eligibility_sha256}".encode())
    return digest.hexdigest()
