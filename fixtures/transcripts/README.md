# Frozen transcripts

One file per recorded run: every model call it made, keyed by what was being
asked — purpose, criterion, proposition, attempt — with the prompt beside it.
`FrozenReplayModel` answers from these, so a run replays without a key, an
endpoint, or a network.

**These transcripts are authored, not captured.** They were produced by a
scripted answerer reading the packets the loop built and replying by rule. They
are here so the end-to-end path has something deterministic to run against, and
so the tests never depend on a live model.

They are not a model's behaviour and no published number may be computed from
them. A reported result is recorded from the hosted or local adapter, and the
run records which adapter produced it.

**Provenance.** Drafted by the assistant with AI assistance; reviewed by rendong
on 2026-08-25, recorded in each file.
