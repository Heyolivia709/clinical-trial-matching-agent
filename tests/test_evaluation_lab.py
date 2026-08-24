"""Offline grading, the baseline, and the reported counts.

Gate 4, specification sections 8.1 and 20. Every number here is computed from
frozen transcripts, which is why the assertions are about shape, denominators,
and discipline rather than about how well a model did. `fixtures/transcripts`
says why no published number may come from them.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctma.adapters.model import REPLAY_CONFIGURATION, FrozenReplayModel, RecordedCall
from ctma.adapters.transcripts import load_transcript
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.enums import CriterionState, Partition
from ctma.evaluation.baseline import BASELINE_PROMPT_VERSION, baseline_prompt, one_shot
from ctma.evaluation.cases import EvalCase, eval_cases
from ctma.evaluation.counts import corrections_attempted, validity_before_correction
from ctma.evaluation.grading import (
    NotComparableError,
    Variant,
    compare_reference_validity,
)
from ctma.evaluation.lab import VariantResult, run_agent, run_one_shot, timeline_for, totals

CASES = eval_cases(Partition.DEVELOPMENT)


def agent_results() -> list[VariantResult]:
    return [
        run_agent(
            case,
            model=load_transcript(f"{case.scenario_id.lower()}-development").replay(
                REPLAY_CONFIGURATION
            ),
        )
        for case in CASES
    ]


def baseline_results() -> list[VariantResult]:
    return [
        run_one_shot(
            case,
            model=load_transcript(f"{case.scenario_id.lower()}-baseline").replay(
                REPLAY_CONFIGURATION
            ),
        )
        for case in CASES
    ]


AGENT = agent_results()
BASELINE = baseline_results()


def test_every_track_one_invariant_is_executable_and_reports_pass_or_fail() -> None:
    """Section 20's release gates, as results rather than as prose."""
    for result in AGENT:
        assert len(result.invariants) == 7
        for invariant in result.invariants:
            assert isinstance(invariant.passed, bool)
            assert invariant.detail
        failed = [item for item in result.invariants if not item.passed]
        assert not failed, [(item.invariant.value, item.detail) for item in failed]


def test_reference_validity_in_final_output_may_not_be_compared() -> None:
    """It is 100% because the verifier degrades what it cannot verify.

    A variant with no verifier has no such guarantee, so the comparison would
    publish an architectural difference as a finding. The harness refuses.
    """
    with pytest.raises(NotComparableError, match="structural"):
        compare_reference_validity(AGENT, BASELINE)


def test_the_comparison_uses_the_agent_before_correction() -> None:
    """What the citations were when the agent first committed to them."""
    graded = tuple(item for result in AGENT for item in result.graded)
    before = validity_before_correction(graded)
    assert before.denominator == sum(1 for item in graded if item.runtime_verdicts)
    assert before.denominator > 0
    assert corrections_attempted(graded).denominator == before.denominator


def test_both_variants_are_graded_by_the_same_verifier_at_the_same_call_site() -> None:
    source = Path("src/ctma/evaluation/grading.py").read_text()
    assert source.count("verify(") >= 3, "grading calls one verifier for every variant"
    assert "verifier_feedback" not in source, "grading never turns feedback on for anyone"


def test_the_baseline_sees_the_whole_record_and_calls_no_tool() -> None:
    """The asymmetry the comparison rests on, as an assertion about the prompt."""
    case = CASES[0]
    timeline = timeline_for(case.scenario_id)
    trial = next(item for item in load_trial_fixtures() if item.nct_id == case.nct_id)
    prompt = baseline_prompt(trial.criteria[0], timeline)
    for fact in timeline.facts:
        assert fact.resource_id in prompt
    assert "find_patient_facts" not in prompt
    assert "get_latest_observation" not in prompt
    assert BASELINE_PROMPT_VERSION == "baseline-one-shot-v1"


def test_a_baseline_reply_that_will_not_parse_is_recorded_and_not_retried() -> None:
    """Section 16 allows recorded retries and forbids hidden ones."""
    case = CASES[0]
    trial = next(item for item in load_trial_fixtures() if item.nct_id == case.nct_id)
    criterion = trial.criteria[0]
    model = FrozenReplayModel.from_transcript(
        (
            RecordedCall(
                key=f"assessment|{criterion.criterion_id}|ALL|1",
                prompt="recorded",
                json_text="I would say the patient qualifies.",
            ),
        ),
        configuration=REPLAY_CONFIGURATION,
    )
    answers = one_shot(criterion, timeline=timeline_for(case.scenario_id), trial=trial, model=model)
    assert answers.assessments == ()
    assert len(answers.failures) == 1
    assert len(model.requests) == 1


def test_a_baseline_answer_that_does_not_fit_the_schema_is_recorded_per_assessment() -> None:
    case = CASES[0]
    trial = next(item for item in load_trial_fixtures() if item.nct_id == case.nct_id)
    criterion = trial.criteria[0]
    model = FrozenReplayModel.from_transcript(
        (
            RecordedCall(
                key=f"assessment|{criterion.criterion_id}|ALL|1",
                prompt="recorded",
                json_text=json.dumps(
                    {"assessments": [{"proposition_id": "P1", "state": "eligible"}]}
                ),
            ),
        ),
        configuration=REPLAY_CONFIGURATION,
    )
    answers = one_shot(criterion, timeline=timeline_for(case.scenario_id), trial=trial, model=model)
    assert answers.assessments == ()
    assert answers.failures


def test_the_counts_state_their_denominators() -> None:
    counts = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    assert counts.scenarios == 4
    assert counts.trials == 2
    assert counts.propositions == sum(len(result.graded) for result in AGENT)
    assert "4 scenarios and 2 trials" in counts.sample_sentence()
    assert "no interval, test, or effect size" in counts.sample_sentence()


def test_state_agreement_is_per_state_and_never_one_aggregate() -> None:
    """An aggregate over four states hides which state the system is bad at."""
    counts = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    assert set(counts.state_agreement) == set(CriterionState)
    for count in counts.state_agreement.values():
        assert count.numerator <= count.denominator


def test_unknown_reason_agreement_is_reported_separately_from_the_state() -> None:
    """Right state, wrong reason is a different failure, and it shows up here."""
    agent = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    baseline = totals(BASELINE, variant=Variant.BASELINE, partition=Partition.DEVELOPMENT)
    assert agent.reason_agreement.denominator == baseline.reason_agreement.denominator
    assert (
        baseline.reason_agreement.numerator
        < baseline.state_agreement[CriterionState.UNKNOWN].numerator
    ), "the baseline reaches `unknown` more often than it reaches the right reason"


def test_coverage_only_propositions_are_visible_and_not_scored() -> None:
    counts = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    assert counts.scorable_propositions + counts.coverage_only_propositions == counts.propositions
    scorable = sum(1 for result in AGENT for item in result.graded if item.scorable)
    assert counts.scorable_propositions == scorable


def test_cost_is_reported_beside_the_grounding_it_purchased() -> None:
    counts = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    assert counts.cost.criterion_assessments > 0
    assert counts.cost.calls_per_criterion is not None
    assert counts.reference_validity.denominator == counts.propositions


def test_a_count_with_no_denominator_has_no_percentage() -> None:
    """0% reads as a result. "0 of 0" reads as what it is."""
    counts = totals(AGENT, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    empty = counts.state_agreement[CriterionState.NOT_APPLICABLE]
    assert empty.denominator == 0
    assert empty.percent is None
    assert empty.rendered() == "0 of 0"


def test_the_held_out_half_is_not_run_by_asking_for_the_development_one() -> None:
    """Held-out artifacts stay inert until someone names them."""
    assert all(case.partition is Partition.DEVELOPMENT for case in CASES)
    assert all(
        result.case_id.split("|")[0] in {"SCN-01", "SCN-02", "SCN-03", "SCN-04"} for result in AGENT
    )


def test_every_scorable_proposition_has_an_expected_state_from_the_manifest() -> None:
    """No label is model-produced, so every one of them came from the derivation."""
    cases = {case.case_id: case for case in CASES}
    for result in AGENT:
        case: EvalCase = cases[result.case_id]
        expected = {
            (criterion.criterion_id, proposition.proposition_id)
            for criterion in case.criteria
            for proposition in criterion.propositions
        }
        for item in result.graded:
            assert (item.criterion_id, item.proposition_id) in expected
