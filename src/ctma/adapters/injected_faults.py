"""The frozen injected-fault fixtures.

Specification section 3, requirement 7: the verifier catching a fabricated or
incorrect citation must be reproducibly demonstrable. A model happening to make
a particular mistake is not an acceptance criterion, so the faults are authored:
one correct assessment, and one deliberately corrupted copy per rejection class
of section 8.1.

The expected rejection is part of the fixture rather than of the test. The catch
rate over these faults is a release gate and is published, so what each fault
was injected to prove has to travel with it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState
from ctma.domain.expression import AuthoringProvenance
from ctma.domain.proposal import ProposedAssessment
from ctma.domain.trace import VerifierRejection

FAULTS = Path(__file__).resolve().parents[3] / "fixtures" / "faults.json"


class CitationFault(Frozen):
    """One Proposed Assessment, and the check it was authored to trip.

    `expected_rejection` is None for the correct assessment in the set. It is
    there deliberately: a fixture set of nothing but faults cannot tell a
    working verifier from one that rejects everything.
    """

    fault_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    expected_rejection: VerifierRejection | None = None
    intent: str = Field(min_length=1)
    proposal: ProposedAssessment


class AggregationFault(Frozen):
    """A claimed Criterion State, and the proposition states behind it."""

    fault_id: str = Field(min_length=1)
    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    criterion_id: str = Field(min_length=1)
    proposition_states: Mapping[str, CriterionState]
    claimed_state: CriterionState
    expected_rejection: VerifierRejection | None = None
    intent: str = Field(min_length=1)


class InjectedFaults(Frozen):
    provenance: AuthoringProvenance
    citations: tuple[CitationFault, ...] = Field(min_length=1)
    aggregations: tuple[AggregationFault, ...] = Field(min_length=1)


def load_injected_faults() -> InjectedFaults:
    payload = cast(dict[str, Any], json.loads(FAULTS.read_text(encoding="utf-8")))
    return InjectedFaults.model_validate(payload)
