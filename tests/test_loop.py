"""The per-proposition agent loop, against a frozen transcript.

Gate 3, specification sections 8.1, 10, 14 and 16. No test here reaches a
model: every answer comes from a recorded transcript, which is also what makes
the counts — how many calls, in what order — assertable at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ctma.adapters.model import (
    REPLAY_CONFIGURATION,
    FrozenReplayModel,
    ModelPurpose,
    ModelUnavailableError,
    RecordedCall,
)
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.agent.loop import assess_criterion, assess_proposition
from ctma.domain.assessment import MetAssessment, NotMetAssessment, UnknownAssessment
from ctma.domain.enums import CriterionState, UnknownReason
from ctma.domain.expression import AtomicProposition, EligibilityCriterion
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trace import VerifierVerdict
from ctma.timeline.build import build

TRIALS = {trial.nct_id: trial for trial in load_trial_fixtures()}
ECOG_CRITERION = "NCT07349537:INC-2"
AGE_CRITERION = "NCT07349537:INC-1"


def timeline_of(scenario_id: str) -> PatientTimeline:
    scenario = load_scenario_input(scenario_id)
    return build(
        scenario.bundle_json,
        scenario_id=scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )


def criterion_of(nct_id: str, criterion_id: str) -> EligibilityCriterion:
    return next(item for item in TRIALS[nct_id].criteria if item.criterion_id == criterion_id)


def proposition_of(criterion: EligibilityCriterion, proposition_id: str) -> AtomicProposition:
    return next(item for item in criterion.propositions if item.proposition_id == proposition_id)


def call(
    purpose: ModelPurpose,
    criterion_id: str,
    proposition_id: str,
    payload: dict[str, Any],
    attempt: int = 1,
) -> RecordedCall:
    return RecordedCall(
        key=f"{purpose.value}|{criterion_id}|{proposition_id}|{attempt}",
        prompt="recorded",
        json_text=json.dumps(payload),
    )


def selection(lookup: str, **comparison: Any) -> dict[str, Any]:
    return {"lookup": lookup, "comparison": comparison or None}


def answer(state: str, *fact_ids: str, relation: str = "supports") -> dict[str, Any]:
    return {
        "state": state,
        "citations": [{"fact_ids": list(fact_ids), "relation": relation}],
        "rationale": "The recorded result answers the proposition.",
    }


def replay(*calls: RecordedCall) -> FrozenReplayModel:
    return FrozenReplayModel.from_transcript(calls, configuration=REPLAY_CONFIGURATION)


def assess(
    scenario_id: str,
    nct_id: str,
    criterion_id: str,
    proposition_id: str,
    model: FrozenReplayModel,
    *,
    verifier_feedback: bool = True,
):
    criterion = criterion_of(nct_id, criterion_id)
    return assess_proposition(
        proposition_of(criterion, proposition_id),
        criterion=criterion,
        timeline=timeline_of(scenario_id),
        trial=TRIALS[nct_id],
        model=model,
        verifier_feedback=verifier_feedback,
    )


def ecog_transcript(state: str = "met", fact_id: str = "Observation/obs-ecog") -> FrozenReplayModel:
    return replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation", operator="==", threshold=1, unit=None),
        ),
        call(ModelPurpose.ASSESSMENT, ECOG_CRITERION, "P2", answer(state, fact_id)),
    )


def test_a_proposition_the_record_answers_produces_a_cited_state() -> None:
    model = ecog_transcript()
    assessment = assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)

    assert isinstance(assessment, MetAssessment)
    assert [call.tool for call in assessment.tool_calls] == [
        "get_latest_observation",
        "compare_numeric",
    ]
    assert assessment.last_verdict is VerifierVerdict.ACCEPTED
    fact = assessment.patient_evidence[0].facts[0]
    assert (fact.resource_id, fact.value, fact.status) == ("obs-ecog", "1.0 {score}", "final")


def test_the_citation_is_written_from_the_record_and_not_from_the_answer() -> None:
    """The model names a fact; the loop fills in what the fact says.

    So the transcript never states a value, and an assessment cannot carry one
    that drifted from the timeline. This is why the agent's citation validity is
    structural rather than a measurement of the model.
    """
    model = ecog_transcript()
    assessment = assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)
    for request in model.requests:
        assert "1.0 {score}" not in request.prompt.split("Facts the tools returned:")[0]
    fact = assessment.patient_evidence[0].facts[0]
    assert fact.display == "ECOG performance status score"
    assert fact.value == "1.0 {score}"


def test_the_packet_withholds_the_bundle_the_trial_record_and_the_manifest() -> None:
    """Section 10 fixes what the model may see, so this checks what it saw."""
    model = ecog_transcript()
    assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)
    scenario = load_scenario_input("SCN-01")
    prompts = "\n".join(request.prompt for request in model.requests)

    assert "Eastern Cooperative Oncology Group" in prompts
    assert '"resourceType"' not in prompts
    assert "cond-htn" not in prompts, "a fact no tool returned reached the model"
    assert "Pathologically documented" not in prompts, "another criterion of the trial leaked"
    assert "design_intent" not in prompts
    assert scenario.bundle_json[:200] not in prompts


def test_a_hazard_is_never_put_to_the_model_as_a_question() -> None:
    """SCN-02's two ECOG scores disagree, so there is nothing to ask about.

    The model chooses the lookup — you have to look before you can know the
    record cannot answer — and is then never asked to assess. That is the
    difference from a one-shot baseline: handed a timeline and a question, a
    baseline answers.
    """
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation"),
        )
    )
    assessment = assess("SCN-02", "NCT07349537", ECOG_CRITERION, "P2", model)

    assert isinstance(assessment, UnknownAssessment)
    assert assessment.reason is UnknownReason.CONFLICTING_EVIDENCE
    assert [request.purpose for request in model.requests] == [ModelPurpose.TOOL_SELECTION]
    cited = {
        fact.resource_id for evidence in assessment.patient_evidence for fact in evidence.facts
    }
    assert cited == {"obs-ecog-clinic", "obs-ecog-infusion"}


def test_a_rejected_citation_gets_exactly_one_correction() -> None:
    """The first answer cites a fact no tool returned, so nothing is cited."""
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation"),
        ),
        call(
            ModelPurpose.ASSESSMENT,
            ECOG_CRITERION,
            "P2",
            answer("met", "Observation/obs-invented"),
        ),
        call(
            ModelPurpose.CORRECTION,
            ECOG_CRITERION,
            "P2",
            answer("met", "Observation/obs-ecog"),
            attempt=2,
        ),
    )
    assessment = assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)

    assert isinstance(assessment, MetAssessment)
    assert [outcome.verdict for outcome in assessment.verification] == [
        VerifierVerdict.REJECTED,
        VerifierVerdict.ACCEPTED,
    ]
    assert [request.purpose for request in model.requests] == [
        ModelPurpose.TOOL_SELECTION,
        ModelPurpose.ASSESSMENT,
        ModelPurpose.CORRECTION,
    ]


def test_a_second_rejection_is_unknown_with_verification_failed() -> None:
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation"),
        ),
        call(
            ModelPurpose.ASSESSMENT,
            ECOG_CRITERION,
            "P2",
            answer("met", "Observation/obs-invented"),
        ),
        call(
            ModelPurpose.CORRECTION,
            ECOG_CRITERION,
            "P2",
            answer("met", "Observation/obs-still-invented"),
            attempt=2,
        ),
    )
    assessment = assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)

    assert isinstance(assessment, UnknownAssessment)
    assert assessment.reason is UnknownReason.VERIFICATION_FAILED
    assert len(assessment.verification) == 2
    assert len(model.requests) == 3, "there are no hidden retries"


def test_the_model_does_not_get_to_overrule_the_arithmetic() -> None:
    """`compare_numeric` says the score is 1 and the answer says it is not.

    Neither side wins: one of the two is wrong and the run cannot say which, so
    the proposition is `unknown` with `reasoning_conflict`.
    """
    model = ecog_transcript(state="not_met")
    assessment = assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)

    assert isinstance(assessment, UnknownAssessment)
    assert assessment.reason is UnknownReason.REASONING_CONFLICT


def test_the_no_verifier_configuration_runs_no_verifier_and_no_correction() -> None:
    """Its output is graded offline by the same code, at another call site."""
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation"),
        ),
        call(
            ModelPurpose.ASSESSMENT,
            ECOG_CRITERION,
            "P2",
            answer("met", "Observation/obs-ecog"),
        ),
    )
    assessment = assess(
        "SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model, verifier_feedback=False
    )
    assert isinstance(assessment, MetAssessment)
    assert assessment.verification == ()
    assert len(model.requests) == 2


def test_an_unreachable_model_is_a_failure_and_never_a_criterion_state() -> None:
    """Section 8.2: scoring an outage as correct uncertainty is a release gate."""
    with pytest.raises(ModelUnavailableError) as raised:
        assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", replay())
    assert raised.value.failure.kind.value == "model_unavailable"


def test_a_reply_that_will_not_parse_twice_is_a_failure_too() -> None:
    """One recorded retry, and then it is the model that is not answering."""
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation"),
        ),
        RecordedCall(
            key=f"assessment|{ECOG_CRITERION}|P2|1", prompt="x", json_text="I think it is met."
        ),
        RecordedCall(
            key=f"correction|{ECOG_CRITERION}|P2|2", prompt="x", json_text="Still met, I'd say."
        ),
    )
    with pytest.raises(ModelUnavailableError):
        assess("SCN-01", "NCT07349537", ECOG_CRITERION, "P2", model)


def test_an_unsupported_proposition_is_resolved_without_a_model_call() -> None:
    criterion = criterion_of("NCT07349537", "NCT07349537:INC-5")
    model = replay()
    assessment = assess_proposition(
        criterion.propositions[0],
        criterion=criterion,
        timeline=timeline_of("SCN-01"),
        trial=TRIALS["NCT07349537"],
        model=model,
    )
    assert isinstance(assessment, UnknownAssessment)
    assert assessment.reason is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE
    assert model.requests == []


def test_an_age_criterion_is_answered_from_the_birth_date_by_code() -> None:
    """No tool reaches the `Patient` resource, and no model does the arithmetic."""
    model = replay(
        call(ModelPurpose.ASSESSMENT, AGE_CRITERION, "P1", answer("met", "Patient/patient-1"))
    )
    assessment = assess("SCN-01", "NCT07349537", AGE_CRITERION, "P1", model)

    assert isinstance(assessment, MetAssessment)
    fact = assessment.patient_evidence[0].facts[0]
    assert (fact.resource_type, fact.value) == ("Patient", "64")
    assert "age at 2026-08-04 is 64 years" in model.requests[0].prompt


def test_a_criterion_is_aggregated_from_its_propositions_and_never_asserted() -> None:
    """SCN-01's ECOG is 1: P1 is not_met, P2 is met, and `any_of` decides."""
    model = replay(
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P1",
            selection("get_latest_observation", operator="==", threshold=0, unit=None),
        ),
        call(
            ModelPurpose.ASSESSMENT,
            ECOG_CRITERION,
            "P1",
            answer("not_met", "Observation/obs-ecog", relation="contradicts"),
        ),
        call(
            ModelPurpose.TOOL_SELECTION,
            ECOG_CRITERION,
            "P2",
            selection("get_latest_observation", operator="==", threshold=1, unit=None),
        ),
        call(ModelPurpose.ASSESSMENT, ECOG_CRITERION, "P2", answer("met", "Observation/obs-ecog")),
    )
    criterion = criterion_of("NCT07349537", ECOG_CRITERION)
    assessed = assess_criterion(
        criterion,
        timeline=timeline_of("SCN-01"),
        trial=TRIALS["NCT07349537"],
        model=model,
    )
    assert assessed.state is CriterionState.MET
    assert isinstance(assessed.propositions[0], NotMetAssessment)
    assert isinstance(assessed.propositions[1], MetAssessment)
    assert assessed.aggregation.trace[-1].node == "any_of"
