"""The six Authored Synthetic Scenarios, and what the fixtures promise.

Gate 2, specification sections 4.4 and 8.3. These tests read the frozen files
rather than constructing patients in code: a scenario built in a test is a
scenario the benchmark never runs.
"""

from __future__ import annotations

import pytest

from ctma.adapters.scenario_bundles import ScenarioInput, load_scenario_inputs
from ctma.domain.enums import Partition, ReviewStatus
from ctma.evaluation.manifest import DistractorKind, ScenarioManifest, missing_distractor_kinds
from ctma.evaluation.scenarios import load_scenario_manifests
from ctma.timeline.build import build

SCENARIOS = load_scenario_inputs()
MANIFESTS = load_scenario_manifests()
PAIRS = list(zip(SCENARIOS, MANIFESTS, strict=True))
IDS = [scenario.scenario_id for scenario in SCENARIOS]


def timeline_of(scenario: ScenarioInput):
    return build(
        scenario.bundle_json,
        scenario_id=scenario.scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )


def test_there_are_six_scenarios_split_four_and_two() -> None:
    """The benchmark plan's two-axis partition: four development, two held out."""
    assert len(MANIFESTS) == 6
    partitions = [manifest.partition for manifest in MANIFESTS]
    assert partitions.count(Partition.DEVELOPMENT) == 4
    assert partitions.count(Partition.HELD_OUT) == 2


@pytest.mark.parametrize(("scenario", "manifest"), PAIRS, ids=IDS)
def test_a_scenario_builds_reproducibly_from_its_frozen_bundle(
    scenario: ScenarioInput, manifest: ScenarioManifest
) -> None:
    """Same bytes, same timeline, and the hash the manifest was authored against.

    The hash is the join between the two files. Without it a Bundle could be
    edited after the manifest was reviewed, and the benchmark would grade a run
    against facts the patient no longer has.
    """
    timeline = timeline_of(scenario)
    assert timeline.bundle_sha256 == manifest.bundle_sha256
    assert timeline == timeline_of(scenario)


@pytest.mark.parametrize(("scenario", "manifest"), PAIRS, ids=IDS)
def test_a_scenario_carries_between_thirty_and_forty_five_facts(
    scenario: ScenarioInput, manifest: ScenarioManifest
) -> None:
    """Enough record that finding the right fact is work, and not more."""
    timeline = timeline_of(scenario)
    assert 30 <= len(timeline.facts) + len(timeline.exposures) <= 45


@pytest.mark.parametrize(("scenario", "manifest"), PAIRS, ids=IDS)
def test_every_timeline_fact_traces_to_an_authored_resource(
    scenario: ScenarioInput, manifest: ScenarioManifest
) -> None:
    """Nothing appears in a timeline that the manifest did not put there.

    Provenance runs both ways. The loader checks that every authored fact
    resolves in the Bundle; this checks the other direction, so a resource added
    to a Bundle without being recorded shows up here rather than in a grading
    run as an unexplained fact.
    """
    authored = {fact.fact_id: fact for fact in manifest.facts}
    timeline = timeline_of(scenario)
    for item in (*timeline.facts, *timeline.exposures):
        assert item.fact_id in authored, f"{item.fact_id} is in the Bundle and not the manifest"
        fact = authored[item.fact_id]
        assert fact.resource_type in item.fact_id
        assert fact.resource_id == item.resource_id
        assert fact.json_path.startswith(item.json_path)


@pytest.mark.parametrize(("scenario", "manifest"), PAIRS, ids=IDS)
def test_an_unusable_authored_fact_is_kept_rather_than_dropped(
    scenario: ScenarioInput, manifest: ScenarioManifest
) -> None:
    """A fact the scenario planted to be unusable is still in the record.

    Either as a timeline fact with its disqualifying status, or in the
    unsupported inventory. Dropping it would make `unusable_status` and
    `unsupported_evidence_type` impossible to tell from a concept nobody
    recorded.
    """
    timeline = timeline_of(scenario)
    present = {item.fact_id for item in (*timeline.facts, *timeline.exposures)} | {
        f"{item.resource_type}/{item.resource_id}" for item in timeline.unsupported_content
    }
    for fact in manifest.facts:
        assert fact.fact_id in present, f"{fact.fact_id} vanished during parsing"


@pytest.mark.parametrize("manifest", MANIFESTS, ids=IDS)
def test_a_manifest_is_reviewed_and_says_what_it_is_for(manifest: ScenarioManifest) -> None:
    """Section 17: AI drafting is allowed, unreviewed content is not frozen."""
    assert manifest.provenance.review_status is ReviewStatus.REVIEWED
    assert manifest.provenance.reviewed_by
    assert manifest.design_intent


def test_the_scenario_set_plants_every_hazard() -> None:
    """Section 4.4 obliges the six collectively, which is how this is checked."""
    assert missing_distractor_kinds(MANIFESTS) == frozenset()


def test_every_hazard_is_planted_in_a_development_scenario() -> None:
    """Held-out scenarios are assessed once, at the end, so they cannot carry a
    hazard the development tests are the only proof of. Every kind appears in
    the development half; the held-out half repeats some of them elsewhere in
    the record, which is what makes it a held-out set rather than an easier one.
    """
    development = tuple(
        manifest for manifest in MANIFESTS if manifest.partition is Partition.DEVELOPMENT
    )
    assert missing_distractor_kinds(development) == frozenset()


@pytest.mark.parametrize("manifest", MANIFESTS, ids=IDS)
def test_a_planted_hazard_names_the_facts_that_carry_it(manifest: ScenarioManifest) -> None:
    """A distractor with no fact behind it is a claim about a patient who does
    not exist, and would be graded as though the hazard had been planted."""
    authored = {fact.fact_id for fact in manifest.facts}
    for distractor in manifest.distractors:
        assert set(distractor.fact_ids) <= authored
        assert distractor.intent.endswith(".")


def test_a_disqualified_fact_keeps_its_status_in_the_timeline() -> None:
    """SCN-02's retracted PD-L1 and SCN-03's preliminary ECOG, as parsed."""
    statuses = {}
    for scenario, manifest in PAIRS:
        timeline = timeline_of(scenario)
        for item in timeline.facts:
            statuses[(manifest.scenario_id, item.fact_id)] = item.status
    assert statuses[("SCN-02", "Observation/obs-pdl1-error")] == "entered-in-error"
    assert statuses[("SCN-03", "Observation/obs-ecog-prelim")] == "preliminary"


def test_an_order_is_inventoried_as_unsupported_content_not_as_exposure() -> None:
    """SCN-04 holds an osimertinib order and no administration of it."""
    scenario = next(item for item in SCENARIOS if item.scenario_id == "SCN-04")
    timeline = timeline_of(scenario)
    assert not any(item.medication.code == "1721581" for item in timeline.exposures)
    orders = [
        item for item in timeline.unsupported_content if item.resource_type == "MedicationRequest"
    ]
    assert len(orders) == 1
    assert orders[0].code is not None
    assert orders[0].code.code == "1721581"


def test_a_post_assessment_observation_is_inventoried_and_is_not_a_fact() -> None:
    """SCN-04's only ECOG score was recorded after the Assessment Time."""
    scenario = next(item for item in SCENARIOS if item.scenario_id == "SCN-04")
    timeline = timeline_of(scenario)
    assert not any(item.code.code == "89247-1" for item in timeline.facts)
    assert any(
        item.code is not None and item.code.code == "89247-1"
        for item in timeline.unsupported_content
    )


def test_the_near_miss_concept_is_a_different_code_from_the_test_it_resembles() -> None:
    """SCN-04 holds an ALK protein stain and no ALK rearrangement result.

    If the two shared a code the hazard would be a naming problem rather than a
    concept problem, and the reviewed terminology mapping would be what fails.
    """
    scenario = next(item for item in SCENARIOS if item.scenario_id == "SCN-04")
    codes = {item.code.code for item in timeline_of(scenario).facts}
    assert "47303-3" in codes
    assert "78205-2" not in codes


def test_a_correction_supersedes_its_earlier_result() -> None:
    """SCN-06's ALK result was corrected on the day it was reported.

    A correction is not a conflict, and the difference decides whether the
    proposition resolves or reports `conflicting_evidence`.
    """
    scenario = next(item for item in SCENARIOS if item.scenario_id == "SCN-06")
    facts = {item.fact_id: item for item in timeline_of(scenario).facts}
    assert facts["Observation/obs-alk-first"].superseded_by == "Observation/obs-alk-corrected"
    assert facts["Observation/obs-alk-corrected"].superseded_by is None


def test_the_hazards_are_spread_across_the_scenario_set() -> None:
    """No scenario is the only one carrying a hazard the others could hide."""
    counts = {manifest.scenario_id: len(manifest.distractors) for manifest in MANIFESTS}
    assert counts["SCN-01"] == 0, "one scenario resolves cleanly, as the contrast case"
    assert sum(counts.values()) == 10
    assert len(DistractorKind) == 7
