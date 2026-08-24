"""Tool calls, verifier outcomes, Infrastructure Failures, and cost.

The claim under test in the last group is a release gate: an Infrastructure
Failure is never scored as correct uncertainty. It is checked structurally
because that is where it is actually held — there is no field to put a state in.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.domain.assessment import (
    AssessedCriterion,
    MetAssessment,
    NotApplicableAssessment,
    NotMetAssessment,
    SkippedCriterion,
    TrialAssessment,
    UnexpressedCriterion,
    UnknownAssessment,
)
from ctma.domain.enums import CriterionState, ReportingStatus, UnknownReason
from ctma.domain.trace import (
    FailureKind,
    FilterDecision,
    InfrastructureFailure,
    Measurements,
    ReasoningTrace,
    SupervisorAction,
    SupervisorDecision,
    ToolCall,
    ToolFailed,
    ToolReturned,
    VerifierOutcome,
    VerifierRejection,
    VerifierVerdict,
)

STATE_TYPES = (CriterionState, ReportingStatus, UnknownReason)

ASSESSMENT_MODELS = (
    MetAssessment,
    NotMetAssessment,
    NotApplicableAssessment,
    UnknownAssessment,
    AssessedCriterion,
    UnexpressedCriterion,
    SkippedCriterion,
    TrialAssessment,
)


def a_tool_call() -> ToolCall:
    return ToolCall(
        tool="find_medication_exposure",
        arguments_json='{"concept": "EGFR_TKI", "time_window": "P14D"}',
        outcome=ToolReturned(result_json='{"facts": [{"resource_id": "medadmin-4"}]}'),
    )


def test_a_tool_call_round_trips_through_json_without_loss() -> None:
    original = a_tool_call()
    assert ToolCall.model_validate_json(original.model_dump_json()) == original


def test_a_failed_tool_call_round_trips_as_a_failure() -> None:
    original = ToolCall(
        tool="get_latest_observation",
        arguments_json='{"code": "LOINC:85337-4", "as_of": "2026-08-24"}',
        outcome=ToolFailed(
            failure=InfrastructureFailure(
                kind=FailureKind.TOOL_EXCEPTION,
                detail="KeyError: 'valueQuantity'",
                where="get_latest_observation",
            )
        ),
    )
    restored = ToolCall.model_validate_json(original.model_dump_json())
    assert restored == original
    assert isinstance(restored.outcome, ToolFailed)


def test_arguments_that_are_not_json_are_refused() -> None:
    """A trace is re-read offline, where malformed JSON is a lost run."""
    with pytest.raises(ValidationError, match="valid JSON"):
        ToolCall(
            tool="compare_numeric",
            arguments_json="value=22, operator=>=",
            outcome=ToolReturned(result_json="true"),
        )


def test_arguments_are_a_json_object_so_every_argument_has_a_name() -> None:
    with pytest.raises(ValidationError, match="JSON object"):
        ToolCall(
            tool="compare_numeric",
            arguments_json="[22, 1]",
            outcome=ToolReturned(result_json="true"),
        )


def test_a_rejection_names_the_check_that_failed() -> None:
    """The correction is targeted, so it has to know what to correct."""
    with pytest.raises(ValidationError, match="names at least one failed check"):
        VerifierOutcome(verdict=VerifierVerdict.REJECTED)


def test_an_acceptance_names_no_failed_check() -> None:
    with pytest.raises(ValidationError, match="names no failed checks"):
        VerifierOutcome(
            verdict=VerifierVerdict.ACCEPTED,
            rejections=(VerifierRejection.NONEXISTENT_REFERENCE,),
        )


def test_the_verifier_vocabulary_is_the_eight_checks_of_section_8_1() -> None:
    assert len(VerifierRejection) == 8


def test_measurements_sum_across_assessments() -> None:
    """Cost is published beside the value it purchased, so it has to add up."""
    total = Measurements.summed(
        (
            Measurements(latency_ms=100, model_calls=1, prompt_tokens=600, completion_tokens=90),
            Measurements(latency_ms=250, model_calls=2, prompt_tokens=800, completion_tokens=40),
        )
    )
    assert total.latency_ms == 350
    assert total.model_calls == 3
    assert total.tokens == 1530


def test_measurements_start_at_zero_rather_than_at_nothing() -> None:
    """An unmeasured run reports zero cost, not an absent one."""
    assert Measurements().tokens == 0
    assert Measurements().estimated_cost_usd == 0.0


def test_the_trace_holds_what_no_assessment_holds() -> None:
    trace = ReasoningTrace(
        filter_decisions=(
            FilterDecision(
                nct_id="NCT05222222",
                filter_name="age",
                removed=True,
                patient_value="61",
                trial_constraint="18-55",
            ),
        ),
        supervisor_decisions=(
            SupervisorDecision(
                nct_id="NCT05123456",
                action=SupervisorAction.EARLY_TERMINATION,
                detail="stopped after a confirmed blocker",
                criterion_id="NCT05123456:EXC-7",
            ),
        ),
    )
    assert ReasoningTrace.model_validate_json(trace.model_dump_json()) == trace


def test_an_empty_trace_is_a_valid_trace() -> None:
    """Flags default off, and no filter ran in a Gate 1 run."""
    assert ReasoningTrace() == ReasoningTrace(filter_decisions=(), supervisor_decisions=())


def test_a_tool_outcome_has_no_state_variant() -> None:
    """A tool exception is a fact about the system, not about the patient."""
    for outcome in (ToolReturned, ToolFailed):
        for field in outcome.model_fields.values():
            assert field.annotation not in STATE_TYPES


def test_an_infrastructure_failure_carries_no_state_and_no_reason() -> None:
    """Section 8.2, held by construction: there is nowhere to write one.

    Scoring a broken endpoint as correct uncertainty would pay the benchmark for
    its own outages, and it is a release gate that it cannot.
    """
    for field in InfrastructureFailure.model_fields.values():
        assert field.annotation not in STATE_TYPES


def test_no_assessment_record_admits_an_infrastructure_failure() -> None:
    """A failure is recorded on the run, and never in place of an answer."""
    for model in ASSESSMENT_MODELS:
        for name, field in model.model_fields.items():
            assert field.annotation is not InfrastructureFailure, f"{model.__name__}.{name}"
