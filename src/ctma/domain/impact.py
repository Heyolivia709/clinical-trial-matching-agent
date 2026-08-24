"""Criterion Impact and Match Conclusion.

Specification section 7.2. Criterion State says whether the patient satisfies
the statement; Criterion Impact says what that means for this trial. Keeping
them apart is why an exclusion criterion the patient meets reads as `blocking`
rather than as a criterion that "failed", and why the same state can be good
news on one criterion and bad news on the next.

The conclusions here are screening workflow labels, not clinical eligibility
decisions.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Self

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionImpact, CriterionPolarity, CriterionState, MatchConclusion

_IMPACT: dict[tuple[CriterionPolarity, CriterionState], CriterionImpact] = {
    (CriterionPolarity.INCLUSION, CriterionState.MET): CriterionImpact.SATISFIED,
    (CriterionPolarity.INCLUSION, CriterionState.NOT_MET): CriterionImpact.BLOCKING,
    (CriterionPolarity.INCLUSION, CriterionState.UNKNOWN): CriterionImpact.UNRESOLVED,
    (CriterionPolarity.INCLUSION, CriterionState.NOT_APPLICABLE): CriterionImpact.NEUTRAL,
    (CriterionPolarity.EXCLUSION, CriterionState.MET): CriterionImpact.BLOCKING,
    (CriterionPolarity.EXCLUSION, CriterionState.NOT_MET): CriterionImpact.SATISFIED,
    (CriterionPolarity.EXCLUSION, CriterionState.UNKNOWN): CriterionImpact.UNRESOLVED,
    (CriterionPolarity.EXCLUSION, CriterionState.NOT_APPLICABLE): CriterionImpact.NEUTRAL,
}
"""Specification section 7.2 as data. Every polarity and state pair is present,
so there is no default branch to disagree with the table."""


def impact_of(state: CriterionState, polarity: CriterionPolarity) -> CriterionImpact:
    """What a Criterion State means for a trial, given the criterion's polarity."""
    return _IMPACT[(polarity, state)]


class ImpactCounts(Frozen):
    """The tally a Trial Assessment reports, and the conclusion it derives.

    `not_assessed` is counted here and is not an impact, because a criterion the
    supervisor skipped has no Criterion State to map. Merging it into
    `unresolved` would report a budget decision as missing evidence.
    """

    satisfied: int = Field(default=0, ge=0)
    blocking: int = Field(default=0, ge=0)
    unresolved: int = Field(default=0, ge=0)
    neutral: int = Field(default=0, ge=0)
    not_assessed: int = Field(default=0, ge=0)

    @classmethod
    def tally(cls, impacts: Iterable[CriterionImpact], not_assessed: int = 0) -> Self:
        counted = {impact: 0 for impact in CriterionImpact}
        for impact in impacts:
            counted[impact] += 1
        return cls(
            satisfied=counted[CriterionImpact.SATISFIED],
            blocking=counted[CriterionImpact.BLOCKING],
            unresolved=counted[CriterionImpact.UNRESOLVED],
            neutral=counted[CriterionImpact.NEUTRAL],
            not_assessed=not_assessed,
        )

    @property
    def total(self) -> int:
        """Every criterion accounted for, assessed or not.

        Criterion Coverage is checked against this: a trial whose total falls
        short of its authored criterion count has dropped one somewhere.
        """
        return self.satisfied + self.blocking + self.unresolved + self.neutral + self.not_assessed

    @property
    def conclusion(self) -> MatchConclusion:
        """Specification section 7.2, including the early-termination rule.

        A skipped criterion forces at least `insufficient_information`: nobody
        looked, so the absence of a blocker among the rest is not reassurance. A
        confirmed blocker still wins, because it is a finding and not a gap.
        """
        if self.blocking:
            return MatchConclusion.UNLIKELY_MATCH
        if self.unresolved or self.not_assessed:
            return MatchConclusion.INSUFFICIENT_INFORMATION
        return MatchConclusion.POTENTIAL_MATCH
