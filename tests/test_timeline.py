"""Building a Patient Timeline from a FHIR Bundle.

One coverage Bundle under `fixtures/bundles/`, carrying every parsing case the
specification names: a year-only date, a corrected result, a disqualified
status, a result dated after screening, an order with no administration, and two
resource types the boundary does not interpret.

The parser itself is module-private, so everything here goes through `build`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ctma.domain.enums import TemporalPrecision
from ctma.domain.timeline import (
    ClinicalInterval,
    CodedValue,
    PatientTimeline,
    QuantityValue,
    TimelineFact,
    UnsupportedContent,
    UnsupportedReason,
)
from ctma.timeline.build import NORMALIZATION_VERSION, BundleError, build

BUNDLE = Path(__file__).resolve().parents[1] / "fixtures" / "bundles" / "timeline-coverage.json"
BUNDLE_JSON = BUNDLE.read_text(encoding="utf-8")
AS_OF = dt.date(2026, 8, 24)

TIMELINE = build(BUNDLE_JSON, scenario_id="coverage", assessment_as_of=AS_OF)


def fact(fact_id: str) -> TimelineFact:
    matches = [item for item in TIMELINE.facts if item.fact_id == fact_id]
    assert matches, f"{fact_id} is not in the timeline"
    return matches[0]


def when(fact_id: str) -> ClinicalInterval:
    time = fact(fact_id).time
    assert time is not None, f"{fact_id} carries no Clinical Time"
    return time


def inventoried(resource_id: str) -> UnsupportedContent:
    matches = [item for item in TIMELINE.unsupported_content if item.resource_id == resource_id]
    assert matches, f"{resource_id} is not in the unsupported inventory"
    return matches[0]


def test_the_four_evidence_bearing_resource_types_are_parsed() -> None:
    assert TIMELINE.demographics.administrative_sex == "female"
    assert {item.resource_type for item in TIMELINE.facts} == {"Condition", "Observation"}
    assert [item.fact_id for item in TIMELINE.exposures] == ["MedicationAdministration/medadmin-1"]


def test_every_bundle_entry_is_accounted_for() -> None:
    """A resource cannot go missing: it is a fact, an exposure, or inventoried."""
    entries: Any = json.loads(BUNDLE_JSON)["entry"]
    patient = 1
    assert len(TIMELINE.facts) + len(TIMELINE.exposures) + len(
        TIMELINE.unsupported_content
    ) + patient == len(entries)


def test_every_fact_traces_back_to_its_resource() -> None:
    """The JSON path is resolved here, not trusted: it has to find the resource."""
    bundle: Any = json.loads(BUNDLE_JSON)
    for item in (*TIMELINE.facts, *TIMELINE.exposures):
        index = int(item.json_path.removeprefix("entry[").split("]")[0])
        resource: Any = bundle["entry"][index]["resource"]
        assert resource["id"] == item.resource_id
        assert item.json_path == f"entry[{index}].resource"


def test_source_precision_is_preserved_and_never_widened() -> None:
    """`"2025"` is January 2025 at year precision, not the first of January."""
    brain_metastasis = when("Condition/cond-2")
    assert brain_metastasis.start == dt.date(2025, 1, 1)
    assert brain_metastasis.start_precision is TemporalPrecision.YEAR
    assert when("Condition/cond-1").start_precision is TemporalPrecision.DAY


def test_clinical_time_is_used_rather_than_when_the_row_was_written() -> None:
    """`onsetDateTime` and `effectiveDateTime`, never `recordedDate` or `issued`."""
    assert when("Condition/cond-1").start == dt.date(2024, 11, 2)  # recorded 2024-11-08
    assert when("Observation/obs-1").start == dt.date(2025, 1, 15)  # issued 2025-01-17


def test_an_exposure_keeps_its_interval_status_and_route() -> None:
    """Section 5.3: a washout window is computed from the end of the exposure."""
    exposure = TIMELINE.exposures[0]
    assert exposure.status == "completed"
    assert exposure.route == "Oral route"
    assert exposure.time is not None
    assert (exposure.time.start, exposure.time.end) == (dt.date(2025, 2, 1), dt.date(2026, 6, 30))
    assert exposure.medication.code == "1721581"


def test_a_quantity_keeps_its_comparator_unit_and_reference_range() -> None:
    """A result of "< 0.5" is not 0.5, and ignoring that is wrong quietly."""
    value = fact("Observation/obs-6").value
    assert isinstance(value, QuantityValue)
    assert (value.comparator, value.value, value.unit) == ("<", 0.5, "10*9/L")
    assert (value.reference_low, value.reference_high) == (1.5, 8.0)


def test_a_qualitative_result_stays_qualitative() -> None:
    """Section 5.2: no conversion to a number without a reviewed mapping."""
    value = fact("Observation/obs-3").value
    assert isinstance(value, CodedValue)
    assert value.text == "Present"


def test_a_corrected_result_supersedes_the_earlier_one_which_stays() -> None:
    """Provenance is retained: the report can show that the value was revised.

    This correction flips the answer — PD-L1 negative became positive — which is
    why showing only the correction would not be enough for a reader.
    """
    superseded = fact("Observation/obs-1")
    correction = fact("Observation/obs-2")
    assert superseded.superseded_by == correction.fact_id
    assert correction.superseded_by is None
    assert isinstance(superseded.value, CodedValue)
    assert isinstance(correction.value, CodedValue)
    assert (superseded.value.text, correction.value.text) == ("Negative", "Positive")


def test_a_disqualifying_status_keeps_its_fact() -> None:
    """Deleting it would make `unusable_status` unreportable.

    The Unknown Reason table needs a fact for the concept to exist and be
    disqualified. A dropped `entered-in-error` result is indistinguishable from a
    concept nobody ever recorded, and those are different diagnoses.
    """
    assert fact("Observation/obs-4").status == "entered-in-error"
    assert fact("Observation/obs-5").status == "preliminary"


def test_a_result_dated_after_screening_is_not_a_fact() -> None:
    """Section 5.1. It is inventoried, so a reader can see it was set aside."""
    assert "Observation/obs-7" not in {item.fact_id for item in TIMELINE.facts}
    assert inventoried("obs-7").reason is UnsupportedReason.AFTER_ASSESSMENT_TIME


def test_an_order_is_never_an_exposure() -> None:
    """Order intent is not exposure, and this is the citation the verifier catches."""
    assert inventoried("medreq-1").reason is UnsupportedReason.ORDER_INTENT_IS_NOT_EXPOSURE
    assert all(
        exposure.fact_id.startswith("MedicationAdministration/") for exposure in TIMELINE.exposures
    )


def test_content_outside_the_boundary_is_inventoried_with_its_identity() -> None:
    assert inventoried("enc-1").reason is UnsupportedReason.RESOURCE_TYPE_NOT_INTERPRETED
    assert inventoried("doc-1").resource_type == "DocumentReference"


def test_a_supported_resource_missing_what_it_needs_is_inventoried() -> None:
    """A `Condition` with no code cannot be normalised, and is not dropped for it."""
    assert inventoried("cond-3").reason is UnsupportedReason.INCOMPLETE_FOR_INTERPRETATION


def test_facts_are_ordered_by_clinical_time() -> None:
    starts = [item.time.start for item in TIMELINE.facts if item.time is not None]
    assert starts == sorted(starts)


def test_the_timeline_records_the_bundle_it_read_and_the_parser_that_read_it() -> None:
    assert TIMELINE.bundle_sha256 == hashlib.sha256(BUNDLE_JSON.encode()).hexdigest()
    assert TIMELINE.normalization_version == NORMALIZATION_VERSION
    assert TIMELINE.assessment_as_of == AS_OF


def test_the_timeline_round_trips_through_json_without_loss() -> None:
    assert PatientTimeline.model_validate_json(TIMELINE.model_dump_json()) == TIMELINE


def test_a_timeline_cannot_hold_a_fact_dated_after_its_assessment_time() -> None:
    """Held by the type, not by the parser remembering to filter."""
    with pytest.raises(ValidationError, match="dated after"):
        PatientTimeline.model_validate(
            TIMELINE.model_dump() | {"assessment_as_of": dt.date(2024, 12, 31)}
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json at all", "not valid JSON"),
        ('{"resourceType": "Patient"}', "not a FHIR Bundle"),
        ('{"resourceType": "Bundle", "entry": []}', "no Patient resource"),
        ('{"resourceType": "Bundle", "entry": [{}]}', "is not a JSON object"),
    ],
)
def test_a_bundle_this_system_cannot_read_is_an_error_and_not_an_unknown(
    payload: str, message: str
) -> None:
    """Section 8.2: a malformed input is a failure, never a Criterion State."""
    with pytest.raises(BundleError, match=message):
        build(payload, scenario_id="broken", assessment_as_of=AS_OF)


def test_two_patients_in_one_bundle_are_refused() -> None:
    """A timeline is one patient. Merging two silently is how records cross."""
    bundle: Any = json.loads(BUNDLE_JSON)
    bundle["entry"].append({"resource": {"resourceType": "Patient", "id": "patient-2"}})
    with pytest.raises(BundleError, match="more than one patient"):
        build(json.dumps(bundle), scenario_id="coverage", assessment_as_of=AS_OF)
