"""Citations: what they must carry, and what they are allowed to point at."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from ctma.domain.enums import EvidenceRelation, TemporalPrecision
from ctma.domain.evidence import PatientEvidence, PatientFactReference, TrialEvidence
from tests.builders import (
    EXC7_TEXT,
    SPAN_START,
    exc7_trial_evidence,
    exposure_evidence,
    osimertinib_administration,
)


def test_patient_evidence_round_trips_through_json_without_loss() -> None:
    original = exposure_evidence()
    assert PatientEvidence.model_validate_json(original.model_dump_json()) == original


def test_trial_evidence_round_trips_through_json_without_loss() -> None:
    original = exc7_trial_evidence()
    assert TrialEvidence.model_validate_json(original.model_dump_json()) == original


def test_the_json_path_and_the_cited_value_both_survive_the_round_trip() -> None:
    """The path lets the verifier find the fact; the value lets it disagree."""
    restored = PatientEvidence.model_validate_json(exposure_evidence().model_dump_json())
    fact = restored.facts[0]
    assert fact.json_path == "entry[12].resource.effectiveDateTime"
    assert fact.value == "osimertinib 80 mg oral tablet"
    assert fact.status == "completed"
    assert fact.precision is TemporalPrecision.YEAR


def test_a_dated_fact_declares_its_precision() -> None:
    """Section 5.1: source precision is preserved, not assumed to be a day."""
    with pytest.raises(ValidationError, match="precision"):
        PatientFactReference(
            resource_type="Observation",
            resource_id="obs-1",
            json_path="entry[3].resource.effectiveDateTime",
            clinical_time=dt.date(2024, 1, 1),
            status="final",
            code="LOINC:83052-1",
            display="PD-L1 by 22C3: Positive",
        )


def test_a_precision_without_a_date_is_refused_too() -> None:
    with pytest.raises(ValidationError, match="precision"):
        PatientFactReference(
            resource_type="Observation",
            resource_id="obs-1",
            json_path="entry[3].resource.valueQuantity",
            precision=TemporalPrecision.DAY,
            status="final",
            code="LOINC:83052-1",
            display="PD-L1 by 22C3: Positive",
        )


def test_an_undated_fact_needs_no_precision() -> None:
    """Demographics and conditions may carry no clinical time at all."""
    reference = PatientFactReference(
        resource_type="Patient",
        resource_id="patient-1",
        json_path="entry[0].resource.gender",
        status="active",
        code="administrativeGender",
        value="female",
        display="Female",
    )
    assert reference.clinical_time is None


def test_evidence_states_its_relation_to_the_proposition() -> None:
    """Section 8.1 rejects an unlabeled relation, so there is no default here."""
    with pytest.raises(ValidationError, match="relation"):
        PatientEvidence.model_validate({"facts": [osimertinib_administration().model_dump()]})


def test_evidence_cites_at_least_one_fact() -> None:
    with pytest.raises(ValidationError, match="at least 1 item"):
        PatientEvidence(facts=(), relation=EvidenceRelation.SUPPORTS)


def test_a_citation_may_name_a_resource_outside_the_evidence_boundary() -> None:
    """Deliberate: the sixth verifier check needs this citation to be buildable.

    A `MedicationRequest` cited as treatment exposure resolves cleanly and is
    still not evidence, and the injected-fault demonstration is exactly that
    citation. A type that forbade it here would move the demonstration out of
    reach and leave the check untestable.
    """
    order = PatientFactReference(
        resource_type="MedicationRequest",
        resource_id="medreq-9",
        json_path="entry[7].resource.authoredOn",
        clinical_time=dt.date(2026, 6, 1),
        precision=TemporalPrecision.DAY,
        status="active",
        code="RxNorm:1721581",
        value="osimertinib 80 mg oral tablet",
        display="Osimertinib order, 2026-06-01",
    )
    assert order.resource_type == "MedicationRequest"


def test_a_trial_span_must_contain_the_text_it_claims() -> None:
    """A span that does not fit the text points somewhere else in the snapshot."""
    with pytest.raises(ValidationError, match="span width"):
        TrialEvidence(
            snapshot_id="ctgov-2026-08-01",
            nct_id="NCT05123456",
            source_section="exclusionCriteria",
            criterion_ordinal=7,
            span_start=SPAN_START,
            span_end=SPAN_START + len(EXC7_TEXT) - 3,
            source_text=EXC7_TEXT,
        )


def test_a_trial_citation_names_a_real_nct_identifier() -> None:
    with pytest.raises(ValidationError, match="pattern"):
        TrialEvidence(
            snapshot_id="ctgov-2026-08-01",
            nct_id="EXC-7",
            source_section="exclusionCriteria",
            criterion_ordinal=7,
            span_start=0,
            span_end=len(EXC7_TEXT),
            source_text=EXC7_TEXT,
        )


def test_citations_are_immutable() -> None:
    with pytest.raises(ValidationError):
        exc7_trial_evidence().source_text = "something shorter"  # type: ignore[misc]
