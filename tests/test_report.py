"""The Trace Report: what the page must and must not contain.

Gate 5, specification section 15 and 15.1. The constraints here are the ones a
reader would not notice until the artifact fails them: a font fetched over the
network makes the page useless offline, colour keyed to Criterion State inverts
the meaning of an exclusion criterion, and a match percentage is a claim this
project does not make.
"""

from __future__ import annotations

import re

import pytest

from ctma.adapters.model import REPLAY_CONFIGURATION
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.transcripts import load_transcript
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.enums import Partition
from ctma.evaluation.lab import timeline_for
from ctma.match import match
from ctma.report.inputs import (
    DISCLAIMER,
    CountRow,
    FaultRow,
    InvariantRow,
    ReportInputs,
    ResultsSection,
)
from ctma.report.page import SECTIONS, render

TRIALS = load_trial_fixtures(Partition.DEVELOPMENT)
DEMONSTRATIVE = "NCT07349537:INC-2"


def built(transcript: str = "scn-01-development", scenario_id: str = "SCN-01") -> str:
    scenario = load_scenario_input(scenario_id)
    run = match(
        scenario_id=scenario_id,
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=TRIALS,
        model=load_transcript(transcript).replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id=transcript,
    )
    return render(
        ReportInputs(
            run=run,
            timeline=timeline_for(scenario_id),
            trials=TRIALS,
            demonstrative_criterion_id=DEMONSTRATIVE,
            plain_language="This system reads a patient's record and a trial's entry "
            "requirements and says, one requirement at a time, what the record supports.",
            faults=(
                FaultRow(
                    fault_id="F2",
                    intent="The right resource and the wrong number.",
                    cited="Observation/obs-ecog",
                    rejection="citation_disagrees_with_timeline",
                    detail="cites value '0.0 {score}' and the timeline holds '1.0 {score}'",
                ),
            ),
            results=ResultsSection(
                sample_sentence="120 propositions across 4 scenarios and 2 trials.",
                invariants=(InvariantRow(name="reference_validity", passed=True, detail="held"),),
                counts=(CountRow(label="Citation validity", agent="6 of 6", baseline="9 of 12"),),
            ),
        )
    )


PAGE = built()


def test_the_page_fetches_nothing_at_view_time() -> None:
    """The one hard constraint on the surface: it has to work offline."""
    for tag in ("<script", "<link", "<img", "@import", "url(http"):
        assert tag not in PAGE.lower(), f"{tag} would make the page depend on something"
    assert not re.search(r'(src|href)="https?://', PAGE)


def test_one_column_below_a_phone_width() -> None:
    """A two-column grid at 375px squeezes the text to about ten characters wide.

    Which makes the page unreadable on the device a reviewer is most likely to
    open a link on, and an unreadable page cannot be read in five minutes.
    """
    assert "@media (max-width: 52rem)" in PAGE
    collapsed = PAGE.split("@media (max-width: 52rem)")[1].split("}\n@media print")[0]
    assert "grid-template-columns: minmax(0, 1fr)" in collapsed
    assert "position: static" in collapsed, "a sticky index costs a phone a third of its screen"
    assert "flex-wrap: wrap" in collapsed, "ten stacked index lines push the verdict off screen one"
    assert "overflow-x: auto" in collapsed, "wide tables scroll rather than crushing the prose"


def test_print_styles_exist_and_the_disclaimer_survives_them() -> None:
    assert "@media print" in PAGE
    assert DISCLAIMER in PAGE
    assert ".disclaimer { border: 1px solid #000; }" in PAGE
    assert "details > summary { display: none; }" in PAGE, "print opens what the screen collapses"


def test_the_sections_are_in_verdict_first_order() -> None:
    """The claim comes before the setup, or the reader stops before reaching it."""
    positions = [PAGE.index(f'id="{key}"') for key, _ in SECTIONS]
    assert positions == sorted(positions)
    assert PAGE.index('id="s2"') < PAGE.index('id="s7"'), (
        "the worked criterion precedes the timeline"
    )
    assert PAGE.index('id="s4"') < PAGE.index('id="s10"'), "the comparison precedes the metadata"


def test_a_persistent_section_index_is_present_and_is_the_only_chrome() -> None:
    assert '<nav class="index"' in PAGE
    assert "position: sticky" in PAGE
    for chrome in ("breadcrumb", "back to", 'role="tablist"', "<header"):
        assert chrome not in PAGE.lower()


def test_no_score_percentage_gauge_or_rating_appears() -> None:
    for forbidden in ("match score", "progress bar", "gauge", "star rating", "confidence score"):
        assert forbidden not in PAGE.lower()
    assert "<progress" not in PAGE
    assert "<meter" not in PAGE
    assert not re.search(r"\d+(\.\d+)?\s*%?\s*(match|eligib|confiden)", PAGE, re.I)
    conclusions = {
        "Worth a coordinator's time",
        "Someone needs to check the chart",
        "A criterion rules this patient out",
    }
    assert any(phrase in PAGE for phrase in conclusions), (
        "the verdict vocabulary is three discrete labels, not a number"
    )


def test_colour_and_shape_encode_impact_and_never_state() -> None:
    """An exclusion criterion assessed `met` is bad news; green would invert it."""
    assert "--blocking" in PAGE
    assert "--unresolved" in PAGE
    for state in ("met", "not_met", "unknown", "not_applicable"):
        assert f'class="mark {state}"' not in PAGE
    assert 'class="mark satisfied"' in PAGE or 'class="mark unresolved"' in PAGE


def test_the_verifier_has_its_own_process_colour() -> None:
    """Sharing a colour with `blocking` would merge two different signals."""
    assert "--process" in PAGE
    assert 'class="verifier"' in PAGE
    assert "--process: #6b3fa0" in PAGE


def test_state_uses_the_specification_wording_with_the_enum_beside_it() -> None:
    assert "Supported" in PAGE
    assert "Contradicted" in PAGE
    assert "Not Supported" not in PAGE, "that reads contradiction and absence as the same thing"
    assert '<span class="enum">met</span>' in PAGE


def test_trial_source_text_is_verbatim() -> None:
    criterion = next(
        item for trial in TRIALS for item in trial.criteria if item.criterion_id == DEMONSTRATIVE
    )
    assert criterion.source_text in PAGE
    assert "Trial source text, verbatim" in PAGE


def test_retrieval_rank_and_review_priority_both_appear_and_stay_apart() -> None:
    assert "Retrieval rank" in PAGE
    assert "Review priority" in PAGE
    assert "never merged" in PAGE


def test_citations_name_the_json_path_and_the_trial_span() -> None:
    assert "entry[8].resource" in PAGE
    assert "82 to 153)" in PAGE, "the trial span is named beside the quoted text"


def test_sections_with_a_collapsed_state_ship_both_and_start_collapsed() -> None:
    collapsed = PAGE.count("<details>")
    assert collapsed >= 3, "per-trial tables and the timeline collapse by default"
    assert PAGE.count("<details open>") <= 1, "only the worked criterion's tool calls open"


def test_the_run_independent_section_says_it_is_not_about_this_run() -> None:
    section = PAGE.split('id="s8"')[1]
    assert "not a fact about the run above it" in section


def test_no_manifest_content_and_no_chain_of_thought_reach_the_page() -> None:
    """Structural: the report is rendered from records that hold neither."""
    for forbidden in ("design_intent", "distractor", "manifest", "chain of thought"):
        assert forbidden not in PAGE.lower()


@pytest.mark.parametrize(
    "goal",
    [
        "patient timeline",
        "candidate",
        "proposition",
        "tool call",
        "deterministic",
        "cites",
        "verifier",
        "baseline",
    ],
)
def test_every_demonstration_goal_of_section_three_is_on_the_page(goal: str) -> None:
    assert goal in PAGE.lower(), f"a reader cannot see {goal!r}"


def test_a_failing_run_is_reported_as_one() -> None:
    """Section 15 requires at least one report to cover a run that fails."""
    page = built(transcript="scn-04-failing", scenario_id="SCN-04")
    assert "verification_failed" in page
    assert "Caught in this run:" in page
