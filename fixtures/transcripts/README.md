# Frozen transcripts

One file per recorded run: every model call it made, keyed by what was being
asked — purpose, criterion, proposition, attempt — with the prompt beside it.
`FrozenReplayModel` answers from these, so a run replays without a key, an
endpoint, or a network.

**Two kinds live here, and the filename says which.**

`*-development.json` and `*-baseline.json` are **authored**: produced by a
scripted answerer reading the packets the loop built and replying by rule. They
exist so the end-to-end path has something deterministic to run against and so
the tests never depend on a live model. They are not a model's behaviour, and no
published number is computed from them.

`*-hosted*.json` are **captured** from a real run. Those are what the results
report.

**Provenance.** Drafted by the assistant with AI assistance; reviewed by rendong
on 2026-08-25, recorded in each file.

## The recorded run, 2026-08-25

`*-hosted.json` and `*-hosted-baseline.json` are **captured**, not authored:
`claude-sonnet-5` through `HostedModel`, written by `scripts/record_run.py`.
They are what [the results](../../docs/evaluation/development-results.md)
report, and they replay without a key like any other transcript.

`*-hosted-baseline-v1.json` is the superseded first attempt, kept on purpose. 27
of its 68 replies failed schema validation because the prompt never stated three
rules the domain enforces. Stating them took the same run to 0 of 68, and the
pair is the evidence for that.

Decoding is unpinned in all of them: the model rejects a `temperature`
parameter, so a run cannot be made greedy and the transcript is the only
reproducibility there is.

The authored transcripts stay. They are what the test suite runs against, and a
test that needs a key is a test nobody runs.
