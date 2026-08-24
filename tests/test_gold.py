"""Gold expected states, derived from the manifest and the authored expression.

Gate 4, specification section 20 and ADR 0005. What these tests hold is that
nothing here is a judgement: every expected state follows from an authored fact
and an authored predicate, and where it does not follow, the case says so
instead of guessing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.enums import CriterionCategory, CriterionState, Partition, UnknownReason
from ctma.domain.expression import AtomicProposition
from ctma.evaluation.cases import EvalCase, eval_cases
from ctma.evaluation.gold import ExpectedProposition, expected_criterion, expected_proposition
from ctma.evaluation.manifest import EXPECTED_REASON_BY_DISTRACTOR, DistractorKind
from ctma.evaluation.scenarios import load_scenario_manifest

DEVELOPMENT = eval_cases(Partition.DEVELOPMENT)
TRIALS = {trial.nct_id: trial for trial in load_trial_fixtures()}


def proposition_gold(
    scenario_id: str, nct_id: str, criterion_id: str, proposition_id: str
) -> ExpectedProposition:
    criterion = next(item for item in TRIALS[nct_id].criteria if item.criterion_id == criterion_id)
    proposition = next(
        item for item in criterion.propositions if item.proposition_id == proposition_id
    )
    return expected_proposition(proposition, manifest=load_scenario_manifest(scenario_id))


def case(scenario_id: str, nct_id: str) -> EvalCase:
    return next(
        item for item in DEVELOPMENT if item.scenario_id == scenario_id and item.nct_id == nct_id
    )


def test_gold_never_consults_the_reviewed_terminology_mapping() -> None:
    """Structural, because the alternative hides the gap the numbers exist to show.

    Gold matches facts by the concept the scenario author recorded. Deriving it
    through the same mapping the system queries with would make a concept the
    mapping does not cover agree with itself: the system reports
    `missing_evidence`, gold expects `missing_evidence`, and a coverage gap
    scores as a hit.
    """
    source = Path("src/ctma/evaluation/gold.py").read_text()
    assert "_terminology" not in source
    assert "codes_for" not in source


def test_gold_is_derived_from_authored_artifacts_and_not_from_a_run() -> None:
    """No timeline, no tool selection, no model: a manifest and an expression."""
    source = Path("src/ctma/evaluation/gold.py").read_text()
    for forbidden in ("ModelClient", "assess_proposition", "PatientTimeline", "build("):
        assert forbidden not in source


@pytest.mark.parametrize(
    ("scenario_id", "criterion_id", "proposition_id", "kind"),
    [
        ("SCN-02", "NCT07185997:INC-2", "P1", DistractorKind.NEAR_MISS_CONCEPT),
        ("SCN-03", "NCT07349537:INC-2", "P2", DistractorKind.PRELIMINARY_RESULT),
        ("SCN-04", "NCT07349537:INC-2", "P1", DistractorKind.POST_ASSESSMENT_OBSERVATION),
        ("SCN-02", "NCT07349537:INC-2", "P1", DistractorKind.CONFLICTING_RESULTS),
    ],
)
def test_a_planted_hazard_derives_to_the_reason_it_was_planted_for(
    scenario_id: str, criterion_id: str, proposition_id: str, kind: DistractorKind
) -> None:
    """The same obligation the runtime has, on the grading side.

    If gold expected something else, every hazard would score as a miss however
    correctly the system behaved.
    """
    nct_id = criterion_id.split(":")[0]
    gold = proposition_gold(scenario_id, nct_id, criterion_id, proposition_id)
    assert gold.state is CriterionState.UNKNOWN
    assert gold.reason is EXPECTED_REASON_BY_DISTRACTOR[kind]


def test_a_disqualified_fact_is_unusable_status_and_is_still_named() -> None:
    """SCN-03's only ECOG is preliminary, and gold cites it.

    The citable set is what a correct `unknown` may point at, so a reason with
    nothing behind it would grade a citation of the withdrawn result as wrong.
    """
    gold = proposition_gold("SCN-03", "NCT07349537", "NCT07349537:INC-2", "P1")
    assert gold.reason is UnknownReason.UNUSABLE_STATUS
    assert gold.citable_fact_ids == ("Observation/obs-ecog-prelim",)


def test_two_results_that_disagree_are_conflicting_and_both_are_citable() -> None:
    gold = proposition_gold("SCN-02", "NCT07349537", "NCT07349537:INC-2", "P2")
    assert gold.reason is UnknownReason.CONFLICTING_EVIDENCE
    assert set(gold.citable_fact_ids) == {
        "Observation/obs-ecog-clinic",
        "Observation/obs-ecog-infusion",
    }


def test_the_authored_predicate_decides_met_from_not_met() -> None:
    """SCN-01's ECOG is 1: the `is 0` branch is not_met and the `is 1` branch is met."""
    assert proposition_gold("SCN-01", "NCT07349537", "NCT07349537:INC-2", "P1").state is (
        CriterionState.NOT_MET
    )
    assert proposition_gold("SCN-01", "NCT07349537", "NCT07349537:INC-2", "P2").state is (
        CriterionState.MET
    )
    assert case("SCN-01", "NCT07349537").criteria[1].state is CriterionState.MET


def test_a_proposition_with_facts_and_no_predicate_is_coverage_only() -> None:
    """SCN-01 records an ECOG of 1, and nothing says what satisfies the statement.

    Constructed here rather than taken from a fixture: every authored
    proposition that reaches a fact does state a predicate, which is the point
    of authoring them. What this holds is what happens to one that does not.
    """
    unstated = AtomicProposition(
        proposition_id="P9",
        statement="The performance status is acceptable",
        category=CriterionCategory.PERFORMANCE_STATUS,
        concept="ECOG_SCORE",
    )
    gold = expected_proposition(unstated, manifest=load_scenario_manifest("SCN-01"))
    assert gold.scorable is False
    assert gold.state is None
    assert gold.citable_fact_ids == ("Observation/obs-ecog",)
    assert gold.note is not None


def test_a_criterion_with_a_coverage_only_branch_cannot_be_aggregated() -> None:
    """Guessing the missing branch would put a label in through the back door."""
    criterion = next(
        item for item in TRIALS["NCT07349537"].criteria if item.criterion_id == "NCT07349537:INC-2"
    )
    stripped = criterion.model_copy(
        update={
            "propositions": (
                criterion.propositions[0].model_copy(update={"predicate": None}),
                criterion.propositions[1],
            )
        }
    )
    expected = expected_criterion(stripped, manifest=load_scenario_manifest("SCN-01"))
    assert expected.scorable is False
    assert expected.state is None
    assert [item.scorable for item in expected.propositions] == [False, True]


def test_nothing_in_the_development_set_is_coverage_only_today() -> None:
    """A count worth recording, because it is a property of the authoring.

    Every development proposition either reaches no fact — and derives to
    `missing_evidence` — or reaches one and has a predicate to read it with.
    """
    assert [item.coverage_only for item in DEVELOPMENT] == [() for _ in DEVELOPMENT]


def test_an_unsupported_proposition_expects_unsupported_evidence_type() -> None:
    gold = proposition_gold("SCN-01", "NCT07349537", "NCT07349537:INC-5", "P1")
    assert gold.state is CriterionState.UNKNOWN
    assert gold.reason is UnknownReason.UNSUPPORTED_EVIDENCE_TYPE


def test_the_development_half_is_four_scenarios_against_two_trials() -> None:
    assert len(DEVELOPMENT) == 8
    assert {item.scenario_id for item in DEVELOPMENT} == {"SCN-01", "SCN-02", "SCN-03", "SCN-04"}
    assert {item.nct_id for item in DEVELOPMENT} == {"NCT07185997", "NCT07349537"}


def test_a_development_scenario_against_a_held_out_trial_is_held_out() -> None:
    """The partition is the stricter of the two, whichever axis it came in on."""
    held_out = eval_cases(Partition.HELD_OUT)
    mixed = [item for item in held_out if item.scenario_partition is Partition.DEVELOPMENT]
    assert mixed, "the two-axis split has mixed pairs, and they are held out"
    assert all(item.trial_partition is Partition.HELD_OUT for item in mixed)
    assert len(held_out) == 24 - len(DEVELOPMENT)


def test_a_case_names_the_exact_inputs_it_was_derived_from() -> None:
    """Edited inputs make a different case rather than a contradictory one."""
    item = case("SCN-01", "NCT07349537")
    assert item.bundle_sha256 == load_scenario_manifest("SCN-01").bundle_sha256
    assert item.eligibility_sha256 == TRIALS["NCT07349537"].eligibility_sha256
    assert item.case_id == "SCN-01|NCT07349537"


def test_every_criterion_of_every_trial_is_present_in_its_case() -> None:
    """Coverage is counted from these, so a missing criterion would inflate it."""
    for item in DEVELOPMENT:
        assert len(item.criteria) == len(TRIALS[item.nct_id].criteria)
