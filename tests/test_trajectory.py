"""The Evidence Trajectory: what a coordinator reads instead of the trace.

Gate 3, specification section 14. The two guarantees worth testing are what it
carries and what it cannot carry.
"""

from __future__ import annotations

import json

from ctma.adapters.model import REPLAY_CONFIGURATION, FrozenReplayModel, ModelPurpose, RecordedCall
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.agent.loop import assess_criterion
from ctma.domain.assessment import TrialAssessment
from ctma.domain.enums import CriterionImpact, CriterionState, ReportingStatus
from ctma.domain.trajectory import evidence_trajectory
from ctma.evaluation.scenarios import load_scenario_manifest
from ctma.timeline.build import build

TRIALS = {trial.nct_id: trial for trial in load_trial_fixtures()}
CRITERION = "NCT07349537:INC-2"


def recorded(purpose: ModelPurpose, proposition_id: str, payload: object, attempt: int = 1):
    return RecordedCall(
        key=f"{purpose.value}|{CRITERION}|{proposition_id}|{attempt}",
        prompt="recorded",
        json_text=json.dumps(payload),
    )


def assessed_trial() -> TrialAssessment:
    """One criterion of one trial, assessed with a correction along the way."""
    scenario = load_scenario_input("SCN-01")
    timeline = build(
        scenario.bundle_json,
        scenario_id=scenario.scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )
    trial = TRIALS["NCT07349537"]
    criterion = next(item for item in trial.criteria if item.criterion_id == CRITERION)
    cite = {
        "state": "not_met",
        "citations": [{"fact_ids": ["Observation/obs-ecog"], "relation": "contradicts"}],
        "rationale": "The recorded ECOG score is 1, so it is not 0.",
    }
    met = {
        "state": "met",
        "citations": [{"fact_ids": ["Observation/obs-ecog"], "relation": "supports"}],
        "rationale": "The ECOG score recorded on 28 July is 1.",
    }
    invented = {
        "state": "met",
        "citations": [{"fact_ids": ["Observation/obs-invented"], "relation": "supports"}],
        "rationale": "A score of 1 is recorded.",
    }
    model = FrozenReplayModel.from_transcript(
        (
            recorded(ModelPurpose.TOOL_SELECTION, "P1", {"lookup": "get_latest_observation"}),
            recorded(ModelPurpose.ASSESSMENT, "P1", cite),
            recorded(ModelPurpose.TOOL_SELECTION, "P2", {"lookup": "get_latest_observation"}),
            recorded(ModelPurpose.ASSESSMENT, "P2", invented),
            recorded(ModelPurpose.CORRECTION, "P2", met, attempt=2),
        ),
        configuration=REPLAY_CONFIGURATION,
    )
    return TrialAssessment(
        nct_id=trial.nct_id,
        snapshot_record_id=trial.snapshot_record_id,
        retrieval_rank=1,
        criteria=(assess_criterion(criterion, timeline=timeline, trial=trial, model=model),),
    )


TRAJECTORY = evidence_trajectory(assessed_trial())


def test_a_step_names_the_criterion_the_state_and_what_it_rests_on() -> None:
    step = TRAJECTORY[0]
    assert step.criterion_id == CRITERION
    assert step.reporting_status is ReportingStatus.ASSESSED
    assert step.state is CriterionState.MET
    assert step.impact is CriterionImpact.SATISFIED
    assert step.tools_called == ("get_latest_observation", "get_latest_observation")
    assert step.citations == (
        "Observation/obs-ecog at entry[8].resource",
        "Observation/obs-ecog at entry[8].resource",
    )


def test_a_step_shows_the_rejection_and_the_correction_that_followed() -> None:
    """The catch is the thing a reader came for, so it is not summarised away.

    Both named checks belong here. The citation named an id no tool returned,
    which is why the state ended up with no evidence behind it — reporting only
    the second aims the correction at the wrong thing, and a real run spent five
    of six corrections that way.
    """
    assert TRAJECTORY[0].verification == (
        "verifier accepted the citation",
        "verifier rejected the citation: nonexistent_reference, state_without_patient_evidence",
        "verifier accepted the citation",
    )


def test_a_trajectory_carries_no_manifest_content() -> None:
    """Structural: it is derived from records that never held any.

    The check is written against the manifest's own words rather than against a
    field name, because the failure it guards against is a sentence leaking, not
    a schema growing a column.
    """
    manifest = load_scenario_manifest("SCN-01")
    rendered = json.dumps([step.model_dump(mode="json") for step in TRAJECTORY])
    assert manifest.design_intent[:40] not in rendered
    for fact in manifest.facts:
        assert fact.concept not in rendered or fact.concept == "ECOG_SCORE"


def test_a_trajectory_carries_the_answer_and_not_the_reasoning_behind_it() -> None:
    """One explanatory sentence per proposition, and no chain of thought."""
    for sentence in TRAJECTORY[0].rationale:
        assert len(sentence.split(".")) <= 3
    assert TRAJECTORY[0].rationale == (
        "The recorded ECOG score is 1, so it is not 0.",
        "The ECOG score recorded on 28 July is 1.",
    )
