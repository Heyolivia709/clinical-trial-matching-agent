"""Loading the six Authored Synthetic Scenarios and their hidden manifests.

Specification section 4.4. The Bundle is public and the manifest is not, so they
are loaded by two different modules: `ctma.adapters.scenario_bundles` hands the
Bundle to the matching system, and this module — which nothing may import — is
the only way to reach the manifest beside it.

Loading is where the two are checked against each other. A manifest is ground
truth for grading, and a manifest describing facts the Bundle does not contain
would grade a run against a patient who was never presented to it. So every
authored fact has to resolve at its recorded JSON path, in a resource of the
declared type and id, in a Bundle whose bytes hash to the recorded digest.
Editing either file alone makes the pair fail to load rather than drift.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from ctma.adapters.scenario_bundles import ScenarioInput, load_scenario_inputs
from ctma.evaluation.manifest import AuthoredFact, ScenarioManifest

MANIFESTS = Path(__file__).resolve().parents[3] / "fixtures" / "manifests"


class ScenarioError(ValueError):
    """A frozen scenario does not describe the Bundle it claims to describe."""


def load_scenario_manifests() -> tuple[ScenarioManifest, ...]:
    """Every manifest, in scenario id order, each checked against its Bundle."""
    return tuple(_load(scenario) for scenario in load_scenario_inputs())


def load_scenario_manifest(scenario_id: str) -> ScenarioManifest:
    for manifest in load_scenario_manifests():
        if manifest.scenario_id == scenario_id:
            return manifest
    msg = f"no manifest for {scenario_id!r} under {MANIFESTS}"
    raise ScenarioError(msg)


def _load(scenario: ScenarioInput) -> ScenarioManifest:
    path = MANIFESTS / f"{scenario.scenario_id.lower()}.json"
    if not path.is_file():
        msg = f"{scenario.scenario_id} has a Bundle and no manifest: {path} is missing"
        raise ScenarioError(msg)
    manifest = ScenarioManifest.model_validate_json(path.read_text(encoding="utf-8"))

    if manifest.scenario_id != scenario.scenario_id:
        msg = f"{path.name} calls itself {manifest.scenario_id!r}"
        raise ScenarioError(msg)
    if manifest.assessment_as_of != scenario.assessment_as_of:
        msg = (
            f"{scenario.scenario_id}: the manifest is written as of "
            f"{manifest.assessment_as_of} and the scenario index says "
            f"{scenario.assessment_as_of}"
        )
        raise ScenarioError(msg)

    digest = hashlib.sha256(scenario.bundle_json.encode()).hexdigest()
    if digest != manifest.bundle_sha256:
        msg = (
            f"{scenario.scenario_id}: the Bundle has changed since the manifest was "
            f"authored, so the manifest is no longer ground truth for it"
        )
        raise ScenarioError(msg)

    bundle: object = json.loads(scenario.bundle_json)
    for fact in manifest.facts:
        _check(scenario.scenario_id, bundle, fact)
    return manifest


def _check(scenario_id: str, bundle: object, fact: AuthoredFact) -> None:
    """The authored fact points at a real resource, and at the right one."""
    resource_path, _, _ = fact.json_path.partition(".resource")
    resource = _resolve(bundle, f"{resource_path}.resource")
    if not isinstance(resource, dict):
        msg = f"{scenario_id}: {fact.fact_id} names no resource at {fact.json_path}"
        raise ScenarioError(msg)
    fields = cast(Mapping[str, Any], resource)
    identity = (fields.get("resourceType"), fields.get("id"))
    if identity != (fact.resource_type, fact.resource_id):
        msg = (
            f"{scenario_id}: {fact.fact_id} is authored as {fact.resource_type}/"
            f"{fact.resource_id} and the Bundle holds {identity[0]}/{identity[1]} there"
        )
        raise ScenarioError(msg)
    if _resolve(bundle, fact.json_path) is None:
        msg = f"{scenario_id}: {fact.fact_id} has no value at {fact.json_path}"
        raise ScenarioError(msg)


def _resolve(bundle: object, path: str) -> object | None:
    """Walk a path of the form `entry[3].resource.valueQuantity.value`.

    Enough JSON path for what a manifest cites and no more. A general
    implementation would accept expressions no authored fact uses, and the
    citations in a report have to be paths a reader can follow by eye.
    """
    current: object = bundle
    for step in path.split("."):
        name, bracket, index = step.partition("[")
        if not isinstance(current, dict):
            return None
        current = cast(Mapping[str, Any], current).get(name)
        if not bracket:
            continue
        if not isinstance(current, list):
            return None
        items = cast(Sequence[Any], current)
        position = int(index.removesuffix("]"))
        if position >= len(items):
            return None
        current = items[position]
    return current
