"""Gold expected states, derived by code from the manifest and the expression.

Specification section 20 and ADR 0005. No model produces a label and no model
grades one. What makes that possible is that both halves of the answer are
authored artifacts: the Scenario Manifest says what facts were placed in the
patient, and the Criterion Expression says what satisfies the proposition. This
module applies the second to the first.

It is a second implementation of the same semantics, deliberately. It reads the
manifest rather than the Patient Timeline, matches facts by the concept the
scenario author recorded rather than by the reviewed terminology mapping, and
never calls a tool that the agent calls — with one exception, noted where it
happens: placing a date in a window is arithmetic, and reimplementing arithmetic
to disagree with itself measures nothing.

That difference in matching is the point. If a scenario carries a fact for a
concept the runtime mapping does not cover, gold says `met` and the system says
`missing_evidence`, and the benchmark counts a miss. Deriving gold through the
same mapping would hide exactly the gap the numbers exist to show.

**A proposition whose expected state cannot be derived is Coverage-Only.** It
stays visible and is excluded from accuracy counts. Inventing a label for it
would be the labelling judgement this module exists to avoid.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence

from pydantic import Field

from ctma.domain.aggregation import aggregate
from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionCategory, CriterionState, UnknownReason
from ctma.domain.expression import (
    AtomicProposition,
    EligibilityCriterion,
    NumericPredicate,
    PresencePredicate,
)
from ctma.domain.timeline import QuantityValue
from ctma.evaluation.manifest import AuthoredFact, ScenarioManifest
from ctma.timeline.tools import Verdict, compare_numeric

_QUANTITY = re.compile(r"^\s*([<>]=?)?\s*(-?\d+(?:\.\d+)?)\s*(.*?)\s*$")


class ExpectedProposition(Frozen):
    """What one proposition should come out as, and whether it can be scored."""

    proposition_id: str = Field(min_length=1)
    scorable: bool
    state: CriterionState | None = None
    reason: UnknownReason | None = None
    citable_fact_ids: tuple[str, ...] = ()
    """The facts an assessment may cite for this proposition. Any of them counts:
    two ECOG scores recorded on one day are one piece of evidence about the
    patient, and grading a citation against a single "right" fact would score a
    tie-break nobody made."""

    note: str | None = None
    """Why this is Coverage-Only, where it is."""


class ExpectedCriterion(Frozen):
    """The aggregate expected state, and the propositions it came from."""

    criterion_id: str = Field(min_length=1)
    scorable: bool
    state: CriterionState | None = None
    propositions: tuple[ExpectedProposition, ...] = Field(min_length=1)


def expected_proposition(
    proposition: AtomicProposition,
    *,
    manifest: ScenarioManifest,
) -> ExpectedProposition:
    """Derive one proposition's expected state from the authored facts."""
    if proposition.category is CriterionCategory.UNSUPPORTED:
        return _unknown(proposition, UnknownReason.UNSUPPORTED_EVIDENCE_TYPE)
    window = proposition.window
    if window is not None and not window.anchor_is_resolvable:
        return _unknown(proposition, UnknownReason.AMBIGUOUS_CRITERION)

    facts = _facts_for(proposition, manifest)
    usable = tuple(fact for fact in facts if fact.usable_as_evidence)
    if not facts:
        return _unknown(proposition, UnknownReason.MISSING_EVIDENCE)
    if not usable:
        return _unknown(proposition, UnknownReason.UNUSABLE_STATUS, facts=facts)
    if _disagree(usable):
        return _unknown(proposition, UnknownReason.CONFLICTING_EVIDENCE, facts=usable)
    if proposition.predicate is None:
        return ExpectedProposition(
            proposition_id=proposition.proposition_id,
            scorable=False,
            citable_fact_ids=tuple(fact.fact_id for fact in usable),
            note="the authored expression states no predicate, so no state follows from the facts",
        )
    return _apply(proposition, usable)


def expected_criterion(
    criterion: EligibilityCriterion, *, manifest: ScenarioManifest
) -> ExpectedCriterion:
    """Every proposition of one criterion, aggregated through its expression.

    A criterion with one Coverage-Only proposition is Coverage-Only itself: the
    aggregate cannot be computed without every branch, and guessing the missing
    one would put a label into the benchmark by the back door.
    """
    propositions = tuple(
        expected_proposition(proposition, manifest=manifest)
        for proposition in criterion.propositions
    )
    if not all(proposition.scorable for proposition in propositions):
        return ExpectedCriterion(
            criterion_id=criterion.criterion_id, scorable=False, propositions=propositions
        )
    states = {
        proposition.proposition_id: state
        for proposition in propositions
        if (state := proposition.state) is not None
    }
    return ExpectedCriterion(
        criterion_id=criterion.criterion_id,
        scorable=True,
        state=aggregate(criterion.expression, states).state,
        propositions=propositions,
    )


def _facts_for(
    proposition: AtomicProposition, manifest: ScenarioManifest
) -> tuple[AuthoredFact, ...]:
    """The authored facts for this concept, as they stood at the Assessment Time.

    Matched on the concept the scenario author recorded, not through the
    reviewed terminology mapping the system uses. A fact dated after the
    Assessment Time did not exist then and is not here, which is why a scenario
    whose only result is in the future derives to `missing_evidence`.
    """
    return tuple(
        fact
        for fact in manifest.facts
        if fact.concept == proposition.concept
        if fact.clinical_time is None or fact.clinical_time <= manifest.assessment_as_of
    )


def _disagree(facts: Sequence[AuthoredFact]) -> bool:
    """Two usable facts for one concept, recorded on one day, saying different things."""
    by_day: dict[dt.date | None, set[str | None]] = {}
    for fact in facts:
        by_day.setdefault(fact.clinical_time, set()).add(fact.value)
    return any(len(values) > 1 for values in by_day.values())


def _apply(proposition: AtomicProposition, facts: Sequence[AuthoredFact]) -> ExpectedProposition:
    """The authored predicate, over the authored fact."""
    predicate = proposition.predicate
    latest = max(facts, key=lambda fact: (fact.clinical_time is not None, fact.clinical_time))
    citable = tuple(fact.fact_id for fact in facts)

    if isinstance(predicate, PresencePredicate):
        holds = predicate.expects == "present"
        return ExpectedProposition(
            proposition_id=proposition.proposition_id,
            scorable=True,
            state=CriterionState.MET if holds else CriterionState.NOT_MET,
            citable_fact_ids=citable,
        )
    if isinstance(predicate, NumericPredicate):
        return _numeric(proposition, predicate, latest, citable)
    return ExpectedProposition(
        proposition_id=proposition.proposition_id,
        scorable=False,
        citable_fact_ids=citable,
        note="the predicate form has no derivation",
    )


def _numeric(
    proposition: AtomicProposition,
    predicate: NumericPredicate,
    fact: AuthoredFact,
    citable: tuple[str, ...],
) -> ExpectedProposition:
    """Compare the recorded value with the threshold the criterion states.

    The comparison runs through the same deterministic tool the agent uses.
    Arithmetic is not what the benchmark is measuring, and a second
    implementation of `<=` would only be able to disagree with the first by
    being wrong.
    """
    quantity = _quantity(fact.value)
    if quantity is None:
        return ExpectedProposition(
            proposition_id=proposition.proposition_id,
            scorable=False,
            citable_fact_ids=citable,
            note=f"the authored value {fact.value!r} is not a quantity this predicate can read",
        )
    comparison = compare_numeric(
        quantity,
        operator=predicate.operator,
        threshold=predicate.threshold,
        unit=predicate.unit,
    )
    if comparison.verdict is Verdict.REFUSED:
        return ExpectedProposition(
            proposition_id=proposition.proposition_id,
            scorable=False,
            citable_fact_ids=citable,
            note=f"the comparison was refused: {comparison.refusal}",
        )
    return ExpectedProposition(
        proposition_id=proposition.proposition_id,
        scorable=True,
        state=CriterionState.MET if comparison.verdict is Verdict.HOLDS else CriterionState.NOT_MET,
        citable_fact_ids=citable,
    )


def _quantity(value: str | None) -> QuantityValue | None:
    """A recorded value as a number and a unit, or None if it is not one."""
    if value is None:
        return None
    found = _QUANTITY.match(value)
    if found is None:
        return None
    comparator, number, unit = found.groups()
    return QuantityValue(value=float(number), unit=unit or None, comparator=comparator or None)


def _unknown(
    proposition: AtomicProposition,
    reason: UnknownReason,
    *,
    facts: Sequence[AuthoredFact] = (),
) -> ExpectedProposition:
    return ExpectedProposition(
        proposition_id=proposition.proposition_id,
        scorable=True,
        state=CriterionState.UNKNOWN,
        reason=reason,
        citable_fact_ids=tuple(fact.fact_id for fact in facts),
    )
