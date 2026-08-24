"""Shared authored artifacts, so tests read as data rather than as setup."""

from __future__ import annotations

import datetime as dt
import hashlib

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
    MatchingRun,
    ModelAdapter,
    ModelConfiguration,
    RunConfiguration,
    RunIdentities,
    SupervisorConfiguration,
)
from ctma.domain.trace import Measurements
from ctma.domain.trial import TrialRecord
from ctma.policy import CandidateInput

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
                    source_anchor_text="the first dose of study drug",
                    anchor_substitution=AnchorSubstitution(
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


def retrieved(rank: int, *, has_expression: bool = True) -> CandidateInput:
    """One candidate. `rank` only names the trial; the policy numbers them."""
    nct_id = f"NCT0500{rank:04d}"
    return CandidateInput(
        nct_id=nct_id,
        snapshot_record_id=f"{SNAPSHOT_ID}:{nct_id}",
        has_authored_expression=has_expression,
    )


SCREENING_TEXT = (
    "Inclusion Criteria:\n"
    "* Eastern Cooperative Oncology Group (ECOG) performance status of 0 or 1.\n"
    "Exclusion Criteria:\n"
    "* Symptomatic brain metastases."
)


def screening_trial() -> TrialRecord:
    """A two-criterion trial, built here to exercise trial-level strategy.

    Not a benchmark artifact and not one of the four frozen records: the
    supervisor needs a criterion that comes out blocking, and no development
    scenario meets an exclusion of the two development trials, because the
    reviewed terminology mapping does not cover the conditions they exclude.
    That gap belongs in the published limitations; a test of `early_termination`
    should not wait on it.
    """
    exclusion_text = "Symptomatic brain metastases."
    inclusion_text = "Eastern Cooperative Oncology Group (ECOG) performance status of 0 or 1."
    return TrialRecord(
        nct_id="NCT00000001",
        snapshot_record_id="supervisor-fixture-v1:NCT00000001",
        source_url="https://clinicaltrials.gov/study/NCT00000001",
        overall_status="RECRUITING",
        study_type="INTERVENTIONAL",
        brief_title="A two-criterion trial for supervisor tests",
        brief_summary="Authored for tests. Not a real study.",
        conditions=("Non-small cell lung cancer",),
        eligibility_source_text=SCREENING_TEXT,
        eligibility_sha256=hashlib.sha256(SCREENING_TEXT.encode()).hexdigest(),
        partition=Partition.DEVELOPMENT,
        last_update_posted=dt.date(2026, 8, 1),
        criteria=(
            EligibilityCriterion(
                criterion_id="NCT00000001:EXC-1",
                polarity=CriterionPolarity.EXCLUSION,
                source_section="exclusionCriteria",
                ordinal=1,
                span_start=SCREENING_TEXT.index(exclusion_text),
                span_end=SCREENING_TEXT.index(exclusion_text) + len(exclusion_text),
                source_text=exclusion_text,
                expression_version="v1",
                propositions=(
                    AtomicProposition(
                        proposition_id="P1",
                        statement="Brain metastases are documented",
                        category=CriterionCategory.DISEASE,
                        concept="BRAIN_METASTASIS",
                    ),
                ),
                expression=PropositionRef(proposition_id="P1"),
                provenance=REVIEWED,
            ),
            EligibilityCriterion(
                criterion_id="NCT00000001:INC-1",
                polarity=CriterionPolarity.INCLUSION,
                source_section="inclusionCriteria",
                ordinal=1,
                span_start=SCREENING_TEXT.index(inclusion_text),
                span_end=SCREENING_TEXT.index(inclusion_text) + len(inclusion_text),
                source_text=inclusion_text,
                expression_version="v1",
                propositions=(
                    AtomicProposition(
                        proposition_id="P1",
                        statement="ECOG performance status is 0 or 1",
                        category=CriterionCategory.PERFORMANCE_STATUS,
                        concept="ECOG_SCORE",
                    ),
                ),
                expression=PropositionRef(proposition_id="P1"),
                provenance=REVIEWED,
            ),
        ),
    )
