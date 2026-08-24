"""Authored Criterion Expressions: round-tripping and authoring mistakes."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.domain.enums import CriterionCategory, ReviewStatus
from ctma.domain.expression import (
    AllOf,
    AnyOf,
    AtomicProposition,
    AuthoringProvenance,
    Conditional,
    EligibilityCriterion,
    PropositionRef,
)
from tests.builders import exc7


def test_round_trips_through_json_without_loss() -> None:
    """A Gate 1 exit criterion: no provenance field is dropped on the way."""
    original = exc7()
    restored = EligibilityCriterion.model_validate_json(original.model_dump_json())
    assert restored == original


def test_the_anchor_substitution_survives_the_round_trip() -> None:
    """The substitution is displayed beside the criterion, so it must persist."""
    restored = EligibilityCriterion.model_validate_json(exc7().model_dump_json())
    window = restored.propositions[1].window
    assert window is not None
    assert window.anchor_substitution is not None
    assert window.source_anchor_text == "the first dose of study drug"
    assert window.anchor_substitution.substituted_with == "assessment_as_of"


def test_criteria_are_immutable() -> None:
    with pytest.raises(ValidationError):
        exc7().propositions[0].statement = "something else"  # type: ignore[misc]


def test_a_dangling_reference_is_rejected() -> None:
    with pytest.raises(ValidationError, match="undeclared propositions"):
        EligibilityCriterion.model_validate(
            exc7().model_dump() | {"expression": {"kind": "proposition", "proposition_id": "P9"}}
        )


def test_a_proposition_nobody_references_is_rejected() -> None:
    """Authored, reviewed, and then silently never assessed is the failure here."""
    with pytest.raises(ValidationError, match="never referenced"):
        EligibilityCriterion.model_validate(
            exc7().model_dump() | {"expression": {"kind": "proposition", "proposition_id": "P1"}}
        )


def test_a_span_that_disagrees_with_the_text_is_rejected() -> None:
    with pytest.raises(ValidationError, match="span width"):
        EligibilityCriterion.model_validate(exc7().model_dump() | {"span_end": 1900})


def test_duplicate_proposition_ids_are_rejected() -> None:
    doubled = exc7().model_dump()
    doubled["propositions"] = (doubled["propositions"][0], doubled["propositions"][0])
    with pytest.raises(ValidationError, match="duplicate proposition_id"):
        EligibilityCriterion.model_validate(doubled)


def test_an_unsupported_proposition_declares_no_comparison() -> None:
    """It resolves to unknown without being assessed, so machinery would lie."""
    with pytest.raises(ValidationError, match="must not declare a concept"):
        AtomicProposition(
            proposition_id="P1",
            statement="Clinically significant interstitial lung disease",
            category=CriterionCategory.UNSUPPORTED,
            concept="ILD",
        )


def test_an_unsupported_proposition_is_otherwise_fine() -> None:
    proposition = AtomicProposition(
        proposition_id="P1",
        statement="Clinically significant interstitial lung disease",
        category=CriterionCategory.UNSUPPORTED,
    )
    assert proposition.category is CriterionCategory.UNSUPPORTED


def test_review_status_reviewed_requires_a_reviewer() -> None:
    with pytest.raises(ValidationError, match="requires both reviewed_by"):
        AuthoringProvenance(
            drafted_by="assistant", ai_assisted=True, review_status=ReviewStatus.REVIEWED
        )


def test_every_supported_expression_form_parses() -> None:
    """Specification section 6 lists exactly these, and the union admits no more."""
    forms = (
        PropositionRef(proposition_id="P1"),
        AllOf(children=(PropositionRef(proposition_id="P1"),)),
        AnyOf(children=(PropositionRef(proposition_id="P1"),)),
        Conditional(
            antecedent=PropositionRef(proposition_id="P1"),
            consequent=PropositionRef(proposition_id="P1"),
        ),
    )
    for form in forms:
        assert form.model_dump()["kind"] == form.kind


def test_an_unknown_expression_form_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EligibilityCriterion.model_validate(
            exc7().model_dump() | {"expression": {"kind": "none_of", "children": []}}
        )
