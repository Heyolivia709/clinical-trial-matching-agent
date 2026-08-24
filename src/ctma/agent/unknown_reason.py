"""Unknown Reason assignment.

Specification section 8.0. Every `unknown` carries a structured reason, the
reason is chosen by deterministic code from the timeline and the criterion, and
the choice is reproducible. The model never picks it.

This lives in `agent` rather than `domain` because specification section 12
puts it there: it is part of the Criterion Agent's work, just not part of the
model's. It is nonetheless pure, so it can be settled in Gate 1 and tested
without a timeline, a snapshot, or a model.

Why the taxonomy is this fine-grained: section 8.3 plants a `preliminary`
result and a year-only date as separate hazards. If both surfaced as "evidence
is missing", the failure taxonomy could not tell either apart from a concept
the agent simply never looked for, and the reason would stop being diagnostic.
A disqualified fact, an imprecise date, and no fact at all are three different
diagnoses.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import NamedTuple, Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionCategory, UnknownReason


class ExpressionStatus(StrEnum):
    """Stage 1: whether the trial has an authored Criterion Expression at all."""

    AUTHORED = "authored"
    UNAVAILABLE = "unavailable"


class AgentOutcome(StrEnum):
    """Stage 3: what the agent loop concluded, where it overrides the evidence.

    `ASSESSED` means the loop finished without either override, so stage 2
    stands. The other two are not evidence diagnoses at all, which is why they
    replace whatever the evidence looked like.
    """

    ASSESSED = "assessed"
    VERIFICATION_FAILED_TWICE = "verification_failed_twice"
    DETERMINISTIC_DISAGREEMENT = "deterministic_disagreement"


class UnassignableReasonError(ValueError):
    """No row matches, so the situation does not explain an `unknown`.

    Reached only when a caller reports `unknown` for evidence that should have
    produced a state. Guessing a reason here would put a fabricated diagnosis
    into the benchmark's failure taxonomy.
    """


class EvidenceSituation(Frozen):
    """What the timeline held for one Atomic Proposition, at `assessment_as_of`.

    This is deliberately a summary rather than the facts themselves. The seven
    rows of section 8.0 turn on counts and classifications, not on values, so
    the table can be settled and tested before a Patient Timeline exists. The
    Timeline Tools build this in Gate 2.

    Facts dated after `assessment_as_of` are not represented, because section
    5.1 excludes them: the only occurrence being in the future leaves no fact,
    which is why planted distractor 3 resolves to `missing_evidence`. A fact for
    a semantically near but distinct concept is likewise absent, for the same
    reason and to the same effect.
    """

    category: CriterionCategory
    """The authored category. `unsupported` decides the first row on its own."""

    only_candidate_facts_are_outside_the_boundary: bool = False
    """Every candidate sits in a resource type section 5 does not treat as
    evidence-bearing — a `MedicationRequest` cited as exposure, say."""

    anchor_was_not_operationalized: bool = False
    """The criterion names an anchor, threshold, or concept the expression could
    not operationalize, and declares no substitution."""

    qualifying_facts: int = Field(default=0, ge=0)
    """Facts for the concept with a usable status, at or before the assessment
    time."""

    facts_with_disqualifying_status: int = Field(default=0, ge=0)
    """Facts for the concept that section 5.2 disqualifies: `preliminary`,
    `entered-in-error`."""

    qualifying_facts_conflict: bool = False
    """Two or more qualifying facts disagree and deterministic precedence cannot
    resolve them."""

    precision_is_coarser_than_required: bool = False
    """A qualifying fact's temporal precision is coarser than the comparison
    requires."""

    qualifying_facts_are_all_out_of_window: bool = False
    """Qualifying facts exist but all fall outside the window the criterion
    requires."""

    @property
    def facts_for_the_concept(self) -> int:
        """A disqualified fact is still a fact for the concept."""
        return self.qualifying_facts + self.facts_with_disqualifying_status

    @model_validator(mode="after")
    def _unsupported_propositions_have_nothing_looked_up(self) -> Self:
        """An `unsupported` proposition resolves without being assessed.

        Reporting facts for it would imply a lookup that never ran, and would
        make the first row of the table look like a coincidence.
        """
        if self.category is CriterionCategory.UNSUPPORTED and self.facts_for_the_concept:
            msg = "an 'unsupported' proposition is not assessed, so it has no facts"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _a_conflict_needs_two_facts_to_disagree(self) -> Self:
        if self.qualifying_facts_conflict and self.qualifying_facts < 2:
            msg = "a conflict requires at least two qualifying facts"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _precision_and_window_findings_need_a_qualifying_fact(self) -> Self:
        """Both rows read "a qualifying fact exists but..." — so one must."""
        for finding, field in (
            (self.precision_is_coarser_than_required, "precision_is_coarser_than_required"),
            (self.qualifying_facts_are_all_out_of_window, "qualifying_facts_are_all_out_of_window"),
        ):
            if finding and not self.qualifying_facts:
                msg = f"{field} requires at least one qualifying fact"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _facts_outside_the_boundary_are_the_only_candidates(self) -> Self:
        if self.only_candidate_facts_are_outside_the_boundary and self.facts_for_the_concept:
            msg = "'only' candidates outside the boundary means no fact inside it"
            raise ValueError(msg)
        return self


class Row(NamedTuple):
    """One row of the section 8.0 stage 2 table."""

    reason: UnknownReason
    applies: Callable[[EvidenceSituation], bool]


def _nothing_here_can_be_evidence(situation: EvidenceSituation) -> bool:
    return (
        situation.category is CriterionCategory.UNSUPPORTED
        or situation.only_candidate_facts_are_outside_the_boundary
    )


def _the_criterion_could_not_be_operationalized(situation: EvidenceSituation) -> bool:
    return situation.anchor_was_not_operationalized


def _no_fact_exists_for_the_concept(situation: EvidenceSituation) -> bool:
    return situation.facts_for_the_concept == 0


def _every_fact_for_the_concept_is_disqualified(situation: EvidenceSituation) -> bool:
    """Section 5.2 phrases this as a disqualified result being the *only* fact.

    With a usable fact alongside it, the disqualified one explains nothing, and
    whatever kept the proposition from resolving is described by a later row.
    """
    return situation.facts_with_disqualifying_status > 0 and situation.qualifying_facts == 0


def _qualifying_facts_disagree(situation: EvidenceSituation) -> bool:
    return situation.qualifying_facts_conflict


def _the_date_is_coarser_than_the_comparison(situation: EvidenceSituation) -> bool:
    return situation.precision_is_coarser_than_required


def _every_qualifying_fact_is_out_of_window(situation: EvidenceSituation) -> bool:
    return situation.qualifying_facts_are_all_out_of_window


STAGE_2: tuple[Row, ...] = (
    Row(UnknownReason.UNSUPPORTED_EVIDENCE_TYPE, _nothing_here_can_be_evidence),
    Row(UnknownReason.AMBIGUOUS_CRITERION, _the_criterion_could_not_be_operationalized),
    Row(UnknownReason.MISSING_EVIDENCE, _no_fact_exists_for_the_concept),
    Row(UnknownReason.UNUSABLE_STATUS, _every_fact_for_the_concept_is_disqualified),
    Row(UnknownReason.CONFLICTING_EVIDENCE, _qualifying_facts_disagree),
    Row(UnknownReason.INSUFFICIENT_PRECISION, _the_date_is_coarser_than_the_comparison),
    Row(UnknownReason.STALE_EVIDENCE, _every_qualifying_fact_is_out_of_window),
)
"""The seven rows of specification section 8.0, in specification order.

Order is load-bearing: the first matching row wins, and rows do overlap. An
`unsupported` proposition also has no facts, so rows 1 and 3 both match and row
1 must decide. Reordering this tuple changes published failure taxonomies.
"""


def assign_unknown_reason(
    situation: EvidenceSituation | None = None,
    *,
    expression: ExpressionStatus = ExpressionStatus.AUTHORED,
    outcome: AgentOutcome = AgentOutcome.ASSESSED,
) -> UnknownReason:
    """The reason for one `unknown`, by the three stages of section 8.0.

    Stage 3 is checked first because it replaces whatever stage 2 assigned: a
    second verification failure is the reason regardless of what the evidence
    looked like. Stage 1 comes next, since a trial with no expression is never
    assessed and has no situation to describe.

    Raises `UnassignableReasonError` if stage 2 is reached and no row matches,
    or if it is reached with no situation to read.
    """
    if outcome is AgentOutcome.VERIFICATION_FAILED_TWICE:
        return UnknownReason.VERIFICATION_FAILED
    if outcome is AgentOutcome.DETERMINISTIC_DISAGREEMENT:
        return UnknownReason.REASONING_CONFLICT
    if expression is ExpressionStatus.UNAVAILABLE:
        return UnknownReason.EXPRESSION_UNAVAILABLE
    if situation is None:
        msg = "stage 2 needs an EvidenceSituation to read"
        raise UnassignableReasonError(msg)
    for row in STAGE_2:
        if row.applies(situation):
            return row.reason
    msg = f"no row of section 8.0 explains this situation: {situation!r}"
    raise UnassignableReasonError(msg)
