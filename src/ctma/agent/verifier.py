"""The Evidence Verifier: the eight checks of specification section 8.1.

What it is for, concretely. A model asked whether a patient has had an EGFR TKI
finds an osimertinib order in the record and answers `met`, citing
`MedicationRequest/medreq-osi`. Everything about that citation is true: the
resource exists, the JSON path resolves, the drug is named correctly, the date
is real. A reviewer skimming the output sees a confident answer with a
provenance link and has no reason to doubt it. What is wrong is that an order is
not an administration — nobody knows whether the patient ever took the drug —
and no amount of checking that the citation *resolves* will say so.

So the verifier checks two different things: whether the citation points at
something real and says what the source says, and whether what it points at
could establish the state claimed on it. The second is not implied by the first,
and it is the one the injected-fault demonstration turns on.

Every rejection names its check. A verdict with no named check cannot be argued
with and cannot be corrected, and the failure taxonomy counts rejections by
check.

**One implementation, two roles.** Offline grading scores every variant with
this code and this configuration, and its results never flow back into the
system under test. Runtime feedback is the same call inside the agent loop,
where the verdict triggers one correction. The roles differ by call site, not by
configuration; conflating them would make the grounding comparison meaningless.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import NamedTuple

from ctma.domain.aggregation import UnassessedPropositionError, aggregate
from ctma.domain.enums import CriterionState, EvidenceRelation, TemporalPrecision
from ctma.domain.evidence import PatientFactReference
from ctma.domain.expression import EligibilityCriterion
from ctma.domain.proposal import ProposedAssessment, ProposedCitation
from ctma.domain.timeline import (
    CodedValue,
    FactValue,
    MedicationExposure,
    PatientTimeline,
    TimelineFact,
    UnsupportedContent,
    UnsupportedReason,
)
from ctma.domain.trace import VerifierOutcome, VerifierRejection, VerifierVerdict
from ctma.domain.trial import TrialRecord
from ctma.timeline.tools import DISQUALIFYING_OBSERVATION_STATUSES

STATES_THAT_CITE_THE_PATIENT = frozenset(
    {CriterionState.MET, CriterionState.NOT_MET, CriterionState.NOT_APPLICABLE}
)
"""Section 8. `not_applicable` is here with the other two: it claims a
conditional antecedent is false, which is a finding about the patient rather
than the absence of one."""

CONFIDENT_STATES = frozenset({CriterionState.MET, CriterionState.NOT_MET})

REQUIRED_RELATION: dict[CriterionState, EvidenceRelation] = {
    CriterionState.MET: EvidenceRelation.SUPPORTS,
    CriterionState.NOT_MET: EvidenceRelation.CONTRADICTS,
}
"""What a state needs at least one citation to be doing.

A `met` resting entirely on facts labelled `contradicts` is not a failure a
reader would notice — the citations resolve and the values agree — and it is
not the state the evidence describes."""

Resolved = TimelineFact | MedicationExposure | UnsupportedContent


class _Findings:
    """Failed checks, collected rather than raised at the first one.

    Stopping early would make the single targeted correction that follows a
    guess about what else is wrong, and would under-count every rejection class
    but whichever is checked first.
    """

    def __init__(self) -> None:
        self.rejections: list[VerifierRejection] = []
        self.details: list[str] = []

    def add(self, rejection: VerifierRejection, detail: str) -> None:
        if rejection not in self.rejections:
            self.rejections.append(rejection)
        self.details.append(detail)

    def outcome(self) -> VerifierOutcome:
        if not self.rejections:
            return VerifierOutcome(verdict=VerifierVerdict.ACCEPTED)
        return VerifierOutcome(
            verdict=VerifierVerdict.REJECTED,
            rejections=tuple(self.rejections),
            detail="; ".join(self.details),
        )


class _Recorded(NamedTuple):
    """The fields a citation is compared against, from either kind of fact."""

    status: str
    code: str
    display: str
    value: str | None
    clinical_time: dt.date | None
    precision: TemporalPrecision | None


def verify(
    proposal: ProposedAssessment,
    *,
    timeline: PatientTimeline,
    trial: TrialRecord,
) -> VerifierOutcome:
    """Check one Proposed Assessment against the timeline and the snapshot."""
    findings = _Findings()
    _check_trial_evidence(proposal, trial, findings)
    _check_state_has_evidence(proposal, findings)
    _check_relations(proposal, findings)
    for citation in proposal.patient_evidence:
        for fact in citation.facts:
            _check_fact(proposal, fact, timeline, findings)
    return findings.outcome()


def verify_aggregation(
    claimed: CriterionState,
    *,
    criterion: EligibilityCriterion,
    states: Mapping[str, CriterionState],
) -> VerifierOutcome:
    """Check that a claimed Criterion State follows from its propositions.

    Recomputed rather than reviewed. The aggregation is deterministic code, so
    the honest check is to run it again over the same proposition states: an
    assessment claiming an aggregate the expression does not produce is
    rejected whether a model or a bug produced it.
    """
    findings = _Findings()
    try:
        recomputed = aggregate(criterion.expression, states)
    except UnassessedPropositionError as error:
        findings.add(VerifierRejection.INCORRECT_AGGREGATION, f"{criterion.criterion_id}: {error}")
        return findings.outcome()
    if recomputed.state is not claimed:
        findings.add(
            VerifierRejection.INCORRECT_AGGREGATION,
            f"{criterion.criterion_id} claims {claimed.value} and its propositions "
            f"aggregate to {recomputed.state.value}",
        )
    return findings.outcome()


def _check_trial_evidence(
    proposal: ProposedAssessment, trial: TrialRecord, findings: _Findings
) -> None:
    """The cited trial text is in the snapshot, at the span that was cited.

    Trial text is verbatim everywhere it appears, so a paraphrase that reads
    plausibly still fails here: the check is against the snapshot, not against
    the copy the citation carries.
    """
    evidence = proposal.trial_evidence
    text = trial.eligibility_source_text
    if evidence.nct_id != trial.nct_id or evidence.snapshot_id != trial.snapshot_record_id:
        findings.add(
            VerifierRejection.INVALID_TRIAL_SPAN,
            f"the citation names {evidence.nct_id}/{evidence.snapshot_id} and the snapshot "
            f"is {trial.nct_id}/{trial.snapshot_record_id}",
        )
        return
    if evidence.span_end > len(text):
        findings.add(
            VerifierRejection.INVALID_TRIAL_SPAN,
            f"span [{evidence.span_start}, {evidence.span_end}) runs past the "
            f"{len(text)}-character eligibility text",
        )
        return
    if text[evidence.span_start : evidence.span_end] != evidence.source_text:
        findings.add(
            VerifierRejection.INVALID_TRIAL_SPAN,
            f"the text at [{evidence.span_start}, {evidence.span_end}) is not what was "
            f"cited: {evidence.source_text!r}",
        )


def _check_state_has_evidence(proposal: ProposedAssessment, findings: _Findings) -> None:
    if proposal.state in STATES_THAT_CITE_THE_PATIENT and not proposal.patient_evidence:
        findings.add(
            VerifierRejection.STATE_WITHOUT_PATIENT_EVIDENCE,
            f"{proposal.state.value} cites no patient evidence",
        )


def _check_relations(proposal: ProposedAssessment, findings: _Findings) -> None:
    """Every citation is labelled, and something cited does what the state claims.

    An unlabelled citation stops the second check rather than failing it. With a
    label missing there is no reading of what the citations do, and reporting
    both would name one defect twice and inflate every count that groups
    rejections by check.
    """
    unlabelled = [citation for citation in proposal.patient_evidence if citation.relation is None]
    if unlabelled:
        findings.add(
            VerifierRejection.MISSING_EVIDENCE_RELATION,
            f"{len(unlabelled)} citation(s) on {proposal.proposition_id} state no evidence "
            f"relation",
        )
        return
    required = REQUIRED_RELATION.get(proposal.state)
    if required is None or not proposal.patient_evidence:
        return
    if not _cites(proposal.patient_evidence, required):
        findings.add(
            VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,
            f"{proposal.state.value} cites nothing whose relation is {required.value}",
        )


def _cites(citations: tuple[ProposedCitation, ...], relation: EvidenceRelation) -> bool:
    return any(citation.relation is relation for citation in citations)


def _check_fact(
    proposal: ProposedAssessment,
    fact: PatientFactReference,
    timeline: PatientTimeline,
    findings: _Findings,
) -> None:
    resolved = _resolve(fact, timeline)
    if resolved is None:
        findings.add(
            VerifierRejection.NONEXISTENT_REFERENCE,
            f"{fact.resource_type}/{fact.resource_id} at {fact.json_path} is not in this Bundle",
        )
        return
    if isinstance(resolved, UnsupportedContent):
        _check_unsupported(proposal, fact, resolved, findings)
        return
    _check_agreement(fact, resolved, findings)
    _check_usability(proposal, fact, resolved, findings)
    _check_time(fact, timeline.assessment_as_of, findings)


def _check_unsupported(
    proposal: ProposedAssessment,
    fact: PatientFactReference,
    resolved: UnsupportedContent,
    findings: _Findings,
) -> None:
    """A citation that resolves into the inventory rather than into evidence.

    This is the check the section 3 demonstration turns on. The resource is
    there, the path is valid, the date is real, and it still is not Patient
    Evidence — so the rejection has to say that, rather than say the reference
    does not exist, which would send the correction looking for a typo.
    """
    if resolved.reason is UnsupportedReason.AFTER_ASSESSMENT_TIME:
        findings.add(
            VerifierRejection.EVIDENCE_AFTER_ASSESSMENT_TIME,
            f"{fact.resource_type}/{fact.resource_id} did not exist at the Assessment Time",
        )
        return
    findings.add(
        VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,
        f"{fact.resource_type}/{fact.resource_id} is outside the evidence-bearing boundary "
        f"({resolved.reason.value}), so {proposal.state.value} rests on nothing",
    )


def _check_agreement(
    fact: PatientFactReference, resolved: TimelineFact | MedicationExposure, findings: _Findings
) -> None:
    """What the citation says the fact says, against what it says.

    Without this an altered value resolves perfectly: right resource, right
    path, wrong number. That is the citation a reviewer is least able to catch
    by eye, because everything checkable at a glance is correct.
    """
    recorded = _recorded(resolved)
    for field, cited, actual in (
        ("status", fact.status, recorded.status),
        ("code", fact.code, recorded.code),
        ("display", fact.display, recorded.display),
        ("value", fact.value, recorded.value),
        ("clinical_time", fact.clinical_time, recorded.clinical_time),
        ("precision", fact.precision, recorded.precision),
    ):
        if cited != actual:
            findings.add(
                VerifierRejection.CITATION_DISAGREES_WITH_TIMELINE,
                f"{fact.resource_type}/{fact.resource_id} cites {field} {cited!r} and the "
                f"timeline holds {actual!r}",
            )


def _check_usability(
    proposal: ProposedAssessment,
    fact: PatientFactReference,
    resolved: TimelineFact | MedicationExposure,
    findings: _Findings,
) -> None:
    """Section 5.2: a disqualified result cannot establish `met` or `not_met`.

    Citing one for `unknown` with `unusable_status` is right and stays right —
    the withdrawn result is exactly what that reason is about.
    """
    if proposal.state in CONFIDENT_STATES and resolved.status in DISQUALIFYING_OBSERVATION_STATUSES:
        findings.add(
            VerifierRejection.CITATION_CANNOT_ESTABLISH_STATE,
            f"{fact.resource_type}/{fact.resource_id} is {resolved.status}, which cannot "
            f"establish {proposal.state.value}",
        )


def _check_time(fact: PatientFactReference, as_of: dt.date, findings: _Findings) -> None:
    if fact.clinical_time is not None and fact.clinical_time > as_of:
        findings.add(
            VerifierRejection.EVIDENCE_AFTER_ASSESSMENT_TIME,
            f"{fact.resource_type}/{fact.resource_id} is cited at {fact.clinical_time}, "
            f"after the Assessment Time {as_of}",
        )


def _resolve(fact: PatientFactReference, timeline: PatientTimeline) -> Resolved | None:
    """Find the cited resource anywhere in the Bundle the timeline accounted for.

    The inventory is searched too. A citation to a `MedicationRequest` has to
    resolve before it can be rejected for what it is; coming back "no such
    resource" would describe the wrong defect.
    """
    for item in (*timeline.facts, *timeline.exposures):
        if (
            item.resource_id == fact.resource_id
            and item.json_path == fact.json_path
            and _resource_type(item) == fact.resource_type
        ):
            return item
    for content in timeline.unsupported_content:
        if (
            content.resource_id == fact.resource_id
            and content.json_path == fact.json_path
            and content.resource_type == fact.resource_type
        ):
            return content
    return None


def _recorded(item: TimelineFact | MedicationExposure) -> _Recorded:
    coding = item.code if isinstance(item, TimelineFact) else item.medication
    value = item.value if isinstance(item, TimelineFact) else None
    return _Recorded(
        status=item.status,
        code=coding.code,
        display=item.display,
        value=_rendered(value) if value is not None else None,
        clinical_time=item.time.start if item.time is not None else None,
        precision=item.time.start_precision if item.time is not None else None,
    )


def _rendered(value: FactValue) -> str:
    """How a cited value is written down: the recorded value with its unit."""
    if isinstance(value, CodedValue):
        return value.text
    return f"{value.comparator or ''}{value.value}{f' {value.unit}' if value.unit else ''}"


def _resource_type(item: TimelineFact | MedicationExposure) -> str:
    return item.resource_type if isinstance(item, TimelineFact) else "MedicationAdministration"
