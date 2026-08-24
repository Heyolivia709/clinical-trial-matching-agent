"""Proposition, Criterion, and Trial Assessments.

Specification sections 8 and 13. Two invariants live in this module, and both
are held by the shape of the types rather than by a test that hopes to catch
them:

- A `met` or `not_met` assessment always cites patient evidence, and an
  `unknown` always carries a reason. So the states are separate classes. There
  is no constructor for a `met` without evidence and no attribute to read a
  reason from where none exists, which means the mistake cannot be written down
  and does not need to be looked for in review.
- `not_assessed` is a reporting status and never a Criterion State. A skipped
  criterion is therefore a class with no `state` attribute at all. One optional
  `CriterionState` field on a single record type is the whole distance between
  "the supervisor stopped early" and "the evidence was inadequate", and a
  coordinator reading the second when the first is true goes looking for a
  patient record that would not have helped.

The cost is that callers match on a union instead of reading a field. That is
the intended cost: a match statement on four states has to name all four, while
a nullable field has a default reading, and the default reading of a missing
state is the one this project must never publish.
"""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ctma.domain.aggregation import Aggregation
from ctma.domain.base import Frozen
from ctma.domain.enums import (
    CriterionCategory,
    CriterionImpact,
    CriterionPolarity,
    CriterionState,
    EvidenceRelation,
    MatchConclusion,
    ReportingStatus,
    UnknownReason,
)
from ctma.domain.evidence import PatientEvidence, TrialEvidence
from ctma.domain.impact import ImpactCounts, impact_of
from ctma.domain.trace import Measurements, ToolCall, VerifierOutcome, VerifierVerdict


class _PropositionRecord(Frozen):
    """What every Proposition Assessment carries, whatever its state.

    `verification` holds at most two entries because section 8.1 allows exactly
    one targeted correction: an accepted first pass, or a rejection followed by
    one more attempt. A third entry would be a retry loop, and there are no
    hidden model retries in evaluation.
    """

    proposition_id: str = Field(min_length=1)
    category: CriterionCategory
    trial_evidence: TrialEvidence
    tool_calls: tuple[ToolCall, ...] = ()
    verification: tuple[VerifierOutcome, ...] = Field(default=(), max_length=2)
    rationale: str | None = None
    """Explanatory only. It never counts as evidence, which is why it sits
    beside the citations rather than among them."""
    measurements: Measurements = Measurements()

    @model_validator(mode="after")
    def _a_correction_follows_a_rejection(self) -> Self:
        """A second attempt exists only because the first was rejected.

        Two accepted passes over one proposition would mean the loop ran twice
        for no recorded reason, and the correction rate published beside
        citation validity would count it.
        """
        if len(self.verification) == 2 and self.verification[0].verdict is not (
            VerifierVerdict.REJECTED
        ):
            msg = "a correction is recorded only after a rejected verification"
            raise ValueError(msg)
        return self

    @property
    def last_verdict(self) -> VerifierVerdict | None:
        """The verdict the assessment was left with, or None if unverified.

        Unverified is a real configuration: the no-verifier ablation runs the
        loop without one, and its assessments are graded offline like any other.
        """
        return self.verification[-1].verdict if self.verification else None


class _EvidencedProposition(_PropositionRecord):
    """The three states that cite patient evidence, and cannot exist without it.

    `met` and `not_met` are required to cite it by section 8. `not_applicable`
    is too, and for the same reason: it claims a conditional antecedent is
    false, which is a finding about the patient and not the absence of one.
    """

    patient_evidence: tuple[PatientEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _a_rejected_citation_cannot_carry_a_confident_state(self) -> Self:
        """After a second rejection the state is `unknown`, not the claim itself.

        Leaving a `met` standing on a citation the verifier threw out is the
        exact failure the verifier exists to prevent, and it would be scored as
        a correct answer with a valid-looking citation attached.
        """
        if self.last_verdict is VerifierVerdict.REJECTED:
            msg = (
                "an assessment resting on a rejected citation is 'unknown' with "
                "verification_failed, not a state with evidence"
            )
            raise ValueError(msg)
        return self


class MetAssessment(_EvidencedProposition):
    """The patient evidence supports the proposition.

    On an exclusion criterion this is bad news for the patient's chances, which
    is Criterion Impact's job to say and not this state's.
    """

    state: Literal[CriterionState.MET] = CriterionState.MET

    @model_validator(mode="after")
    def _something_cited_supports_it(self) -> Self:
        if not any(
            evidence.relation is EvidenceRelation.SUPPORTS for evidence in self.patient_evidence
        ):
            msg = "'met' cites at least one fact whose relation is 'supports'"
            raise ValueError(msg)
        return self


class NotMetAssessment(_EvidencedProposition):
    """The patient evidence contradicts the proposition.

    Not a synonym for missing evidence. The contradicting citation is what makes
    the difference readable, so at least one is required.
    """

    state: Literal[CriterionState.NOT_MET] = CriterionState.NOT_MET

    @model_validator(mode="after")
    def _something_cited_contradicts_it(self) -> Self:
        if not any(
            evidence.relation is EvidenceRelation.CONTRADICTS for evidence in self.patient_evidence
        ):
            msg = "'not_met' cites at least one fact whose relation is 'contradicts'"
            raise ValueError(msg)
        return self


class NotApplicableAssessment(_EvidencedProposition):
    """A conditional antecedent is false, so this proposition does not apply."""

    state: Literal[CriterionState.NOT_APPLICABLE] = CriterionState.NOT_APPLICABLE


class UnknownAssessment(_PropositionRecord):
    """The proposition could not be determined, and says which diagnosis applies.

    Patient evidence is optional and often present: `conflicting_evidence` cites
    the facts that disagree, `unusable_status` cites the disqualified result.
    `missing_evidence` cites nothing, because there was nothing to cite, and a
    type that demanded a citation here would push a caller into inventing one.
    """

    state: Literal[CriterionState.UNKNOWN] = CriterionState.UNKNOWN
    reason: UnknownReason
    patient_evidence: tuple[PatientEvidence, ...] = ()

    @model_validator(mode="after")
    def _the_reason_belongs_to_a_proposition(self) -> Self:
        """`expression_unavailable` is a criterion-level reason and cannot land here.

        Stage 1 of section 8.0 assigns it to a trial whose criteria have no
        authored expression. Without an expression there are no Atomic
        Propositions, so a proposition claiming this reason is describing a
        proposition that could not have been created.
        """
        if self.reason is UnknownReason.EXPRESSION_UNAVAILABLE:
            msg = "expression_unavailable belongs to a criterion, which has no propositions"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _verification_failed_names_two_rejections(self) -> Self:
        """Section 8.1: the reason is the *second* failure, not the first.

        One rejection is followed by a correction, and the corrected assessment
        usually stands. Recording this reason after a single rejection would
        report a caught-and-fixed citation as an unresolved criterion, and the
        verification-induced `unknown` rate is published, so the inflation would
        be published with it.
        """
        if self.reason is not UnknownReason.VERIFICATION_FAILED:
            return self
        rejected = tuple(
            outcome for outcome in self.verification if outcome.verdict is VerifierVerdict.REJECTED
        )
        if len(rejected) != 2:
            msg = "verification_failed records the two rejected verifications behind it"
            raise ValueError(msg)
        return self


PropositionAssessment = Annotated[
    MetAssessment | NotMetAssessment | NotApplicableAssessment | UnknownAssessment,
    Field(discriminator="state"),
]
"""One judgment on one Atomic Proposition, in the four states of section 7."""


class AssessedCriterion(Frozen):
    """A criterion whose propositions were assessed and deterministically aggregated.

    The state is the aggregation's, and the impact follows from the state and the
    polarity. Neither is stored: a stored tally can disagree with the
    propositions it claims to summarize, and the disagreement would be invisible
    in a frozen artifact that is re-read months later. The aggregation trace is
    stored, because the verifier rejects incorrect aggregation and needs
    something to check.
    """

    kind: Literal["assessed"] = "assessed"
    criterion_id: str = Field(min_length=1)
    polarity: CriterionPolarity
    propositions: tuple[PropositionAssessment, ...] = Field(min_length=1)
    aggregation: Aggregation

    @property
    def state(self) -> CriterionState:
        return self.aggregation.state

    @property
    def impact(self) -> CriterionImpact:
        return impact_of(self.state, self.polarity)

    @property
    def unknown_reason(self) -> UnknownReason | None:
        """The reason carried by the proposition that decided an `unknown`.

        A criterion has no diagnosis of its own. Its `unknown` came from one of
        its propositions, and reporting anything but that proposition's reason
        would put a second, unsourced diagnosis into the failure taxonomy.
        """
        if self.state is not CriterionState.UNKNOWN:
            return None
        return self._deciding_unknown_reason()

    @model_validator(mode="after")
    def _proposition_ids_are_unique(self) -> Self:
        seen: set[str] = set()
        for assessment in self.propositions:
            if assessment.proposition_id in seen:
                msg = f"duplicate proposition_id {assessment.proposition_id!r}"
                raise ValueError(msg)
            seen.add(assessment.proposition_id)
        return self

    @model_validator(mode="after")
    def _the_aggregation_decided_over_these_propositions(self) -> Self:
        """Every id in the trace resolves to an assessment present here.

        A trace naming a proposition this criterion does not carry is either a
        trace from another criterion or an assessment that went missing on the
        way here. Either way the reported state cannot be explained by the record
        reporting it, which is what a silently dropped assessment looks like.
        """
        present = {assessment.proposition_id for assessment in self.propositions}
        cited = {
            proposition_id for step in self.aggregation.trace for proposition_id in step.decided_by
        }
        if dangling := cited - present:
            msg = f"the aggregation cites absent propositions: {sorted(dangling)}"
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _an_unknown_criterion_has_an_unknown_proposition_to_blame(self) -> Self:
        if self.state is CriterionState.UNKNOWN and self._deciding_unknown_reason() is None:
            msg = (
                "an 'unknown' criterion is decided by an 'unknown' proposition, "
                "which is what carries the reason"
            )
            raise ValueError(msg)
        return self

    def _deciding_unknown_reason(self) -> UnknownReason | None:
        by_id = {assessment.proposition_id: assessment for assessment in self.propositions}
        for proposition_id in self.aggregation.decided_by:
            deciding = by_id.get(proposition_id)
            if isinstance(deciding, UnknownAssessment):
                return deciding.reason
        return None


class UnexpressedCriterion(Frozen):
    """A criterion nobody authored an expression for. Stage 1 of section 8.0.

    It is quoted and reported as `unknown` with `expression_unavailable`, and it
    has no propositions because there is no expression to hold any. Reporting it
    as `not_assessed` instead would claim a decision was made to skip it; the
    truth is that the authoring budget did not reach this trial, which is a
    property of the project and not of the patient. It still counts toward
    Criterion Coverage, so the gap stays visible.
    """

    kind: Literal["expression_unavailable"] = "expression_unavailable"
    criterion_id: str = Field(min_length=1)
    polarity: CriterionPolarity
    trial_evidence: TrialEvidence

    @property
    def state(self) -> CriterionState:
        return CriterionState.UNKNOWN

    @property
    def impact(self) -> CriterionImpact:
        return impact_of(self.state, self.polarity)

    @property
    def unknown_reason(self) -> UnknownReason:
        return UnknownReason.EXPRESSION_UNAVAILABLE


class SkippedCriterion(Frozen):
    """A criterion the Trial Supervisor deliberately did not assess.

    This class has no `state`, no `impact`, and no Unknown Reason, and that
    absence is the invariant rather than an omission. `not_assessed` is a
    reporting status: nobody looked, so there is no evidence to describe. A
    coordinator told "unresolved" goes to the patient record for an answer that
    was never sought there, and the accuracy metrics would score a budget
    decision as a model's uncertainty.
    """

    kind: Literal["not_assessed"] = "not_assessed"
    criterion_id: str = Field(min_length=1)
    polarity: CriterionPolarity
    trial_evidence: TrialEvidence
    blocker_criterion_id: str | None = None
    """The criterion whose confirmed blocker stopped the trial early, when
    `early_termination` is what skipped this one."""


CriterionAssessment = Annotated[
    AssessedCriterion | UnexpressedCriterion | SkippedCriterion,
    Field(discriminator="kind"),
]
"""One Eligibility Criterion's outcome: aggregated, unexpressed, or skipped.

The three tags are record kinds and not `ReportingStatus`. Two of them happen to
name what that enum names; the third, a criterion with no authored expression,
is neither assessed nor deliberately skipped, and folding it into either would
misreport an authoring gap as one of the two."""


def reporting_status_of(criterion: CriterionAssessment) -> ReportingStatus:
    """Whether a criterion was attempted at all, for Criterion Coverage.

    An unexpressed criterion counts as attempted: it is reported with a state
    and a reason, and the gap it stands for is in the authoring budget rather
    than in the run. Only Early Termination produces `not_assessed`, which is
    why coverage falls when that flag is on and not when authoring is short.
    """
    if isinstance(criterion, SkippedCriterion):
        return ReportingStatus.NOT_ASSESSED
    return ReportingStatus.ASSESSED


class TrialAssessment(Frozen):
    """Every criterion of one assessed Candidate Trial, and what they add up to.

    The counts and the Match Conclusion are derived here rather than stored, for
    the reason `AssessedCriterion` does not store its state: a frozen artifact
    holding both a tally and the criteria behind it can hold two different
    answers, and the report would show whichever it read first.

    Review Priority is deliberately absent. It is a position among trials rather
    than a property of one, so section 9's policy computes it and a Matching Run
    keeps its assessments in that order. Each assessment keeps its immutable
    Retrieval Rank, so both orderings are present and neither overwrites the
    other.

    The Evidence Trajectory is likewise derived from these records rather than
    stored beside them, which is also what keeps it unable to contain Scenario
    Manifest content or hidden reasoning: it has none to draw on.
    """

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    snapshot_record_id: str = Field(min_length=1)
    retrieval_rank: int = Field(ge=1)
    criteria: tuple[CriterionAssessment, ...] = Field(min_length=1)
    measurements: Measurements = Measurements()

    @property
    def counts(self) -> ImpactCounts:
        impacts: list[CriterionImpact] = []
        not_assessed = 0
        for criterion in self.criteria:
            if isinstance(criterion, SkippedCriterion):
                not_assessed += 1
            else:
                impacts.append(criterion.impact)
        return ImpactCounts.tally(impacts, not_assessed=not_assessed)

    @property
    def conclusion(self) -> MatchConclusion:
        return self.counts.conclusion

    @model_validator(mode="after")
    def _criterion_ids_are_unique(self) -> Self:
        """Two records for one criterion means one of them is not reported.

        Criterion Coverage is counted from these records, so a duplicate inflates
        it while hiding whichever record the report did not show.
        """
        seen: set[str] = set()
        for criterion in self.criteria:
            if criterion.criterion_id in seen:
                msg = f"duplicate criterion_id {criterion.criterion_id!r}"
                raise ValueError(msg)
            seen.add(criterion.criterion_id)
        return self
