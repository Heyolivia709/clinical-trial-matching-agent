"""Building a Patient Timeline from a FHIR R4 Bundle.

Specification sections 5 through 5.4. `build` is the whole public interface;
everything else here is the parser, which is module-private by section 12 and
has no test that imports it directly.

Three rules the parser follows and the docstrings below keep pointing at:

Clinical Time only. Onset, effective, and administration times are clinical;
`recordedDate` and `issued` are when a system wrote the row down, and a criterion
asking "within 14 days" means the event, not the paperwork.

Precision is never widened. `"2025"` becomes 1 January 2025 with `YEAR`
precision, so a comparison that needs a day can refuse rather than quietly using
the first of January.

Nothing is dropped. Every Bundle entry becomes a fact, an exposure, or a line in
the unsupported inventory. A resource the parser cannot interpret is inventoried
with whatever identity it has, which is what keeps "the parser skipped it" from
looking the same as "the record never mentioned it".
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from collections.abc import Mapping
from typing import Any, cast

from ctma.domain.enums import TemporalPrecision
from ctma.domain.timeline import (
    ClinicalInterval,
    CodedValue,
    Coding,
    Demographics,
    FactValue,
    MedicationExposure,
    PatientTimeline,
    QuantityValue,
    TimelineFact,
    UnsupportedContent,
    UnsupportedReason,
)

NORMALIZATION_VERSION = "timeline-v1"
"""Bumped when parsing changes. It is recorded on every timeline, so a rerun
under different parsing is visibly a different artifact rather than a
contradiction of the first one."""

Resource = Mapping[str, Any]
"""One FHIR resource as `json` handed it over. Untyped on purpose: this module
is where an unvalidated Bundle becomes typed, and pretending it arrives typed
would move the checks somewhere they cannot fail."""

_SUPERSEDING_STATUSES = frozenset({"corrected", "amended"})
"""Section 5.2: a corrected or amended result supersedes prior versions."""


class BundleError(ValueError):
    """The Bundle is not one this system can build a timeline from.

    Raised rather than degraded. A malformed input is an Infrastructure Failure,
    and section 8.2 keeps those out of the Criterion States.
    """


def build(bundle_json: str, *, scenario_id: str, assessment_as_of: dt.date) -> PatientTimeline:
    """Parse one Bundle into a timeline as it stood at `assessment_as_of`.

    Takes the serialized Bundle rather than a parsed one so the recorded hash is
    over the bytes that were actually read.
    """
    digest = hashlib.sha256(bundle_json.encode()).hexdigest()
    try:
        parsed_bundle: object = json.loads(bundle_json)
    except json.JSONDecodeError as error:
        msg = f"the Bundle is not valid JSON: {error}"
        raise BundleError(msg) from error

    bundle = _object(parsed_bundle, "the payload")
    if bundle.get("resourceType") != "Bundle":
        msg = "the payload is not a FHIR Bundle"
        raise BundleError(msg)

    facts: list[TimelineFact] = []
    exposures: list[MedicationExposure] = []
    unsupported: list[UnsupportedContent] = []
    demographics: Demographics | None = None

    entries: Any = bundle.get("entry") or ()
    for index, raw_entry in enumerate(entries):
        path = f"entry[{index}].resource"
        entry = _object(raw_entry, f"entry[{index}]")
        resource = _object(entry.get("resource"), path)
        kind: str = resource.get("resourceType") or ""

        if kind == "Patient":
            if demographics is not None:
                msg = "the Bundle describes more than one patient"
                raise BundleError(msg)
            demographics = _demographics(resource, path)
            continue

        parsed = _resource(kind, resource, path, assessment_as_of)
        match parsed:
            case TimelineFact():
                facts.append(parsed)
            case MedicationExposure():
                exposures.append(parsed)
            case UnsupportedContent():
                unsupported.append(parsed)

    if demographics is None:
        msg = "the Bundle contains no Patient resource"
        raise BundleError(msg)

    return PatientTimeline(
        scenario_id=scenario_id,
        bundle_sha256=digest,
        normalization_version=NORMALIZATION_VERSION,
        assessment_as_of=assessment_as_of,
        demographics=demographics,
        facts=_superseded(_ordered(facts)),
        exposures=tuple(exposures),
        unsupported_content=tuple(unsupported),
    )


def _object(value: object, what: str) -> Resource:
    """A JSON object, or a `BundleError` naming what was expected where."""
    if not isinstance(value, dict):
        msg = f"{what} is not a JSON object"
        raise BundleError(msg)
    return cast(Resource, value)


def _resource(
    kind: str, resource: Resource, path: str, as_of: dt.date
) -> TimelineFact | MedicationExposure | UnsupportedContent:
    """One entry, routed by resource type. Section 5's boundary, as a dispatch."""
    if kind == "MedicationRequest":
        return _inventory(kind, resource, path, UnsupportedReason.ORDER_INTENT_IS_NOT_EXPOSURE)
    if kind not in {"Condition", "Observation", "MedicationAdministration"}:
        return _inventory(kind, resource, path, UnsupportedReason.RESOURCE_TYPE_NOT_INTERPRETED)

    resource_id: str | None = resource.get("id")
    status = _status(kind, resource)
    code = _code(kind, resource)
    if not resource_id or status is None or code is None:
        return _inventory(kind, resource, path, UnsupportedReason.INCOMPLETE_FOR_INTERPRETATION)

    time = _time(resource)
    if time is not None and time.start > as_of:
        return _inventory(kind, resource, path, UnsupportedReason.AFTER_ASSESSMENT_TIME)

    if kind == "MedicationAdministration":
        return MedicationExposure(
            fact_id=f"{kind}/{resource_id}",
            resource_id=resource_id,
            json_path=path,
            medication=code,
            status=status,
            route=_route(resource),
            time=time,
        )
    return TimelineFact(
        fact_id=f"{kind}/{resource_id}",
        resource_type=kind,
        resource_id=resource_id,
        json_path=path,
        code=code,
        status=status,
        time=time,
        value=_value(resource),
    )


def _inventory(
    kind: str, resource: Resource, path: str, reason: UnsupportedReason
) -> UnsupportedContent:
    return UnsupportedContent(
        resource_type=kind or "unknown",
        resource_id=resource.get("id"),
        json_path=path,
        reason=reason,
    )


def _demographics(resource: Resource, path: str) -> Demographics:
    addresses: Any = resource.get("address") or ()
    address: Any = addresses[0] if addresses else None
    birth = _date(resource.get("birthDate"))
    return Demographics(
        resource_id=resource.get("id") or "",
        json_path=path,
        birth_date=birth[0] if birth else None,
        birth_date_precision=birth[1] if birth else None,
        administrative_sex=resource.get("gender"),
        country=address.get("country") if address else None,
        state=address.get("state") if address else None,
    )


def _status(kind: str, resource: Resource) -> str | None:
    """The status that can disqualify the fact.

    For a `Condition` that is `verificationStatus`, because `entered-in-error`
    lives there; `clinicalStatus` is the fallback and says whether the problem is
    active, which is a different question.
    """
    if kind != "Condition":
        return resource.get("status")
    for field in ("verificationStatus", "clinicalStatus"):
        code = _coding(resource.get(field))
        if code is not None:
            return code.code
    return None


def _code(kind: str, resource: Resource) -> Coding | None:
    field = "medicationCodeableConcept" if kind == "MedicationAdministration" else "code"
    return _coding(resource.get(field))


def _coding(concept: Resource | None) -> Coding | None:
    """The first coding of a CodeableConcept, or its text if it has no coding."""
    if not concept:
        return None
    codings: Any = concept.get("coding") or ()
    if codings:
        first: Any = codings[0]
        code: Any = first.get("code")
        if code:
            return Coding(system=first.get("system"), code=code, display=first.get("display"))
    text: Any = concept.get("text")
    return Coding(code=text) if text else None


def _time(resource: Resource) -> ClinicalInterval | None:
    """Clinical Time, from whichever field this resource type puts it in."""
    for field in ("effectiveDateTime", "onsetDateTime", "occurrenceDateTime"):
        moment = _date(resource.get(field))
        if moment is not None:
            return ClinicalInterval(start=moment[0], start_precision=moment[1])
    for field in ("effectivePeriod", "onsetPeriod", "occurrencePeriod"):
        period: Any = resource.get(field)
        if period:
            start = _date(period.get("start"))
            if start is None:
                continue
            end = _date(period.get("end"))
            return ClinicalInterval(
                start=start[0],
                start_precision=start[1],
                end=end[0] if end else None,
                end_precision=end[1] if end else None,
            )
    return None


def _date(raw: object) -> tuple[dt.date, TemporalPrecision] | None:
    """A FHIR date, dateTime, or instant, with the precision it was written at.

    The precision is the whole reason this returns a pair. `"2024"` and
    `"2024-01-01"` both become 1 January 2024, and only the precision says which
    of the two the record actually supports.
    """
    if not isinstance(raw, str) or not raw:
        return None
    text = raw.strip()
    try:
        if len(text) == 4:
            return dt.date(int(text), 1, 1), TemporalPrecision.YEAR
        if len(text) == 7:
            year, month = text.split("-")
            return dt.date(int(year), int(month), 1), TemporalPrecision.MONTH
        if len(text) == 10:
            return dt.date.fromisoformat(text), TemporalPrecision.DAY
        return (
            dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date(),
            TemporalPrecision.INSTANT,
        )
    except ValueError as error:
        msg = f"unparsable FHIR date {raw!r}: {error}"
        raise BundleError(msg) from error


def _value(resource: Resource) -> FactValue | None:
    quantity: Any = resource.get("valueQuantity")
    if quantity and quantity.get("value") is not None:
        low, high = _reference_range(resource)
        return QuantityValue(
            value=float(quantity["value"]),
            unit=quantity.get("unit") or quantity.get("code"),
            comparator=quantity.get("comparator"),
            reference_low=low,
            reference_high=high,
        )
    coded = _coding(resource.get("valueCodeableConcept"))
    if coded is not None:
        return CodedValue(text=coded.display or coded.code, coding=coded)
    text: Any = resource.get("valueString")
    return CodedValue(text=text) if isinstance(text, str) and text else None


def _reference_range(resource: Resource) -> tuple[float | None, float | None]:
    ranges: Any = resource.get("referenceRange") or ()
    if not ranges:
        return None, None
    first: Any = ranges[0]
    low_bound: Any = first.get("low")
    high_bound: Any = first.get("high")
    low: Any = low_bound.get("value") if low_bound else None
    high: Any = high_bound.get("value") if high_bound else None
    return (
        float(low) if low is not None else None,
        float(high) if high is not None else None,
    )


def _route(resource: Resource) -> str | None:
    dosage: Any = resource.get("dosage")
    route = _coding(dosage.get("route") if dosage else None)
    return route.display or route.code if route is not None else None


def _ordered(facts: list[TimelineFact]) -> list[TimelineFact]:
    """Time-ordered, with undated facts last and in Bundle order."""
    return sorted(
        facts,
        key=lambda fact: (fact.time is None, fact.time.start if fact.time else dt.date.min),
    )


def _superseded(facts: list[TimelineFact]) -> tuple[TimelineFact, ...]:
    """Point earlier results at the correction that replaced them.

    Two results for one code at one Clinical Time are a correction, not a
    conflict, and the difference matters: a correction resolves deterministically
    and a conflict is `unknown` with `conflicting_evidence`. The superseded fact
    stays, so the report can show that the value was revised.
    """
    corrections: dict[tuple[str, dt.date | None], str] = {}
    for fact in facts:
        if fact.status in _SUPERSEDING_STATUSES:
            corrections[_group(fact)] = fact.fact_id
    return tuple(
        fact
        if _group(fact) not in corrections or corrections[_group(fact)] == fact.fact_id
        else fact.model_copy(update={"superseded_by": corrections[_group(fact)]})
        for fact in facts
    )


def _group(fact: TimelineFact) -> tuple[str, dt.date | None]:
    return fact.code.code, fact.time.start if fact.time else None
