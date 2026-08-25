"""The Candidate Set and the Matching Run: one reproducible comparison.

Specification sections 9, 11, 13, 14 and 16. A Matching Run is the unit that can
be written to disk, read back, re-graded offline, and replayed, so everything
needed to reproduce it is a field rather than an ambient fact about the machine
that produced it. A run that records its answers but not the versions behind
them is a result nobody can check, including its author six weeks later.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from ctma.domain.assessment import TrialAssessment
from ctma.domain.base import Frozen
from ctma.domain.enums import CandidateStatus, Partition
from ctma.domain.trace import InfrastructureFailure, Measurements, ReasoningTrace


class CandidateTrial(Frozen):
    """One trial in the candidate set, with its immutable rank.

    Candidate status says nothing about clinical eligibility, and
    `retrieval_rank` is never recomputed from anything a later criterion
    assessment concluded. Keeping the rank here and the Review Priority
    elsewhere is what stops the two from being quietly merged into one number
    that means neither.
    """

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    snapshot_record_id: str = Field(min_length=1)
    retrieval_rank: int = Field(ge=1)
    status: CandidateStatus


class CandidateSet(Frozen):
    """The immutable ordered collection of candidates for one run.

    The tuple order is the ranking, and the ranks are dense and start at one, so
    a candidate cannot be dropped from the middle without the set failing to
    validate. Section 9's cardinalities are the Matching Policy's and are not
    repeated here; what this type holds is the structure they are applied to.
    """

    candidates: tuple[CandidateTrial, ...] = Field(min_length=1)

    @property
    def presented(self) -> tuple[CandidateTrial, ...]:
        """Everything the reader is shown, assessed or not."""
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.status is not CandidateStatus.RETAINED
        )

    @property
    def assessed(self) -> tuple[CandidateTrial, ...]:
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.status is CandidateStatus.ASSESSED
        )

    @model_validator(mode="after")
    def _trials_appear_once(self) -> Self:
        ids = [candidate.nct_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            msg = "a trial appears twice in one Candidate Set"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _the_tuple_order_is_the_ranking(self) -> Self:
        ranks = tuple(candidate.retrieval_rank for candidate in self.candidates)
        expected = tuple(range(1, len(self.candidates) + 1))
        if ranks != expected:
            msg = f"retrieval ranks must be {expected} in order, got {ranks}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _presentation_follows_the_ranking(self) -> Self:
        """The presented candidates are the top of the ranking, not a selection.

        Section 9 presents the top five. A presented candidate ranked below a
        retained one would mean presentation was decided by something other than
        the rank — which is exactly the blended ordering the report is forbidden
        to show, arrived at by accident.
        """
        seen_retained = False
        for candidate in self.candidates:
            if candidate.status is CandidateStatus.RETAINED:
                seen_retained = True
            elif seen_retained:
                msg = (
                    f"{candidate.nct_id} is presented at rank {candidate.retrieval_rank} "
                    "below a retained candidate"
                )
                raise ValueError(msg)
        return self


class ModelAdapter(StrEnum):
    """The three inference adapters of specification sections 12 and 16.

    `FROZEN_REPLAY` is what makes a published run re-runnable without the model
    that produced it, and the adapter interface rather than the model choice is
    the engineering claim.
    """

    HOSTED = "hosted"
    LOCAL = "local"
    FROZEN_REPLAY = "frozen_replay"


class ModelConfiguration(Frozen):
    """Exact model, revision, decoding, and the prompt and schema versions.

    Section 16 freezes all of these before the held-out scenarios are assessed.
    Recording them per run is what lets the comparison state that the two variants
    differed in architecture and in nothing else.
    """

    adapter: ModelAdapter
    model_id: str = Field(min_length=1)
    revision: str = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0)
    """`None` means decoding was not pinned, which is not the same as pinning it
    to zero. Some endpoints reject the parameter outright, and a run recording
    `0.0` for a request that never carried it would be describing a determinism
    it does not have."""

    top_p: float | None = Field(default=None, gt=0, le=1)
    max_output_tokens: int = Field(ge=1)
    prompt_version: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)


class SupervisorConfiguration(Frozen):
    """The two flags of specification section 11, both default off.

    Off for correctness measurement and on for cost measurement, so multi-turn
    behaviour appears as its own reported row rather than as a confound inside a
    single number.
    """

    order_criteria: bool = False
    early_termination: bool = False


class RunConfiguration(Frozen):
    """Everything frozen for the run, version by version.

    `evaluator_version` is here for the same reason the model revision is: a
    grading change between two runs is indistinguishable from a behaviour change
    unless both are recorded.
    """

    tool_version: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)
    hardware_profile: str = Field(min_length=1)
    seed: int
    model: ModelConfiguration
    supervisor: SupervisorConfiguration = SupervisorConfiguration()


class RunIdentities(Frozen):
    """What was compared, when, and which partition it came from.

    The hashes are the point: a run cites the exact Bundle and snapshot payloads
    it read, so a later run over edited inputs is visibly a different run rather
    than a contradiction of this one.
    """

    scenario_id: str = Field(min_length=1)
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1)
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assessment_as_of: dt.date
    partition: Partition


class RunWarning(Frozen):
    """Something worth telling the reader that did not stop the run.

    A Stale Snapshot is the standing example: staleness warns, and never mutates
    or invalidates a historical Matching Run. Warnings are therefore recorded
    beside the results rather than raised over them, and the report shows them in
    the reproducibility header.
    """

    code: str = Field(min_length=1)
    detail: str = Field(min_length=1)


class MatchingRun(Frozen):
    """One patient, one snapshot, one Assessment Time, under frozen configuration.

    `trial_assessments` are held in Review Priority order — Match Conclusion
    first, then Retrieval Rank — while each assessment keeps the rank the candidate
    order gave it. The ordering and the rank are both recoverable and neither is
    derived from the other, which is what section 15 requires of the two.

    Infrastructure Failures are recorded here, in their own field, and never as
    a Criterion State. That separation is a release gate, and this is where it is
    visible: a failed run has failures and possibly fewer assessments, not more
    `unknown`s.
    """

    run_id: str = Field(min_length=1)
    identities: RunIdentities
    configuration: RunConfiguration
    candidates: CandidateSet
    trial_assessments: tuple[TrialAssessment, ...] = ()
    trace: ReasoningTrace = ReasoningTrace()
    warnings: tuple[RunWarning, ...] = ()
    failures: tuple[InfrastructureFailure, ...] = ()
    measurements: Measurements = Measurements()
    """Run-level totals, including wall-clock latency, which is elapsed time and
    not the sum of the per-assessment measurements."""

    @model_validator(mode="after")
    def _every_assessment_belongs_to_a_presented_candidate(self) -> Self:
        """A trial nobody was shown cannot arrive with an assessment attached.

        The assessed set is a subset of what was presented, and this is where
        that holds even if the policy that chose it is wrong: an assessment
        whose candidate was merely retained, or absent from the set, or ranked
        differently there, fails to validate rather than reaching a report.
        """
        by_id = {candidate.nct_id: candidate for candidate in self.candidates.candidates}
        seen: set[str] = set()
        for assessment in self.trial_assessments:
            if assessment.nct_id in seen:
                msg = f"two assessments for {assessment.nct_id}"
                raise ValueError(msg)
            seen.add(assessment.nct_id)
            candidate = by_id.get(assessment.nct_id)
            if candidate is None:
                msg = f"{assessment.nct_id} was assessed but is not in the Candidate Set"
                raise ValueError(msg)
            if candidate.status is CandidateStatus.RETAINED:
                msg = f"{assessment.nct_id} was assessed but never presented"
                raise ValueError(msg)
            if candidate.retrieval_rank != assessment.retrieval_rank:
                msg = (
                    f"{assessment.nct_id} is ranked {candidate.retrieval_rank} in the "
                    f"Candidate Set and {assessment.retrieval_rank} in its assessment"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _every_assessed_candidate_has_its_assessment(self) -> Self:
        """The other direction: a candidate marked assessed must carry the result.

        Otherwise a run can report three assessed candidates and publish two,
        which is a criterion set silently dropped from output at trial scale.
        """
        assessed = {assessment.nct_id for assessment in self.trial_assessments}
        missing = [
            candidate.nct_id
            for candidate in self.candidates.assessed
            if candidate.nct_id not in assessed
        ]
        if missing:
            msg = f"candidates marked assessed with no Trial Assessment: {sorted(missing)}"
            raise ValueError(msg)
        return self
