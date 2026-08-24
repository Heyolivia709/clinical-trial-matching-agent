"""The four frozen Gate 1 trials.

These are real ClinicalTrials.gov records, so the tests are mostly about the
authoring holding up: every published criterion is represented, every quote is
verbatim, and the four together exercise every category and expression form the
system supports.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ctma.adapters import trial_fixtures
from ctma.adapters.trial_fixtures import FixtureError, load_trial_fixtures
from ctma.domain.aggregation import aggregate
from ctma.domain.enums import CriterionCategory, CriterionState, Partition, ReviewStatus
from ctma.domain.expression import (
    AllOf,
    AnyOf,
    Conditional,
    EligibilityCriterion,
    ExpressionNode,
    PropositionRef,
)
from ctma.domain.trial import TrialRecord

TRIALS = load_trial_fixtures()


def criteria() -> list[EligibilityCriterion]:
    return [criterion for trial in TRIALS for criterion in trial.criteria]


def forms(node: ExpressionNode) -> set[str]:
    """Every expression form used anywhere in one tree."""
    match node:
        case PropositionRef():
            return {"proposition"}
        case AllOf():
            return {"all_of"}.union(*(forms(child) for child in node.children))
        case AnyOf():
            return {"any_of"}.union(*(forms(child) for child in node.children))
        case Conditional():
            return {"conditional"} | forms(node.antecedent) | forms(node.consequent)


def bullets(trial: TrialRecord) -> list[str]:
    """The criterion lines as ClinicalTrials.gov published them."""
    return [
        line.strip().removeprefix("* ")
        for line in trial.eligibility_source_text.splitlines()
        if line.strip().startswith("* ")
    ]


def test_four_trials_are_frozen_two_development_and_two_held_out() -> None:
    assert len(TRIALS) == 4
    partitions = [trial.partition for trial in TRIALS]
    assert partitions.count(Partition.DEVELOPMENT) == 2
    assert partitions.count(Partition.HELD_OUT) == 2


def test_every_published_criterion_has_a_record() -> None:
    """The count is the point: a criterion nobody authored would be missing here.

    Criteria outside the supported categories are authored as `unsupported`
    rather than dropped, so this holds for all of them and not only the
    assessable ones.
    """
    for trial in TRIALS:
        authored = {criterion.source_text for criterion in trial.criteria}
        missing = [line for line in bullets(trial) if line not in authored]
        assert not missing, f"{trial.nct_id} has unauthored criteria: {missing}"
        assert len(trial.criteria) == len(bullets(trial))


def test_every_criterion_quotes_its_source_verbatim() -> None:
    for trial in TRIALS:
        for criterion in trial.criteria:
            quoted = trial.eligibility_source_text[criterion.span_start : criterion.span_end]
            assert quoted == criterion.source_text


def test_the_four_cover_all_five_supported_categories() -> None:
    used = {
        proposition.category for criterion in criteria() for proposition in criterion.propositions
    }
    assert used == set(CriterionCategory)


def test_the_two_development_trials_cover_them_too() -> None:
    """Held-out trials stay frozen, so development work cannot depend on them."""
    used = {
        proposition.category
        for trial in TRIALS
        if trial.partition is Partition.DEVELOPMENT
        for criterion in trial.criteria
        for proposition in criterion.propositions
    }
    assert used == set(CriterionCategory)


def test_the_four_cover_every_supported_expression_form() -> None:
    used = set[str]().union(*(forms(criterion.expression) for criterion in criteria()))
    assert used == {"proposition", "all_of", "any_of", "conditional"}


def test_a_conditional_criterion_can_produce_not_applicable() -> None:
    """A patient who never had adjuvant therapy is not held to its washout."""
    conditionals = [
        criterion for criterion in criteria() if isinstance(criterion.expression, Conditional)
    ]
    assert conditionals
    criterion = conditionals[0]
    expression = criterion.expression
    assert isinstance(expression, Conditional)
    assert isinstance(expression.antecedent, PropositionRef)
    states = {
        proposition.proposition_id: CriterionState.UNKNOWN for proposition in criterion.propositions
    }
    states[expression.antecedent.proposition_id] = CriterionState.NOT_MET
    assert aggregate(criterion.expression, states).state is CriterionState.NOT_APPLICABLE


def test_every_expression_is_reviewed_and_says_who_drafted_it() -> None:
    for criterion in criteria():
        assert criterion.provenance.review_status is ReviewStatus.REVIEWED
        assert criterion.provenance.reviewed_by
        assert criterion.provenance.drafted_by


def test_unsupported_propositions_are_authored_rather_than_omitted() -> None:
    """Organ function, RECIST, and consent are all out of scope and all present."""
    unsupported = [
        proposition
        for criterion in criteria()
        for proposition in criterion.propositions
        if proposition.category is CriterionCategory.UNSUPPORTED
    ]
    assert len(unsupported) >= 10
    assert all(proposition.concept is None for proposition in unsupported)


def test_a_criterion_that_paraphrases_its_source_fails_to_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard that keeps "verbatim" from decaying into "close enough"."""
    original = json.loads((trial_fixtures.FIXTURES / "NCT07185997.json").read_text())
    original["criteria"][1]["source_text"] = "Documented EGFR PACC mutation."
    directory = tmp_path / "trials"
    directory.mkdir()
    (directory / "NCT07185997.json").write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(trial_fixtures, "FIXTURES", directory)

    with pytest.raises(FixtureError, match="not in the eligibility text verbatim"):
        load_trial_fixtures()


def test_an_edited_eligibility_text_needs_a_new_review() -> None:
    """The hash ties the review to a wording, so a quiet edit fails loudly."""
    trial = TRIALS[0]
    with pytest.raises(ValidationError, match="does not hash to"):
        TrialRecord.model_validate(
            trial.model_dump()
            | {"eligibility_source_text": trial.eligibility_source_text + " and one more thing"}
        )


def test_a_criterion_from_another_trial_is_refused() -> None:
    trial = TRIALS[0]
    borrowed = trial.criteria[0].model_dump() | {"criterion_id": "NCT09999999:INC-1"}
    with pytest.raises(ValidationError, match="is not a criterion of"):
        TrialRecord.model_validate(trial.model_dump() | {"criteria": [borrowed]})


def test_records_round_trip_through_json_without_loss() -> None:
    for trial in TRIALS:
        assert TrialRecord.model_validate_json(trial.model_dump_json()) == trial


def test_the_one_criterion_counting_from_study_treatment_declares_its_substitution() -> None:
    """Section 5.1: an anchor the record cannot supply is substituted at
    authoring time, with a rationale, or the proposition is `ambiguous_criterion`.

    NCT07185997's twelve-month treatment-free interval is counted from the start
    of study treatment, which has not happened at screening. It read as an
    ordinary window until the anchor rule was implemented, which is exactly the
    silent substitution the section prohibits.
    """
    criterion = next(
        item
        for trial in TRIALS
        for item in trial.criteria
        if item.criterion_id == "NCT07185997:INC-4"
    )
    window = criterion.propositions[1].window
    assert window is not None
    assert window.source_anchor_text is not None
    assert window.anchor_substitution is not None
    assert window.anchor_substitution.rationale
    assert window.anchor_is_resolvable
