"""The bounded per-proposition loop of specification section 10.

The division of labour, which is the whole design:

**Code decides whether the record can answer.** The tools look, and the section
8.0 table reads what they found. If there is no qualifying fact, or the facts
disagree, or the date is too coarse, the proposition resolves to `unknown` with
a reason and the model is never asked. This is what a one-shot baseline cannot
do: handed a whole timeline and a question, it answers.

**The model decides what the answer is.** Given facts the record can support an
answer from, it says whether they establish the proposition and which of them to
cite. It never chooses the concept — that is a reviewed terminology judgement no
verifier could check — and it never performs a comparison, an aggregation, or a
date placement.

**The model cites which fact; the code writes down what the fact says.** The
citation's value, status, time, and display are filled in from the timeline, so
an assessment cannot carry a value that drifted from the record. This makes the
agent's citation validity a structural property rather than a measurement of the
model, which is why section 20 forbids comparing it against the baseline.

Bounds: at most one tool-selection call, one assessment call, and one
correction. There are no hidden retries. A model that cannot be reached raises
an Infrastructure Failure, which never becomes a Criterion State.

**What this loop does not assess.** The five tools of section 10.1 reach
`Condition`, `Observation`, and `MedicationAdministration`, and nothing reaches
the `Patient` resource, so a `demographic` proposition is answered here without
a lookup: the age is computed by code from the recorded birth date, and the
citation points at the `Patient` resource itself.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Literal

from pydantic import Field, ValidationError

from ctma.adapters.model import (
    ModelClient,
    ModelPurpose,
    ModelRequest,
    ModelUnavailableError,
)
from ctma.agent._packet import assessment_prompt, correction_prompt, tool_selection_prompt
from ctma.agent.situation import ToolResult, situation_from
from ctma.agent.unknown_reason import AgentOutcome, assign_unknown_reason
from ctma.agent.verifier import verify
from ctma.domain.aggregation import aggregate
from ctma.domain.assessment import (
    AssessedCriterion,
    MetAssessment,
    NotApplicableAssessment,
    NotMetAssessment,
    PropositionAssessment,
    UnknownAssessment,
)
from ctma.domain.base import Frozen
from ctma.domain.enums import (
    ComparisonOperator,
    CriterionCategory,
    CriterionState,
    EvidenceRelation,
    UnknownReason,
)
from ctma.domain.evidence import PatientEvidence, PatientFactReference, TrialEvidence
from ctma.domain.expression import AtomicProposition, EligibilityCriterion
from ctma.domain.proposal import ProposedAssessment, ProposedCitation
from ctma.domain.timeline import (
    MedicationExposure,
    PatientTimeline,
    QuantityValue,
    TimelineFact,
)
from ctma.domain.trace import (
    FailureKind,
    InfrastructureFailure,
    Measurements,
    ToolCall,
    VerifierOutcome,
    VerifierVerdict,
)
from ctma.domain.trial import TrialRecord
from ctma.timeline.tools import (
    Comparison,
    ExposureQuery,
    FactQuery,
    LatestObservation,
    Refusal,
    Verdict,
    compare_numeric,
    find_medication_exposure,
    find_patient_facts,
    get_latest_observation,
    record,
)

CitableFact = TimelineFact | MedicationExposure


class LookupTool(StrEnum):
    """The three looking-up tools of section 10.1. The two computing ones are
    not selected: they run when the comparison the model named needs them."""

    FACTS = "find_patient_facts"
    LATEST = "get_latest_observation"
    EXPOSURE = "find_medication_exposure"


LOOKUPS_BY_CATEGORY: dict[CriterionCategory, tuple[LookupTool, ...]] = {
    CriterionCategory.DISEASE: (LookupTool.FACTS,),
    CriterionCategory.BIOMARKER: (LookupTool.FACTS, LookupTool.LATEST),
    CriterionCategory.PERFORMANCE_STATUS: (LookupTool.LATEST, LookupTool.FACTS),
    CriterionCategory.PRIOR_THERAPY: (LookupTool.EXPOSURE,),
    CriterionCategory.DEMOGRAPHIC: (),
}
"""Which lookups can answer a proposition of each category.

The choice among them is the model's, and it is a real one: a biomarker
proposition asking "is there a result" wants every fact, and one asking "what
does the current result say" wants the latest. Offering tools that cannot
answer the category would be offering a wrong turn with no upside."""

REASON_BY_REFUSAL: dict[Refusal, UnknownReason] = {
    Refusal.UNIT_MISMATCH: UnknownReason.UNSUPPORTED_EVIDENCE_TYPE,
    Refusal.VALUE_IS_NOT_NUMERIC: UnknownReason.UNSUPPORTED_EVIDENCE_TYPE,
    Refusal.BOUND_STRADDLES_THE_THRESHOLD: UnknownReason.INSUFFICIENT_PRECISION,
    Refusal.PRECISION_TOO_COARSE: UnknownReason.INSUFFICIENT_PRECISION,
    Refusal.NO_CLINICAL_TIME: UnknownReason.INSUFFICIENT_PRECISION,
}
"""A refused comparison, in the closed vocabulary of section 8.0.

Two of these are readings rather than transcriptions. A cross-unit or
qualitative value is a conversion the system does not perform, which is what
`unsupported_evidence_type` says. A result recorded as "< 0.5" against a
threshold of 1.5 answers; one recorded as "< 2.0" does not, and
`insufficient_precision` is the reason in the vocabulary for a record that does
not state a quantity finely enough to decide. Adding a reason instead would be
a specification change, and section 8.0's vocabulary is closed."""


class _Comparison(Frozen):
    """The comparison the model read out of the criterion text, for code to run."""

    operator: ComparisonOperator
    threshold: float
    unit: str | None = None


class _Selection(Frozen):
    """The tool-selection answer."""

    lookup: LookupTool
    comparison: _Comparison | None = None


class _Citation(Frozen):
    """The model cites facts by id; the loop fills in what they say."""

    fact_ids: tuple[str, ...] = Field(min_length=1)
    relation: EvidenceRelation


class _Answer(Frozen):
    """The assessment answer.

    Three states, not four. The loop asks only once code has established that
    the record can answer, so `unknown` is not among the model's options: the
    diagnosis behind an `unknown` is assigned by the section 8.0 table from the
    evidence, and a model-chosen one would be a diagnosis nobody can reproduce.
    """

    state: Literal[CriterionState.MET, CriterionState.NOT_MET, CriterionState.NOT_APPLICABLE]
    citations: tuple[_Citation, ...] = Field(min_length=1)
    rationale: str | None = None


class MalformedAnswerError(ValueError):
    """The model returned something the schema does not admit."""


def assess_proposition(
    proposition: AtomicProposition,
    *,
    criterion: EligibilityCriterion,
    timeline: PatientTimeline,
    trial: TrialRecord,
    model: ModelClient,
    verifier_feedback: bool = True,
) -> PropositionAssessment:
    """Assess one Atomic Proposition, bounded as section 10 bounds it.

    `verifier_feedback` off is the no-verifier configuration of the measurement
    plan: the verifier still grades the output offline, at another call site,
    and the assessment is simply not given a chance to correct itself.
    """
    evidence = TrialEvidence(
        snapshot_id=trial.snapshot_record_id,
        nct_id=trial.nct_id,
        source_section=criterion.source_section,
        criterion_ordinal=criterion.ordinal,
        span_start=criterion.span_start,
        span_end=criterion.span_end,
        source_text=criterion.source_text,
    )
    context = _Context(proposition, criterion, timeline, trial, model, evidence, verifier_feedback)

    if proposition.category is CriterionCategory.UNSUPPORTED:
        return context.unknown(UnknownReason.UNSUPPORTED_EVIDENCE_TYPE)
    window = proposition.window
    if window is not None and not window.anchor_is_resolvable:
        return context.unknown(UnknownReason.AMBIGUOUS_CRITERION)
    if proposition.category is CriterionCategory.DEMOGRAPHIC:
        return _assess_demographics(context)

    selection = _select(context)
    result = _look_up(context, selection.lookup)
    facts = _citable(result)
    comparison = _compare(context, selection, facts)

    if comparison is not None and comparison.verdict is Verdict.REFUSED:
        assert comparison.refusal is not None
        return context.unknown(REASON_BY_REFUSAL[comparison.refusal], facts=_unusable(result))
    if not facts:
        situation = situation_from(result, category=proposition.category, window=window)
        return context.unknown(assign_unknown_reason(situation), facts=_unusable(result))

    return _answer(context, facts, comparison)


def assess_criterion(
    criterion: EligibilityCriterion,
    *,
    timeline: PatientTimeline,
    trial: TrialRecord,
    model: ModelClient,
    verifier_feedback: bool = True,
) -> AssessedCriterion:
    """Every proposition of one criterion, aggregated deterministically.

    The aggregate state is never asked for and never asserted: it is computed
    from the proposition states through the authored expression, which is what
    makes "models never perform Boolean aggregation" a property of the code.
    """
    assessments = tuple(
        assess_proposition(
            proposition,
            criterion=criterion,
            timeline=timeline,
            trial=trial,
            model=model,
            verifier_feedback=verifier_feedback,
        )
        for proposition in criterion.propositions
    )
    states = {assessment.proposition_id: assessment.state for assessment in assessments}
    return AssessedCriterion(
        criterion_id=criterion.criterion_id,
        polarity=criterion.polarity,
        propositions=assessments,
        aggregation=aggregate(criterion.expression, states),
    )


class _Context:
    """One proposition's working state: what has been called, and what it cost."""

    def __init__(
        self,
        proposition: AtomicProposition,
        criterion: EligibilityCriterion,
        timeline: PatientTimeline,
        trial: TrialRecord,
        model: ModelClient,
        evidence: TrialEvidence,
        verifier_feedback: bool,
    ) -> None:
        self.proposition = proposition
        self.criterion = criterion
        self.timeline = timeline
        self.trial = trial
        self.model = model
        self.evidence = evidence
        self.verifier_feedback = verifier_feedback
        self.calls: list[ToolCall] = []
        self.computations: list[str] = []
        self.measurements = Measurements()
        self.verification: list[VerifierOutcome] = []

    def ask(self, purpose: ModelPurpose, prompt: str, *, attempt: int = 1) -> str:
        response = self.model.complete(
            ModelRequest(
                purpose=purpose,
                criterion_id=self.criterion.criterion_id,
                proposition_id=self.proposition.proposition_id,
                attempt=attempt,
                prompt=prompt,
            )
        )
        self.measurements = Measurements.summed((self.measurements, response.measurements))
        return response.json_text

    def unknown(
        self, reason: UnknownReason, *, facts: Sequence[CitableFact] = ()
    ) -> UnknownAssessment:
        """An `unknown` with the facts that explain it, where there are any.

        `conflicting_evidence` cites the results that disagree and
        `unusable_status` cites the disqualified one, because a coordinator
        reading either needs to know which record to go and look at.
        """
        evidence = (
            (
                PatientEvidence(
                    facts=tuple(_reference(fact) for fact in facts),
                    relation=EvidenceRelation.SUPPORTS,
                ),
            )
            if facts
            else ()
        )
        return UnknownAssessment(
            proposition_id=self.proposition.proposition_id,
            category=self.proposition.category,
            trial_evidence=self.evidence,
            tool_calls=tuple(self.calls),
            verification=tuple(self.verification),
            reason=reason,
            patient_evidence=evidence,
            measurements=self.measurements,
        )


def _select(context: _Context) -> _Selection:
    """Ask which lookup answers this proposition, and whether to compare.

    A category with one legal lookup is not put to the model: there is no choice
    to make, and asking would spend a call to be told the only answer.
    """
    lookups = LOOKUPS_BY_CATEGORY[context.proposition.category]
    if len(lookups) == 1:
        return _Selection(lookup=lookups[0])
    prompt = tool_selection_prompt(
        context.proposition, context.criterion, [tool.value for tool in lookups]
    )
    raw = context.ask(ModelPurpose.TOOL_SELECTION, prompt)
    selection = _parse(_Selection, raw)
    if selection.lookup not in lookups:
        msg = f"{selection.lookup.value} cannot answer a {context.proposition.category.value}"
        raise MalformedAnswerError(msg)
    return selection


def _look_up(context: _Context, lookup: LookupTool) -> ToolResult:
    """Run the chosen lookup and record the call in the trace."""
    proposition = context.proposition
    concept = proposition.concept or ""
    result: ToolResult
    match lookup:
        case LookupTool.FACTS:
            result = find_patient_facts(
                context.timeline, category=proposition.category, concept=concept
            )
            arguments: Mapping[str, str | float | bool | None] = {
                "category": proposition.category.value,
                "concept": concept,
            }
        case LookupTool.LATEST:
            result = get_latest_observation(context.timeline, concept=concept)
            arguments = {"concept": concept, "as_of": context.timeline.assessment_as_of.isoformat()}
        case LookupTool.EXPOSURE:
            result = find_medication_exposure(
                context.timeline, concept=concept, window=proposition.window
            )
            arguments = {
                "concept": concept,
                "window_days": (
                    proposition.window.duration.days if proposition.window is not None else None
                ),
            }
    context.calls.append(record(lookup.value, arguments, result))
    return result


def _compare(
    context: _Context, selection: _Selection, facts: Sequence[CitableFact]
) -> Comparison | None:
    """Run the comparison the model named, on the value the record holds."""
    if selection.comparison is None or not facts:
        return None
    first = facts[0]
    value = first.value if isinstance(first, TimelineFact) else None
    if value is None:
        return None
    comparison = compare_numeric(
        value,
        operator=selection.comparison.operator,
        threshold=selection.comparison.threshold,
        unit=selection.comparison.unit,
    )
    context.calls.append(
        record(
            "compare_numeric",
            {
                "operator": selection.comparison.operator.value,
                "threshold": selection.comparison.threshold,
                "unit": selection.comparison.unit,
            },
            comparison,
        )
    )
    context.computations.append(f"{comparison.compared} -> {comparison.verdict.value}")
    return comparison


def _answer(
    context: _Context, facts: Sequence[CitableFact], comparison: Comparison | None
) -> PropositionAssessment:
    """Ask the model, check the answer, and allow exactly one correction."""
    prompt = assessment_prompt(context.proposition, context.criterion, facts, context.computations)
    raw = context.ask(ModelPurpose.ASSESSMENT, prompt)
    try:
        answer = _parse(_Answer, raw)
    except MalformedAnswerError as error:
        return _correct(context, facts, raw, f"the answer did not match the schema: {error}")

    if _disagrees(answer.state, comparison):
        return context.unknown(UnknownReason.REASONING_CONFLICT, facts=facts)

    proposal = _proposal(context, answer, facts)
    if not context.verifier_feedback:
        return _assessment(context, answer, proposal)
    outcome = verify(proposal, timeline=context.timeline, trial=context.trial)
    context.verification.append(outcome)
    if outcome.verdict is VerifierVerdict.ACCEPTED:
        return _assessment(context, answer, proposal)
    return _correct(context, facts, raw, outcome.detail or "the citation could not be verified")


def _correct(
    context: _Context, facts: Sequence[CitableFact], previous: str, detail: str
) -> PropositionAssessment:
    """The one targeted correction of section 8.1, and what follows a second failure."""
    prompt = correction_prompt(
        context.proposition, context.criterion, facts, context.computations, previous, detail
    )
    raw = context.ask(ModelPurpose.CORRECTION, prompt, attempt=2)
    try:
        answer = _parse(_Answer, raw)
    except MalformedAnswerError as error:
        raise ModelUnavailableError(
            InfrastructureFailure(
                kind=FailureKind.MODEL_UNAVAILABLE,
                detail=(f"no schema-valid answer after one recorded retry: {error}"),
                where=context.criterion.criterion_id,
            )
        ) from error

    proposal = _proposal(context, answer, facts)
    outcome = verify(proposal, timeline=context.timeline, trial=context.trial)
    context.verification.append(outcome)
    if outcome.verdict is VerifierVerdict.ACCEPTED:
        return _assessment(context, answer, proposal)
    return _failed_verification(context)


def _failed_verification(context: _Context) -> UnknownAssessment:
    """Two rejections, so the assessment is `unknown` and says why.

    The reason replaces whatever the evidence would have explained: stage 3 of
    section 8.0. What the record held stopped being the account of this answer
    the moment the answer could not be verified twice.
    """
    return context.unknown(assign_unknown_reason(outcome=AgentOutcome.VERIFICATION_FAILED_TWICE))


def _assess_demographics(context: _Context) -> PropositionAssessment:
    """Age, computed by code from the recorded birth date.

    No lookup tool reaches the `Patient` resource, and no model call is needed
    for a comparison whose operands are both in the record: the birth date is
    there and the threshold is in the criterion the model would only be reading
    back. Doing it here keeps date arithmetic out of the model, which is the
    rule this whole loop is built around.
    """
    demographics = context.timeline.demographics
    if demographics.birth_date is None or demographics.birth_date_precision is None:
        return context.unknown(UnknownReason.MISSING_EVIDENCE)
    as_of = context.timeline.assessment_as_of
    age = _years_between(demographics.birth_date, as_of)
    context.computations.append(f"age at {as_of} is {age} years")
    reference = PatientFactReference(
        resource_type="Patient",
        resource_id=demographics.resource_id,
        json_path=demographics.json_path,
        clinical_time=demographics.birth_date,
        precision=demographics.birth_date_precision,
        status="active",
        code="21112-8",
        value=str(age),
        display=f"born {demographics.birth_date}",
    )
    prompt = assessment_prompt(context.proposition, context.criterion, (), context.computations)
    raw = context.ask(ModelPurpose.ASSESSMENT, prompt)
    answer = _parse(_Answer, raw)
    relation = (
        EvidenceRelation.SUPPORTS
        if answer.state is CriterionState.MET
        else EvidenceRelation.CONTRADICTS
    )
    evidence = (PatientEvidence(facts=(reference,), relation=relation),)
    record_type = _RECORD_BY_STATE[answer.state]
    return record_type(
        proposition_id=context.proposition.proposition_id,
        category=context.proposition.category,
        trial_evidence=context.evidence,
        tool_calls=tuple(context.calls),
        verification=tuple(context.verification),
        rationale=answer.rationale,
        measurements=context.measurements,
        patient_evidence=evidence,
    )


def _years_between(birth_date: dt.date, as_of: dt.date) -> int:
    """Whole years, the way an age is counted. Deterministic, and not the model's."""
    years = as_of.year - birth_date.year
    if (as_of.month, as_of.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


_RECORD_BY_STATE: dict[
    CriterionState, type[MetAssessment] | type[NotMetAssessment] | type[NotApplicableAssessment]
] = {
    CriterionState.MET: MetAssessment,
    CriterionState.NOT_MET: NotMetAssessment,
    CriterionState.NOT_APPLICABLE: NotApplicableAssessment,
}


def _assessment(
    context: _Context, answer: _Answer, proposal: ProposedAssessment
) -> PropositionAssessment:
    record_type = _RECORD_BY_STATE[answer.state]
    return record_type(
        proposition_id=context.proposition.proposition_id,
        category=context.proposition.category,
        trial_evidence=context.evidence,
        tool_calls=tuple(context.calls),
        verification=tuple(context.verification),
        rationale=proposal.rationale,
        measurements=context.measurements,
        patient_evidence=tuple(
            PatientEvidence(facts=citation.facts, relation=citation.relation)
            for citation in proposal.patient_evidence
            if citation.relation is not None
        ),
    )


def _proposal(
    context: _Context, answer: _Answer, facts: Sequence[CitableFact]
) -> ProposedAssessment:
    """Expand the model's fact ids into citations, from the record.

    A cited id the tools did not return is dropped rather than invented, which
    the verifier then sees as a state with no patient evidence.
    """
    by_id = {fact.fact_id: fact for fact in facts}
    citations: list[ProposedCitation] = []
    for citation in answer.citations:
        cited = tuple(by_id[fact_id] for fact_id in citation.fact_ids if fact_id in by_id)
        if not cited:
            continue
        citations.append(
            ProposedCitation(
                facts=tuple(_reference(fact) for fact in cited), relation=citation.relation
            )
        )
    return ProposedAssessment(
        proposition_id=context.proposition.proposition_id,
        state=answer.state,
        trial_evidence=context.evidence,
        patient_evidence=tuple(citations),
        rationale=answer.rationale,
    )


def _reference(fact: CitableFact) -> PatientFactReference:
    """One citation, written from the record rather than from the answer."""
    coding = fact.code if isinstance(fact, TimelineFact) else fact.medication
    value = fact.value if isinstance(fact, TimelineFact) else None
    return PatientFactReference(
        resource_type=fact.resource_type
        if isinstance(fact, TimelineFact)
        else "MedicationAdministration",
        resource_id=fact.resource_id,
        json_path=fact.json_path,
        clinical_time=fact.time.start if fact.time is not None else None,
        precision=fact.time.start_precision if fact.time is not None else None,
        status=fact.status,
        code=coding.code,
        value=_rendered(value) if value is not None else None,
        display=fact.display,
    )


def _rendered(value: QuantityValue | object) -> str:
    if isinstance(value, QuantityValue):
        return f"{value.comparator or ''}{value.value}{f' {value.unit}' if value.unit else ''}"
    return getattr(value, "text", str(value))


def _citable(result: ToolResult) -> tuple[CitableFact, ...]:
    """The facts an answer may be built on, which is not everything found."""
    match result:
        case FactQuery():
            return result.qualifying
        case LatestObservation():
            return (result.latest,) if result.latest is not None else ()
        case ExposureQuery():
            return result.matched


def _unusable(result: ToolResult) -> tuple[CitableFact, ...]:
    """The facts that explain an `unknown`, where the record holds any."""
    match result:
        case FactQuery():
            return result.disqualified
        case LatestObservation():
            return result.conflicting or result.disqualified
        case ExposureQuery():
            return result.disqualified or result.undecidable or result.outside_window


def _disagrees(state: CriterionState, comparison: Comparison | None) -> bool:
    """Deterministic computation against model interpretation (section 8.1).

    The comparison is the arithmetic, and the model does not get to overrule it.
    A disagreement is not resolved in either direction: it is `unknown` with
    `reasoning_conflict`, because one of the two is wrong and the run cannot say
    which.
    """
    if comparison is None:
        return False
    if comparison.verdict is Verdict.HOLDS:
        return state is CriterionState.NOT_MET
    if comparison.verdict is Verdict.FAILS:
        return state is CriterionState.MET
    return False


def _parse[T: Frozen](model: type[T], raw: str) -> T:
    """Schema validation, with no hidden retry behind it."""
    try:
        return model.model_validate_json(_json_object(raw))
    except ValidationError as error:
        raise MalformedAnswerError(str(error)) from error


def _json_object(raw: str) -> str:
    """The JSON object in a reply, tolerating a code fence around it.

    Tolerating the fence is not tolerating a wrong answer: the content still has
    to validate, and a reply with no object in it fails here.
    """
    text = raw.strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        msg = f"no JSON object in the reply: {raw[:120]!r}"
        raise MalformedAnswerError(msg)
    return text[start : end + 1]
