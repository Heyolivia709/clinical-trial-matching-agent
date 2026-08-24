"""Scenario Manifests: hidden ground truth for authored synthetic patients.

Specification sections 4.4, 8.3 and 17, and ADR 0005. The manifest records what
was authored into a scenario so the Evaluation Lab can *derive* expected states
by code. It never contains an expected state itself, and the matching system
never receives it.

This module lives in `ctma.evaluation` rather than in `ctma.domain` on purpose.
`tests/test_architecture.py` forbids every other package from importing
`ctma.evaluation`, so the manifest is unreachable from the matching system by
construction. Moving these types into `domain` would make them importable from
the agent and turn a structural guarantee back into a matter of discipline.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import TemporalPrecision, UnknownReason
from ctma.domain.expression import AuthoringProvenance


class DistractorKind(StrEnum):
    """The seven planted hazards of specification section 8.3.

    Difficulty comes from these rather than from clinical subtlety, which is the
    honest consequence of deriving gold labels from authored facts.
    """

    ERROR_STATUS_RESULT = "error_status_result"
    ORDER_WITHOUT_ADMINISTRATION = "order_without_administration"
    POST_ASSESSMENT_OBSERVATION = "post_assessment_observation"
    CONFLICTING_RESULTS = "conflicting_results"
    INSUFFICIENT_DATE_PRECISION = "insufficient_date_precision"
    PRELIMINARY_RESULT = "preliminary_result"
    NEAR_MISS_CONCEPT = "near_miss_concept"


EXPECTED_REASON_BY_DISTRACTOR: dict[DistractorKind, UnknownReason] = {
    DistractorKind.ERROR_STATUS_RESULT: UnknownReason.UNUSABLE_STATUS,
    DistractorKind.ORDER_WITHOUT_ADMINISTRATION: UnknownReason.UNSUPPORTED_EVIDENCE_TYPE,
    DistractorKind.POST_ASSESSMENT_OBSERVATION: UnknownReason.MISSING_EVIDENCE,
    DistractorKind.CONFLICTING_RESULTS: UnknownReason.CONFLICTING_EVIDENCE,
    DistractorKind.INSUFFICIENT_DATE_PRECISION: UnknownReason.INSUFFICIENT_PRECISION,
    DistractorKind.PRELIMINARY_RESULT: UnknownReason.UNUSABLE_STATUS,
    DistractorKind.NEAR_MISS_CONCEPT: UnknownReason.MISSING_EVIDENCE,
}
"""Specification section 8.3, as data rather than as prose.

Two hazards may share a reason where they share a nature, but a hazard
resolving to any *other* reason is a defect in the timeline or in the
assignment table. Gate 2 asserts this mapping per hazard.
"""


class AuthoredFact(Frozen):
    """One fact deliberately placed in a scenario, with what makes it usable.

    `usable_as_evidence` is authored rather than inferred: it is what the
    scenario designer intended, and gold derivation compares the system's
    behaviour against the intent.
    """

    fact_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    value: str | None = None
    status: str = Field(min_length=1)
    clinical_time: dt.date | None = None
    precision: TemporalPrecision | None = None
    usable_as_evidence: bool

    @model_validator(mode="after")
    def _dated_facts_declare_their_precision(self) -> Self:
        if (self.clinical_time is None) != (self.precision is None):
            msg = "clinical_time and precision are declared together or not at all"
            raise ValueError(msg)
        return self


class PlantedDistractor(Frozen):
    """A hazard, the facts that carry it, and the reason it should produce."""

    distractor_id: str = Field(min_length=1)
    kind: DistractorKind
    fact_ids: tuple[str, ...] = Field(min_length=1)
    intent: str = Field(min_length=1)

    @property
    def expected_reason(self) -> UnknownReason:
        return EXPECTED_REASON_BY_DISTRACTOR[self.kind]


class ScenarioManifest(Frozen):
    """Evaluator-only ground truth for one Authored Synthetic Scenario.

    Deliberately absent: any expected Criterion State. Expected states are
    computed by code from these facts and the authored expression, because a
    manifest that carried answers would let a labelling judgement in through
    the back door, which ADR 0005 exists to prevent.
    """

    scenario_id: str = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment_as_of: dt.date
    facts: tuple[AuthoredFact, ...] = Field(min_length=1)
    distractors: tuple[PlantedDistractor, ...] = ()
    provenance: AuthoringProvenance

    @model_validator(mode="after")
    def _fact_ids_are_unique(self) -> Self:
        seen: set[str] = set()
        for fact in self.facts:
            if fact.fact_id in seen:
                msg = f"duplicate fact_id {fact.fact_id!r}"
                raise ValueError(msg)
            seen.add(fact.fact_id)
        return self

    @model_validator(mode="after")
    def _distractors_point_at_real_facts(self) -> Self:
        known = {fact.fact_id for fact in self.facts}
        for distractor in self.distractors:
            if dangling := set(distractor.fact_ids) - known:
                msg = f"{distractor.distractor_id} references unknown facts: {sorted(dangling)}"
                raise ValueError(msg)
        return self

    def distractor_kinds(self) -> frozenset[DistractorKind]:
        return frozenset(distractor.kind for distractor in self.distractors)


def missing_distractor_kinds(
    manifests: tuple[ScenarioManifest, ...],
) -> frozenset[DistractorKind]:
    """Which hazards the scenario set does not yet cover, collectively.

    Specification section 4.4 makes coverage an obligation on the scenario set
    as a whole rather than on any one scenario, so this is the check Gate 2
    runs across all six.
    """
    covered = frozenset[DistractorKind]().union(*(m.distractor_kinds() for m in manifests))
    return frozenset(DistractorKind) - covered
