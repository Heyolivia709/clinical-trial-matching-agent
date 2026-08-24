"""The Trial Record: one trial as one snapshot captured it.

Specification sections 4.1, 4.3 and 13. The record holds the trial metadata
retrieval ranks on, the verbatim eligibility text, and the source-aligned
criteria with their authored expressions.

The eligibility text is kept whole, and each criterion carries a span into it.
That is what makes a citation checkable: a report quotes the criterion, and the
span says where in the source that quote came from. A record holding only the
per-criterion strings would let a paraphrase in and nothing would notice.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Self

from pydantic import Field, model_validator

from ctma.domain.base import Frozen
from ctma.domain.enums import Partition
from ctma.domain.expression import EligibilityCriterion


class TrialRecord(Frozen):
    """One trial, frozen: metadata, eligibility text, and authored criteria."""

    nct_id: str = Field(pattern=r"^NCT\d{8}$")
    snapshot_record_id: str = Field(min_length=1)
    partition: Partition
    source_url: str = Field(min_length=1)

    overall_status: str = Field(min_length=1)
    study_type: str = Field(min_length=1)
    phases: tuple[str, ...] = ()
    last_update_posted: dt.date
    recruiting_countries: tuple[str, ...] = ()

    brief_title: str = Field(min_length=1)
    brief_summary: str = Field(min_length=1)
    conditions: tuple[str, ...] = Field(min_length=1)
    mesh_terms: tuple[str, ...] = ()
    interventions: tuple[str, ...] = ()

    eligibility_source_text: str = Field(min_length=1)
    eligibility_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    """The hash of the eligibility text as reviewed.

    It is recomputed on load, so it is not a copy of something derivable: it is
    what ties the review status below to a particular wording. Editing the text
    without a new review makes the record fail to load.

    Gate 1 fixtures freeze the eligibility text rather than the whole
    ClinicalTrials.gov payload. The full-payload hash arrives with the snapshot
    in Gate 3.
    """

    criteria: tuple[EligibilityCriterion, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _the_hash_matches_the_text_that_was_reviewed(self) -> Self:
        digest = hashlib.sha256(self.eligibility_source_text.encode()).hexdigest()
        if digest != self.eligibility_sha256:
            msg = (
                f"{self.nct_id}: the eligibility text does not hash to "
                f"{self.eligibility_sha256}. Re-review the text and record the new hash."
            )
            raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _every_criterion_quotes_the_source_exactly(self) -> Self:
        """The span has to slice the criterion's own text out of the source.

        This is the check that keeps "verbatim" honest. A criterion whose text
        was tidied up while authoring — a stray comma, a normalised dash — no
        longer matches the snapshot it claims to come from, and the citation in
        the report would point at text the trial never published.
        """
        for criterion in self.criteria:
            quoted = self.eligibility_source_text[criterion.span_start : criterion.span_end]
            if quoted != criterion.source_text:
                msg = (
                    f"{criterion.criterion_id}: the span holds {quoted!r}, "
                    f"not {criterion.source_text!r}"
                )
                raise ValueError(msg)
        return self

    @model_validator(mode="after")
    def _criteria_belong_to_this_trial_and_appear_once(self) -> Self:
        seen: set[str] = set()
        for criterion in self.criteria:
            if not criterion.criterion_id.startswith(f"{self.nct_id}:"):
                msg = f"{criterion.criterion_id} is not a criterion of {self.nct_id}"
                raise ValueError(msg)
            if criterion.criterion_id in seen:
                msg = f"duplicate criterion_id {criterion.criterion_id!r}"
                raise ValueError(msg)
            seen.add(criterion.criterion_id)
        return self
