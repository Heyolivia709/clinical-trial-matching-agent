"""Patient Evidence and Trial Evidence: what an assessment stands on.

Specification sections 8 and 13. An assessment nobody can re-check is an
opinion, and handing a coordinator an opinion dressed as a finding is the
failure this project exists to avoid. These types carry the provenance half of
the evidence contract, and their fields are chosen for one job: letting the
Evidence Verifier of section 8.1 resolve a citation again, against the timeline
and the snapshot rather than against the assessment that made it.

A reference the verifier cannot re-resolve cannot be rejected either, which is
why every field the verifier compares is recorded here at citation time.
"""

from __future__ import annotations

import datetime as dt
from typing import Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import EvidenceRelation, TemporalPrecision


class PatientFactReference(Frozen):
    """Where one cited patient fact lives, and what it said when it was cited.

    Both halves are load-bearing. The resource identity and JSON path let the
    verifier find the fact again; the status, code, value, and Clinical Time let
    it notice that the citation disagrees with the fact it points at. Without
    the second half an altered value resolves perfectly and passes.

    `resource_type` is a plain string rather than the four evidence-bearing
    types of section 5. Narrowing it here would make the sixth verifier check of
    section 8.1 unwritable: a `MedicationRequest` cited as treatment exposure
    has to be constructible before anything can reject it, and the injected-fault
    demonstration of section 3 turns on exactly that citation.
    """

    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    json_path: str = Field(min_length=1)
    clinical_time: dt.date | None = None
    precision: TemporalPrecision | None = None
    status: str = Field(min_length=1)
    code: str = Field(min_length=1)
    value: str | None = None
    display: str = Field(min_length=1)
    """Derived from the source record, never written by the model.

    The report shows this beside the citation. A model-authored label here would
    be rationale wearing provenance's clothes, and section 8 keeps the two
    apart."""

    @model_validator(mode="after")
    def _dated_facts_declare_their_precision(self) -> Self:
        """Section 5.1 preserves source precision, so a date arrives with its own.

        A date recorded without its precision is indistinguishable from a
        day-precise one, and `insufficient_precision` stops being detectable.
        """
        if (self.clinical_time is None) != (self.precision is None):
            msg = "clinical_time and precision are declared together or not at all"
            raise ValueError(msg)
        return self


class PatientEvidence(Frozen):
    """One or more cited patient facts, and what they do to the proposition.

    The relation is a required field because "missing or unlabeled evidence
    relations" is a verifier rejection in section 8.1. A citation with no stated
    relation is a fact placed near a claim rather than evidence for it, and it
    reads as support to anyone skimming.
    """

    facts: tuple[PatientFactReference, ...] = Field(min_length=1)
    relation: EvidenceRelation
    reused_from_criterion_id: str | None = None
    """The criterion this evidence was first verified for, when the supervisor
    reused it (specification section 11). Reuse can propagate one bad reading
    across a trial, and reuse-induced error propagation is reported separately,
    which is only possible if the reused citations say so."""


class TrialEvidence(Frozen):
    """The exact trial source text a proposition was assessed against.

    Trial text is verbatim everywhere it appears (section 15.3), so this records
    the span as well as the text. The span is what makes the text checkable: a
    paraphrase that reads plausibly still fails against the snapshot, and a span
    that does not contain this text means the citation points somewhere else.
    """

    snapshot_id: str = Field(min_length=1)
    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    source_section: str = Field(min_length=1)
    criterion_ordinal: int = Field(ge=0)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    source_text: str = Field(min_length=1)
    """Verbatim, and possibly a sub-span of the criterion: a proposition may
    cite the phrase it covers rather than the whole criterion."""

    @model_validator(mode="after")
    def _span_is_well_formed(self) -> Self:
        if self.span_end <= self.span_start:
            msg = f"span_end must exceed span_start, got [{self.span_start}, {self.span_end})"
            raise ValueError(msg)
        if self.span_end - self.span_start != len(self.source_text):
            msg = (
                "span width does not match source_text length: "
                f"{self.span_end - self.span_start} vs {len(self.source_text)}"
            )
            raise ValueError(msg)
        return self
