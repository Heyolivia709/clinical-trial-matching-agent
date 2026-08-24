"""The five Timeline Tools, over the coverage Bundle.

Every tool is tested on its empty path and its ambiguous path, because those are
the two that decide whether an `unknown` gets the right reason later. The
terminology mapping is module-private, so it is exercised only through the tools.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from ctma.domain.enums import CriterionCategory, TemporalPrecision
from ctma.domain.expression import TemporalWindow
from ctma.domain.timeline import ClinicalInterval, CodedValue, PatientTimeline, QuantityValue
from ctma.domain.trace import ToolCall, ToolReturned
from ctma.timeline.build import build
from ctma.timeline.tools import (
    Comparison,
    Operator,
    Refusal,
    Verdict,
    check_temporal_window,
    compare_numeric,
    find_medication_exposure,
    find_patient_facts,
    get_latest_observation,
    record,
)
from tests.test_timeline import AS_OF, TIMELINE

BIOMARKER = CriterionCategory.BIOMARKER
DISEASE = CriterionCategory.DISEASE
THERAPY = CriterionCategory.PRIOR_THERAPY
PERFORMANCE = CriterionCategory.PERFORMANCE_STATUS

FOURTEEN_DAYS = TemporalWindow(duration=dt.timedelta(days=14))


def day(moment: dt.date) -> ClinicalInterval:
    return ClinicalInterval(start=moment, start_precision=TemporalPrecision.DAY)


# --- find_patient_facts ----------------------------------------------------


def test_facts_are_found_by_category_and_concept() -> None:
    found = find_patient_facts(TIMELINE, category=DISEASE, concept="NSCLC")
    assert [item.resource_id for item in found.qualifying] == ["cond-1"]
    assert found.disqualified == ()


def test_a_concept_the_mapping_does_not_cover_says_so() -> None:
    """Not the same as finding nothing: nothing was looked for.

    This is the difference between `ambiguous_criterion` and `missing_evidence`,
    and a tool that returned an empty list for both would erase it.
    """
    found = find_patient_facts(TIMELINE, category=BIOMARKER, concept="KRAS_G12V")
    assert found.mapped is False
    assert found.qualifying == ()


def test_a_concept_asked_for_under_the_wrong_category_is_not_answered() -> None:
    """Answering it anyway would hide an authoring mistake behind a real result."""
    assert find_patient_facts(TIMELINE, category=DISEASE, concept="ECOG_SCORE").mapped is False


def test_a_covered_concept_with_no_facts_returns_an_empty_result() -> None:
    """The empty path: mapped, looked for, and genuinely not there."""
    found = find_patient_facts(TIMELINE, category=DISEASE, concept="BRAIN_METASTASIS")
    assert found.mapped is True
    assert len(found.qualifying) == 1  # the year-precision brain metastasis
    nothing = find_patient_facts(TIMELINE, category=THERAPY, concept="EGFR_TKI")
    assert nothing.mapped is True
    assert nothing.qualifying == ()  # exposures are not facts


def test_a_disqualified_fact_is_reported_apart_from_the_usable_ones() -> None:
    """`entered-in-error` is a fact with a bad status, not a missing fact."""
    found = find_patient_facts(TIMELINE, category=BIOMARKER, concept="ALK_REARRANGEMENT")
    assert found.qualifying == ()
    assert [item.resource_id for item in found.disqualified] == ["obs-4"]


def test_a_superseded_fact_is_neither_qualifying_nor_disqualified() -> None:
    """The correction replaced it; the timeline keeps the link either way."""
    found = find_patient_facts(TIMELINE, category=BIOMARKER, concept="PD_L1_EXPRESSION")
    ids = {item.resource_id for item in (*found.qualifying, *found.disqualified)}
    assert "obs-1" not in ids
    assert "obs-2" in ids


# --- get_latest_observation ------------------------------------------------


def test_the_latest_qualifying_observation_wins() -> None:
    latest = get_latest_observation(TIMELINE, concept="PD_L1_EXPRESSION")
    assert latest.latest is not None
    assert latest.latest.resource_id == "obs-2"  # the correction, 2025-01-15
    assert isinstance(latest.latest.value, CodedValue)
    assert latest.latest.value.text == "Positive"


def test_two_results_at_one_time_that_disagree_are_reported_as_conflicting() -> None:
    """The ambiguous path. Picking one would be a coin toss with a citation."""
    latest = get_latest_observation(
        TIMELINE, concept="PD_L1_EXPRESSION", as_of=dt.date(2024, 12, 31)
    )
    assert latest.latest is None
    assert {item.resource_id for item in latest.conflicting} == {"obs-8", "obs-9"}


def test_a_result_after_the_asked_time_is_not_the_latest() -> None:
    assert (
        get_latest_observation(
            TIMELINE, concept="PD_L1_EXPRESSION", as_of=dt.date(2024, 1, 1)
        ).latest
        is None
    )


def test_only_a_disqualified_result_yields_no_observation_and_says_which() -> None:
    latest = get_latest_observation(TIMELINE, concept="ECOG_SCORE")
    assert latest.latest is None
    assert [item.resource_id for item in latest.disqualified] == ["obs-5"]


def test_an_unmapped_concept_is_distinguished_from_an_empty_record() -> None:
    assert get_latest_observation(TIMELINE, concept="PSA_LEVEL").mapped is False


# --- find_medication_exposure ---------------------------------------------


def test_documented_administrations_are_found_by_concept() -> None:
    found = find_medication_exposure(TIMELINE, concept="EGFR_TKI")
    assert {item.resource_id for item in found.matched} == {"medadmin-1", "medadmin-2"}
    assert found.orders_only is False


def test_an_exposure_outside_the_window_is_reported_apart_from_one_inside() -> None:
    """The precise course ended 2026-06-30, well before a 14-day window."""
    found = find_medication_exposure(TIMELINE, concept="EGFR_TKI", window=FOURTEEN_DAYS)
    assert [item.resource_id for item in found.outside_window] == ["medadmin-1"]
    assert [item.resource_id for item in found.undecidable] == ["medadmin-2"]
    assert found.matched == ()


ORDER_ONLY_BUNDLE = json.dumps(
    {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "patient-1", "gender": "female"}},
            {
                "resource": {
                    "resourceType": "MedicationRequest",
                    "id": "medreq-1",
                    "status": "active",
                    "intent": "order",
                    "medicationCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                                "code": "1721581",
                                "display": "osimertinib 80 MG Oral Tablet",
                            }
                        ]
                    },
                    "authoredOn": "2026-07-15",
                }
            },
        ],
    }
)


def test_an_order_with_no_administration_is_reported_as_an_order() -> None:
    """`unsupported_evidence_type`, not `missing_evidence`: the record has intent.

    The drug was prescribed and never documented as given. Reporting that as "no
    evidence for this drug" is the failure the verifier's sixth check exists to
    catch, and it starts here: the tool has to say which of the two it found.
    """
    timeline = build(ORDER_ONLY_BUNDLE, scenario_id="orders-only", assessment_as_of=AS_OF)
    orders = find_medication_exposure(timeline, concept="EGFR_TKI")
    assert orders.matched == ()
    assert orders.orders_only is True


def test_a_record_with_neither_an_exposure_nor_an_order_says_so() -> None:
    """The empty path, and the one that really is `missing_evidence`."""
    empty = json.dumps(
        {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "patient-1", "gender": "female"}}
            ],
        }
    )
    found = find_medication_exposure(
        build(empty, scenario_id="empty", assessment_as_of=AS_OF), concept="EGFR_TKI"
    )
    assert found.mapped is True
    assert found.matched == ()
    assert found.orders_only is False


def test_an_unmapped_drug_concept_is_not_an_empty_record() -> None:
    assert find_medication_exposure(TIMELINE, concept="PEMETREXED").mapped is False


# --- compare_numeric ------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "operator", "threshold", "expected"),
    [
        (1.0, Operator.LTE, 1.0, Verdict.HOLDS),
        (2.0, Operator.LTE, 1.0, Verdict.FAILS),
        (0.0, Operator.EQ, 0.0, Verdict.HOLDS),
        (1.0, Operator.EQ, 0.0, Verdict.FAILS),
        (22.0, Operator.GTE, 1.0, Verdict.HOLDS),
    ],
)
def test_a_plain_number_compares_exactly(
    value: float, operator: Operator, threshold: float, expected: Verdict
) -> None:
    assert compare_numeric(value, operator=operator, threshold=threshold).verdict is expected


def test_a_bound_decides_the_question_when_it_can() -> None:
    """ "< 0.5" is definitely not "at least 1.5", and refusing there is not humility."""
    anc = QuantityValue(value=0.5, unit="10*9/L", comparator="<")
    verdict = compare_numeric(anc, operator=Operator.GTE, threshold=1.5, unit="10*9/L")
    assert verdict.verdict is Verdict.FAILS
    assert verdict.refusal is None


def test_a_bound_that_straddles_the_threshold_is_refused() -> None:
    """ "< 0.5" against "at least 0.4" could be either. That is not a comparison."""
    anc = QuantityValue(value=0.5, unit="10*9/L", comparator="<")
    result = compare_numeric(anc, operator=Operator.GTE, threshold=0.4, unit="10*9/L")
    assert result.verdict is Verdict.REFUSED
    assert result.refusal is Refusal.BOUND_STRADDLES_THE_THRESHOLD


def test_a_bound_can_also_hold() -> None:
    anc = QuantityValue(value=0.5, unit="10*9/L", comparator="<")
    assert (
        compare_numeric(anc, operator=Operator.LT, threshold=1.5, unit="10*9/L").verdict
        is Verdict.HOLDS
    )


def test_a_comparison_across_units_is_refused_rather_than_converted() -> None:
    """Section 5.2 puts unit conversion out of scope, so this is not a shortfall."""
    anc = QuantityValue(value=0.5, unit="10*9/L", comparator="<")
    result = compare_numeric(anc, operator=Operator.GTE, threshold=1500, unit="/uL")
    assert result.verdict is Verdict.REFUSED
    assert result.refusal is Refusal.UNIT_MISMATCH


def test_a_criterion_that_states_no_unit_compares_against_a_score() -> None:
    """ECOG has no unit worth matching, and refusing every score would be silly."""
    ecog = QuantityValue(value=1.0, unit="{score}")
    assert compare_numeric(ecog, operator=Operator.LTE, threshold=1).verdict is Verdict.HOLDS


def test_a_qualitative_value_is_never_turned_into_a_number() -> None:
    result = compare_numeric(CodedValue(text="Positive"), operator=Operator.GTE, threshold=1.0)
    assert result.verdict is Verdict.REFUSED
    assert result.refusal is Refusal.VALUE_IS_NOT_NUMERIC


def test_the_comparison_records_what_it_compared() -> None:
    """The trace shows the comparison, so a reader can redo it by hand."""
    anc = QuantityValue(value=0.5, unit="10*9/L", comparator="<")
    result = compare_numeric(anc, operator=Operator.GTE, threshold=1.5, unit="10*9/L")
    assert result.compared == "<0.5 10*9/L >= 1.5 10*9/L"


# --- check_temporal_window ------------------------------------------------


def test_an_event_inside_the_window_holds() -> None:
    check = check_temporal_window(day(dt.date(2026, 8, 20)), anchor=AS_OF, window=FOURTEEN_DAYS)
    assert check.verdict is Verdict.HOLDS
    assert (check.window_start, check.window_end) == (dt.date(2026, 8, 10), AS_OF)


def test_an_event_before_the_window_fails() -> None:
    assert (
        check_temporal_window(day(dt.date(2026, 6, 30)), anchor=AS_OF, window=FOURTEEN_DAYS).verdict
        is Verdict.FAILS
    )


def test_endpoints_are_inclusive_unless_the_criterion_says_otherwise() -> None:
    """Section 5.1. Both ends, and the exclusive reading has to be authored."""
    edge = day(dt.date(2026, 8, 10))
    assert check_temporal_window(edge, anchor=AS_OF, window=FOURTEEN_DAYS).verdict is Verdict.HOLDS
    exclusive = TemporalWindow(duration=dt.timedelta(days=14), endpoints_inclusive=False)
    assert check_temporal_window(edge, anchor=AS_OF, window=exclusive).verdict is Verdict.FAILS
    assert (
        check_temporal_window(day(AS_OF), anchor=AS_OF, window=exclusive).verdict is Verdict.FAILS
    )


def test_a_year_only_date_that_straddles_the_window_is_refused() -> None:
    """The flagship case: "2026" could be inside the last 14 days or not."""
    coarse = ClinicalInterval(start=dt.date(2026, 1, 1), start_precision=TemporalPrecision.YEAR)
    check = check_temporal_window(coarse, anchor=AS_OF, window=FOURTEEN_DAYS)
    assert check.verdict is Verdict.REFUSED
    assert check.refusal is Refusal.PRECISION_TOO_COARSE


def test_a_year_only_date_far_from_the_window_still_decides() -> None:
    """Refusing here would manufacture uncertainty. All of 2020 is outside."""
    coarse = ClinicalInterval(start=dt.date(2020, 1, 1), start_precision=TemporalPrecision.YEAR)
    assert (
        check_temporal_window(coarse, anchor=AS_OF, window=FOURTEEN_DAYS).verdict is Verdict.FAILS
    )


def test_a_month_precision_date_is_read_as_the_whole_month() -> None:
    coarse = ClinicalInterval(start=dt.date(2026, 8, 1), start_precision=TemporalPrecision.MONTH)
    assert (
        check_temporal_window(coarse, anchor=AS_OF, window=FOURTEEN_DAYS).verdict is Verdict.REFUSED
    )


def test_the_window_is_placed_against_the_end_of_an_exposure() -> None:
    """Section 5.3: a washout counts from when the exposure stopped."""
    course = ClinicalInterval(
        start=dt.date(2025, 2, 1),
        start_precision=TemporalPrecision.DAY,
        end=dt.date(2026, 8, 15),
        end_precision=TemporalPrecision.DAY,
    )
    assert check_temporal_window(course, anchor=AS_OF, window=FOURTEEN_DAYS).verdict is (
        Verdict.HOLDS
    )


def test_an_event_with_no_clinical_time_is_refused_and_says_so() -> None:
    check = check_temporal_window(None, anchor=AS_OF, window=FOURTEEN_DAYS)
    assert check.verdict is Verdict.REFUSED
    assert check.refusal is Refusal.NO_CLINICAL_TIME


# --- recording and immutability -------------------------------------------


def test_a_call_and_its_result_become_one_trace_record() -> None:
    """Section 14 records tool calls with their arguments and their results."""
    result = compare_numeric(1.0, operator=Operator.LTE, threshold=1.0)
    call = record("compare_numeric", {"value": 1.0, "operator": "<=", "threshold": 1.0}, result)
    assert isinstance(call.outcome, ToolReturned)
    assert json.loads(call.arguments_json)["operator"] == "<="
    assert Comparison.model_validate_json(call.outcome.result_json) == result
    assert ToolCall.model_validate_json(call.model_dump_json()) == call


def test_no_tool_changes_the_timeline() -> None:
    """Read-only, checked rather than asserted in a docstring."""
    before = TIMELINE.model_dump_json()
    find_patient_facts(TIMELINE, category=DISEASE, concept="NSCLC")
    get_latest_observation(TIMELINE, concept="PD_L1_EXPRESSION")
    find_medication_exposure(TIMELINE, concept="EGFR_TKI", window=FOURTEEN_DAYS)
    assert TIMELINE.model_dump_json() == before
    assert PatientTimeline.model_validate_json(before) == TIMELINE
