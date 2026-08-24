"""Closed vocabularies from the specification.

Every member here is named in the specification or in CONTEXT.md. Adding a
value is a specification change, not an implementation detail.
"""

from __future__ import annotations

from enum import StrEnum


class CriterionState(StrEnum):
    """Specification section 7. Independent of inclusion or exclusion polarity.

    `not_assessed` is deliberately absent: it is a reporting status for a
    criterion the supervisor skipped, not a state evidence can produce, and
    merging the two is prohibited.
    """

    MET = "met"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class ReportingStatus(StrEnum):
    """Whether a criterion was attempted at all. Orthogonal to CriterionState."""

    ASSESSED = "assessed"
    NOT_ASSESSED = "not_assessed"


class CriterionPolarity(StrEnum):
    INCLUSION = "inclusion"
    EXCLUSION = "exclusion"


class CriterionImpact(StrEnum):
    """Specification section 7.2. Derived from state and polarity, never asserted."""

    SATISFIED = "satisfied"
    BLOCKING = "blocking"
    UNRESOLVED = "unresolved"
    NEUTRAL = "neutral"


class MatchConclusion(StrEnum):
    """A screening workflow label, not a clinical eligibility decision."""

    POTENTIAL_MATCH = "potential_match"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    UNLIKELY_MATCH = "unlikely_match"


class CriterionCategory(StrEnum):
    """Specification section 6, five supported categories and one for the rest.

    `UNSUPPORTED` is a value rather than an absence of one. Without it a
    proposition outside the supported set has no legal category and acquires a
    misleading neighbouring one.
    """

    DEMOGRAPHIC = "demographic"
    DISEASE = "disease"
    BIOMARKER = "biomarker"
    PRIOR_THERAPY = "prior_therapy"
    PERFORMANCE_STATUS = "performance_status"
    UNSUPPORTED = "unsupported"


class UnknownReason(StrEnum):
    """Specification section 8.0, assigned by a deterministic table.

    `UNUSABLE_STATUS` and `INSUFFICIENT_PRECISION` are separate from
    `MISSING_EVIDENCE` on purpose. A disqualified fact, an imprecise date, and a
    concept nobody looked for are three different diagnoses, and collapsing them
    makes the failure taxonomy unable to tell planted hazards apart.
    """

    MISSING_EVIDENCE = "missing_evidence"
    UNUSABLE_STATUS = "unusable_status"
    INSUFFICIENT_PRECISION = "insufficient_precision"
    CONFLICTING_EVIDENCE = "conflicting_evidence"
    STALE_EVIDENCE = "stale_evidence"
    AMBIGUOUS_CRITERION = "ambiguous_criterion"
    UNSUPPORTED_EVIDENCE_TYPE = "unsupported_evidence_type"
    EXPRESSION_UNAVAILABLE = "expression_unavailable"
    VERIFICATION_FAILED = "verification_failed"
    REASONING_CONFLICT = "reasoning_conflict"


EVIDENCE_DERIVED_REASONS: frozenset[UnknownReason] = frozenset(
    {
        UnknownReason.MISSING_EVIDENCE,
        UnknownReason.UNUSABLE_STATUS,
        UnknownReason.INSUFFICIENT_PRECISION,
        UnknownReason.CONFLICTING_EVIDENCE,
        UnknownReason.STALE_EVIDENCE,
        UnknownReason.AMBIGUOUS_CRITERION,
        UnknownReason.UNSUPPORTED_EVIDENCE_TYPE,
    }
)
"""Reasons an authored scenario can produce. The remaining three arise from
configuration or injected faults and are covered by the Gate 3 fixtures
instead."""


class EvidenceRelation(StrEnum):
    """What cited Patient Evidence does to the proposition it is cited for.

    Section 8 requires the relation to be explicit, and section 8.1 rejects a
    citation that omits it. Two members and no third: "relevant" is not a
    relation, and a relevance score is what this deliberately is not.
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"


class CandidateStatus(StrEnum):
    """How far a Candidate Trial got: retained, presented, or assessed.

    One ordered vocabulary rather than two flags, because the states nest.
    Section 9 presents the candidates and assesses three of them, so "assessed
    but never presented" is not a state a run can be in — and with two
    independent booleans it would be.
    """

    RETAINED = "retained"
    PRESENTED = "presented"
    ASSESSED = "assessed"


class Partition(StrEnum):
    """Which half of the two-axis split an artifact belongs to.

    Held-out scenarios and trials stay frozen and must not influence prompts,
    models, tools, or supervisor configuration, so every run records
    which partition it ran on.
    """

    DEVELOPMENT = "development"
    HELD_OUT = "held_out"


class TemporalPrecision(StrEnum):
    """Source-supported granularity. Never widened to invent a finer instant."""

    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    INSTANT = "instant"


class ReviewStatus(StrEnum):
    """Nothing reaches a frozen artifact while still `DRAFTED`."""

    DRAFTED = "drafted"
    REVIEWED = "reviewed"
