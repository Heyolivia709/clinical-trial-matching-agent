"""What the report is given. Frozen artifacts in, one page out.

Specification section 15 and ADR 0007. The report is generated from frozen
artifacts and is never a dependency of a reasoning module, so it cannot reach
into the Evaluation Lab for the run-independent counts — nothing may import
`ctma.evaluation`, and nothing may import this package either.

So the numbers arrive as data. Whoever builds a report computes them and hands
them over, which is also what keeps section 8 honest: a count across the
scenario set is a different kind of claim from a fact about the run above it,
and here it is literally a different input.
"""

from __future__ import annotations

from pydantic import Field

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState, UnknownReason
from ctma.domain.run import MatchingRun
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trial import TrialRecord

DISCLAIMER = (
    "Screening workflow labels only. This report does not diagnose, determine "
    "clinical eligibility, recommend treatment, or enrol patients. Recruiting status, "
    "site availability, and actual eligibility must be verified through "
    "ClinicalTrials.gov and the study team."
)


class BaselineRow(Frozen):
    """One proposition, as the agent answered it and as the baseline did.

    Both columns and no third: specification v7 cut the other two baselines.
    """

    proposition_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    agent_state: CriterionState
    agent_reason: UnknownReason | None = None
    agent_citations: tuple[str, ...] = ()
    baseline_state: CriterionState | None = None
    baseline_reason: UnknownReason | None = None
    baseline_citations: tuple[str, ...] = ()
    baseline_rejections: tuple[str, ...] = ()
    """What the offline verifier said about the baseline's citation. The
    baseline never saw this; it is what grading found."""


class FaultRow(Frozen):
    """One injected fault and the check that caught it.

    Section 3 of the specification requires the verifier catch to be
    reproducibly demonstrable rather than dependent on a model happening to make
    a mistake. So the report shows an injected fault and says it is injected.
    """

    fault_id: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    cited: str = Field(min_length=1)
    rejection: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    corrected_to: str | None = None


class InvariantRow(Frozen):
    name: str = Field(min_length=1)
    passed: bool
    detail: str = Field(min_length=1)


class CountRow(Frozen):
    """A count over a stated denominator, already rendered as one."""

    label: str = Field(min_length=1)
    agent: str = Field(min_length=1)
    baseline: str | None = None
    note: str | None = None


class ResultsSection(Frozen):
    """The run-independent part, and the sentence that says it is not about this run."""

    sample_sentence: str = Field(min_length=1)
    invariants: tuple[InvariantRow, ...] = ()
    counts: tuple[CountRow, ...] = ()
    worked_failures: tuple[str, ...] = ()


class ReportInputs(Frozen):
    """One run, everything it cited, and the counts that sit beside it."""

    run: MatchingRun
    timeline: PatientTimeline
    trials: tuple[TrialRecord, ...] = Field(min_length=1)
    demonstrative_criterion_id: str = Field(min_length=1)
    plain_language: str = Field(min_length=1)
    """One sentence on what the system does, for a reader with no vocabulary."""

    baseline: tuple[BaselineRow, ...] = ()
    faults: tuple[FaultRow, ...] = ()
    results: ResultsSection | None = None

    def trial_for(self, nct_id: str) -> TrialRecord | None:
        return next((item for item in self.trials if item.nct_id == nct_id), None)
