"""Evidence-packet construction: what the model is allowed to see.

Module-private by specification section 12, and tested through the loop rather
than directly — the assertion that matters is about what the model received, and
`FrozenReplayModel` records every prompt for exactly that.

Section 10 fixes the contents: the exact criterion text, the frozen expression,
polarity and provenance, and tool results. Never the full Bundle, never the full
trial record, never a Scenario Manifest. The packet is therefore built from one
`EligibilityCriterion` and the facts the tools returned, and there is nothing
else in scope here to leak.

Facts are listed with an id the model answers with. It cites *which* fact, and
the loop writes down what the fact says, from the timeline. That removes the
whole class of transcription errors — a citation whose value drifted from the
record cannot be produced by an agent that never types the value — and it is
also why the agent's citation validity is a structural property rather than a
measurement of the model, which section 20 says out loud.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from ctma.domain.expression import AtomicProposition, EligibilityCriterion
from ctma.domain.timeline import MedicationExposure, TimelineFact

CitableFact = TimelineFact | MedicationExposure

TOOL_SELECTION_SCHEMA = """{
  "lookup": "<one of the lookup tools listed above>",
  "comparison": null | {"operator": "<|<=|>|>=|==", "threshold": <number>, "unit": <string|null>}
}"""

COMPUTED_SCHEMA = """{
  "state": "met" | "not_met" | "not_applicable",
  "rationale": "<one sentence, explanatory only>"
}"""

ASSESSMENT_SCHEMA = """{
  "state": "met" | "not_met" | "not_applicable",
  "citations": [{"fact_ids": ["<id from the facts above>"], "relation": "supports"|"contradicts"}],
  "rationale": "<one sentence, explanatory only>"
}"""


def tool_selection_prompt(
    proposition: AtomicProposition,
    criterion: EligibilityCriterion,
    lookups: Sequence[str],
) -> str:
    """Ask which lookup answers this proposition, and whether to compare."""
    return "\n".join(
        (
            "You are assessing one atomic proposition of one clinical trial "
            "eligibility criterion, for research coordinator review.",
            "",
            _criterion_block(criterion),
            _proposition_block(proposition),
            "",
            "Available lookup tools:",
            *(f"- {name}" for name in lookups),
            "",
            "The concept is fixed by the authored expression and you do not choose it. "
            "Choose the lookup that answers this proposition. If deciding it needs a "
            "numeric comparison, state the operator and threshold the criterion text "
            "gives; the comparison itself is performed by code.",
            "",
            "Reply with JSON only:",
            TOOL_SELECTION_SCHEMA,
        )
    )


def assessment_prompt(
    proposition: AtomicProposition,
    criterion: EligibilityCriterion,
    facts: Sequence[CitableFact],
    computations: Sequence[str],
) -> str:
    """Ask what the facts establish, and which of them to cite."""
    return "\n".join(
        (
            "You are assessing one atomic proposition of one clinical trial "
            "eligibility criterion, for research coordinator review.",
            "",
            _criterion_block(criterion),
            _proposition_block(proposition),
            "",
            "Facts the tools returned:",
            *(f"- {_fact_line(fact)}" for fact in facts),
            *_computation_block(computations),
            "",
            'Cite by fact id, copied exactly as it appears after "fact id" — '
            "including the resource type before the slash. An id that is not in "
            "the list above cites nothing. Do not restate a value, a date, or a "
            "status: the citation is filled in from the record. Answer only "
            "about this proposition, and only from the facts above.",
            "",
            "Reply with JSON only:",
            ASSESSMENT_SCHEMA,
        )
    )


def computed_prompt(
    proposition: AtomicProposition,
    criterion: EligibilityCriterion,
    computations: Sequence[str],
) -> str:
    """Ask only what the comparison means, when code already did the comparison.

    No citations are requested, because there are none to request: the operand
    is a computed value and the reference to the record it came from is built
    here. Asking anyway offered a list of facts that was always empty and then
    discarded whatever came back — so the model either invented an id or, told
    honestly that computations are not citable, returned none and failed the
    schema. Both are the same bug, which is asking for something unusable.
    """
    return "\n".join(
        (
            "You are assessing one atomic proposition of one clinical trial "
            "eligibility criterion, for research coordinator review.",
            "",
            _criterion_block(criterion),
            _proposition_block(proposition),
            *_computation_block(computations),
            "",
            "The comparison has already been made. Say what it means for this "
            "proposition and nothing else. The citation to the patient record is "
            "filled in here and is not yours to supply.",
            "",
            "Reply with JSON only:",
            COMPUTED_SCHEMA,
        )
    )


def correction_prompt(
    proposition: AtomicProposition,
    criterion: EligibilityCriterion,
    facts: Sequence[CitableFact],
    computations: Sequence[str],
    previous_answer: str,
    rejection_detail: str,
) -> str:
    """One targeted retry, naming what the verifier rejected and why.

    Targeted rather than "try again": the verifier already knows which check
    failed, and a correction that does not say which one is a second guess at
    the same question.
    """
    return "\n".join(
        (
            assessment_prompt(proposition, criterion, facts, computations),
            "",
            "Your previous answer was rejected by a deterministic verifier.",
            f"Previous answer: {previous_answer}",
            f"Rejected because: {rejection_detail}",
            "Correct exactly what was rejected. If the facts above cannot "
            "establish the proposition, do not assert one.",
        )
    )


def _criterion_block(criterion: EligibilityCriterion) -> str:
    provenance = criterion.provenance
    return "\n".join(
        (
            f"Criterion ({criterion.polarity.value}, {criterion.source_section}, "
            f"ordinal {criterion.ordinal}):",
            f'  "{criterion.source_text}"',
            f"Authored expression ({criterion.expression_version}, drafted by "
            f"{provenance.drafted_by}, review status {provenance.review_status.value}):",
            f"  {json.dumps(criterion.expression.model_dump(mode='json'), sort_keys=True)}",
        )
    )


def _proposition_block(proposition: AtomicProposition) -> str:
    lines = [
        f"Proposition {proposition.proposition_id} ({proposition.category.value}):",
        f"  {proposition.statement}",
    ]
    if proposition.concept is not None:
        lines.append(f"  concept: {proposition.concept}")
    window = proposition.window
    if window is not None:
        lines.append(f"  window: {window.duration.days} days, endpoints inclusive")
        if window.anchor_substitution is not None:
            lines.append(
                f"  anchor: {window.source_anchor_text!r}, substituted at authoring time "
                f"with the Assessment Time"
            )
    return "\n".join(lines)


def _fact_line(fact: CitableFact) -> str:
    """One fact, with everything a reader needs and nothing to retype."""
    coding = fact.code if isinstance(fact, TimelineFact) else fact.medication
    parts = [f"fact id {fact.fact_id} — {fact.display} [{coding.code}]", f"status {fact.status}"]
    if isinstance(fact, TimelineFact) and fact.value is not None:
        parts.append(f"value {_value(fact)}")
    if fact.time is not None:
        parts.append(f"recorded {fact.time.start} ({fact.time.start_precision.value} precision)")
        if fact.time.end is not None:
            parts.append(f"through {fact.time.end}")
    return ", ".join(parts)


def _value(fact: TimelineFact) -> str:
    value = fact.value
    if value is None:
        return ""
    if value.kind == "coded":
        return value.text
    return f"{value.comparator or ''}{value.value}{f' {value.unit}' if value.unit else ''}"


def _computation_block(computations: Sequence[str]) -> tuple[str, ...]:
    if not computations:
        return ()
    return (
        "",
        "Deterministic computations already performed. These are results, not "
        "facts: they have no fact id and cannot be cited.",
        *(f"- {c}" for c in computations),
    )
