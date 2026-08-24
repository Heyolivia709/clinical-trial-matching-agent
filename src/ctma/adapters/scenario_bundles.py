"""The fixture adapter for Authored Synthetic Scenarios.

Specification section 4.2: patient input is a FHIR R4 Bundle *plus* an explicit
`assessment_as_of`. The Bundle alone does not say when screening happened, and a
system that inferred it from the newest resource in the file would move the
Assessment Time whenever a record gained a row. So the two arrive together, from
`fixtures/scenarios.json`.

What is not here is the Scenario Manifest. The manifests sit in a separate
directory read only by `ctma.evaluation`, which nothing may import. This module
is the whole of what the matching system may see about a scenario.
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from ctma.domain.base import Frozen

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
INDEX = FIXTURES / "scenarios.json"


class ScenarioFixtureError(ValueError):
    """A scenario fixture is missing or does not describe what it claims to."""


class ScenarioInput(Frozen):
    """One scenario as the matching system receives it.

    The serialized Bundle rather than a parsed one, because the timeline records
    the SHA-256 of the bytes it read and a re-serialized Bundle is different
    bytes.
    """

    scenario_id: str
    bundle_json: str
    assessment_as_of: dt.date


def load_scenario_inputs() -> tuple[ScenarioInput, ...]:
    """The six authored scenarios, in scenario id order."""
    payload = cast(Mapping[str, Any], json.loads(INDEX.read_text(encoding="utf-8")))
    listed = cast(list[Mapping[str, str]], payload["scenarios"])
    return tuple(_load(entry) for entry in listed)


def load_scenario_input(scenario_id: str) -> ScenarioInput:
    for scenario in load_scenario_inputs():
        if scenario.scenario_id == scenario_id:
            return scenario
    msg = f"{INDEX.name} lists no scenario {scenario_id!r}"
    raise ScenarioFixtureError(msg)


def _load(entry: Mapping[str, str]) -> ScenarioInput:
    path = FIXTURES / entry["bundle"]
    if not path.is_file():
        msg = f"{entry['scenario_id']} names a Bundle that is not there: {entry['bundle']}"
        raise ScenarioFixtureError(msg)
    return ScenarioInput(
        scenario_id=entry["scenario_id"],
        bundle_json=path.read_text(encoding="utf-8"),
        assessment_as_of=dt.date.fromisoformat(entry["assessment_as_of"]),
    )
