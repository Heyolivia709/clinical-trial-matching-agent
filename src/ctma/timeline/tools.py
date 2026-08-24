"""The five Timeline Tools of specification section 10.1.

Typed, read-only, and the agent's only way to see patient data. Three of them
look things up; two of them compute. The split matters: dates, numbers, and
Boolean logic route to code, and these two are where the routing lands.

**No tool returns a Criterion State.** A tool says what the record holds, or that
it cannot decide; turning that into `met`, `not_met`, or `unknown` with a reason
is the agent's job and the section 8.0 table's. That is why `Verdict` has no
`unknown` member: a tool that could return one would let an Infrastructure
Failure and an evidentiary gap arrive through the same channel, and keeping those
apart is a release gate.

Refusing is a real answer here. A comparison across units, or a date too coarse
to place in a window, is not a hard case to muddle through — it is a comparison
the record does not support, and saying so is the whole point of routing it to
code instead of to a model.

Where a bound *does* decide the question, though, these tools decide it. A
neutrophil count reported as "< 0.5" answers "is it at least 1.5?" with no
ambiguity at all, and refusing there would manufacture uncertainty, which is the
same defect as manufacturing certainty.
"""

from __future__ import annotations

import calendar
import datetime as dt
import json
from collections.abc import Mapping
from enum import StrEnum

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionCategory, TemporalPrecision
from ctma.domain.expression import TemporalWindow
from ctma.domain.timeline import (
    ClinicalInterval,
    FactValue,
    MedicationExposure,
    PatientTimeline,
    QuantityValue,
    TimelineFact,
)
from ctma.domain.trace import ToolCall, ToolReturned
from ctma.timeline._terminology import codes_for, codes_for_concept

DISQUALIFYING_OBSERVATION_STATUSES = frozenset({"preliminary", "entered-in-error"})
"""Section 5.2 names both. `corrected` and `amended` are not here: a corrected
result is the authoritative one."""

DISQUALIFYING_ADMINISTRATION_STATUSES = frozenset({"not-done", "entered-in-error"})
"""Section 5.3 requires a *valid* administration. A `not-done` record documents
that the drug was not given, which is the opposite of exposure."""


class Verdict(StrEnum):
    """What a deterministic tool concluded.

    Deliberately not a Criterion State. `REFUSED` means the comparison did not
    happen, which is a fact about the record and not yet a judgement about the
    patient.
    """

    HOLDS = "holds"
    FAILS = "fails"
    REFUSED = "refused"


class Refusal(StrEnum):
    """Why a deterministic tool refused. Each maps to one Unknown Reason later."""

    UNIT_MISMATCH = "unit_mismatch"
    """Cross-unit conversion is out of scope (section 5.2), so the units must
    match exactly."""

    VALUE_IS_NOT_NUMERIC = "value_is_not_numeric"
    """A qualitative result is never converted to a number without a reviewed
    mapping."""

    BOUND_STRADDLES_THE_THRESHOLD = "bound_straddles_the_threshold"
    """The value is reported as a bound — "< 0.5" — and the bound contains both
    answers."""

    PRECISION_TOO_COARSE = "precision_too_coarse"
    """The date is coarser than the window boundary it has to fall on."""

    NO_CLINICAL_TIME = "no_clinical_time"
    """The event carries no Clinical Time, so there is nothing to place."""


class Operator(StrEnum):
    LT = "<"
    LTE = "<="
    GT = ">"
    GTE = ">="
    EQ = "=="


class FactQuery(Frozen):
    """What `find_patient_facts` found, sorted into what it can and cannot support.

    `qualifying` and `disqualified` are separate because the section 8.0 table
    reads them separately: no fact at all is `missing_evidence`, and a fact whose
    status disqualifies it is `unusable_status`. Superseded facts are in neither;
    the correction that replaced them is in `qualifying`.
    """

    concept: str
    category: CriterionCategory
    qualifying: tuple[TimelineFact, ...] = ()
    disqualified: tuple[TimelineFact, ...] = ()
    mapped: bool = True
    """False when the reviewed mapping does not cover this concept and category.
    Not the same as finding nothing: nothing was looked for."""


class LatestObservation(Frozen):
    """The most recent qualifying observation, or why there is not one.

    `conflicting` is the ambiguous path: two qualifying results at the same
    Clinical Time disagreeing, which deterministic precedence cannot resolve. It
    is reported rather than resolved by picking one, because picking one is a
    coin toss with a citation attached.
    """

    concept: str
    latest: TimelineFact | None = None
    conflicting: tuple[TimelineFact, ...] = ()
    disqualified: tuple[TimelineFact, ...] = ()
    mapped: bool = True


class ExposureQuery(Frozen):
    """Documented administrations for a concept, placed against a window."""

    concept: str
    matched: tuple[MedicationExposure, ...] = ()
    outside_window: tuple[MedicationExposure, ...] = ()
    undecidable: tuple[MedicationExposure, ...] = ()
    """Exposures whose dates are too coarse to place in the window."""
    disqualified: tuple[MedicationExposure, ...] = ()
    orders_only: bool = False
    """The record holds an order for this drug and no administration. Order
    intent is not exposure, and this is the distinction the verifier's sixth
    check exists for."""
    mapped: bool = True


class Comparison(Frozen):
    """One deterministic numeric comparison, and its reason when it refused."""

    verdict: Verdict
    refusal: Refusal | None = None
    compared: str = Field(min_length=1)
    """The comparison as performed, for the trace to show."""


class WindowCheck(Frozen):
    """Whether an event falls in a window, with the window it was placed against."""

    verdict: Verdict
    refusal: Refusal | None = None
    window_start: dt.date | None = None
    window_end: dt.date | None = None


def find_patient_facts(
    timeline: PatientTimeline, *, category: CriterionCategory, concept: str
) -> FactQuery:
    """Locate timeline facts by Criterion Category and reviewed concept."""
    codes = codes_for(concept, category)
    if codes is None:
        return FactQuery(concept=concept, category=category, mapped=False)
    candidates = [
        item for item in timeline.facts if item.code.code in codes and item.superseded_by is None
    ]
    return FactQuery(
        concept=concept,
        category=category,
        qualifying=tuple(
            item for item in candidates if item.status not in DISQUALIFYING_OBSERVATION_STATUSES
        ),
        disqualified=tuple(
            item for item in candidates if item.status in DISQUALIFYING_OBSERVATION_STATUSES
        ),
    )


def get_latest_observation(
    timeline: PatientTimeline, *, concept: str, as_of: dt.date | None = None
) -> LatestObservation:
    """Retrieve the most recent qualifying observation at or before `as_of`."""
    moment = as_of or timeline.assessment_as_of
    codes = codes_for_concept(concept)
    if codes is None:
        return LatestObservation(concept=concept, mapped=False)
    candidates = [
        item
        for item in timeline.facts
        if item.code.code in codes and item.superseded_by is None
        if item.resource_type == "Observation"
    ]
    disqualified = tuple(
        item for item in candidates if item.status in DISQUALIFYING_OBSERVATION_STATUSES
    )
    dated = [
        item
        for item in candidates
        if item not in disqualified
        if item.time is not None and item.time.start <= moment
    ]
    if not dated:
        return LatestObservation(concept=concept, disqualified=disqualified)

    latest_time = max(item.time.start for item in dated if item.time is not None)
    at_latest = tuple(
        item for item in dated if item.time is not None and item.time.start == latest_time
    )
    if len({_reading(item) for item in at_latest}) > 1:
        return LatestObservation(concept=concept, conflicting=at_latest, disqualified=disqualified)
    return LatestObservation(concept=concept, latest=at_latest[-1], disqualified=disqualified)


def find_medication_exposure(
    timeline: PatientTimeline, *, concept: str, window: TemporalWindow | None = None
) -> ExposureQuery:
    """Locate documented administrations, optionally within a window.

    A window is placed against the *end* of documented exposure, because that is
    what a washout period counts from (section 5.3). An exposure with no recorded
    end is placed by its start.
    """
    codes = codes_for(concept, CriterionCategory.PRIOR_THERAPY)
    if codes is None:
        return ExposureQuery(concept=concept, mapped=False)

    candidates = [item for item in timeline.exposures if item.medication.code in codes]
    disqualified = tuple(
        item for item in candidates if item.status in DISQUALIFYING_ADMINISTRATION_STATUSES
    )
    qualifying = [item for item in candidates if item not in disqualified]

    if not qualifying:
        ordered = any(
            item.code is not None and item.code.code in codes
            for item in timeline.unsupported_content
        )
        return ExposureQuery(concept=concept, disqualified=disqualified, orders_only=ordered)
    if window is None:
        return ExposureQuery(concept=concept, matched=tuple(qualifying), disqualified=disqualified)

    placed: dict[Verdict, list[MedicationExposure]] = {verdict: [] for verdict in Verdict}
    for item in qualifying:
        check = check_temporal_window(item.time, anchor=timeline.assessment_as_of, window=window)
        placed[check.verdict].append(item)
    return ExposureQuery(
        concept=concept,
        matched=tuple(placed[Verdict.HOLDS]),
        outside_window=tuple(placed[Verdict.FAILS]),
        undecidable=tuple(placed[Verdict.REFUSED]),
        disqualified=disqualified,
    )


def compare_numeric(
    value: FactValue | float,
    *,
    operator: Operator,
    threshold: float,
    unit: str | None = None,
) -> Comparison:
    """Compare a recorded value with a threshold, within a single unit.

    A bound decides the question when it can: "< 0.5" is definitely not "at least
    1.5". Where the bound contains both answers, the comparison is refused rather
    than resolved to the nearer side.
    """
    compared = f"{_recorded(value)} {operator.value} {threshold}{f' {unit}' if unit else ''}"
    if isinstance(value, float | int):
        observed = _point(float(value))
    elif isinstance(value, QuantityValue):
        if _mismatched(value.unit, unit):
            return Comparison(
                verdict=Verdict.REFUSED, refusal=Refusal.UNIT_MISMATCH, compared=compared
            )
        observed = _bounded(value)
    else:
        return Comparison(
            verdict=Verdict.REFUSED, refusal=Refusal.VALUE_IS_NOT_NUMERIC, compared=compared
        )

    verdict = _place(observed, _predicate(operator, threshold))
    return Comparison(
        verdict=verdict,
        refusal=Refusal.BOUND_STRADDLES_THE_THRESHOLD if verdict is Verdict.REFUSED else None,
        compared=compared,
    )


def check_temporal_window(
    event: ClinicalInterval | None, *, anchor: dt.date, window: TemporalWindow
) -> WindowCheck:
    """Evaluate whether an event falls inside a window ending at the anchor.

    Endpoints are inclusive unless the criterion says otherwise (section 5.1).
    A coarse date is read as the range it stands for — `"2026"` is the whole of
    2026 — so it decides the question when the whole range falls on one side and
    refuses when it straddles the boundary.
    """
    start = anchor - window.duration
    if event is None:
        return WindowCheck(
            verdict=Verdict.REFUSED,
            refusal=Refusal.NO_CLINICAL_TIME,
            window_start=start,
            window_end=anchor,
        )
    inclusive = window.endpoints_inclusive
    span = _span(event)
    frame = (
        (start.toordinal(), 0 if inclusive else 1),
        (anchor.toordinal(), 0 if inclusive else -1),
    )
    verdict = _place(span, frame)
    return WindowCheck(
        verdict=verdict,
        refusal=Refusal.PRECISION_TOO_COARSE if verdict is Verdict.REFUSED else None,
        window_start=start,
        window_end=anchor,
    )


def record(
    tool: str, arguments: Mapping[str, str | float | bool | None], result: Frozen
) -> ToolCall:
    """The trace record for one tool call: what was asked, and what came back.

    Section 14 records tool calls with their arguments and results. Building the
    record here rather than at each call site means the trace cannot disagree
    with the result the agent actually received.
    """
    return ToolCall(
        tool=tool,
        arguments_json=json.dumps(dict(arguments), sort_keys=True),
        outcome=ToolReturned(result_json=result.model_dump_json()),
    )


# A position on a number line, with a tiebreak that encodes inclusivity: -1 is
# just below the value, 0 is the value itself, +1 is just above it. Two intervals
# can then be compared with plain tuple ordering, which is what lets one function
# answer both "is every possible value inside?" and "is any of them?".
_Bound = tuple[float, int]
_Range = tuple[_Bound, _Bound]


def _point(value: float) -> _Range:
    return (value, 0), (value, 0)


def _bounded(value: QuantityValue) -> _Range:
    """The set of values a recorded result stands for, comparator included."""
    match value.comparator:
        case "<":
            return (float("-inf"), 0), (value.value, -1)
        case "<=":
            return (float("-inf"), 0), (value.value, 0)
        case ">":
            return (value.value, 1), (float("inf"), 0)
        case ">=":
            return (value.value, 0), (float("inf"), 0)
        case _:
            return _point(value.value)


def _predicate(operator: Operator, threshold: float) -> _Range:
    """The set of values that satisfy the criterion's comparison."""
    match operator:
        case Operator.LT:
            return (float("-inf"), 0), (threshold, -1)
        case Operator.LTE:
            return (float("-inf"), 0), (threshold, 0)
        case Operator.GT:
            return (threshold, 1), (float("inf"), 0)
        case Operator.GTE:
            return (threshold, 0), (float("inf"), 0)
        case Operator.EQ:
            return (threshold, 0), (threshold, 0)


def _place(observed: _Range, predicate: _Range) -> Verdict:
    """Every possible value satisfies it, none does, or the answer is not there."""
    if predicate[0] <= observed[0] and observed[1] <= predicate[1]:
        return Verdict.HOLDS
    if max(observed[0], predicate[0]) > min(observed[1], predicate[1]):
        return Verdict.FAILS
    return Verdict.REFUSED


def _span(event: ClinicalInterval) -> _Range:
    """The days an event could have happened on, given its source precision."""
    if event.end is not None and event.end_precision is not None:
        moment, precision = event.end, event.end_precision
    else:
        moment, precision = event.start, event.start_precision
    first, last = _widen(moment, precision)
    return (first.toordinal(), 0), (last.toordinal(), 0)


def _widen(moment: dt.date, precision: TemporalPrecision) -> tuple[dt.date, dt.date]:
    """What a coarse date stands for: a year means the whole year."""
    match precision:
        case TemporalPrecision.YEAR:
            return dt.date(moment.year, 1, 1), dt.date(moment.year, 12, 31)
        case TemporalPrecision.MONTH:
            days = calendar.monthrange(moment.year, moment.month)[1]
            return dt.date(moment.year, moment.month, 1), dt.date(moment.year, moment.month, days)
        case _:
            return moment, moment


def _mismatched(recorded_unit: str | None, criterion_unit: str | None) -> bool:
    """Units must match exactly when both are stated. Conversion is out of scope.

    A criterion that states no unit is read as unitless — an ECOG score, a count
    of prior regimens — and compares against whatever the record holds.
    """
    if criterion_unit is None or recorded_unit is None:
        return False
    return recorded_unit.strip().casefold() != criterion_unit.strip().casefold()


def _recorded(value: FactValue | float) -> str:
    if isinstance(value, QuantityValue):
        return f"{value.comparator or ''}{value.value}{f' {value.unit}' if value.unit else ''}"
    if isinstance(value, float | int):
        return str(value)
    return value.text


def _reading(fact: TimelineFact) -> str:
    """What a fact says, for deciding whether two facts disagree."""
    return _recorded(fact.value) if fact.value is not None else fact.status
