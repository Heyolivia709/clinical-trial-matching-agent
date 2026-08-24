"""The fixture adapter for ClinicalTrials.gov records.

Specification section 12 gives ClinicalTrials.gov a fixture adapter. This is it:
it reads the four frozen trial records from `fixtures/trials/`, so a run has
trial data without a network call in a test.

Criterion spans are not stored in the fixture files. They are located here, by
searching the frozen eligibility text for the criterion's own text. An authored
criterion that paraphrases its source therefore fails to load rather than
loading with a span that points somewhere plausible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ctma.domain.trial import TrialRecord

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "trials"


class FixtureError(ValueError):
    """A frozen fixture does not describe the source it claims to come from."""


def load_trial_fixtures() -> tuple[TrialRecord, ...]:
    """The four frozen Gate 1 trials, in NCT order."""
    paths = sorted(FIXTURES.glob("NCT*.json"))
    if not paths:
        msg = f"no trial fixtures found under {FIXTURES}"
        raise FixtureError(msg)
    return tuple(_load(path) for path in paths)


def _load(path: Path) -> TrialRecord:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    text: str = payload["eligibility_source_text"]
    for criterion in payload["criteria"]:
        start, end = _locate(text, criterion["source_text"], path)
        criterion["span_start"] = start
        criterion["span_end"] = end
    return TrialRecord.model_validate(payload)


def _locate(text: str, source_text: str, path: Path) -> tuple[int, int]:
    start = text.find(source_text)
    if start < 0:
        msg = f"{path.name}: this text is not in the eligibility text verbatim: {source_text!r}"
        raise FixtureError(msg)
    if text.find(source_text, start + 1) >= 0:
        msg = f"{path.name}: this text appears twice, so its span is ambiguous: {source_text!r}"
        raise FixtureError(msg)
    return start, start + len(source_text)
