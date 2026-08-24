"""The Evidence Verifier, against the frozen injected faults.

Gate 3, specification sections 8.1 and 8.2. The catch rate over these faults is
a release gate, so the test that reports it walks the fixture file rather than a
list written here: a fault added to the fixtures is a fault this suite runs.
"""

from __future__ import annotations

import datetime as dt

import pytest

from ctma.adapters.injected_faults import (
    AggregationFault,
    CitationFault,
    load_injected_faults,
)
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.agent.verifier import verify, verify_aggregation
from ctma.domain.enums import CriterionState, EvidenceRelation, UnknownReason
from ctma.domain.expression import EligibilityCriterion
from ctma.domain.proposal import ProposedAssessment, ProposedCitation
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trace import VerifierOutcome, VerifierRejection, VerifierVerdict
from ctma.timeline.build import build

FAULTS = load_injected_faults()
TRIALS = {trial.nct_id: trial for trial in load_trial_fixtures()}
CITATION_IDS = [fault.fault_id for fault in FAULTS.citations]
AGGREGATION_IDS = [fault.fault_id for fault in FAULTS.aggregations]


def timeline_of(scenario_id: str) -> PatientTimeline:
    scenario = load_scenario_input(scenario_id)
    return build(
        scenario.bundle_json,
        scenario_id=scenario_id,
        assessment_as_of=scenario.assessment_as_of,
    )


def run(fault: CitationFault) -> VerifierOutcome:
    return verify(
        fault.proposal,
        timeline=timeline_of(fault.scenario_id),
        trial=TRIALS[fault.nct_id],
    )


def criterion_of(nct_id: str, criterion_id: str) -> EligibilityCriterion:
    return next(item for item in TRIALS[nct_id].criteria if item.criterion_id == criterion_id)


@pytest.mark.parametrize("fault", FAULTS.citations, ids=CITATION_IDS)
def test_each_injected_fault_is_caught_by_the_check_it_was_authored_for(
    fault: CitationFault,
) -> None:
    outcome = run(fault)
    if fault.expected_rejection is None:
        assert outcome.verdict is VerifierVerdict.ACCEPTED, outcome.detail
        return
    assert outcome.verdict is VerifierVerdict.REJECTED
    assert fault.expected_rejection in outcome.rejections, outcome.detail


def test_the_catch_rate_over_the_injected_faults_is_total() -> None:
    """The release gate of section 20, as the number it is reported as."""
    injected = [fault for fault in FAULTS.citations if fault.expected_rejection is not None]
    caught = [fault for fault in injected if fault.expected_rejection in run(fault).rejections]
    assert len(caught) == len(injected), f"caught {len(caught)} of {len(injected)}"


def test_every_rejection_class_has_a_fault_behind_it() -> None:
    """Section 8.1 lists eight checks, and each is proven by a fixture.

    Two of them are not citation faults: `incorrect_aggregation` is a claim
    about a criterion rather than about a citation, and it has its own fixtures
    below.
    """
    covered = {fault.expected_rejection for fault in FAULTS.citations} | {
        fault.expected_rejection for fault in FAULTS.aggregations
    }
    assert covered >= set(VerifierRejection)


def test_a_correct_assessment_is_accepted() -> None:
    """A verifier that rejected everything would pass every release gate."""
    clean = next(fault for fault in FAULTS.citations if fault.expected_rejection is None)
    outcome = run(clean)
    assert outcome.verdict is VerifierVerdict.ACCEPTED
    assert outcome.rejections == ()


def test_the_order_fault_passes_every_other_check() -> None:
    """The section 3 demonstration only works if nothing else is wrong with it.

    A `MedicationRequest` cited as exposure resolves: the resource is there, the
    path is valid, the drug is named correctly. If it were also rejected as a
    nonexistent reference, the fault would prove the wrong check.
    """
    fault = next(fault for fault in FAULTS.citations if fault.fault_id == "F6")
    outcome = run(fault)
    assert outcome.rejections == (VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,)


def test_a_disqualified_result_may_still_be_cited_for_an_unknown() -> None:
    """`unusable_status` cites the very result that disqualified the answer.

    Rejecting that citation would leave the reason unable to point at what it is
    about, and a coordinator with no way to see which result was withdrawn.
    """
    fault = next(fault for fault in FAULTS.citations if fault.fault_id == "F7")
    as_unknown = ProposedAssessment(
        proposition_id=fault.proposal.proposition_id,
        state=CriterionState.UNKNOWN,
        reason=UnknownReason.UNUSABLE_STATUS,
        trial_evidence=fault.proposal.trial_evidence,
        patient_evidence=fault.proposal.patient_evidence,
    )
    outcome = verify(
        as_unknown, timeline=timeline_of(fault.scenario_id), trial=TRIALS[fault.nct_id]
    )
    assert outcome.verdict is VerifierVerdict.ACCEPTED


def test_a_met_that_cites_only_contradicting_evidence_is_rejected() -> None:
    """Every field resolves and agrees; the state is not the one cited."""
    clean = next(fault for fault in FAULTS.citations if fault.expected_rejection is None)
    inverted = ProposedAssessment(
        proposition_id=clean.proposal.proposition_id,
        state=CriterionState.MET,
        trial_evidence=clean.proposal.trial_evidence,
        patient_evidence=tuple(
            ProposedCitation(facts=citation.facts, relation=EvidenceRelation.CONTRADICTS)
            for citation in clean.proposal.patient_evidence
        ),
    )
    outcome = verify(inverted, timeline=timeline_of(clean.scenario_id), trial=TRIALS[clean.nct_id])
    assert outcome.rejections == (VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,)


def test_an_unknown_cites_nothing_and_is_still_accepted() -> None:
    """`missing_evidence` has nothing to cite, and demanding a citation there
    would push a caller into inventing one."""
    clean = next(fault for fault in FAULTS.citations if fault.expected_rejection is None)
    unknown = ProposedAssessment(
        proposition_id="P1",
        state=CriterionState.UNKNOWN,
        reason=UnknownReason.MISSING_EVIDENCE,
        trial_evidence=clean.proposal.trial_evidence,
    )
    outcome = verify(unknown, timeline=timeline_of(clean.scenario_id), trial=TRIALS[clean.nct_id])
    assert outcome.verdict is VerifierVerdict.ACCEPTED


def test_a_rejection_names_every_check_that_failed() -> None:
    """The correction that follows is targeted, so it needs the whole list."""
    clean = next(fault for fault in FAULTS.citations if fault.expected_rejection is None)
    doubly_wrong = ProposedAssessment(
        proposition_id=clean.proposal.proposition_id,
        state=CriterionState.MET,
        trial_evidence=clean.proposal.trial_evidence.model_copy(
            update={
                "span_start": clean.proposal.trial_evidence.span_start + 7,
                "span_end": clean.proposal.trial_evidence.span_end + 7,
            }
        ),
        patient_evidence=tuple(
            ProposedCitation(
                facts=tuple(
                    fact.model_copy(update={"resource_id": "obs-nowhere"})
                    for fact in citation.facts
                ),
                relation=None,
            )
            for citation in clean.proposal.patient_evidence
        ),
    )
    outcome = verify(
        doubly_wrong, timeline=timeline_of(clean.scenario_id), trial=TRIALS[clean.nct_id]
    )
    assert set(outcome.rejections) == {
        VerifierRejection.INVALID_TRIAL_SPAN,
        VerifierRejection.MISSING_EVIDENCE_RELATION,
        VerifierRejection.NONEXISTENT_REFERENCE,
    }
    assert outcome.detail is not None


@pytest.mark.parametrize("fault", FAULTS.aggregations, ids=AGGREGATION_IDS)
def test_an_aggregation_claim_is_recomputed_rather_than_believed(
    fault: AggregationFault,
) -> None:
    outcome = verify_aggregation(
        fault.claimed_state,
        criterion=criterion_of(fault.nct_id, fault.criterion_id),
        states=fault.proposition_states,
    )
    if fault.expected_rejection is None:
        assert outcome.verdict is VerifierVerdict.ACCEPTED, outcome.detail
    else:
        assert outcome.rejections == (fault.expected_rejection,)


def test_a_timeline_from_another_scenario_makes_a_good_citation_fail() -> None:
    """The same assessment against the wrong patient.

    Nothing about the assessment changed, so this is what it means for the
    verifier to check the record rather than the claim.
    """
    clean = next(fault for fault in FAULTS.citations if fault.expected_rejection is None)
    outcome = verify(clean.proposal, timeline=timeline_of("SCN-06"), trial=TRIALS[clean.nct_id])
    assert outcome.verdict is VerifierVerdict.REJECTED


def test_a_citation_dated_after_the_assessment_time_is_rejected_on_its_own_terms() -> None:
    """SCN-04's late ECOG resolves in the inventory, and is not evidence."""
    fault = next(fault for fault in FAULTS.citations if fault.fault_id == "F9")
    assert fault.proposal.patient_evidence[0].facts[0].clinical_time == dt.date(2026, 7, 15)
    outcome = run(fault)
    assert VerifierRejection.EVIDENCE_AFTER_ASSESSMENT_TIME in outcome.rejections
