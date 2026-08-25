"""Record a real model run, as transcripts the replay adapter can read.

    ANTHROPIC_API_KEY=... uv run python scripts/record_run.py

Writes `fixtures/transcripts/{scenario}-hosted.json` for the agent and
`{scenario}-hosted-baseline.json` for the one-shot baseline, in the same format
as the authored transcripts. Everything downstream — grading, the invariants,
the reports — then runs against a recorded run without a key.

This is the script the whole repository has been waiting for. Until it runs, the
published counts measure the harness rather than a model, which
`fixtures/transcripts/README.md` and the results document both say.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from ctma.adapters.model import (
    HostedModel,
    RecordingModel,
)
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.transcripts import TRANSCRIPTS, Transcript
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.domain.enums import Partition
from ctma.domain.expression import AuthoringProvenance, ReviewStatus
from ctma.domain.run import ModelAdapter, ModelConfiguration
from ctma.evaluation.baseline import one_shot
from ctma.evaluation.cases import eval_cases
from ctma.evaluation.lab import timeline_for
from ctma.match import match

ENDPOINT = "https://api.anthropic.com/v1/messages"
MODEL_ID = "claude-sonnet-5"


def configuration(prompt_version: str) -> ModelConfiguration:
    """The configuration one half of the run was made under.

    The prompt version differs between the halves and has to, because the two
    prompts are edited independently — stamping both with one string would make
    a transcript recorded before a prompt fix indistinguishable from one after.
    """
    return ModelConfiguration(
        adapter=ModelAdapter.HOSTED,
        model_id=MODEL_ID,
        revision="2026-08-25",
        temperature=None,
        top_p=None,
        max_output_tokens=4000,
        prompt_version=prompt_version,
        schema_version="proposed-assessment-v1",
    )


AGENT_PROMPTS = "agent-prompts-v1"
BASELINE_PROMPTS = "baseline-prompt-v2"
"""No temperature and no top_p: this model rejects both outright, so the run
cannot be pinned by asking for greedy decoding. That is what the transcript is
for — reproducibility here is the recorded exchange, not a seed.

4000 output tokens rather than the replay configuration's 1024. The baseline
prompt asks for every proposition of a criterion in one reply, and at 1024 the
JSON was cut mid-object — which arrives downstream as "the reply is not JSON"
and reads like a model that cannot produce valid output, when the cause is a
budget this file set."""

PROVENANCE = AuthoringProvenance(
    drafted_by="assistant",
    ai_assisted=True,
    reviewed_by="rendong",
    reviewed_on=dt.date(2026, 8, 25),
    review_status=ReviewStatus.REVIEWED,
)


def _key() -> str:
    value = os.environ.get("ANTHROPIC_API_KEY")
    if not value:
        sys.exit("ANTHROPIC_API_KEY is not set")
    return value


KEY = _key()

PARTS = frozenset(os.environ.get("CTMA_RECORD", "agent,baseline").split(","))
"""Which halves to record. Recording is the step that costs money, so re-running
one half after a prompt fix does not pay for the other."""

TRIALS = load_trial_fixtures(Partition.DEVELOPMENT)
scenarios = sys.argv[1:] or sorted({case.scenario_id for case in eval_cases(Partition.DEVELOPMENT)})
"""Named scenarios, or every development one. Recording is the step that costs
money, so it takes an argument rather than always doing all of them."""


def hosted(prompt_version: str) -> RecordingModel:
    return RecordingModel(
        HostedModel(
            configuration=configuration(prompt_version),
            endpoint=ENDPOINT,
            api_key=KEY,
            timeout_s=120.0,
            pace_s=1.0,
        )
    )


def write(transcript_id: str, scenario_id: str, recorder: RecordingModel) -> None:
    if not recorder.calls:
        # Every call failed. Crashing here would throw away the scenarios already
        # recorded, and an empty transcript would claim a run that never happened.
        print(f"  no calls succeeded; {transcript_id} not written")
        return
    transcript = Transcript(
        transcript_id=transcript_id,
        scenario_id=scenario_id,
        trials=tuple(trial.nct_id for trial in TRIALS),
        provenance=PROVENANCE,
        configuration=recorder.configuration,
        calls=tuple(recorder.calls),
    )
    path = TRANSCRIPTS / f"{transcript_id}.json"
    path.write_text(
        json.dumps(json.loads(transcript.model_dump_json()), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    spent = sum(call.measurements.model_calls for call in recorder.calls)
    tokens = sum(call.measurements.tokens for call in recorder.calls)
    print(f"  wrote {path.name}: {len(recorder.calls)} calls, {spent} model calls, {tokens} tokens")


for scenario_id in scenarios:
    scenario = load_scenario_input(scenario_id)

    if "agent" in PARTS:
        print(f"{scenario_id}: agent")
        recorder = hosted(AGENT_PROMPTS)
        run = match(
            scenario_id=scenario_id,
            bundle_json=scenario.bundle_json,
            assessment_as_of=scenario.assessment_as_of,
            trials=TRIALS,
            model=recorder,
            partition=Partition.DEVELOPMENT,
            run_id=f"{scenario_id.lower()}-hosted",
        )
        conclusions = ", ".join(
            f"{item.nct_id} {item.conclusion.value}" for item in run.trial_assessments
        )
        print(f"  {conclusions or 'no trial was assessed'}")
        print(f"  infrastructure failures: {len(run.failures)}")
        write(f"{scenario_id.lower()}-hosted", scenario_id, recorder)

    if "baseline" in PARTS:
        print(f"{scenario_id}: one-shot baseline")
        baseline = hosted(BASELINE_PROMPTS)
        timeline = timeline_for(scenario_id)
        failures = [
            failure
            for trial in TRIALS
            for criterion in trial.criteria
            for failure in one_shot(
                criterion, timeline=timeline, trial=trial, model=baseline
            ).failures
        ]
        for failure in failures:
            # Reported rather than retried. Retrying until a run looks clean
            # would hide the rate at which a reply comes back unusable, and that
            # rate is one of the things this comparison is for.
            print(f"  unusable reply: {failure.detail.splitlines()[1].strip()[:90]}")
        print(f"  {len(failures)} unusable of {sum(len(t.criteria) for t in TRIALS)} criteria")
        write(f"{scenario_id.lower()}-hosted-baseline", scenario_id, baseline)
