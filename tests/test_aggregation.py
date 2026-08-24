"""Expression truth tables, exhaustively.

The tables below are transcribed from specification section 7.1 by hand rather
than generated from the implementation. A table derived from the code under
test only asserts that the code equals itself.
"""

from __future__ import annotations

import pytest

from ctma.domain.aggregation import UnassessedPropositionError, aggregate
from ctma.domain.enums import CriterionState
from ctma.domain.expression import AllOf, AnyOf, Conditional, ExpressionNode, PropositionRef
from tests.builders import exc7

MET = CriterionState.MET
NOT_MET = CriterionState.NOT_MET
UNKNOWN = CriterionState.UNKNOWN
NOT_APPLICABLE = CriterionState.NOT_APPLICABLE

EVERY_STATE = (MET, NOT_MET, UNKNOWN, NOT_APPLICABLE)
EVERY_PAIR = frozenset((first, second) for first in EVERY_STATE for second in EVERY_STATE)

P1 = PropositionRef(proposition_id="P1")
P2 = PropositionRef(proposition_id="P2")
P3 = PropositionRef(proposition_id="P3")

# Any `not_met` yields `not_met`; otherwise any `unknown` yields `unknown`;
# otherwise all applicable children `met` yields `met`. `not_applicable`
# children are ignored unless every child is `not_applicable`.
ALL_OF: dict[tuple[CriterionState, CriterionState], CriterionState] = {
    (MET, MET): MET,
    (MET, NOT_MET): NOT_MET,
    (MET, UNKNOWN): UNKNOWN,
    (MET, NOT_APPLICABLE): MET,
    (NOT_MET, MET): NOT_MET,
    (NOT_MET, NOT_MET): NOT_MET,
    (NOT_MET, UNKNOWN): NOT_MET,
    (NOT_MET, NOT_APPLICABLE): NOT_MET,
    (UNKNOWN, MET): UNKNOWN,
    (UNKNOWN, NOT_MET): NOT_MET,
    (UNKNOWN, UNKNOWN): UNKNOWN,
    (UNKNOWN, NOT_APPLICABLE): UNKNOWN,
    (NOT_APPLICABLE, MET): MET,
    (NOT_APPLICABLE, NOT_MET): NOT_MET,
    (NOT_APPLICABLE, UNKNOWN): UNKNOWN,
    (NOT_APPLICABLE, NOT_APPLICABLE): NOT_APPLICABLE,
}

# Any `met` yields `met`; otherwise any `unknown` yields `unknown`; otherwise
# all applicable children `not_met` yields `not_met`. Same `not_applicable` rule.
ANY_OF: dict[tuple[CriterionState, CriterionState], CriterionState] = {
    (MET, MET): MET,
    (MET, NOT_MET): MET,
    (MET, UNKNOWN): MET,
    (MET, NOT_APPLICABLE): MET,
    (NOT_MET, MET): MET,
    (NOT_MET, NOT_MET): NOT_MET,
    (NOT_MET, UNKNOWN): UNKNOWN,
    (NOT_MET, NOT_APPLICABLE): NOT_MET,
    (UNKNOWN, MET): MET,
    (UNKNOWN, NOT_MET): UNKNOWN,
    (UNKNOWN, UNKNOWN): UNKNOWN,
    (UNKNOWN, NOT_APPLICABLE): UNKNOWN,
    (NOT_APPLICABLE, MET): MET,
    (NOT_APPLICABLE, NOT_MET): NOT_MET,
    (NOT_APPLICABLE, UNKNOWN): UNKNOWN,
    (NOT_APPLICABLE, NOT_APPLICABLE): NOT_APPLICABLE,
}

# Antecedent `not_met` yields `not_applicable`, antecedent `met` yields the
# consequent state, antecedent `unknown` yields `unknown`. Section 7.1 does not
# name a `not_applicable` antecedent; this module resolves it to
# `not_applicable`, and the reasoning is in the aggregation module docstring.
CONDITIONAL: dict[tuple[CriterionState, CriterionState], CriterionState] = {
    (MET, MET): MET,
    (MET, NOT_MET): NOT_MET,
    (MET, UNKNOWN): UNKNOWN,
    (MET, NOT_APPLICABLE): NOT_APPLICABLE,
    (NOT_MET, MET): NOT_APPLICABLE,
    (NOT_MET, NOT_MET): NOT_APPLICABLE,
    (NOT_MET, UNKNOWN): NOT_APPLICABLE,
    (NOT_MET, NOT_APPLICABLE): NOT_APPLICABLE,
    (UNKNOWN, MET): UNKNOWN,
    (UNKNOWN, NOT_MET): UNKNOWN,
    (UNKNOWN, UNKNOWN): UNKNOWN,
    (UNKNOWN, NOT_APPLICABLE): UNKNOWN,
    (NOT_APPLICABLE, MET): NOT_APPLICABLE,
    (NOT_APPLICABLE, NOT_MET): NOT_APPLICABLE,
    (NOT_APPLICABLE, UNKNOWN): NOT_APPLICABLE,
    (NOT_APPLICABLE, NOT_APPLICABLE): NOT_APPLICABLE,
}


def pair(node: ExpressionNode, first: CriterionState, second: CriterionState) -> CriterionState:
    return aggregate(node, {"P1": first, "P2": second}).state


@pytest.mark.parametrize("table", [ALL_OF, ANY_OF, CONDITIONAL])
def test_each_table_covers_every_combination_of_states(
    table: dict[tuple[CriterionState, CriterionState], CriterionState],
) -> None:
    """A missing row would pass silently, so the tables are checked for holes."""
    assert frozenset(table) == EVERY_PAIR


@pytest.mark.parametrize(("first", "second", "expected"), [(*k, v) for k, v in ALL_OF.items()])
def test_all_of(first: CriterionState, second: CriterionState, expected: CriterionState) -> None:
    assert pair(AllOf(children=(P1, P2)), first, second) is expected


@pytest.mark.parametrize(("first", "second", "expected"), [(*k, v) for k, v in ANY_OF.items()])
def test_any_of(first: CriterionState, second: CriterionState, expected: CriterionState) -> None:
    assert pair(AnyOf(children=(P1, P2)), first, second) is expected


@pytest.mark.parametrize(("first", "second", "expected"), [(*k, v) for k, v in CONDITIONAL.items()])
def test_conditional(
    first: CriterionState, second: CriterionState, expected: CriterionState
) -> None:
    assert pair(Conditional(antecedent=P1, consequent=P2), first, second) is expected


@pytest.mark.parametrize("kind", [AllOf, AnyOf])
def test_all_children_not_applicable_yields_not_applicable_at_arity_three(
    kind: type[AllOf] | type[AnyOf],
) -> None:
    """The exception to ignoring `not_applicable` children is not arity-specific."""
    states: dict[str, CriterionState] = dict.fromkeys(("P1", "P2", "P3"), NOT_APPLICABLE)
    assert aggregate(kind(children=(P1, P2, P3)), states).state is NOT_APPLICABLE


@pytest.mark.parametrize("kind", [AllOf, AnyOf])
@pytest.mark.parametrize(("first", "second"), sorted(EVERY_PAIR))
def test_child_order_does_not_change_the_state(
    kind: type[AllOf] | type[AnyOf], first: CriterionState, second: CriterionState
) -> None:
    """`all_of` and `any_of` are commutative, so a reordered authoring is safe."""
    node = kind(children=(P1, P2))
    assert pair(node, first, second) is pair(node, second, first)


def test_a_not_applicable_subtree_is_ignored_by_its_parent() -> None:
    """A conditional that did not apply must not drag its whole criterion down."""
    node = AllOf(children=(AnyOf(children=(P1, P2)), P3))
    states = {"P1": NOT_APPLICABLE, "P2": NOT_APPLICABLE, "P3": MET}
    assert aggregate(node, states).state is MET


def test_a_nested_expression_aggregates_bottom_up() -> None:
    node = AllOf(children=(AnyOf(children=(P1, P2)), P3))
    states = {"P1": NOT_MET, "P2": MET, "P3": UNKNOWN}
    assert aggregate(node, states).state is UNKNOWN


def test_the_trace_is_post_order_with_the_root_last() -> None:
    node = AllOf(children=(AnyOf(children=(P1, P2)), P3))
    states = {"P1": NOT_MET, "P2": MET, "P3": MET}
    trace = aggregate(node, states).trace
    assert [step.node for step in trace] == [
        "proposition",
        "proposition",
        "any_of",
        "proposition",
        "all_of",
    ]
    assert trace[-1].state is MET


def test_the_trace_names_only_the_children_that_decided_the_outcome() -> None:
    aggregation = aggregate(AllOf(children=(P1, P2)), {"P1": MET, "P2": NOT_MET})
    assert aggregation.decided_by == ("P2",)


def test_a_not_applicable_child_does_not_decide_a_met_outcome() -> None:
    aggregation = aggregate(AllOf(children=(P1, P2)), {"P1": MET, "P2": NOT_APPLICABLE})
    assert aggregation.decided_by == ("P1",)


def test_every_child_decides_when_all_of_them_are_not_applicable() -> None:
    states = {"P1": NOT_APPLICABLE, "P2": NOT_APPLICABLE}
    aggregation = aggregate(AllOf(children=(P1, P2)), states)
    assert aggregation.decided_by == ("P1", "P2")


def test_not_met_outranks_unknown_in_the_trace_as_well_as_the_state() -> None:
    """Reporting both would suggest the `unknown` contributed to the outcome."""
    aggregation = aggregate(AllOf(children=(P1, P2)), {"P1": UNKNOWN, "P2": NOT_MET})
    assert aggregation.state is NOT_MET
    assert aggregation.decided_by == ("P2",)


def test_an_unmet_antecedent_leaves_the_consequent_out_of_the_trace() -> None:
    """The consequent was never read, so the trace must not imply it was."""
    node = Conditional(antecedent=P1, consequent=P2)
    aggregation = aggregate(node, {"P1": NOT_MET, "P2": MET})
    assert aggregation.state is NOT_APPLICABLE
    assert aggregation.decided_by == ("P1",)
    assert [step.node for step in aggregation.trace] == ["proposition", "conditional"]


def test_a_proposition_reached_from_two_branches_is_not_named_twice() -> None:
    """Both children decide here, and P1 decides through each of them."""
    node = AllOf(children=(P1, AnyOf(children=(P1, P2))))
    aggregation = aggregate(node, {"P1": NOT_MET, "P2": NOT_MET})
    assert aggregation.decided_by == ("P1", "P2")
    assert len(aggregation.decided_by) == len(set(aggregation.decided_by))


def test_a_proposition_with_no_state_is_refused_rather_than_assumed_unknown() -> None:
    """Defaulting would satisfy every table above while dropping an assessment."""
    with pytest.raises(UnassessedPropositionError, match="P2"):
        aggregate(AllOf(children=(P1, P2)), {"P1": MET})


def test_an_authored_criterion_aggregates() -> None:
    """The Gate 1 fixture, so the tables are exercised against real authoring."""
    criterion = exc7()
    aggregation = aggregate(criterion.expression, {"P1": MET, "P2": MET})
    assert aggregation.state is MET
    assert aggregation.decided_by == ("P1", "P2")
