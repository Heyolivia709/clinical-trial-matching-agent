"""Eval Cases: one scenario against one trial, with its expected answers.

Specification section 13. A case is immutable and names the exact inputs it was
derived from — the Bundle hash and the eligibility hash — so a case built
against edited inputs is visibly a different case rather than a contradiction of
the first.

**The partition is the stricter of the two.** A development scenario against a
held-out trial is held out, because the trial is. Held-out artifacts are
assessed once, at the end, and reading a held-out record while tuning is what
that rule exists to prevent — whichever axis it came in on.

There is no default partition on `eval_cases`. Asking for the held-out set has
to be a thing someone wrote down.
"""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.base import Frozen
from ctma.domain.enums import Partition
from ctma.domain.trial import TrialRecord
from ctma.evaluation.gold import ExpectedCriterion, expected_criterion
from ctma.evaluation.manifest import ScenarioManifest
from ctma.evaluation.scenarios import load_scenario_manifests


class EvalCase(Frozen):
    """One scenario-trial pair, and what every criterion should come out as."""

    case_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    partition: Partition
    scenario_partition: Partition
    trial_partition: Partition
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    eligibility_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment_as_of: dt.date
    criteria: tuple[ExpectedCriterion, ...] = Field(min_length=1)

    @property
    def scorable(self) -> tuple[ExpectedCriterion, ...]:
        return tuple(criterion for criterion in self.criteria if criterion.scorable)

    @property
    def coverage_only(self) -> tuple[ExpectedCriterion, ...]:
        """Visible, and excluded from accuracy counts."""
        return tuple(criterion for criterion in self.criteria if not criterion.scorable)


def eval_cases(partition: Partition) -> tuple[EvalCase, ...]:
    """Every scenario-trial pair in one half of the split, in a fixed order."""
    manifests = load_scenario_manifests()
    trials = load_trial_fixtures()
    cases = tuple(
        _case(manifest, trial)
        for manifest in manifests
        for trial in trials
        if _partition_of(manifest.partition, trial.partition) is partition
    )
    return cases


def _case(manifest: ScenarioManifest, trial: TrialRecord) -> EvalCase:
    return EvalCase(
        case_id=f"{manifest.scenario_id}|{trial.nct_id}",
        scenario_id=manifest.scenario_id,
        nct_id=trial.nct_id,
        partition=_partition_of(manifest.partition, trial.partition),
        scenario_partition=manifest.partition,
        trial_partition=trial.partition,
        bundle_sha256=manifest.bundle_sha256,
        eligibility_sha256=trial.eligibility_sha256,
        assessment_as_of=manifest.assessment_as_of,
        criteria=tuple(
            expected_criterion(criterion, manifest=manifest) for criterion in trial.criteria
        ),
    )


def _partition_of(scenario: Partition, trial: Partition) -> Partition:
    if scenario is Partition.HELD_OUT or trial is Partition.HELD_OUT:
        return Partition.HELD_OUT
    return Partition.DEVELOPMENT
