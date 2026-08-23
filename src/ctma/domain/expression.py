"""Authored Criterion Expressions.

Specification sections 4.3, 5.1 and 6, and ADR 0001 and ADR 0004. The source
criterion text stays authoritative; the expression is a tree over Atomic
Propositions laid beside it, never a replacement for it.

Propositions are declared once on the criterion and referenced by id from the
tree. A proposition can therefore appear in two branches without being
described twice, and an assessment always has one identity to attach to.
"""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ctma.domain.enums import CriterionCategory, CriterionPolarity, ReviewStatus


class Frozen(BaseModel):
    """Immutable, closed to unknown fields, and validated on assignment.

    Authored artifacts are versioned and frozen by the specification, so
    mutability is a defect rather than a convenience. `extra="forbid"` means a
    typo in an authored JSON file fails loudly instead of being dropped.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


class AuthoringProvenance(Frozen):
    """Who drafted an artifact, who reviewed it, and whether review finished.

    Specification section 17 permits AI drafting and requires human review
    before freezing, with both recorded.
    """

    drafted_by: str = Field(min_length=1)
    ai_assisted: bool
    reviewed_by: str | None = None
    reviewed_on: dt.date | None = None
    review_status: ReviewStatus = ReviewStatus.DRAFTED

    @model_validator(mode="after")
    def _reviewed_artifacts_name_their_reviewer(self) -> Self:
        if self.review_status is ReviewStatus.REVIEWED and (
            self.reviewed_by is None or self.reviewed_on is None
        ):
            msg = "review_status 'reviewed' requires both reviewed_by and reviewed_on"
            raise ValueError(msg)
        return self


class AnchorSubstitution(Frozen):
    """An authored replacement for an anchor that cannot exist at screening.

    Specification section 5.1. "Within 14 days prior to the first dose of study
    drug" names an anchor the patient record cannot supply, because the event
    has not happened. Substituting the assessment time is the right proxy and
    the wrong thing to do silently, so it is declared once here, carries its
    rationale, and is displayed beside the criterion. The model never selects
    an anchor; a proposition needing one without this declaration resolves to
    `unknown` with `ambiguous_criterion`.
    """

    source_anchor_text: str = Field(min_length=1)
    substituted_with: Literal["assessment_as_of"] = "assessment_as_of"
    rationale: str = Field(min_length=1)


class TemporalWindow(Frozen):
    """A relative window, anchored to the assessment time unless substituted."""

    duration: dt.timedelta
    anchor_substitution: AnchorSubstitution | None = None
    endpoints_inclusive: bool = True


class AtomicProposition(Frozen):
    """The smallest independently assessable statement in an expression.

    Carries no expected state. Expected states are derived by the Evaluation
    Lab from the hidden Scenario Manifest, never authored here.
    """

    proposition_id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    category: CriterionCategory
    concept: str | None = None
    window: TemporalWindow | None = None

    @model_validator(mode="after")
    def _unsupported_propositions_carry_no_machinery(self) -> Self:
        """An unsupported proposition resolves to `unknown` without being assessed.

        Giving it a concept or a window implies a comparison that will never run,
        and would let an authored artifact promise more than the system does.
        """
        if self.category is CriterionCategory.UNSUPPORTED and (
            self.concept is not None or self.window is not None
        ):
            msg = "an 'unsupported' proposition must not declare a concept or a window"
            raise ValueError(msg)
        return self


class PropositionRef(Frozen):
    """A leaf: the truth of one Atomic Proposition."""

    kind: Literal["proposition"] = "proposition"
    proposition_id: str = Field(min_length=1)


class AllOf(Frozen):
    kind: Literal["all_of"] = "all_of"
    children: tuple[ExpressionNode, ...] = Field(min_length=1)


class AnyOf(Frozen):
    kind: Literal["any_of"] = "any_of"
    children: tuple[ExpressionNode, ...] = Field(min_length=1)


class Conditional(Frozen):
    """If the antecedent holds, the consequent decides; if not, `not_applicable`."""

    kind: Literal["conditional"] = "conditional"
    antecedent: ExpressionNode
    consequent: ExpressionNode


ExpressionNode = Annotated[
    PropositionRef | AllOf | AnyOf | Conditional,
    Field(discriminator="kind"),
]
"""The supported expression forms of specification section 6, and only those."""


class EligibilityCriterion(Frozen):
    """A source-aligned criterion with the expression authored beside it.

    `source_text` is verbatim and is never rewritten, truncated, or paraphrased;
    `span` locates it in the snapshot payload so a citation can be checked
    against the source rather than against this copy.
    """

    criterion_id: str = Field(min_length=1)
    polarity: CriterionPolarity
    source_section: str = Field(min_length=1)
    ordinal: int = Field(ge=0)
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)
    source_text: str = Field(min_length=1)

    expression_version: str = Field(min_length=1)
    propositions: tuple[AtomicProposition, ...] = Field(min_length=1)
    expression: ExpressionNode
    provenance: AuthoringProvenance

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

    @model_validator(mode="after")
    def _proposition_ids_are_unique(self) -> Self:
        seen: set[str] = set()
        for proposition in self.propositions:
            if proposition.proposition_id in seen:
                msg = f"duplicate proposition_id {proposition.proposition_id!r}"
                raise ValueError(msg)
            seen.add(proposition.proposition_id)
        return self

    @model_validator(mode="after")
    def _tree_and_propositions_agree(self) -> Self:
        """Every reference resolves, and every declared proposition is used.

        A dangling reference would assess nothing; an unreferenced proposition
        would be authored, reviewed, and then silently ignored. Both are
        authoring mistakes that are cheap to catch here and expensive to notice
        in a benchmark result.
        """
        declared = {proposition.proposition_id for proposition in self.propositions}
        referenced = _referenced_ids(self.expression)
        if dangling := referenced - declared:
            msg = f"expression references undeclared propositions: {sorted(dangling)}"
            raise ValueError(msg)
        if orphaned := declared - referenced:
            msg = f"propositions declared but never referenced: {sorted(orphaned)}"
            raise ValueError(msg)
        return self


def _referenced_ids(node: ExpressionNode) -> set[str]:
    match node:
        case PropositionRef():
            return {node.proposition_id}
        case AllOf() | AnyOf():
            return {ref for child in node.children for ref in _referenced_ids(child)}
        case Conditional():
            return _referenced_ids(node.antecedent) | _referenced_ids(node.consequent)
