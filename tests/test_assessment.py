"""Assessment records, and the states they refuse to represent.

Most of this file is about what cannot be built. That is the point of the shape:
a `met` with no citation and an `unknown` with no reason are the two ways this
system would quietly become the thing it argues against, and neither has a
constructor.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.domain.assessment import (
    AssessedCriterion,
    MetAssessment,
    NotApplicableAssessment,
    NotMetAssessment,
    SkippedCriterion,
    TrialAssessment,
    UnexpressedCriterion,
    UnknownAssessment,
    reporting_status_of,
)
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
from ctma.domain.trace import VerifierOutcome, VerifierRejection, VerifierVerdict
from tests.builders import (
    assessed_exc7,
    exc7_trial_assessment,
    exc7_trial_evidence,
    exposure_evidence,
    met,
    not_met,
    unknown,
)

ACCEPTED = VerifierOutcome(verdict=VerifierVerdict.ACCEPTED)
REJECTED = VerifierOutcome(
    verdict=VerifierVerdict.REJECTED,
    rejections=(VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,),
    detail="a MedicationRequest is an order, not an exposure",
)


def test_a_met_assessment_cannot_be_built_without_patient_evidence() -> None:
    """Section 8, as a constructor that refuses rather than a test that catches."""
    with pytest.raises(ValidationError, match="at least 1 item"):
        MetAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            patient_evidence=(),
        )


def test_a_met_assessment_cannot_be_built_by_omitting_the_evidence_either() -> None:
    with pytest.raises(ValidationError, match="patient_evidence"):
        MetAssessment.model_validate(
            {
                "proposition_id": "P1",
                "category": CriterionCategory.PRIOR_THERAPY,
                "trial_evidence": exc7_trial_evidence().model_dump(),
            }
        )


def test_a_not_met_assessment_cannot_be_built_without_patient_evidence() -> None:
    """`not_met` is a contradiction found in the record, not evidence missing."""
    with pytest.raises(ValidationError, match="at least 1 item"):
        NotMetAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            patient_evidence=(),
        )


def test_a_not_applicable_assessment_cites_the_evidence_behind_it() -> None:
    """It claims an antecedent is false, which is a finding about the patient."""
    with pytest.raises(ValidationError, match="at least 1 item"):
        NotApplicableAssessment(
            proposition_id="P1",
            category=CriterionCategory.DISEASE,
            trial_evidence=exc7_trial_evidence(),
            patient_evidence=(),
        )


def test_an_unknown_assessment_cannot_be_built_without_a_reason() -> None:
    with pytest.raises(ValidationError, match="reason"):
        UnknownAssessment.model_validate(
            {
                "proposition_id": "P2",
                "category": CriterionCategory.PRIOR_THERAPY,
                "trial_evidence": exc7_trial_evidence().model_dump(),
            }
        )


def test_the_state_classes_carry_only_the_fields_their_state_can_have() -> None:
    """Why this is a union rather than one record with optional fields.

    A `met` has no reason to read, and an `unknown` has no evidence a caller
    could forget to check for.
    """
    assert "reason" not in MetAssessment.model_fields
    assert "reason" in UnknownAssessment.model_fields
    assert "patient_evidence" in MetAssessment.model_fields


def test_an_unknown_proposition_may_cite_nothing_at_all() -> None:
    """`missing_evidence` has nothing to cite, and inventing a citation is worse."""
    assessment = UnknownAssessment(
        proposition_id="P1",
        category=CriterionCategory.BIOMARKER,
        trial_evidence=exc7_trial_evidence(),
        reason=UnknownReason.MISSING_EVIDENCE,
    )
    assert assessment.patient_evidence == ()


def test_a_proposition_cannot_claim_expression_unavailable() -> None:
    """Stage 1 of section 8.0 is criterion-level: with no expression, no propositions."""
    with pytest.raises(ValidationError, match="expression_unavailable belongs to a criterion"):
        UnknownAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            reason=UnknownReason.EXPRESSION_UNAVAILABLE,
        )


def test_met_cites_something_that_supports_it() -> None:
    with pytest.raises(ValidationError, match="relation is 'supports'"):
        MetAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            patient_evidence=(exposure_evidence(EvidenceRelation.CONTRADICTS),),
        )


def test_not_met_cites_something_that_contradicts_it() -> None:
    with pytest.raises(ValidationError, match="relation is 'contradicts'"):
        NotMetAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            patient_evidence=(exposure_evidence(),),
        )


def test_a_corrected_assessment_records_the_rejection_it_answered() -> None:
    assessment = met().model_copy(update={"verification": (REJECTED, ACCEPTED)})
    assert assessment.last_verdict is VerifierVerdict.ACCEPTED


def test_a_second_pass_without_a_first_rejection_is_refused() -> None:
    """Two accepted passes would be a retry, and there are no hidden retries."""
    with pytest.raises(ValidationError, match="only after a rejected verification"):
        MetAssessment.model_validate(
            met().model_dump() | {"verification": [ACCEPTED.model_dump(), ACCEPTED.model_dump()]}
        )


def test_a_third_verification_pass_is_refused() -> None:
    """Section 8.1 allows exactly one targeted correction."""
    with pytest.raises(ValidationError, match="at most 2 items"):
        MetAssessment.model_validate(
            met().model_dump()
            | {
                "verification": [
                    REJECTED.model_dump(),
                    REJECTED.model_dump(),
                    ACCEPTED.model_dump(),
                ]
            }
        )


def test_a_confident_state_cannot_rest_on_a_rejected_citation() -> None:
    """The failure the verifier exists to catch, arriving as a scored answer."""
    with pytest.raises(ValidationError, match="rejected citation"):
        MetAssessment.model_validate(met().model_dump() | {"verification": [REJECTED.model_dump()]})


def test_verification_failed_names_the_two_rejections_behind_it() -> None:
    """One rejection is corrected; two is what makes the criterion unresolved."""
    with pytest.raises(ValidationError, match="two rejected verifications"):
        UnknownAssessment(
            proposition_id="P1",
            category=CriterionCategory.PRIOR_THERAPY,
            trial_evidence=exc7_trial_evidence(),
            reason=UnknownReason.VERIFICATION_FAILED,
            verification=(REJECTED,),
        )


def test_verification_failed_after_two_rejections_is_a_valid_assessment() -> None:
    assessment = UnknownAssessment(
        proposition_id="P1",
        category=CriterionCategory.PRIOR_THERAPY,
        trial_evidence=exc7_trial_evidence(),
        reason=UnknownReason.VERIFICATION_FAILED,
        verification=(REJECTED, REJECTED),
    )
    assert assessment.last_verdict is VerifierVerdict.REJECTED


@pytest.mark.parametrize(
    ("assessment", "state"),
    [
        (met(), CriterionState.MET),
        (not_met(), CriterionState.NOT_MET),
        (unknown(), CriterionState.UNKNOWN),
    ],
)
def test_each_state_round_trips_through_json_without_loss(
    assessment: MetAssessment | NotMetAssessment | UnknownAssessment,
    state: CriterionState,
) -> None:
    restored = type(assessment).model_validate_json(assessment.model_dump_json())
    assert restored == assessment
    assert restored.state is state


def test_an_exclusion_criterion_the_patient_meets_blocks_the_trial() -> None:
    criterion = assessed_exc7((met("P1"), met("P2")))
    assert criterion.state is CriterionState.MET
    assert criterion.impact is CriterionImpact.BLOCKING
    assert criterion.unknown_reason is None


def test_a_criterion_takes_its_reason_from_the_proposition_that_decided_it() -> None:
    """The coordinator is told the date was too coarse, not that the criterion failed."""
    criterion = assessed_exc7((met("P1"), unknown("P2")))
    assert criterion.state is CriterionState.UNKNOWN
    assert criterion.impact is CriterionImpact.UNRESOLVED
    assert criterion.unknown_reason is UnknownReason.INSUFFICIENT_PRECISION


def test_an_aggregation_naming_an_absent_proposition_is_refused() -> None:
    """Either the trace belongs to another criterion or an assessment was dropped."""
    criterion = assessed_exc7((met("P1"), unknown("P2")))
    with pytest.raises(ValidationError, match="cites absent propositions"):
        AssessedCriterion.model_validate(
            criterion.model_dump() | {"propositions": [met("P1").model_dump()]}
        )


def test_two_assessments_of_one_proposition_are_refused() -> None:
    """One proposition, two answers, and no rule for which of them was reported."""
    criterion = assessed_exc7((met("P1"), unknown("P2")))
    with pytest.raises(ValidationError, match="duplicate proposition_id"):
        AssessedCriterion.model_validate(
            criterion.model_dump()
            | {
                "propositions": [
                    met("P1").model_dump(),
                    unknown("P2").model_dump(),
                    met("P1").model_dump(),
                ]
            }
        )


def test_a_criterion_assessment_round_trips_with_its_propositions() -> None:
    original = assessed_exc7((met("P1"), unknown("P2")))
    restored = AssessedCriterion.model_validate_json(original.model_dump_json())
    assert restored == original
    assert isinstance(restored.propositions[1], UnknownAssessment)
    assert restored.aggregation.decided_by == ("P2",)


def test_an_unexpressed_criterion_is_unresolved_and_says_why() -> None:
    criterion = UnexpressedCriterion(
        criterion_id="NCT05999999:INC-1",
        polarity=CriterionPolarity.INCLUSION,
        trial_evidence=exc7_trial_evidence(),
    )
    assert criterion.state is CriterionState.UNKNOWN
    assert criterion.unknown_reason is UnknownReason.EXPRESSION_UNAVAILABLE
    assert criterion.impact is CriterionImpact.UNRESOLVED


def test_a_skipped_criterion_has_no_state_to_read() -> None:
    """The invariant is the absence: `not_assessed` is never merged into `unknown`."""
    skipped = SkippedCriterion(
        criterion_id="NCT05123456:INC-2",
        polarity=CriterionPolarity.INCLUSION,
        trial_evidence=exc7_trial_evidence(),
        blocker_criterion_id="NCT05123456:EXC-7",
    )
    assert not hasattr(skipped, "state")
    assert not hasattr(skipped, "impact")
    assert not hasattr(skipped, "unknown_reason")
    assert "state" not in SkippedCriterion.model_fields


def test_an_unexpressed_criterion_still_counts_toward_coverage() -> None:
    """The gap is in the authoring budget, not in the run, so it stays visible."""
    unexpressed = UnexpressedCriterion(
        criterion_id="NCT05999999:INC-1",
        polarity=CriterionPolarity.INCLUSION,
        trial_evidence=exc7_trial_evidence(),
    )
    skipped = SkippedCriterion(
        criterion_id="NCT05123456:INC-2",
        polarity=CriterionPolarity.INCLUSION,
        trial_evidence=exc7_trial_evidence(),
    )
    assert reporting_status_of(unexpressed) is ReportingStatus.ASSESSED
    assert reporting_status_of(skipped) is ReportingStatus.NOT_ASSESSED
    assert reporting_status_of(assessed_exc7((met("P1"), met("P2")))) is ReportingStatus.ASSESSED


def test_a_trial_assessment_derives_its_counts_from_its_criteria() -> None:
    assessment = exc7_trial_assessment()
    assert assessment.counts.unresolved == 1
    assert assessment.counts.total == 1
    assert assessment.conclusion is MatchConclusion.INSUFFICIENT_INFORMATION


def test_a_skipped_criterion_counts_as_not_assessed_and_not_as_unresolved() -> None:
    assessment = exc7_trial_assessment(
        criteria=(
            assessed_exc7((met("P1"), met("P2"))),
            SkippedCriterion(
                criterion_id="NCT05123456:INC-2",
                polarity=CriterionPolarity.INCLUSION,
                trial_evidence=exc7_trial_evidence(),
                blocker_criterion_id="NCT05123456:EXC-7",
            ),
        )
    )
    assert assessment.counts.unresolved == 0
    assert assessment.counts.not_assessed == 1
    assert assessment.counts.total == 2
    assert assessment.conclusion is MatchConclusion.UNLIKELY_MATCH


def test_two_records_for_one_criterion_are_refused() -> None:
    """A duplicate inflates Criterion Coverage while hiding one of the two."""
    with pytest.raises(ValidationError, match="duplicate criterion_id"):
        exc7_trial_assessment(
            criteria=(assessed_exc7((met("P1"), met("P2"))), assessed_exc7((met("P1"), met("P2"))))
        )


def test_a_trial_assessment_round_trips_and_keeps_each_criterion_kind() -> None:
    original = exc7_trial_assessment(
        criteria=(
            assessed_exc7((met("P1"), unknown("P2"))),
            UnexpressedCriterion(
                criterion_id="NCT05123456:INC-1",
                polarity=CriterionPolarity.INCLUSION,
                trial_evidence=exc7_trial_evidence(),
            ),
            SkippedCriterion(
                criterion_id="NCT05123456:INC-2",
                polarity=CriterionPolarity.INCLUSION,
                trial_evidence=exc7_trial_evidence(),
            ),
        )
    )
    restored = TrialAssessment.model_validate_json(original.model_dump_json())
    assert restored == original
    assert [type(criterion) for criterion in restored.criteria] == [
        AssessedCriterion,
        UnexpressedCriterion,
        SkippedCriterion,
    ]


def test_assessments_are_immutable() -> None:
    with pytest.raises(ValidationError):
        exc7_trial_assessment().retrieval_rank = 2  # type: ignore[misc]
