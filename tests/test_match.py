"""`match()` end to end, and the two supervisor flags.

Gate 3, specification sections 11, 12 and 14. Every run here replays a frozen
transcript, so the counts — criteria covered, calls made, criteria skipped — are
properties of the code rather than of a model's mood.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctma.adapters.model import REPLAY_CONFIGURATION, FrozenReplayModel, RecordedCall
from ctma.adapters.scenario_bundles import ScenarioInput, load_scenario_input
from ctma.adapters.transcripts import load_transcript
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.assessment import AssessedCriterion, SkippedCriterion
from ctma.domain.enums import (
    CandidateStatus,
    CriterionImpact,
    CriterionState,
    MatchConclusion,
    Partition,
    ReportingStatus,
)
from ctma.domain.run import MatchingRun, SupervisorConfiguration
from ctma.domain.trace import SupervisorAction
from ctma.domain.trajectory import evidence_trajectory
from ctma.match import EVALUATOR_VERSION, match, read_run, write_run
from ctma.supervisor.strategy import assess_trial
from ctma.timeline.build import build
from tests.builders import screening_trial

TRIALS = load_trial_fixtures(Partition.DEVELOPMENT)
SCENARIO = load_scenario_input("SCN-01")
TRANSCRIPT = load_transcript("scn-01-development")


def run_for(
    scenario: ScenarioInput = SCENARIO,
    *,
    supervisor: SupervisorConfiguration | None = None,
    verifier_feedback: bool = True,
) -> MatchingRun:
    return match(
        scenario_id=scenario.scenario_id,
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=TRIALS,
        model=TRANSCRIPT.replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id="scn-01-development",
        supervisor=supervisor or SupervisorConfiguration(),
        verifier_feedback=verifier_feedback,
    )


RUN = run_for()


def test_a_run_assesses_every_criterion_of_every_assessed_trial() -> None:
    """Criterion Coverage is 100% with the flags off, and that is a gate."""
    assessed = [
        candidate
        for candidate in RUN.candidates.candidates
        if candidate.status is CandidateStatus.ASSESSED
    ]
    assert {candidate.nct_id for candidate in assessed} == {trial.nct_id for trial in TRIALS}
    for trial in TRIALS:
        assessment = next(item for item in RUN.trial_assessments if item.nct_id == trial.nct_id)
        assert len(assessment.criteria) == len(trial.criteria)
        assert [item.criterion_id for item in assessment.criteria] == [
            item.criterion_id for item in trial.criteria
        ]


def test_a_run_records_what_produced_it() -> None:
    """Section 14: the identities and the frozen configuration versions."""
    assert RUN.identities.scenario_id == "SCN-01"
    assert RUN.identities.bundle_sha256
    assert RUN.identities.partition is Partition.DEVELOPMENT
    assert RUN.configuration.evaluator_version == EVALUATOR_VERSION
    assert RUN.configuration.model.adapter.value == "frozen_replay"
    assert RUN.configuration.tool_version.startswith("timeline-v1")
    assert RUN.measurements.latency_ms >= 0


def test_a_run_round_trips_through_json_and_can_be_re_graded(tmp_path: Path) -> None:
    """A frozen trace is re-read offline, long after the run that wrote it."""
    path = write_run(RUN, tmp_path / "run.json")
    restored = read_run(path)
    assert restored == RUN
    assert evidence_trajectory(restored.trial_assessments[0])


def test_no_criterion_is_dropped_and_none_arrives_twice() -> None:
    for assessment in RUN.trial_assessments:
        ids = [criterion.criterion_id for criterion in assessment.criteria]
        assert len(ids) == len(set(ids))


def test_the_trials_are_ordered_by_review_priority_and_keep_their_rank() -> None:
    """Two orderings, both recoverable, neither derived from the other."""
    ranks = [assessment.retrieval_rank for assessment in RUN.trial_assessments]
    assert sorted(ranks) == [1, 2]
    by_id = {candidate.nct_id: candidate for candidate in RUN.candidates.candidates}
    for assessment in RUN.trial_assessments:
        assert by_id[assessment.nct_id].retrieval_rank == assessment.retrieval_rank


SCREENING = screening_trial()
BRAIN_METS = load_scenario_input("SCN-03")


def screening_replay(state: str = "met"):
    """SCN-03 has documented brain metastases, so the exclusion comes out met.

    No development trial excludes a condition the reviewed terminology mapping
    covers, so a blocker needs the two-criterion trial `tests.builders` authors
    for exactly this. The gap is a limitation to publish, not a reason to leave
    trial-level strategy untested.
    """
    calls = (
        RecordedCall(
            key="assessment|NCT00000001:EXC-1|P1|1",
            prompt="recorded",
            json_text=json.dumps(
                {
                    "state": state,
                    "citations": [
                        {"fact_ids": ["Condition/cond-brainmet"], "relation": "supports"}
                    ],
                    "rationale": "Brain metastases are documented in the record.",
                }
            ),
        ),
        RecordedCall(
            key="tool_selection|NCT00000001:INC-1|P1|1",
            prompt="recorded",
            json_text=json.dumps({"lookup": "get_latest_observation", "comparison": None}),
        ),
    )
    return FrozenReplayModel.from_transcript(calls, configuration=REPLAY_CONFIGURATION)


def screened(*, early_termination: bool):
    timeline = build(
        BRAIN_METS.bundle_json,
        scenario_id=BRAIN_METS.scenario_id,
        assessment_as_of=BRAIN_METS.assessment_as_of,
    )
    return assess_trial(
        SCREENING,
        timeline=timeline,
        model=screening_replay(),
        retrieval_rank=1,
        configuration=SupervisorConfiguration(early_termination=early_termination),
    )


def test_a_confirmed_blocker_stops_the_trial_and_the_rest_is_not_assessed() -> None:
    """Section 11's hazard: what the flag costs is Criterion Coverage.

    A skipped criterion has no state at all, so "the supervisor stopped" cannot
    be read as "the evidence was inadequate".
    """
    supervised = screened(early_termination=True)
    criteria = {item.criterion_id: item for item in supervised.assessment.criteria}
    blocker = criteria["NCT00000001:EXC-1"]
    skipped = criteria["NCT00000001:INC-1"]

    assert isinstance(blocker, AssessedCriterion)
    assert blocker.impact is CriterionImpact.BLOCKING
    assert isinstance(skipped, SkippedCriterion)
    assert skipped.blocker_criterion_id == "NCT00000001:EXC-1"
    assert not hasattr(skipped, "state")

    step = evidence_trajectory(supervised.assessment)[1]
    assert step.reporting_status is ReportingStatus.NOT_ASSESSED
    assert step.state is None
    assert step.unknown_reason is None


def test_early_termination_records_what_it_skipped_and_why() -> None:
    supervised = screened(early_termination=True)
    decision = next(
        item for item in supervised.decisions if item.action is SupervisorAction.EARLY_TERMINATION
    )
    assert decision.criterion_id == "NCT00000001:EXC-1"
    assert "1 criteria not assessed" in decision.detail


def test_with_the_flag_off_the_same_trial_assesses_everything() -> None:
    """The flags-off run is the one correctness is measured on."""
    supervised = screened(early_termination=False)
    assert all(
        isinstance(criterion, AssessedCriterion) for criterion in supervised.assessment.criteria
    )
    assert supervised.decisions == ()


def test_a_blocked_trial_is_an_unlikely_match() -> None:
    """Section 7.2: one confirmed blocker decides the conclusion."""
    assert screened(early_termination=True).assessment.conclusion is MatchConclusion.UNLIKELY_MATCH


def test_ordering_the_criteria_changes_no_result_and_is_recorded() -> None:
    """Section 11: the flag buys time to the first blocker and nothing else.

    Output stays in authored order, so the ablation row compares like with
    like; what the ordering did is in the trace instead.
    """
    ordered = run_for(supervisor=SupervisorConfiguration(order_criteria=True))
    assert _states(ordered) == _states(RUN)
    decisions = [
        decision
        for decision in ordered.trace.supervisor_decisions
        if decision.action is SupervisorAction.ORDER_CRITERIA
    ]
    assert len(decisions) == len(TRIALS)
    assert all("blocker" in decision.detail for decision in decisions)


def test_the_flags_off_run_is_the_one_the_others_are_compared_against() -> None:
    """Same transcript, same configuration, same result. Twice."""
    assert _states(run_for()) == _states(RUN)
    assert RUN.trace.supervisor_decisions == ()


def test_a_dropped_trial_leaves_a_failure_and_not_more_uncertainty() -> None:
    """An empty transcript is an unreachable model, which is section 8.2's case."""
    run = match(
        scenario_id=SCENARIO.scenario_id,
        bundle_json=SCENARIO.bundle_json,
        assessment_as_of=SCENARIO.assessment_as_of,
        trials=TRIALS,
        model=load_transcript("scn-02-development").replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id="mismatched-transcript",
    )
    assert run.failures
    assert all(failure.kind.value == "model_unavailable" for failure in run.failures)
    assessed = {assessment.nct_id for assessment in run.trial_assessments}
    for candidate in run.candidates.candidates:
        if candidate.status is CandidateStatus.ASSESSED:
            assert candidate.nct_id in assessed
    assert any(warning.code == "trial_not_assessed" for warning in run.warnings)


def test_the_no_verifier_configuration_produces_a_run_with_no_verification() -> None:
    run = run_for(verifier_feedback=False)
    for assessment in run.trial_assessments:
        for criterion in assessment.criteria:
            if isinstance(criterion, AssessedCriterion):
                for proposition in criterion.propositions:
                    assert proposition.verification == ()


@pytest.mark.parametrize("scenario_id", ["SCN-01", "SCN-02", "SCN-03", "SCN-04"])
def test_every_development_scenario_runs_end_to_end(scenario_id: str) -> None:
    scenario = load_scenario_input(scenario_id)
    run = match(
        scenario_id=scenario_id,
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=TRIALS,
        model=load_transcript(f"{scenario_id.lower()}-development").replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id=f"{scenario_id.lower()}-development",
    )
    assert run.failures == ()
    assert len(run.trial_assessments) == len(TRIALS)


def _states(run: MatchingRun) -> list[tuple[str, str]]:
    return [
        (
            criterion.criterion_id,
            criterion.state.value if isinstance(criterion, AssessedCriterion) else "not_assessed",
        )
        for assessment in sorted(run.trial_assessments, key=lambda item: item.nct_id)
        for criterion in assessment.criteria
    ]


def test_a_criterion_state_is_never_read_off_a_skipped_criterion() -> None:
    """The type has no state to read, which is the invariant rather than a rule."""
    run = run_for(supervisor=SupervisorConfiguration(early_termination=True))
    for assessment in run.trial_assessments:
        for criterion in assessment.criteria:
            if isinstance(criterion, SkippedCriterion):
                assert not hasattr(criterion, "state")
            else:
                assert isinstance(criterion.state, CriterionState)


def test_the_one_development_pair_a_criterion_rules_out() -> None:
    """The blocking half of the impact model, on a record rather than a builder.

    Until SCN-03 carried a primary brain tumour, every development pair ended
    `insufficient_information` and the whole blocking path — `met` on an
    exclusion becoming `blocking`, and the conclusion flipping because of it —
    was exercised only by unit tests over hand-built criteria.
    """
    scenario = load_scenario_input("SCN-03")
    run = match(
        scenario_id="SCN-03",
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=TRIALS,
        model=load_transcript("scn-03-development").replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id="scn-03-development",
    )
    assessment = next(item for item in run.trial_assessments if item.nct_id == "NCT07349537")
    assert assessment.conclusion is MatchConclusion.UNLIKELY_MATCH

    blocking = [
        criterion
        for criterion in assessment.criteria
        if isinstance(criterion, AssessedCriterion) and criterion.impact is CriterionImpact.BLOCKING
    ]
    assert [criterion.criterion_id for criterion in blocking] == ["NCT07349537:EXC-1"]
    assert blocking[0].state is CriterionState.MET, "an exclusion that is met is what blocks"
