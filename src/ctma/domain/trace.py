"""The diagnostic record: tool calls, verifier outcomes, failures, cost.

Specification sections 8.1, 8.2, 11 and 14. A Reasoning Trace is a read-only
account of how a run reached its answers. It is not execution state, not an
authorization log, and not a resumable checkpoint, which is why nothing here can
be written back into a run.

Two modelling decisions worth stating, because section 13 lists the pieces
separately and this module does not.

Tool calls and deterministic computations arrive as one record type. CONTEXT.md
defines a Timeline Tool as either a timeline query or a deterministic
comparison, so both are tool calls; a second record type describing the same
call would let two accounts of one event disagree, and the report would have to
pick one.

The trace does not copy the tool calls, verifier outcomes, or states of an
assessment. Those live on the assessment they explain, and this module keeps
only what belongs to no single assessment: filter decisions, supervisor
decisions, and the measurements. Duplicating them is how a trace comes to
contradict the answer it is supposed to explain.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ctma.domain.base import Frozen


class FailureKind(StrEnum):
    """The three Infrastructure Failures named in specification section 8.2."""

    MODEL_UNAVAILABLE = "model_unavailable"
    MALFORMED_SNAPSHOT = "malformed_snapshot"
    TOOL_EXCEPTION = "tool_exception"


class InfrastructureFailure(Frozen):
    """A dependency broke. This is not a Criterion State and cannot become one.

    Section 8.2 keeps the two apart because scoring a broken endpoint as correct
    uncertainty would pay the benchmark for its own outages: the more often the
    model was unreachable, the better its calibration would look. That is a
    release gate, so it is held by construction — this type carries no
    Criterion State and no Unknown Reason, and no function in `domain` maps one
    into the other.
    """

    kind: FailureKind
    detail: str = Field(min_length=1)
    where: str | None = None
    """The tool, criterion, or adapter that failed, when it is known."""


class ToolReturned(Frozen):
    """The tool ran and produced a result, recorded as the tool serialized it."""

    outcome: Literal["returned"] = "returned"
    result_json: str = Field(min_length=1)

    @field_validator("result_json")
    @classmethod
    def _result_is_json(cls, value: str) -> str:
        _require_json(value, field="result_json")
        return value


class ToolFailed(Frozen):
    """The tool raised. There is no result, and no state to read from one."""

    outcome: Literal["failed"] = "failed"
    failure: InfrastructureFailure


ToolOutcome = Annotated[ToolReturned | ToolFailed, Field(discriminator="outcome")]
"""A tool either returned or failed, and has no third outcome.

Deliberately no `unknown` variant. `unknown` is a statement about patient
evidence; a tool exception is a statement about the system, and a union with
both variants is all it takes for a caller to write the confusion section 8.2
forbids."""


class ToolCall(Frozen):
    """One Timeline Tool call, with the arguments as sent and what came back.

    Arguments and results are canonical JSON strings rather than parsed
    structures. The trace shows the call that happened, and re-rendering a
    parsed copy of it is how a trace drifts from the run it describes.
    """

    tool: str = Field(min_length=1)
    arguments_json: str = Field(min_length=1)
    outcome: ToolOutcome

    @field_validator("arguments_json")
    @classmethod
    def _arguments_are_a_json_object(cls, value: str) -> str:
        if type(_require_json(value, field="arguments_json")) is not dict:
            msg = "arguments_json must be a JSON object, so an argument has a name"
            raise ValueError(msg)
        return value


class VerifierVerdict(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class VerifierRejection(StrEnum):
    """The eight checks of specification section 8.1, as a closed vocabulary.

    Two of these are unrepresentable in this package's own assessment types: a
    `met` without patient evidence, and an incorrectly aggregated criterion,
    cannot be built here. They stay in the vocabulary because the verifier also
    grades the baselines, whose raw model output is under no such constraint,
    and grading them by a weaker standard would be the confound the comparison
    exists to avoid.
    """

    NONEXISTENT_REFERENCE = "nonexistent_reference"
    CITATION_DISAGREES_WITH_TIMELINE = "citation_disagrees_with_timeline"
    INVALID_TRIAL_SPAN = "invalid_trial_span"
    MISSING_EVIDENCE_RELATION = "missing_evidence_relation"
    STATE_WITHOUT_PATIENT_EVIDENCE = "state_without_patient_evidence"
    CITATION_CANNOT_ESTABLISH_STATE = "citation_cannot_establish_state"
    INCORRECT_AGGREGATION = "incorrect_aggregation"
    EVIDENCE_AFTER_ASSESSMENT_TIME = "evidence_after_assessment_time"


class VerifierOutcome(Frozen):
    """One verifier pass over one assessment.

    The outcomes recorded on an assessment are the feedback role only — the
    verdict that triggers the single correction inside the agent loop. Offline
    grading runs the same code at a different call site and its results never
    flow back into the system under test, so they never appear in a Matching
    Run. Conflating the two roles would make the grounding comparison
    meaningless (section 8.1).
    """

    verdict: VerifierVerdict
    rejections: tuple[VerifierRejection, ...] = ()
    detail: str | None = None

    @model_validator(mode="after")
    def _a_rejection_names_its_check(self) -> Self:
        """A verdict with no named check cannot be argued with, or fixed.

        The correction is targeted, so it needs to know what was wrong; and the
        failure taxonomy counts rejections by check.
        """
        rejected = self.verdict is VerifierVerdict.REJECTED
        if rejected and not self.rejections:
            msg = "a rejected assessment names at least one failed check"
            raise ValueError(msg)
        if not rejected and self.rejections:
            msg = "an accepted assessment names no failed checks"
            raise ValueError(msg)
        return self


class Measurements(Frozen):
    """What one assessment or one run cost.

    Cost is published beside the value it purchased, including when the ratio is
    unfavourable, so it is recorded at the same granularity as the value:
    per assessment, and summed for the run.
    """

    latency_ms: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @classmethod
    def summed(cls, parts: Iterable[Measurements]) -> Self:
        """The total across several measured units.

        Latency is summed rather than maxed: criteria within a trial may run
        concurrently, so this is spent time and not elapsed time, and the two
        are not the same claim. Wall-clock latency is measured at the run.
        """
        parts = tuple(parts)
        return cls(
            latency_ms=sum(part.latency_ms for part in parts),
            model_calls=sum(part.model_calls for part in parts),
            prompt_tokens=sum(part.prompt_tokens for part in parts),
            completion_tokens=sum(part.completion_tokens for part in parts),
            estimated_cost_usd=sum(part.estimated_cost_usd for part in parts),
        )


class FilterDecision(Frozen):
    """A Candidate Filter's verdict on one trial, and the two values behind it.

    Section 9 allows a filter to remove a trial only when both the patient value
    and the trial constraint are structured and known, so both are recorded.
    "Candidate filters cause zero loss of known relevant trials" is checked per
    scenario, and a decision that did not record what it compared cannot be
    audited when that check fails.
    """

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    filter_name: str = Field(min_length=1)
    removed: bool
    patient_value: str = Field(min_length=1)
    trial_constraint: str = Field(min_length=1)


class SupervisorAction(StrEnum):
    """The three flag-gated behaviours of specification section 11."""

    ORDER_CRITERIA = "order_criteria"
    EARLY_TERMINATION = "early_termination"
    EVIDENCE_REUSE = "evidence_reuse"


class SupervisorDecision(Frozen):
    """One trial-level strategy decision, with the criterion it acted on.

    `order_criteria` and `evidence_reuse` introduce order dependence, which
    section 11 requires to be measured rather than assumed away. Measuring it
    means the order the supervisor chose is recorded, not reconstructed.
    """

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    action: SupervisorAction
    detail: str = Field(min_length=1)
    criterion_id: str | None = None


class ReasoningTrace(Frozen):
    """The run-level diagnostic account, and only the parts nothing else holds.

    Filter and supervisor decisions belong to no single assessment, so they live
    here. Tool calls, verifier outcomes, and final states belong to the
    assessment they explain and stay there; see this module's docstring.
    """

    filter_decisions: tuple[FilterDecision, ...] = ()
    supervisor_decisions: tuple[SupervisorDecision, ...] = ()


def _require_json(value: str, *, field: str) -> object:
    """Reject a field that claims to be JSON and is not.

    A trace is re-read offline, long after the run that wrote it. Malformed JSON
    discovered then is a lost run; discovered here it is a bug in the caller.
    """
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        msg = f"{field} must be valid JSON: {error}"
        raise ValueError(msg) from error
