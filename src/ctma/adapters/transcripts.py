"""Frozen transcripts for the replay adapter.

Specification section 16. A transcript is one run's model calls, recorded so the
run can be replayed by someone with no key and no endpoint. `FrozenReplayModel`
reads one; nothing else does.

These particular transcripts are authored rather than captured — see
`fixtures/transcripts/README.md`, which says so plainly. They exist so the
end-to-end path has something deterministic to run against. A published result
is recorded from a real adapter, and the run records which adapter produced it,
which is the point of recording the model configuration at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from pydantic import Field

from ctma.adapters.model import FrozenReplayModel, RecordedCall
from ctma.domain.base import Frozen
from ctma.domain.expression import AuthoringProvenance
from ctma.domain.run import ModelConfiguration

TRANSCRIPTS = Path(__file__).resolve().parents[3] / "fixtures" / "transcripts"


class TranscriptError(ValueError):
    """The named transcript is not there."""


class Transcript(Frozen):
    """One recorded run: which scenario, which trials, and every call."""

    transcript_id: str = Field(min_length=1)
    scenario_id: str = Field(min_length=1)
    trials: tuple[str, ...] = Field(min_length=1)
    provenance: AuthoringProvenance
    calls: tuple[RecordedCall, ...] = Field(min_length=1)

    configuration: ModelConfiguration | None = None
    """What produced these answers, when a real model did.

    A replayed run reported the replay adapter's own configuration until this
    field existed, so a report built from a captured transcript told its reader
    the model was `frozen-replay` with temperature 0.0 — which describes the
    playback, not the run, and is the exact provenance claim this project exists
    to get right. Authored transcripts leave it unset, and the replay
    configuration then describes them correctly.
    """

    def replay(self, configuration: ModelConfiguration | None = None) -> FrozenReplayModel:
        """Replay under the configuration that produced the answers.

        The recorded one wins. An argument is only used when there is none,
        which is the authored case.
        """
        chosen = self.configuration or configuration
        if chosen is None:
            msg = f"{self.transcript_id} records no configuration and none was given"
            raise TranscriptError(msg)
        return FrozenReplayModel.from_transcript(self.calls, configuration=chosen)


def load_transcript(transcript_id: str) -> Transcript:
    path = TRANSCRIPTS / f"{transcript_id}.json"
    if not path.is_file():
        msg = f"no transcript {transcript_id!r} under {TRANSCRIPTS}"
        raise TranscriptError(msg)
    payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    return Transcript.model_validate(payload)
