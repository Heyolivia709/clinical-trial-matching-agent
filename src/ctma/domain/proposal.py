"""What the model hands back, before anything has been checked.

Specification section 8.1. A Proposed Assessment is schema-valid and nothing
more: the state the model chose, the citations it offered, and the trial text it
read. It is not a Proposition Assessment, and the distance between the two is
the verifier.

The separate type is what makes the verifier's rejections representable. A
`MetAssessment` cannot be constructed without patient evidence, and a
`PatientEvidence` cannot be constructed without a relation — which is the right
guarantee for a finished artifact and would make two of the eight checks of
section 8.1 impossible to write a fixture for. The one-shot baseline is under no
such constraint either: it returns whatever it returns, and grading it by a
weaker standard than the agent would be the confound the comparison exists to
avoid.
"""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import CriterionState, EvidenceRelation, UnknownReason
from ctma.domain.evidence import PatientFactReference, TrialEvidence


class ProposedCitation(Frozen):
    """Cited patient facts and, if the model supplied one, their relation.

    `relation` is optional here and required on `PatientEvidence`. An unlabelled
    citation is a fact placed near a claim rather than evidence for it, and it
    reads as support to anyone skimming, so the verifier rejects it — but it has
    to be expressible for that rejection to be provable.
    """

    facts: tuple[PatientFactReference, ...] = Field(min_length=1)
    relation: EvidenceRelation | None = None


class ProposedAssessment(Frozen):
    """One model answer about one Atomic Proposition, as received."""

    proposition_id: str = Field(min_length=1)
    state: CriterionState
    reason: UnknownReason | None = None
    trial_evidence: TrialEvidence
    patient_evidence: tuple[ProposedCitation, ...] = ()
    rationale: str | None = None
    """Explanatory only, and never evidence (section 8)."""

    @model_validator(mode="after")
    def _a_reason_belongs_to_an_unknown(self) -> Self:
        """Shape, not grounding: a reason on a `met` is a malformed answer.

        The verifier checks citations against the record. This is the schema the
        model was asked to fill in, and a state carrying a diagnosis it cannot
        have is a failure to fill it in rather than a claim to check.
        """
        if (self.state is CriterionState.UNKNOWN) != (self.reason is not None):
            msg = "'unknown' carries a reason, and no other state carries one"
            raise ValueError(msg)
        return self
