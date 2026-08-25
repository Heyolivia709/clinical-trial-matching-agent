"""Offline grading: one verifier, one configuration, every variant.

Specification sections 8.1 and 20. The verifier has two roles and they are kept
apart by call site, not by configuration. Runtime feedback reaches the agent
loop and triggers its one correction. This module is the other call site: it
scores final outputs, and nothing it computes flows back into the system under
test.

Grading the baseline by the same standard is the whole point of the comparison.
The baseline never gets to consult that standard, which is the measured
architectural difference rather than a confound, and it is stated wherever the
numbers appear.

**Reference validity in final output is structural and may not be compared.**
The agent reaches 100% because the verifier degrades anything it cannot verify
to `unknown`. A variant with no verifier has no such guarantee, so comparing
them would publish an architectural difference as a result. Asking this module
for that comparison raises.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from enum import StrEnum

from pydantic import Field

from ctma.adapters.injected_faults import load_injected_faults
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.agent.verifier import verify, verify_aggregation
from ctma.domain.assessment import (
    AssessedCriterion,
    PropositionAssessment,
    SkippedCriterion,
    UnexpressedCriterion,
    UnknownAssessment,
)
from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState, UnknownReason
from ctma.domain.proposal import ProposedAssessment, ProposedCitation
from ctma.domain.run import MatchingRun
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trace import VerifierOutcome, VerifierRejection, VerifierVerdict
from ctma.domain.trial import TrialRecord
from ctma.evaluation.baseline import BaselineAnswers
from ctma.evaluation.cases import EvalCase
from ctma.evaluation.gold import ExpectedProposition
from ctma.timeline._terminology import codes_for_concept
from ctma.timeline.build import build

REFERENCE_REJECTIONS = frozenset(
    {
        VerifierRejection.NONEXISTENT_REFERENCE,
        VerifierRejection.CITATION_DISAGREES_WITH_TIMELINE,
        VerifierRejection.INVALID_TRIAL_SPAN,
    }
)
"""What "reference validity" counts: a citation that does not resolve, or that
resolves and disagrees with the source."""


class Variant(StrEnum):
    """The three configurations of the measurement plan."""

    AGENT = "agent"
    AGENT_NO_VERIFIER = "agent_no_verifier"
    BASELINE = "baseline"


class NotComparableError(ValueError):
    """A number that is a property of the implementation, asked for as a result."""


class GradedProposition(Frozen):
    """One variant's answer to one proposition, beside what was expected."""

    case_id: str = Field(min_length=1)
    criterion_id: str = Field(min_length=1)
    proposition_id: str = Field(min_length=1)
    variant: Variant
    state: CriterionState
    reason: UnknownReason | None = None
    expected_state: CriterionState | None = None
    expected_reason: UnknownReason | None = None
    scorable: bool = False
    gradable_reason: bool = True
    """False when the reviewed mapping does not cover this proposition's concept.

    A property of the proposition and the mapping, not of the variant, so both
    variants drop the same propositions from the reason denominator. Excluding
    only the one that reports the coverage limit would compare two different
    question sets, which is the confound this comparison exists to avoid.
    """
    grading: VerifierOutcome
    """The offline verdict on the final output. Never fed back."""

    runtime_verdicts: tuple[VerifierVerdict, ...] = ()
    """What the runtime verifier said, in order. Empty for the baseline and for
    the no-verifier configuration, which is what those variants are."""

    @property
    def state_agrees(self) -> bool:
        return self.scorable and self.state is self.expected_state

    @property
    def reason_agrees(self) -> bool:
        """Only asked of an `unknown`: a right state for the wrong reason is a
        different failure, and section 8.0's taxonomy exists because a
        coordinator acts differently on each."""
        return self.scorable and self.reason is self.expected_reason

    @property
    def references_valid(self) -> bool:
        return not (set(self.grading.rejections) & REFERENCE_REJECTIONS)

    @property
    def unsupported(self) -> bool:
        """A `met` or `not_met` whose citation cannot establish it."""
        return VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE in self.grading.rejections

    @property
    def cites_after_the_assessment_time(self) -> bool:
        return VerifierRejection.EVIDENCE_AFTER_ASSESSMENT_TIME in self.grading.rejections

    @property
    def verification_induced_unknown(self) -> bool:
        """Committed to before correction, `unknown` after it.

        Published beside post-correction validity, at equal prominence: a
        verifier that rejected everything would report perfect validity and be
        worthless, and this is the number that separates the two.
        """
        return self.reason is UnknownReason.VERIFICATION_FAILED


class InvariantName(StrEnum):
    """The seven release gates of specification section 20."""

    REFERENCE_VALIDITY = "reference_validity_in_final_output"
    AGGREGATION_ACCURACY = "deterministic_aggregation_accuracy"
    VERIFIER_CATCH_RATE = "verifier_catch_rate_on_injected_faults"
    UNSUPPORTED_SURVIVING = "unsupported_assessments_surviving_verification"
    CRITERION_COVERAGE = "criterion_coverage_with_early_termination_off"
    CITATIONS_AFTER_ASSESSMENT_TIME = "citations_after_assessment_time"
    FAILURES_SCORED_AS_UNKNOWN = "infrastructure_failures_scored_as_unknown"


class InvariantResult(Frozen):
    """Pass or fail, and the violation named on a failure.

    Absolute rather than a percentage: section 20 makes these properties the
    implementation controls, so one violation is a failure.
    """

    invariant: InvariantName
    passed: bool
    detail: str = Field(min_length=1)


def _reason_is_gradable(criterion_id: str, proposition_id: str, trial: TrialRecord) -> bool:
    """Whether a diagnosis for this proposition can be graded at all.

    Gold describes the record; it knows nothing about what this system covers.
    So for a concept outside the reviewed mapping there is no diagnosis to
    compare — one side is talking about a patient and the other about a
    terminology table.
    """
    criterion = next((item for item in trial.criteria if item.criterion_id == criterion_id), None)
    if criterion is None:
        return True
    proposition = next(
        (item for item in criterion.propositions if item.proposition_id == proposition_id), None
    )
    if proposition is None or proposition.concept is None:
        return True
    return codes_for_concept(proposition.concept) is not None


def grade_run(
    run: MatchingRun,
    *,
    case: EvalCase,
    timeline: PatientTimeline,
    trial: TrialRecord,
    variant: Variant = Variant.AGENT,
) -> tuple[GradedProposition, ...]:
    """Score one trial's final output against the case, offline."""
    expected = _expected(case)
    graded: list[GradedProposition] = []
    for assessment in run.trial_assessments:
        if assessment.nct_id != trial.nct_id:
            continue
        for criterion in assessment.criteria:
            if not isinstance(criterion, AssessedCriterion):
                continue
            for proposition in criterion.propositions:
                graded.append(
                    _graded(
                        proposition,
                        criterion_id=criterion.criterion_id,
                        case=case,
                        expected=expected,
                        timeline=timeline,
                        trial=trial,
                        variant=variant,
                    )
                )
    return tuple(graded)


def grade_baseline(
    answers: Sequence[BaselineAnswers],
    *,
    case: EvalCase,
    timeline: PatientTimeline,
    trial: TrialRecord,
) -> tuple[GradedProposition, ...]:
    """The same verifier, the same configuration, on the control variant."""
    expected = _expected(case)
    graded: list[GradedProposition] = []
    for answer in answers:
        for proposal in answer.assessments:
            key = (answer.criterion_id, proposal.proposition_id)
            gold = expected.get(key)
            graded.append(
                GradedProposition(
                    case_id=case.case_id,
                    criterion_id=answer.criterion_id,
                    proposition_id=proposal.proposition_id,
                    variant=Variant.BASELINE,
                    state=proposal.state,
                    reason=proposal.reason,
                    expected_state=gold.state if gold else None,
                    expected_reason=gold.reason if gold else None,
                    scorable=bool(gold and gold.scorable),
                    gradable_reason=_reason_is_gradable(
                        answer.criterion_id, proposal.proposition_id, trial
                    ),
                    grading=verify(proposal, timeline=timeline, trial=trial),
                )
            )
    return tuple(graded)


def track_one(
    run: MatchingRun,
    graded: Sequence[GradedProposition],
    *,
    case: EvalCase,
    trial: TrialRecord,
    timeline: PatientTimeline,
) -> tuple[InvariantResult, ...]:
    """Every deterministic release gate of section 20, reported pass or fail."""
    return (
        _no_rejection(
            graded,
            InvariantName.REFERENCE_VALIDITY,
            lambda item: not item.references_valid,
            "every citation in final output resolves and agrees with its source",
        ),
        _aggregation(run, trial),
        _catch_rate(),
        _no_rejection(
            graded,
            InvariantName.UNSUPPORTED_SURVIVING,
            lambda item: item.unsupported,
            "no assessment in final output rests on a citation that cannot establish it",
        ),
        _coverage(run, case, trial),
        _no_rejection(
            graded,
            InvariantName.CITATIONS_AFTER_ASSESSMENT_TIME,
            lambda item: item.cites_after_the_assessment_time,
            "nothing in final output is cited from after the Assessment Time",
        ),
        _failures_stay_failures(run, timeline),
    )


def compare_reference_validity(*_: object) -> None:
    """Refuse. This number is a property of the implementation, not a result.

    The agent reaches 100% because the verifier degrades what it cannot verify.
    A variant without one has no such guarantee, so the comparison would report
    an architectural difference as a finding. Comparisons use the agent before
    correction, which is what `runtime_verdicts` records.
    """
    msg = (
        "reference validity in final output is structural and may not be compared "
        "across variants; compare the agent before correction instead"
    )
    raise NotComparableError(msg)


def _expected(case: EvalCase) -> dict[tuple[str, str], ExpectedProposition]:
    return {
        (criterion.criterion_id, proposition.proposition_id): proposition
        for criterion in case.criteria
        for proposition in criterion.propositions
    }


def _graded(
    assessment: PropositionAssessment,
    *,
    criterion_id: str,
    case: EvalCase,
    expected: dict[tuple[str, str], ExpectedProposition],
    timeline: PatientTimeline,
    trial: TrialRecord,
    variant: Variant,
) -> GradedProposition:
    gold = expected.get((criterion_id, assessment.proposition_id))
    return GradedProposition(
        case_id=case.case_id,
        criterion_id=criterion_id,
        proposition_id=assessment.proposition_id,
        variant=variant,
        state=assessment.state,
        reason=assessment.reason if isinstance(assessment, UnknownAssessment) else None,
        expected_state=gold.state if gold else None,
        expected_reason=gold.reason if gold else None,
        scorable=bool(gold and gold.scorable),
        gradable_reason=_reason_is_gradable(criterion_id, assessment.proposition_id, trial),
        grading=verify(as_proposal(assessment), timeline=timeline, trial=trial),
        runtime_verdicts=tuple(outcome.verdict for outcome in assessment.verification),
    )


def as_proposal(assessment: PropositionAssessment) -> ProposedAssessment:
    """A finished assessment, back in the shape the verifier reads.

    Grading has to put both variants through one function, and the baseline
    only ever produces proposals. Nothing is lost on the way: the fields the
    verifier compares are the fields a citation carries.
    """
    return ProposedAssessment(
        proposition_id=assessment.proposition_id,
        state=assessment.state,
        reason=assessment.reason if isinstance(assessment, UnknownAssessment) else None,
        trial_evidence=assessment.trial_evidence,
        patient_evidence=tuple(
            ProposedCitation(facts=evidence.facts, relation=evidence.relation)
            for evidence in assessment.patient_evidence
        ),
        rationale=assessment.rationale,
    )


def _no_rejection(
    graded: Sequence[GradedProposition],
    invariant: InvariantName,
    fails: Callable[[GradedProposition], bool],
    passed_detail: str,
) -> InvariantResult:
    violations = [item for item in graded if fails(item)]
    if violations:
        named = ", ".join(f"{item.criterion_id}/{item.proposition_id}" for item in violations[:5])
        return InvariantResult(
            invariant=invariant,
            passed=False,
            detail=f"{len(violations)} of {len(graded)} violate this: {named}",
        )
    return InvariantResult(
        invariant=invariant, passed=True, detail=f"{passed_detail} ({len(graded)} propositions)"
    )


def _aggregation(run: MatchingRun, trial: TrialRecord) -> InvariantResult:
    """Every claimed Criterion State recomputed from its propositions."""
    by_id = {criterion.criterion_id: criterion for criterion in trial.criteria}
    violations: list[str] = []
    checked = 0
    for assessment in run.trial_assessments:
        if assessment.nct_id != trial.nct_id:
            continue
        for criterion in assessment.criteria:
            if not isinstance(criterion, AssessedCriterion):
                continue
            checked += 1
            outcome = verify_aggregation(
                criterion.state,
                criterion=by_id[criterion.criterion_id],
                states={
                    proposition.proposition_id: proposition.state
                    for proposition in criterion.propositions
                },
            )
            if outcome.verdict is VerifierVerdict.REJECTED:
                violations.append(criterion.criterion_id)
    return InvariantResult(
        invariant=InvariantName.AGGREGATION_ACCURACY,
        passed=not violations,
        detail=(
            f"{checked} criteria recomputed from their propositions"
            if not violations
            else f"these do not follow from their propositions: {violations}"
        ),
    )


def _catch_rate() -> InvariantResult:
    """The injected faults, caught by the check each was authored to trip.

    Run here rather than trusted from the test suite: a release gate reported in
    the same table as the results has to be computed by the same code path.
    """
    trials = {item.nct_id: item for item in load_trial_fixtures()}
    missed: list[str] = []
    faults = load_injected_faults()
    injected = [fault for fault in faults.citations if fault.expected_rejection is not None]
    for fault in injected:
        scenario = load_scenario_input(fault.scenario_id)
        timeline = build(
            scenario.bundle_json,
            scenario_id=scenario.scenario_id,
            assessment_as_of=scenario.assessment_as_of,
        )
        outcome = verify(fault.proposal, timeline=timeline, trial=trials[fault.nct_id])
        if fault.expected_rejection not in outcome.rejections:
            missed.append(fault.fault_id)
    return InvariantResult(
        invariant=InvariantName.VERIFIER_CATCH_RATE,
        passed=not missed,
        detail=(
            f"{len(injected)} of {len(injected)} injected faults caught by the check they "
            "were authored to trip"
            if not missed
            else f"these were not caught: {missed}"
        ),
    )


def _coverage(run: MatchingRun, case: EvalCase, trial: TrialRecord) -> InvariantResult:
    """Every criterion of the trial is reported, in some form."""
    if run.configuration.supervisor.early_termination:
        return InvariantResult(
            invariant=InvariantName.CRITERION_COVERAGE,
            passed=True,
            detail="not gated: early_termination forfeits coverage by design",
        )
    reported = {
        criterion.criterion_id
        for assessment in run.trial_assessments
        if assessment.nct_id == trial.nct_id
        for criterion in assessment.criteria
        if not isinstance(criterion, SkippedCriterion)
    }
    authored = {criterion.criterion_id for criterion in trial.criteria}
    missing = sorted(authored - reported)
    return InvariantResult(
        invariant=InvariantName.CRITERION_COVERAGE,
        passed=not missing,
        detail=(
            f"{len(reported)} of {len(authored)} criteria reported for {case.case_id}"
            if not missing
            else f"these criteria are missing from output: {missing}"
        ),
    )


def _failures_stay_failures(run: MatchingRun, timeline: PatientTimeline) -> InvariantResult:
    """An Infrastructure Failure is recorded as one and scored as nothing.

    Checked two ways, because there are two ways to break it: a failure that
    left an assessment behind, and an `unknown` that is really an outage.
    """
    assessed = {assessment.nct_id for assessment in run.trial_assessments}
    unexpressed = [
        criterion.criterion_id
        for assessment in run.trial_assessments
        for criterion in assessment.criteria
        if isinstance(criterion, UnexpressedCriterion)
    ]
    scored_failures = [failure for failure in run.failures if failure.where in assessed]
    passed = not scored_failures
    return InvariantResult(
        invariant=InvariantName.FAILURES_SCORED_AS_UNKNOWN,
        passed=passed,
        detail=(
            f"{len(run.failures)} failures recorded separately from "
            f"{len(assessed)} assessed trials, {len(unexpressed)} unexpressed criteria"
            if passed
            else f"a failure left an assessment behind: {scored_failures}"
        ),
    )
