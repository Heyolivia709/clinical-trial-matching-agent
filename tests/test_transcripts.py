"""Transcripts, and the provenance a replayed report reports.

A transcript is the only reproducibility a run against a hosted model has: the
endpoint rejects a temperature parameter, so nothing here can be made greedy.
That puts the burden on the file to say what produced it.
"""

from __future__ import annotations

import pytest

from ctma.adapters.model import REPLAY_CONFIGURATION
from ctma.adapters.transcripts import TranscriptError, load_transcript
from ctma.domain.run import ModelAdapter


def test_a_captured_transcript_replays_under_the_model_that_produced_it() -> None:
    """Otherwise a report built from a real run tells its reader the model was
    `frozen-replay` at temperature 0.0 — which describes the playback rather
    than the run, and is the provenance claim this project exists to get right.
    """
    transcript = load_transcript("scn-01-hosted")
    assert transcript.configuration is not None

    model = transcript.replay(REPLAY_CONFIGURATION)
    assert model.configuration.adapter is ModelAdapter.HOSTED
    assert model.configuration.model_id == "claude-sonnet-5"
    assert model.configuration.temperature is None, "this model rejects the parameter"


def test_the_two_baseline_prompt_versions_are_distinguishable() -> None:
    """A transcript recorded before a prompt fix must not look like one after."""
    before = load_transcript("scn-01-hosted-baseline-v1").configuration
    after = load_transcript("scn-01-hosted-baseline").configuration
    assert before is not None
    assert after is not None
    assert before.prompt_version != after.prompt_version


def test_an_authored_transcript_replays_under_the_configuration_it_is_given() -> None:
    """It records none, and `frozen-replay` describes it correctly."""
    transcript = load_transcript("scn-01-development")
    assert transcript.configuration is None
    assert transcript.replay(REPLAY_CONFIGURATION).configuration is REPLAY_CONFIGURATION


def test_a_transcript_with_no_configuration_and_no_argument_is_refused() -> None:
    with pytest.raises(TranscriptError, match="records no configuration"):
        load_transcript("scn-01-development").replay()


def test_a_missing_transcript_names_where_it_looked() -> None:
    with pytest.raises(TranscriptError, match="no transcript 'nope'"):
        load_transcript("nope")
