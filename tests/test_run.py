"""The Candidate Set and the Matching Run.

The run is the artifact that gets frozen, published, re-read, and re-graded, so
the tests here are mostly about two things: that nothing is lost on the way to
disk, and that the ranked set and the assessments cannot disagree about which
trials were looked at.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ctma.domain.assessment import UnexpressedCriterion
from ctma.domain.enums import CandidateStatus, CriterionPolarity, Partition, RetrievalChannel
from ctma.domain.run import CandidateSet, CandidateTrial, ChannelRank, MatchingRun
from ctma.domain.trace import Measurements
from tests.builders import (
    NCT,
    candidate,
    candidate_set,
    exc7_trial_assessment,
    exc7_trial_evidence,
    matching_run,
)


def test_a_candidate_set_keeps_the_ranking_as_its_order() -> None:
    candidates = candidate_set()
    assert [entry.retrieval_rank for entry in candidates.candidates] == [1, 2, 3]
    assert [entry.nct_id for entry in candidates.presented] == [NCT, "NCT05222222"]
    assert [entry.nct_id for entry in candidates.assessed] == [NCT]


def test_a_gap_in_the_ranking_is_refused() -> None:
    """A dropped candidate would otherwise be invisible: the set still looks ranked."""
    with pytest.raises(ValidationError, match="retrieval ranks must be"):
        CandidateSet(candidates=(candidate(NCT, 1), candidate("NCT05222222", 3)))


def test_a_ranking_out_of_order_is_refused() -> None:
    with pytest.raises(ValidationError, match="retrieval ranks must be"):
        CandidateSet(candidates=(candidate(NCT, 2), candidate("NCT05222222", 1)))


def test_one_trial_appears_once() -> None:
    with pytest.raises(ValidationError, match="appears twice"):
        CandidateSet(candidates=(candidate(NCT, 1), candidate(NCT, 2)))


def test_a_presented_candidate_below_a_retained_one_is_refused() -> None:
    """Presentation follows the rank. Anything else is a second, hidden ordering."""
    with pytest.raises(ValidationError, match="below a retained candidate"):
        CandidateSet(
            candidates=(
                candidate(NCT, 1, CandidateStatus.RETAINED),
                candidate("NCT05222222", 2, CandidateStatus.PRESENTED),
            )
        )


def test_a_channel_ranks_a_trial_once() -> None:
    """Two ranks from one channel means one of them is from somewhere else."""
    with pytest.raises(ValidationError, match="a channel appears twice"):
        CandidateTrial(
            nct_id=NCT,
            snapshot_record_id=f"snapshot:{NCT}",
            retrieval_rank=1,
            status=CandidateStatus.ASSESSED,
            channel_ranks=(
                ChannelRank(channel=RetrievalChannel.BM25, rank=1, score=12.5),
                ChannelRank(channel=RetrievalChannel.BM25, rank=4, score=9.0),
            ),
        )


def test_per_channel_provenance_survives_the_round_trip() -> None:
    """The report shows per-channel ranks and scores, and never a blended one."""
    restored = CandidateSet.model_validate_json(candidate_set().model_dump_json())
    channels = restored.candidates[0].channel_ranks
    assert [entry.channel for entry in channels] == [RetrievalChannel.BM25, RetrievalChannel.DENSE]
    assert channels[0].score == 12.5


def test_a_run_round_trips_through_json_without_losing_a_provenance_field() -> None:
    """The Gate 1 exit criterion, on the record that carries all the others."""
    original = matching_run()
    restored = MatchingRun.model_validate_json(original.model_dump_json())
    assert restored == original


def test_the_reproducibility_header_survives_the_round_trip() -> None:
    """Hashes, seed, versions, and hardware: everything the header is made of."""
    restored = MatchingRun.model_validate_json(matching_run().model_dump_json())
    assert restored.identities.bundle_sha256 == "a" * 64
    assert restored.identities.snapshot_sha256 == "b" * 64
    assert restored.identities.partition is Partition.DEVELOPMENT
    assert restored.configuration.seed == 20260824
    assert restored.configuration.model.revision == "2026-05-01"
    assert restored.configuration.model.prompt_version == "prompt-v4"
    assert restored.configuration.hardware_profile == "apple-m3-16gb"
    assert restored.configuration.supervisor.early_termination is False


def test_the_citation_provenance_survives_two_levels_down() -> None:
    """A trial assessment nests the evidence, so the round trip has to reach it."""
    restored = MatchingRun.model_validate_json(matching_run().model_dump_json())
    criterion = restored.trial_assessments[0].criteria[0]
    assert criterion.criterion_id == "NCT05123456:EXC-7"
    proposition = restored.trial_assessments[0].model_dump()["criteria"][0]["propositions"][0]
    assert proposition["patient_evidence"][0]["facts"][0]["json_path"] == (
        "entry[12].resource.effectiveDateTime"
    )
    assert proposition["trial_evidence"]["span_start"] == 1842


def test_an_unhashed_bundle_is_refused() -> None:
    """A run that cannot name the exact payload it read is not reproducible."""
    with pytest.raises(ValidationError, match="pattern"):
        MatchingRun.model_validate(
            matching_run().model_dump()
            | {
                "identities": matching_run().identities.model_dump()
                | {"bundle_sha256": "not-a-hash"}
            }
        )


def test_a_trial_nobody_was_shown_cannot_arrive_assessed() -> None:
    """The assessed set is a subset of what was presented, held at the record."""
    with pytest.raises(ValidationError, match="never presented"):
        MatchingRun.model_validate(
            matching_run().model_dump()
            | {
                "candidates": CandidateSet(
                    candidates=(candidate(NCT, 1, CandidateStatus.RETAINED),)
                ).model_dump()
            }
        )


def test_an_assessment_of_a_trial_outside_the_candidate_set_is_refused() -> None:
    with pytest.raises(ValidationError, match="not in the Candidate Set"):
        MatchingRun.model_validate(
            matching_run().model_dump()
            | {
                "candidates": CandidateSet(
                    candidates=(candidate("NCT05222222", 1, CandidateStatus.PRESENTED),)
                ).model_dump()
            }
        )


def test_a_rank_that_disagrees_with_the_candidate_set_is_refused() -> None:
    """Retrieval Rank is immutable, so two records of it must be the same record."""
    with pytest.raises(ValidationError, match="is ranked 1 in the"):
        matching_run(trial_assessments=(exc7_trial_assessment(retrieval_rank=2),))


def test_a_candidate_marked_assessed_must_carry_its_assessment() -> None:
    """Otherwise a run reports three assessed trials and publishes two."""
    with pytest.raises(ValidationError, match="marked assessed with no Trial Assessment"):
        matching_run(trial_assessments=())


def test_two_assessments_of_one_trial_are_refused() -> None:
    with pytest.raises(ValidationError, match="two assessments for"):
        matching_run(
            trial_assessments=(exc7_trial_assessment(), exc7_trial_assessment()),
        )


def test_a_presented_trial_with_no_expression_may_still_be_reported() -> None:
    """Section 8.0 stage 1: the criteria are quoted and reported unresolved.

    The candidate is presented rather than assessed, because expression coverage
    is an artifact of the authoring budget and the assessed set is defined by it.
    """
    run = matching_run(
        trial_assessments=(
            exc7_trial_assessment(),
            exc7_trial_assessment(retrieval_rank=2).model_copy(
                update={
                    "nct_id": "NCT05222222",
                    "criteria": (
                        UnexpressedCriterion(
                            criterion_id="NCT05222222:INC-1",
                            polarity=CriterionPolarity.INCLUSION,
                            trial_evidence=exc7_trial_evidence(),
                        ),
                    ),
                }
            ),
        )
    )
    assert run.trial_assessments[1].counts.unresolved == 1


def test_a_run_records_its_warnings_rather_than_raising_them() -> None:
    """A Stale Snapshot warns and never invalidates a historical run."""
    run = matching_run()
    assert run.warnings == ()
    assert run.failures == ()
    assert run.measurements == Measurements(
        latency_ms=5200,
        model_calls=6,
        prompt_tokens=3600,
        completion_tokens=540,
        estimated_cost_usd=0.0063,
    )


def test_a_run_is_immutable() -> None:
    with pytest.raises(ValidationError):
        matching_run().run_id = "run-0002"  # type: ignore[misc]
