"""Criterion Impact mapping and Match Conclusion derivation.

The impact table is transcribed from specification section 7.2 by hand. The
interesting half is exclusion polarity, where `met` is bad news.
"""

from __future__ import annotations

import pytest

from ctma.domain.aggregation import aggregate
from ctma.domain.enums import (
    CriterionImpact,
    CriterionPolarity,
    CriterionState,
    MatchConclusion,
)
from ctma.domain.impact import ImpactCounts, impact_of
from tests.builders import exc7

INCLUSION = CriterionPolarity.INCLUSION
EXCLUSION = CriterionPolarity.EXCLUSION

MET = CriterionState.MET
NOT_MET = CriterionState.NOT_MET
UNKNOWN = CriterionState.UNKNOWN
NOT_APPLICABLE = CriterionState.NOT_APPLICABLE

SATISFIED = CriterionImpact.SATISFIED
BLOCKING = CriterionImpact.BLOCKING
UNRESOLVED = CriterionImpact.UNRESOLVED
NEUTRAL = CriterionImpact.NEUTRAL

IMPACT: dict[tuple[CriterionPolarity, CriterionState], CriterionImpact] = {
    (INCLUSION, MET): SATISFIED,
    (INCLUSION, NOT_MET): BLOCKING,
    (INCLUSION, UNKNOWN): UNRESOLVED,
    (INCLUSION, NOT_APPLICABLE): NEUTRAL,
    (EXCLUSION, MET): BLOCKING,
    (EXCLUSION, NOT_MET): SATISFIED,
    (EXCLUSION, UNKNOWN): UNRESOLVED,
    (EXCLUSION, NOT_APPLICABLE): NEUTRAL,
}


def test_the_impact_table_covers_every_polarity_and_state() -> None:
    assert frozenset(IMPACT) == frozenset(
        (polarity, state) for polarity in CriterionPolarity for state in CriterionState
    )


@pytest.mark.parametrize(("polarity", "state", "expected"), [(*k, v) for k, v in IMPACT.items()])
def test_impact_mapping(
    polarity: CriterionPolarity, state: CriterionState, expected: CriterionImpact
) -> None:
    assert impact_of(state, polarity) is expected


def test_the_same_state_reads_differently_on_each_polarity() -> None:
    """The whole reason impact exists as a separate concept."""
    assert impact_of(MET, INCLUSION) is SATISFIED
    assert impact_of(MET, EXCLUSION) is BLOCKING


def test_a_tally_counts_every_impact() -> None:
    counts = ImpactCounts.tally([SATISFIED, SATISFIED, BLOCKING, UNRESOLVED, NEUTRAL])
    assert (counts.satisfied, counts.blocking, counts.unresolved, counts.neutral) == (2, 1, 1, 1)
    assert counts.not_assessed == 0
    assert counts.total == 5


def test_the_total_accounts_for_skipped_criteria_too() -> None:
    """Criterion Coverage is checked against this, so a skip must still count."""
    counts = ImpactCounts.tally([SATISFIED, BLOCKING], not_assessed=3)
    assert counts.total == 5


def test_a_blocker_yields_unlikely_match() -> None:
    counts = ImpactCounts.tally([SATISFIED, BLOCKING, UNRESOLVED])
    assert counts.conclusion is MatchConclusion.UNLIKELY_MATCH


def test_an_unresolved_criterion_without_a_blocker_yields_insufficient_information() -> None:
    counts = ImpactCounts.tally([SATISFIED, UNRESOLVED, NEUTRAL])
    assert counts.conclusion is MatchConclusion.INSUFFICIENT_INFORMATION


def test_no_blocker_and_nothing_unresolved_yields_potential_match() -> None:
    counts = ImpactCounts.tally([SATISFIED, SATISFIED, NEUTRAL])
    assert counts.conclusion is MatchConclusion.POTENTIAL_MATCH


def test_a_neutral_criterion_does_not_hold_back_a_potential_match() -> None:
    """`not_applicable` means the criterion does not apply, not that it is open."""
    assert ImpactCounts.tally([NEUTRAL]).conclusion is MatchConclusion.POTENTIAL_MATCH


def test_a_skipped_criterion_forces_at_least_insufficient_information() -> None:
    """Early termination: nobody looked, so a clean remainder is not reassurance."""
    counts = ImpactCounts.tally([SATISFIED, SATISFIED], not_assessed=1)
    assert counts.conclusion is MatchConclusion.INSUFFICIENT_INFORMATION


def test_a_confirmed_blocker_still_outranks_a_skipped_criterion() -> None:
    """Early termination stops *because* of the blocker; it is a finding, not a gap."""
    counts = ImpactCounts.tally([BLOCKING], not_assessed=4)
    assert counts.conclusion is MatchConclusion.UNLIKELY_MATCH


def test_a_skipped_criterion_is_never_counted_as_unresolved() -> None:
    """Merging them would report a budget decision as missing evidence."""
    counts = ImpactCounts.tally([SATISFIED], not_assessed=2)
    assert counts.unresolved == 0
    assert counts.not_assessed == 2


def test_counts_are_immutable() -> None:
    with pytest.raises(ValueError, match="frozen"):
        ImpactCounts().blocking = 1  # type: ignore[misc]


def test_an_authored_exclusion_criterion_the_patient_meets_blocks_the_trial() -> None:
    """The two halves meet: aggregation decides the state, polarity decides the news."""
    criterion = exc7()
    assert criterion.polarity is EXCLUSION
    state = aggregate(criterion.expression, {"P1": MET, "P2": MET}).state
    impact = impact_of(state, criterion.polarity)
    assert impact is BLOCKING
    assert ImpactCounts.tally([impact]).conclusion is MatchConclusion.UNLIKELY_MATCH
