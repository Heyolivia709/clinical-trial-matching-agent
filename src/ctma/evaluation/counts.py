"""The reported numbers: counts over stated denominators, and nothing else.

Specification section 20 and the measurement plan. No confidence interval, no
hypothesis test, no effect size. At a few dozen graded propositions an interval
would be wider than any difference worth claiming, and computing one would dress
a demonstration up as a study. Every table carries the number of scenarios,
trials, and propositions behind it, so a reader can see the size without being
told it is large.

Three things are deliberately separate:

**State agreement is per state, never one aggregate.** An aggregate over four
states hides which state the system is bad at, and being wrong about `met` and
being wrong about `unknown` cost a coordinator different things.

**Unknown Reason agreement is its own number.** Getting `unknown` right for the
wrong reason is a different failure from getting the state wrong, and the whole
point of the taxonomy is that a coordinator acts differently on each.

**Cost sits beside the grounding number it purchased**, including when the ratio
is unfavourable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState, Partition
from ctma.domain.trace import Measurements, VerifierVerdict
from ctma.evaluation.grading import GradedProposition, Variant


class Count(Frozen):
    """A numerator, a denominator, and no estimate anywhere.

    The percentage is derived and rounded for display only. A count with a
    denominator of zero has no percentage, and says so rather than showing 0%,
    which reads as a result.
    """

    numerator: int = Field(ge=0)
    denominator: int = Field(ge=0)

    @property
    def percent(self) -> float | None:
        if self.denominator == 0:
            return None
        return round(100 * self.numerator / self.denominator, 1)

    def rendered(self) -> str:
        if self.denominator == 0:
            return "0 of 0"
        return f"{self.numerator} of {self.denominator} ({self.percent}%)"


class CostCounts(Frozen):
    """What one variant spent, and per what."""

    model_calls: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    criterion_assessments: int = Field(ge=0)

    @property
    def calls_per_criterion(self) -> float | None:
        if self.criterion_assessments == 0:
            return None
        return round(self.model_calls / self.criterion_assessments, 2)


class ReportedCounts(Frozen):
    """One variant's row, with the denominators it was computed over."""

    variant: Variant
    partition: Partition
    """Which half these came from. Development and held-out results are reported
    separately, so a row that did not say which it was could be read as the
    other one."""

    scenarios: int = Field(ge=0)
    trials: int = Field(ge=0)
    propositions: int = Field(ge=0)
    scorable_propositions: int = Field(ge=0)
    coverage_only_propositions: int = Field(ge=0)
    """Visible and excluded from accuracy counts, because no expected state
    follows from the authored artifacts."""

    reference_validity: Count
    unsupported_assessments: Count
    verification_induced_unknown: Count
    """Published beside post-correction validity, at equal prominence."""

    state_agreement: Mapping[CriterionState, Count]
    reason_agreement: Count
    """Over the propositions this variant actually looked up.

    A proposition it reports as `concept_not_in_mapping` is excluded, because
    grading a diagnosis against a record the system never consulted scores it
    for not having a mapping — and gold, correctly, knows nothing about what
    this system covers. They are counted on their own line instead of vanishing.
    """

    not_looked_up: Count
    """Expected-`unknown` propositions the variant declined to look up, because
    the reviewed mapping does not cover the concept."""

    cost: CostCounts

    def sample_sentence(self) -> str:
        """The sentence that goes under every table.

        The plan says the report states what the sample cannot support where the
        numbers appear, rather than leaving a reader to work it out.
        """
        return (
            f"{self.propositions} propositions across {self.scenarios} {self.partition.value} "
            f"scenarios and {self.trials} trials. Counts only: at this size no interval, "
            f"test, or effect size would mean anything."
        )


def report_counts(
    graded: Sequence[GradedProposition],
    *,
    variant: Variant,
    partition: Partition,
    scenarios: int,
    trials: int,
    cost: Measurements,
    criterion_assessments: int,
) -> ReportedCounts:
    """Every number the measurement plan asks for, for one variant."""
    scorable = [item for item in graded if item.scorable]
    unknowns = [item for item in scorable if item.expected_state is CriterionState.UNKNOWN]
    unmapped = [item for item in unknowns if not item.gradable_reason]
    looked_up = [item for item in unknowns if item.gradable_reason]
    return ReportedCounts(
        variant=variant,
        partition=partition,
        scenarios=scenarios,
        trials=trials,
        propositions=len(graded),
        scorable_propositions=len(scorable),
        coverage_only_propositions=len(graded) - len(scorable),
        reference_validity=Count(
            numerator=sum(1 for item in graded if item.references_valid),
            denominator=len(graded),
        ),
        unsupported_assessments=Count(
            numerator=sum(1 for item in graded if item.unsupported), denominator=len(graded)
        ),
        verification_induced_unknown=Count(
            numerator=sum(1 for item in graded if item.verification_induced_unknown),
            denominator=len(graded),
        ),
        state_agreement={
            state: Count(
                numerator=sum(
                    1 for item in scorable if item.expected_state is state and item.state_agrees
                ),
                denominator=sum(1 for item in scorable if item.expected_state is state),
            )
            for state in CriterionState
        },
        reason_agreement=Count(
            numerator=sum(1 for item in looked_up if item.reason_agrees),
            denominator=len(looked_up),
        ),
        not_looked_up=Count(numerator=len(unmapped), denominator=len(unknowns)),
        cost=CostCounts(
            model_calls=cost.model_calls,
            prompt_tokens=cost.prompt_tokens,
            completion_tokens=cost.completion_tokens,
            latency_ms=cost.latency_ms,
            estimated_cost_usd=cost.estimated_cost_usd,
            criterion_assessments=criterion_assessments,
        ),
    )


def validity_before_correction(graded: Sequence[GradedProposition]) -> Count:
    """The agent's citations as it first committed to them.

    This is the number the comparison uses. Post-correction validity is
    structural — the verifier degrades what it cannot verify — so comparing it
    against a variant that has no verifier would report an architectural
    difference as a finding.
    """
    verified = [item for item in graded if item.runtime_verdicts]
    return Count(
        numerator=sum(
            1 for item in verified if item.runtime_verdicts[0] is VerifierVerdict.ACCEPTED
        ),
        denominator=len(verified),
    )


def corrections_attempted(graded: Sequence[GradedProposition]) -> Count:
    """How often the one correction was spent, over the propositions that could
    spend it. The loop allows exactly one, so this is bounded by construction."""
    verified = [item for item in graded if item.runtime_verdicts]
    return Count(
        numerator=sum(1 for item in verified if len(item.runtime_verdicts) > 1),
        denominator=len(verified),
    )
