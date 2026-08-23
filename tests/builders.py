"""Shared authored artifacts, so tests read as data rather than as setup."""

from __future__ import annotations

import datetime as dt

from ctma.domain.enums import CriterionCategory, CriterionPolarity, ReviewStatus
from ctma.domain.expression import (
    AllOf,
    AnchorSubstitution,
    AtomicProposition,
    AuthoringProvenance,
    EligibilityCriterion,
    PropositionRef,
    TemporalWindow,
)

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
