"""Deterministic aggregation of Proposition Assessments through an expression.

Specification section 7.1. The model assesses one Atomic Proposition at a time
and never chooses the aggregate state. This module is the only thing that does,
which is what makes "models never perform Boolean aggregation" a property of
the code rather than a promise about prompting.

Two decisions this module makes that section 7.1 leaves open:

A conditional whose antecedent is itself `not_applicable` resolves to
`not_applicable`. Section 7.1 names `met`, `not_met`, and `unknown` antecedents
only. An antecedent that does not apply cannot establish that the consequent
should be read, and reporting `unknown` instead would claim the evidence was
inadequate when the expression simply did not reach that branch.

A referenced proposition with no state raises rather than defaulting to
`unknown`. Defaulting would satisfy every truth table below while hiding a
dropped assessment, and "no criterion is silently dropped from output" is an
invariant, not a preference.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Literal

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState
from ctma.domain.expression import AllOf, AnyOf, Conditional, ExpressionNode, PropositionRef

NodeKind = Literal["proposition", "all_of", "any_of", "conditional"]

_Outcome = tuple[CriterionState, tuple[str, ...]]
"""A node's state, and the propositions that decided it."""


class UnassessedPropositionError(LookupError):
    """The expression references a proposition that carries no state."""


class AggregationStep(Frozen):
    """One node's outcome on the way to the root."""

    node: NodeKind
    state: CriterionState
    decided_by: tuple[str, ...] = Field(min_length=1)


class Aggregation(Frozen):
    """The aggregate Criterion State, and how the expression reached it.

    The trace is in post-order, so children precede their parent and the root
    is last. It exists because the Evidence Verifier rejects incorrect
    expression aggregation (specification section 8.1), and a verifier handed
    only a final state has to re-derive the whole tree to disagree with it.
    """

    state: CriterionState
    trace: tuple[AggregationStep, ...] = Field(min_length=1)

    @property
    def decided_by(self) -> tuple[str, ...]:
        """The propositions that decided the root."""
        return self.trace[-1].decided_by


def aggregate(expression: ExpressionNode, states: Mapping[str, CriterionState]) -> Aggregation:
    """Reduce proposition states to one Criterion State through the expression.

    Raises `UnassessedPropositionError` if the expression references a
    proposition `states` does not carry.
    """
    steps: list[AggregationStep] = []
    state, _ = _evaluate(expression, states, steps)
    return Aggregation(state=state, trace=tuple(steps))


def _evaluate(
    node: ExpressionNode,
    states: Mapping[str, CriterionState],
    steps: list[AggregationStep],
) -> _Outcome:
    kind: NodeKind
    match node:
        case PropositionRef():
            kind = "proposition"
            if node.proposition_id not in states:
                msg = f"no state for proposition {node.proposition_id!r}"
                raise UnassessedPropositionError(msg)
            outcome = (states[node.proposition_id], (node.proposition_id,))
        case AllOf():
            kind = "all_of"
            outcome = _all_of([_evaluate(child, states, steps) for child in node.children])
        case AnyOf():
            kind = "any_of"
            outcome = _any_of([_evaluate(child, states, steps) for child in node.children])
        case Conditional():
            kind = "conditional"
            outcome = _conditional(node, states, steps)

    state, decided_by = outcome
    steps.append(AggregationStep(node=kind, state=state, decided_by=decided_by))
    return outcome


def _all_of(children: Sequence[_Outcome]) -> _Outcome:
    """Any `not_met` decides; else any `unknown`; else the applicable children."""
    if contradicted := _with(children, CriterionState.NOT_MET):
        return CriterionState.NOT_MET, _ids(contradicted)
    if uncertain := _with(children, CriterionState.UNKNOWN):
        return CriterionState.UNKNOWN, _ids(uncertain)
    applicable = _applicable(children)
    if not applicable:
        return CriterionState.NOT_APPLICABLE, _ids(children)
    return CriterionState.MET, _ids(applicable)


def _any_of(children: Sequence[_Outcome]) -> _Outcome:
    """Any `met` decides; else any `unknown`; else the applicable children."""
    if supported := _with(children, CriterionState.MET):
        return CriterionState.MET, _ids(supported)
    if uncertain := _with(children, CriterionState.UNKNOWN):
        return CriterionState.UNKNOWN, _ids(uncertain)
    applicable = _applicable(children)
    if not applicable:
        return CriterionState.NOT_APPLICABLE, _ids(children)
    return CriterionState.NOT_MET, _ids(applicable)


def _conditional(
    node: Conditional,
    states: Mapping[str, CriterionState],
    steps: list[AggregationStep],
) -> _Outcome:
    """The antecedent decides whether the consequent is read at all.

    The consequent is evaluated only when the antecedent is `met`, so the trace
    shows the branch that decided the outcome rather than every branch that
    exists.
    """
    antecedent_state, antecedent_ids = _evaluate(node.antecedent, states, steps)
    if antecedent_state is CriterionState.MET:
        return _evaluate(node.consequent, states, steps)
    if antecedent_state is CriterionState.UNKNOWN:
        return CriterionState.UNKNOWN, antecedent_ids
    return CriterionState.NOT_APPLICABLE, antecedent_ids


def _with(children: Iterable[_Outcome], state: CriterionState) -> list[_Outcome]:
    return [child for child in children if child[0] is state]


def _applicable(children: Iterable[_Outcome]) -> list[_Outcome]:
    """`not_applicable` children are ignored unless every child is one."""
    return [child for child in children if child[0] is not CriterionState.NOT_APPLICABLE]


def _ids(children: Iterable[_Outcome]) -> tuple[str, ...]:
    """The deciding propositions, in expression order and without repeats.

    A proposition may be referenced from two branches, so the same id can
    arrive twice; the trace names each deciding proposition once.
    """
    seen: dict[str, None] = {}
    for _, ids in children:
        for proposition_id in ids:
            seen[proposition_id] = None
    return tuple(seen)
