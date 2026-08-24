"""The Patient Timeline: what the record says, with its provenance attached.

Specification sections 5 through 5.4 and 13. The timeline is a faithful view of
one FHIR Bundle, not an interpretation of it. Status is preserved rather than
filtered, source date precision is preserved rather than widened, and a
disqualifying status keeps its fact instead of deleting it.

That last one is the point worth stating. A `preliminary` result and an
`entered-in-error` result cannot establish `met` or `not_met`, so it is tempting
to drop them while parsing. Dropping them makes `unusable_status` impossible to
report: the Unknown Reason table needs a fact for the concept to exist and be
disqualified, and a deleted fact is indistinguishable from a concept nobody ever
recorded. The timeline keeps them; the Timeline Tools decide what they can
support.

The types here carry no normalized concept. Mapping a source code to a canonical
concept is a reviewed judgement that belongs with the tools that query by
concept, and keeping it out means the timeline cannot quietly become an
interpretation of the record.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import TemporalPrecision


class Coding(Frozen):
    """One source code, kept as the record wrote it."""

    system: str | None = None
    code: str = Field(min_length=1)
    display: str | None = None


class ClinicalInterval(Frozen):
    """Clinical Time, with the precision the source supported.

    An interval rather than an instant, because section 5.1 requires intervals
    to be preserved: a washout window is computed from the end of a documented
    exposure, and an exposure collapsed to its start date would answer the wrong
    question.

    `end` absent means the source recorded no end, not that the event ended
    today.
    """

    start: dt.date
    start_precision: TemporalPrecision
    end: dt.date | None = None
    end_precision: TemporalPrecision | None = None

    @model_validator(mode="after")
    def _an_end_declares_its_precision(self) -> Self:
        if (self.end is None) != (self.end_precision is None):
            msg = "end and end_precision are declared together or not at all"
            raise ValueError(msg)
        if self.end is not None and self.end < self.start:
            msg = f"interval ends before it starts: {self.start} to {self.end}"
            raise ValueError(msg)
        return self


class QuantityValue(Frozen):
    """A numeric result with its unit, comparator, and reference range.

    The comparator is kept because "< 0.5" is not 0.5. Cross-unit conversion and
    ULN derivation are out of scope (section 5.2), so the unit and the range are
    recorded for a deterministic comparison to use or refuse, not normalised
    here.
    """

    kind: Literal["quantity"] = "quantity"
    value: float
    unit: str | None = None
    comparator: str | None = None
    reference_low: float | None = None
    reference_high: float | None = None


class CodedValue(Frozen):
    """A qualitative result, which never becomes a number.

    Section 5.2: qualitative values are not converted without a reviewed
    mapping, and this type has nowhere to put a number.
    """

    kind: Literal["coded"] = "coded"
    text: str = Field(min_length=1)
    coding: Coding | None = None


FactValue = Annotated[QuantityValue | CodedValue, Field(discriminator="kind")]


class TimelineFact(Frozen):
    """One clinical fact from a `Condition` or an `Observation`.

    `superseded_by` names the corrected or amended result that replaced this
    one. The superseded fact stays here, because section 5.2 supersedes prior
    versions while retaining provenance, and a report that showed only the
    correction could not show that there had been one.
    """

    fact_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)
    code: Coding
    status: str = Field(min_length=1)
    time: ClinicalInterval | None = None
    value: FactValue | None = None
    superseded_by: str | None = None

    @property
    def display(self) -> str:
        """A label derived from the source record, for a citation to carry."""
        return self.code.display or self.code.code


class MedicationExposure(Frozen):
    """A documented administration. Section 5.3: this is what establishes exposure.

    An order is not here. `MedicationRequest` is Unsupported Patient Content,
    because order intent is not exposure, and the whole injected-fault
    demonstration turns on a citation that confuses the two.
    """

    fact_id: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)
    medication: Coding
    status: str = Field(min_length=1)
    route: str | None = None
    time: ClinicalInterval | None = None

    @property
    def display(self) -> str:
        return self.medication.display or self.medication.code


class UnsupportedReason(StrEnum):
    """Why a resource is inventoried instead of interpreted."""

    ORDER_INTENT_IS_NOT_EXPOSURE = "order_intent_is_not_exposure"
    """`MedicationRequest`, named by section 5 as unsupported content."""

    RESOURCE_TYPE_NOT_INTERPRETED = "resource_type_not_interpreted"
    """Outside the four evidence-bearing types: notes, imaging, encounters."""

    INCOMPLETE_FOR_INTERPRETATION = "incomplete_for_interpretation"
    """A supported resource type missing what interpretation needs, such as a
    `Condition` with no code."""

    AFTER_ASSESSMENT_TIME = "after_assessment_time"
    """Section 5.1 ignores events after `assessment_as_of`. It is inventoried
    rather than dropped so a reader can see the parser met it and set it aside;
    it is not a fact, so it cannot be cited."""


class UnsupportedContent(Frozen):
    """Bundle content preserved for provenance and not interpreted."""

    resource_type: str = Field(min_length=1)
    resource_id: str | None = None
    json_path: str = Field(min_length=1)
    reason: UnsupportedReason


class Demographics(Frozen):
    """The `Patient` resource, reduced to what criteria and filters ask about.

    Geography is the recruiting-site comparison of section 9 and nothing more.
    Nothing here is derived: age is computed where it is compared, against a
    stated Assessment Time, rather than stored as a number that ages.
    """

    resource_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)
    birth_date: dt.date | None = None
    birth_date_precision: TemporalPrecision | None = None
    administrative_sex: str | None = None
    country: str | None = None
    state: str | None = None

    @model_validator(mode="after")
    def _a_birth_date_declares_its_precision(self) -> Self:
        if (self.birth_date is None) != (self.birth_date_precision is None):
            msg = "birth_date and birth_date_precision are declared together or not at all"
            raise ValueError(msg)
        return self


class PatientTimeline(Frozen):
    """One Bundle, at one Assessment Time, with everything it contained accounted for.

    Facts, exposures, and the unsupported inventory together cover the Bundle:
    every entry ends up in exactly one of them, so "the parser dropped it" is
    not a way for a resource to disappear.
    """

    scenario_id: str = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization_version: str = Field(min_length=1)
    assessment_as_of: dt.date
    demographics: Demographics
    facts: tuple[TimelineFact, ...] = ()
    exposures: tuple[MedicationExposure, ...] = ()
    unsupported_content: tuple[UnsupportedContent, ...] = ()

    @model_validator(mode="after")
    def _nothing_is_dated_after_the_assessment_time(self) -> Self:
        """Section 5.1, held by the type rather than by the parser remembering.

        A later result is real information and the wrong information: at
        screening time it did not exist. The timeline is what a tool reads, so
        the exclusion belongs where a tool cannot get around it.
        """
        starts = [
            (item.fact_id, item.time.start)
            for item in (*self.facts, *self.exposures)
            if item.time is not None
        ]
        late = [fact_id for fact_id, start in starts if start > self.assessment_as_of]
        if late:
            msg = f"these are dated after {self.assessment_as_of}: {sorted(late)}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _facts_are_time_ordered_with_undated_facts_last(self) -> Self:
        dated = [fact.time.start for fact in self.facts if fact.time is not None]
        if dated != sorted(dated):
            msg = "facts must be ordered by Clinical Time"
            raise ValueError(msg)
        seen_undated = False
        for fact in self.facts:
            if fact.time is None:
                seen_undated = True
            elif seen_undated:
                msg = f"{fact.fact_id} is dated but follows an undated fact"
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _identifiers_are_unique_and_supersession_resolves(self) -> Self:
        ids = [item.fact_id for item in (*self.facts, *self.exposures)]
        if len(ids) != len(set(ids)):
            msg = "a fact_id appears twice in one timeline"
            raise ValueError(msg)
        known = set(ids)
        for fact in self.facts:
            if fact.superseded_by is not None and fact.superseded_by not in known:
                msg = f"{fact.fact_id} is superseded by {fact.superseded_by}, which is not here"
                raise ValueError(msg)
        return self
