"""Scenario Manifests: hidden ground truth, and what it refuses to carry."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from ctma.domain.enums import EVIDENCE_DERIVED_REASONS, TemporalPrecision
from ctma.evaluation.manifest import (
    EXPECTED_REASON_BY_DISTRACTOR,
    AuthoredFact,
    DistractorKind,
    PlantedDistractor,
    ScenarioManifest,
    missing_distractor_kinds,
)
from tests.builders import REVIEWED

BUNDLE_HASH = "4f1c" + "0" * 60


def preliminary_ecog() -> AuthoredFact:
    return AuthoredFact(
        fact_id="F1",
        resource_type="Observation",
        resource_id="obs-0402",
        json_path="Bundle.entry[57].resource.valueInteger",
        concept="ECOG",
        value="1",
        status="preliminary",
        clinical_time=dt.date(2026, 7, 24),
        precision=TemporalPrecision.DAY,
        usable_as_evidence=False,
    )


def scn03() -> ScenarioManifest:
    return ScenarioManifest(
        scenario_id="SCN-03",
        bundle_sha256=BUNDLE_HASH,
        assessment_as_of=dt.date(2026, 8, 4),
        facts=(preliminary_ecog(),),
        distractors=(
            PlantedDistractor(
                distractor_id="D1",
                kind=DistractorKind.PRELIMINARY_RESULT,
                fact_ids=("F1",),
                intent="A preliminary ECOG cannot establish a threshold comparison.",
            ),
        ),
        provenance=REVIEWED,
    )


def test_round_trips_through_json_without_loss() -> None:
    original = scn03()
    assert ScenarioManifest.model_validate_json(original.model_dump_json()) == original


def test_a_manifest_carries_no_expected_state() -> None:
    """ADR 0005: expected states are derived by code, never authored.

    A field here holding an answer would reintroduce the labelling judgement the
    derivation exists to remove, so the schema must not have one.
    """
    fields = set(ScenarioManifest.model_fields) | set(AuthoredFact.model_fields)
    forbidden = {"expected_state", "expected_states", "gold", "label", "answer"}
    assert not fields & forbidden


def test_a_distractor_pointing_at_no_fact_is_rejected() -> None:
    with pytest.raises(ValidationError, match="references unknown facts"):
        ScenarioManifest.model_validate(
            scn03().model_dump()
            | {
                "distractors": (
                    {
                        "distractor_id": "D9",
                        "kind": "conflicting_results",
                        "fact_ids": ("F404",),
                        "intent": "dangling",
                    },
                )
            }
        )


def test_a_dated_fact_declares_its_precision() -> None:
    with pytest.raises(ValidationError, match="declared together"):
        AuthoredFact.model_validate(preliminary_ecog().model_dump() | {"precision": None})


def test_a_short_bundle_hash_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenarioManifest.model_validate(scn03().model_dump() | {"bundle_sha256": "4f1c"})


def test_every_planted_hazard_maps_to_one_reason() -> None:
    """Specification section 8.3, as a test rather than as a table in prose."""
    assert set(EXPECTED_REASON_BY_DISTRACTOR) == set(DistractorKind)
    assert set(EXPECTED_REASON_BY_DISTRACTOR.values()) <= EVIDENCE_DERIVED_REASONS


def test_a_preliminary_result_is_unusable_status_not_missing_evidence() -> None:
    """The mockups got this wrong twice, calling it stale evidence.

    A fact that exists and is disqualified by its status is a different
    diagnosis from a fact that is absent, and from one that is merely old.
    """
    assert (
        EXPECTED_REASON_BY_DISTRACTOR[DistractorKind.PRELIMINARY_RESULT].value == "unusable_status"
    )
    assert (
        EXPECTED_REASON_BY_DISTRACTOR[DistractorKind.ERROR_STATUS_RESULT].value == "unusable_status"
    )
    assert (
        EXPECTED_REASON_BY_DISTRACTOR[DistractorKind.INSUFFICIENT_DATE_PRECISION].value
        == "insufficient_precision"
    )


def test_coverage_is_reported_across_the_scenario_set() -> None:
    """Section 4.4 obliges the six scenarios collectively, not each of them."""
    missing = missing_distractor_kinds((scn03(),))
    assert DistractorKind.PRELIMINARY_RESULT not in missing
    assert DistractorKind.NEAR_MISS_CONCEPT in missing
    assert len(missing) == len(DistractorKind) - 1
