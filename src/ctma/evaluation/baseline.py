"""The one-shot baseline: the whole timeline, one prompt, no tools.

Specification section 20 and the measurement plan. This is the control the
architecture is worth something against, and it is deliberately generous: it
receives the criterion, the authored expression, and *every* fact in the
patient record, while the agent sees only what its tool calls returned.

So the baseline is the information-advantaged arm. Any advantage the agent
shows comes from grounding discipline rather than from access, and that
sentence is published wherever the comparison is.

It gets no tools and no verifier feedback. Its output is graded by the same
verifier, at the offline call site, with the same configuration — the standard
it was never allowed to consult. That asymmetry is the measured architectural
difference, not a confound.

The prompt template lives here as a version rather than at the call site, and
the version is recorded in the run configuration. A prompt decided per call is
a prompt nobody can reproduce.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, cast

from pydantic import Field, ValidationError

from ctma.adapters.model import ModelClient, ModelPurpose, ModelRequest, ModelUnavailableError
from ctma.domain.base import Frozen
from ctma.domain.evidence import TrialEvidence
from ctma.domain.expression import EligibilityCriterion
from ctma.domain.proposal import ProposedAssessment
from ctma.domain.timeline import MedicationExposure, PatientTimeline, TimelineFact
from ctma.domain.trace import FailureKind, InfrastructureFailure, Measurements
from ctma.domain.trial import TrialRecord

BASELINE_PROMPT_VERSION = "baseline-one-shot-v1"

RESPONSE_SCHEMA = """{
  "assessments": [
    {
      "proposition_id": "<id>",
      "state": "met" | "not_met" | "unknown" | "not_applicable",
      "reason": null | "missing_evidence" | "unusable_status" | "insufficient_precision" |
                "conflicting_evidence" | "stale_evidence" | "ambiguous_criterion" |
                "unsupported_evidence_type",
      "citations": [
        {
          "relation": "supports" | "contradicts",
          "facts": [
            {"resource_type": "...", "resource_id": "...", "json_path": "...",
             "status": "...", "code": "...", "value": "...", "display": "...",
             "clinical_time": "YYYY-MM-DD", "precision": "day"}
          ]
        }
      ],
      "rationale": "<one sentence>"
    }
  ]
}

Three rules the reply is checked against:
- "reason" is set when and only when "state" is "unknown". Every other state
  carries a null reason.
- "clinical_time" is a date copied from the record above, in YYYY-MM-DD form.
  There is no "unknown" date: if you cannot point at a dated fact, the state is
  "unknown" with a reason and no citations.
- "code" and "resource_id" are copied from the record above. The code is the
  value in square brackets after the display name."""


class BaselineAnswers(Frozen):
    """What the baseline returned for one criterion, before anything is checked."""

    criterion_id: str = Field(min_length=1)
    assessments: tuple[ProposedAssessment, ...] = ()
    measurements: Measurements = Measurements()
    failures: tuple[InfrastructureFailure, ...] = ()
    """A reply that will not parse is recorded here rather than retried
    silently. Section 16 allows recorded retries and forbids hidden ones, and a
    baseline given quiet second chances is not the control it claims to be."""


def one_shot(
    criterion: EligibilityCriterion,
    *,
    timeline: PatientTimeline,
    trial: TrialRecord,
    model: ModelClient,
) -> BaselineAnswers:
    """Ask once, for every proposition of one criterion, over the whole record."""
    prompt = baseline_prompt(criterion, timeline)
    request = ModelRequest(
        purpose=ModelPurpose.ASSESSMENT,
        criterion_id=criterion.criterion_id,
        proposition_id="ALL",
        prompt=prompt,
    )
    try:
        response = model.complete(request)
    except ModelUnavailableError as error:
        return BaselineAnswers(criterion_id=criterion.criterion_id, failures=(error.failure,))

    evidence = TrialEvidence(
        snapshot_id=trial.snapshot_record_id,
        nct_id=trial.nct_id,
        source_section=criterion.source_section,
        criterion_ordinal=criterion.ordinal,
        span_start=criterion.span_start,
        span_end=criterion.span_end,
        source_text=criterion.source_text,
    )
    parsed, failures = _parse(response.json_text, criterion, evidence)
    return BaselineAnswers(
        criterion_id=criterion.criterion_id,
        assessments=parsed,
        measurements=response.measurements,
        failures=failures,
    )


def baseline_prompt(criterion: EligibilityCriterion, timeline: PatientTimeline) -> str:
    """The criterion, the authored expression, and the entire patient record."""
    propositions = "\n".join(
        f"- {proposition.proposition_id} ({proposition.category.value}): {proposition.statement}"
        for proposition in criterion.propositions
    )
    return "\n".join(
        (
            "You are assessing one clinical trial eligibility criterion against a "
            "patient record, for research coordinator review.",
            "",
            f"Criterion ({criterion.polarity.value}, ordinal {criterion.ordinal}):",
            f'  "{criterion.source_text}"',
            "",
            "Atomic propositions to assess, each on its own:",
            propositions,
            "",
            f"Patient record as of {timeline.assessment_as_of}:",
            *(f"- {_fact(fact)}" for fact in timeline.facts),
            *(
                f"- {_fact(exposure)} (medication administration)"
                for exposure in timeline.exposures
            ),
            *(
                f"- {content.resource_type}/{content.resource_id} at {content.json_path}, "
                f"not interpreted ({content.reason.value})"
                for content in timeline.unsupported_content
            ),
            "",
            "Cite the exact resource type, id, JSON path, status, code, value and date "
            "for every fact you rely on. Answer only from this record.",
            "",
            "Reply with JSON only:",
            RESPONSE_SCHEMA,
        )
    )


def _fact(item: TimelineFact | MedicationExposure) -> str:
    coding = item.code if isinstance(item, TimelineFact) else item.medication
    parts = [
        f"{item.resource_id} at {item.json_path}: {item.display} [{coding.code}]",
        f"status {item.status}",
    ]
    if isinstance(item, TimelineFact) and item.value is not None:
        value = item.value
        parts.append(
            f"value {value.text}"
            if value.kind == "coded"
            else f"value {value.comparator or ''}{value.value} {value.unit or ''}".strip()
        )
    if item.time is not None:
        parts.append(f"recorded {item.time.start} ({item.time.start_precision.value})")
    return ", ".join(parts)


def _parse(
    raw: str, criterion: EligibilityCriterion, evidence: TrialEvidence
) -> tuple[tuple[ProposedAssessment, ...], tuple[InfrastructureFailure, ...]]:
    """Read the reply, recording what will not parse rather than retrying it."""
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return (), (
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail=f"the baseline reply held no JSON object: {raw[:120]!r}",
                where=criterion.criterion_id,
            ),
        )

    assessments: list[ProposedAssessment] = []
    failures: list[InfrastructureFailure] = []
    try:
        payload: object = json.loads(text[start : end + 1])
    except json.JSONDecodeError as error:
        return (), (
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail=f"the baseline reply is not JSON: {error}",
                where=criterion.criterion_id,
            ),
        )

    for entry in _entries(payload):
        try:
            assessments.append(
                ProposedAssessment.model_validate(
                    {
                        "proposition_id": entry.get("proposition_id", ""),
                        "state": entry.get("state"),
                        "reason": entry.get("reason"),
                        "trial_evidence": evidence.model_dump(mode="json"),
                        "patient_evidence": entry.get("citations", []),
                        "rationale": entry.get("rationale"),
                    }
                )
            )
        except ValidationError as error:
            failures.append(
                InfrastructureFailure(
                    kind=FailureKind.MODEL_UNAVAILABLE,
                    detail=f"a baseline assessment did not match the schema: {error}",
                    where=criterion.criterion_id,
                )
            )
    return tuple(assessments), tuple(failures)


def _entries(payload: object) -> Sequence[Mapping[str, Any]]:
    if not isinstance(payload, dict):
        return ()
    listed = cast(Mapping[str, Any], payload).get("assessments")
    if not isinstance(listed, list):
        return ()
    return [
        cast(Mapping[str, Any], entry)
        for entry in cast(list[Any], listed)
        if isinstance(entry, dict)
    ]
