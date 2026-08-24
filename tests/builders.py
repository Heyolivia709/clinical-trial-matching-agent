"""Shared authored artifacts, so tests read as data rather than as setup."""

from __future__ import annotations

import datetime as dt

from ctma.domain.aggregation import aggregate
from ctma.domain.assessment import (
    AssessedCriterion,
    CriterionAssessment,
    MetAssessment,
    NotMetAssessment,
    PropositionAssessment,
    TrialAssessment,
    UnknownAssessment,
)
from ctma.domain.enums import (
    CandidateStatus,
    CriterionCategory,
    CriterionPolarity,
    EvidenceRelation,
    Partition,
    RetrievalChannel,
    ReviewStatus,
    TemporalPrecision,
    UnknownReason,
)
from ctma.domain.evidence import PatientEvidence, PatientFactReference, TrialEvidence
from ctma.domain.expression import (
    AllOf,
    AnchorSubstitution,
    AtomicProposition,
    AuthoringProvenance,
    EligibilityCriterion,
    PropositionRef,
    TemporalWindow,
)
from ctma.domain.run import (
    CandidateSet,
    CandidateTrial,
    ChannelRank,
    MatchingRun,
    ModelAdapter,
    ModelConfiguration,
    RunConfiguration,
    RunIdentities,
    SupervisorConfiguration,
)
from ctma.domain.trace import Measurements
from ctma.policy import RetrievedTrial

REVIEWED = AuthoringProvenance(
    drafted_by="assistant",
    ai_assisted=True,
    reviewed_by="rendong",
    reviewed_on=dt.date(2026, 8, 23),
    review_status=ReviewStatus.REVIEWED,
)

# EXC-7 from the interface design: the criterion the whole demonstration turns on.
EXC7_TEXT = (
    "Prior treatment with any EGFR tyrosine kinase inhibitor within 14 days "
    "prior to the first dose of study drug."
)


def exc7() -> EligibilityCriterion:
    return EligibilityCriterion(
        criterion_id="NCT05123456:EXC-7",
        polarity=CriterionPolarity.EXCLUSION,
        source_section="exclusionCriteria",
        ordinal=7,
        span_start=1842,
        span_end=1842 + len(EXC7_TEXT),
        source_text=EXC7_TEXT,
        expression_version="v3",
        propositions=(
            AtomicProposition(
                proposition_id="P1",
                statement="Documented exposure to an EGFR tyrosine kinase inhibitor",
                category=CriterionCategory.PRIOR_THERAPY,
                concept="EGFR_TKI",
            ),
            AtomicProposition(
                proposition_id="P2",
                statement="Exposure ends within 14 days of the anchor",
                category=CriterionCategory.PRIOR_THERAPY,
                concept="EGFR_TKI",
                window=TemporalWindow(
                    duration=dt.timedelta(days=14),
                    anchor_substitution=AnchorSubstitution(
                        source_anchor_text="the first dose of study drug",
                        rationale=(
                            "The anchor event has not occurred at screening. "
                            "Assessment time is the screening-time proxy."
                        ),
                    ),
                ),
            ),
        ),
        expression=AllOf(
            children=(PropositionRef(proposition_id="P1"), PropositionRef(proposition_id="P2"))
        ),
        provenance=REVIEWED,
    )


NCT = "NCT05123456"
SNAPSHOT_ID = "ctgov-2026-08-01"
SPAN_START = 1842


def exc7_trial_evidence() -> TrialEvidence:
    """The verbatim span the propositions of EXC-7 are assessed against."""
    return TrialEvidence(
        snapshot_id=SNAPSHOT_ID,
        nct_id=NCT,
        source_section="exclusionCriteria",
        criterion_ordinal=7,
        span_start=SPAN_START,
        span_end=SPAN_START + len(EXC7_TEXT),
        source_text=EXC7_TEXT,
    )


def osimertinib_administration() -> PatientFactReference:
    """A documented exposure whose date is precise to the year and no further.

    The distractor the whole demonstration turns on: the exposure is real, and
    the 14-day window cannot be evaluated against a year.
    """
    return PatientFactReference(
        resource_type="MedicationAdministration",
        resource_id="medadmin-4",
        json_path="entry[12].resource.effectiveDateTime",
        clinical_time=dt.date(2024, 1, 1),
        precision=TemporalPrecision.YEAR,
        status="completed",
        code="RxNorm:1721581",
        value="osimertinib 80 mg oral tablet",
        display="Osimertinib administration, 2024",
    )


def exposure_evidence(
    relation: EvidenceRelation = EvidenceRelation.SUPPORTS,
) -> PatientEvidence:
    return PatientEvidence(facts=(osimertinib_administration(),), relation=relation)


def met(proposition_id: str = "P1") -> MetAssessment:
    return MetAssessment(
        proposition_id=proposition_id,
        category=CriterionCategory.PRIOR_THERAPY,
        trial_evidence=exc7_trial_evidence(),
        patient_evidence=(exposure_evidence(),),
    )


def not_met(proposition_id: str = "P1") -> NotMetAssessment:
    return NotMetAssessment(
        proposition_id=proposition_id,
        category=CriterionCategory.PRIOR_THERAPY,
        trial_evidence=exc7_trial_evidence(),
        patient_evidence=(exposure_evidence(EvidenceRelation.CONTRADICTS),),
    )


def unknown(
    proposition_id: str = "P2",
    reason: UnknownReason = UnknownReason.INSUFFICIENT_PRECISION,
) -> UnknownAssessment:
    return UnknownAssessment(
        proposition_id=proposition_id,
        category=CriterionCategory.PRIOR_THERAPY,
        trial_evidence=exc7_trial_evidence(),
        reason=reason,
        patient_evidence=(exposure_evidence(),),
    )


def assessed_exc7(propositions: tuple[PropositionAssessment, ...]) -> AssessedCriterion:
    """EXC-7 aggregated over the assessments handed in, with its real expression."""
    criterion = exc7()
    return AssessedCriterion(
        criterion_id=criterion.criterion_id,
        polarity=criterion.polarity,
        propositions=propositions,
        aggregation=aggregate(
            criterion.expression,
            {assessment.proposition_id: assessment.state for assessment in propositions},
        ),
    )


def exc7_trial_assessment(
    criteria: tuple[CriterionAssessment, ...] | None = None,
    retrieval_rank: int = 1,
    nct_id: str = NCT,
) -> TrialAssessment:
    return TrialAssessment(
        nct_id=nct_id,
        snapshot_record_id=f"{SNAPSHOT_ID}:{nct_id}",
        retrieval_rank=retrieval_rank,
        criteria=criteria if criteria is not None else (assessed_exc7((met("P1"), unknown("P2"))),),
        measurements=Measurements(
            latency_ms=1840,
            model_calls=2,
            prompt_tokens=1200,
            completion_tokens=180,
            estimated_cost_usd=0.0021,
        ),
    )


def candidate(
    nct_id: str,
    retrieval_rank: int,
    status: CandidateStatus = CandidateStatus.RETAINED,
) -> CandidateTrial:
    return CandidateTrial(
        nct_id=nct_id,
        snapshot_record_id=f"{SNAPSHOT_ID}:{nct_id}",
        retrieval_rank=retrieval_rank,
        status=status,
        fused_score=1.0 / retrieval_rank,
        channel_ranks=(
            ChannelRank(channel=RetrievalChannel.BM25, rank=retrieval_rank, score=12.5),
            ChannelRank(channel=RetrievalChannel.DENSE, rank=retrieval_rank, score=0.81),
        ),
    )


def candidate_set() -> CandidateSet:
    """Three candidates: one assessed, one presented, one merely retained."""
    return CandidateSet(
        candidates=(
            candidate(NCT, 1, CandidateStatus.ASSESSED),
            candidate("NCT05222222", 2, CandidateStatus.PRESENTED),
            candidate("NCT05333333", 3),
        )
    )


def run_configuration() -> RunConfiguration:
    return RunConfiguration(
        retrieval_version="retrieval-v1",
        embedding_model="bge-small-en-v1.5",
        tool_version="tools-v1",
        evaluator_version="evaluator-v1",
        hardware_profile="apple-m3-16gb",
        seed=20260824,
        model=ModelConfiguration(
            adapter=ModelAdapter.HOSTED,
            model_id="a-deliberately-modest-model",
            revision="2026-05-01",
            temperature=0.0,
            top_p=1.0,
            max_output_tokens=1024,
            prompt_version="prompt-v4",
            schema_version="assessment-schema-v2",
        ),
        supervisor=SupervisorConfiguration(),
    )


def matching_run(
    trial_assessments: tuple[TrialAssessment, ...] | None = None,
) -> MatchingRun:
    return MatchingRun(
        run_id="run-0001",
        identities=RunIdentities(
            scenario_id="scenario-03",
            bundle_sha256="a" * 64,
            snapshot_id=SNAPSHOT_ID,
            snapshot_sha256="b" * 64,
            assessment_as_of=dt.date(2026, 8, 24),
            partition=Partition.DEVELOPMENT,
        ),
        configuration=run_configuration(),
        candidates=candidate_set(),
        trial_assessments=(
            trial_assessments if trial_assessments is not None else (exc7_trial_assessment(),)
        ),
        measurements=Measurements(
            latency_ms=5200,
            model_calls=6,
            prompt_tokens=3600,
            completion_tokens=540,
            estimated_cost_usd=0.0063,
        ),
    )


def retrieved(rank: int, *, has_expression: bool = True) -> RetrievedTrial:
    """One retrieval hit. `rank` only names the trial; the policy numbers them."""
    nct_id = f"NCT0500{rank:04d}"
    return RetrievedTrial(
        nct_id=nct_id,
        snapshot_record_id=f"{SNAPSHOT_ID}:{nct_id}",
        has_authored_expression=has_expression,
        fused_score=1.0 / rank,
        channel_ranks=(ChannelRank(channel=RetrievalChannel.BM25, rank=rank, score=12.5),),
    )
