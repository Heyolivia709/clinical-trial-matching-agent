# Development results

Every number the [measurement plan](phase-1-benchmark-plan.md) asks for, on the
four development scenarios against the two development trials. Counts over
stated denominators, and nothing else: no interval, no test, no effect size.

**These are from a recorded model run.** `claude-sonnet-5`, 2026-08-25, both
variants, transcripts committed under `fixtures/transcripts/*-hosted*.json` and
replayable without a key. The run records which adapter produced it. An earlier
version of this document reported the authored transcripts instead and said so;
those numbers are kept at the bottom, because the difference between them is the
most useful thing here.

**Sample.** 120 propositions across 4 scenarios and 2 trials, 68 criterion
assessments. At this size an interval would be wider than any difference worth
claiming.

## Track 1: release gates

Deterministic properties the implementation controls, reported pass or fail. One
violation is a failure, not a percentage.

| Invariant | Result |
| --- | --- |
| Reference validity in final output | pass, 8 of 8 scenario-trial pairs |
| Deterministic aggregation accuracy | pass, 8 of 8 |
| Verifier catch rate on injected faults | pass, 8 of 8 |
| Unsupported assessments surviving verification | pass, 8 of 8 |
| Criterion Coverage with early termination off | pass, 8 of 8 |
| Citations dated after the Assessment Time | pass, 8 of 8 |
| Infrastructure Failures scored as `unknown` | pass, 8 of 8 |

Every gate held against a real model. They also held against the authored
transcripts, which is worth exactly nothing by comparison: the authored answers
were written to satisfy them.

## Track 2: grounding

| Measure | Agent | One-shot baseline |
| --- | --- | --- |
| Citation validity where the variant committed to an answer | **1 of 6 (16.7%)** | 97 of 120 (80.8%) |
| Assessments resting on a citation that cannot establish them | 0 of 120 | 0 of 120 |
| Verification-induced `unknown` | 4 of 120 (3.3%) | not applicable |
| Corrections spent | 5 of 6 (83.3%) | not applicable |

**The agent's first citation was wrong five times out of six.** That single
number is what the whole architecture exists for, and no authored transcript
could have produced it — the authored agent cited correctly 6 times out of 6,
because the same hand wrote both sides.

What happens next is the point. The verifier rejects the citation, one
correction is spent, and what still cannot be verified is degraded: 4 of 120
propositions ended as `unknown` because the evidence would not stand up. None of
the 120 final assessments rests on a citation that cannot establish it.

The baseline's 97 of 120 is the same measurement without a verifier in the way:
**23 invalid citations would have reached a coordinator**. Both denominators are
stated and they differ — the agent commits to an answer only where code has
established the record can answer, and refuses the rest with a reason.

Post-correction reference validity is not compared. It is 100% because the
verifier degrades whatever it cannot verify, so comparing it against a variant
with no verifier would report an architectural difference as a finding. The
harness raises rather than computing that comparison.

## Track 3: accuracy

Per state, never as one aggregate.

| Expected state | Agent | One-shot baseline |
| --- | --- | --- |
| `met` | 6 of 9 | 5 of 9 |
| `not_met` | **0 of 1** | 1 of 1 |
| `unknown` | 110 of 110 | 78 of 110 |
| `not_applicable` | 0 of 0 | 0 of 0 |

| | Agent | One-shot baseline |
| --- | --- | --- |
| Unknown Reason agreement over expected `unknown` | 110 of 110 | 46 of 110 |

Three things here, and one of them is bad news.

**The agent missed the only true negative.** Expected `not_met`, and it did not
produce it — the baseline did. A system this conservative refuses where it
should contradict, and on a screening workflow that is the cheaper direction to
fail in, but it is a failure and one observation is not a rate.

**The agent never gave a right answer for a wrong reason.** 110 of 110 on reason
agreement against the baseline's 46 of 110. The baseline got the state right 78
times and the reason right 46 times, so on roughly 32 propositions it said "we
cannot tell" for a reason that would send a coordinator to the wrong place —
ordering a test that already exists, or chasing a date instead of a conflict.

`not_applicable` has no observations, and that is a finding rather than a gap:
an expected `not_applicable` needs a conditional whose antecedent is
*contradicted*, and the only conditional in the development trials has an
exposure antecedent. Absence of exposure yields `missing_evidence` rather than a
confident negative, so the branch is unreachable by construction. Shown as
`0 of 0` rather than `0%`, because a percentage there would read as a result.

## Track 4: cost

| | Criterion assessments | Model calls | Tokens | Calls per criterion |
| --- | --- | --- | --- | --- |
| Agent | 68 | 31 | 18,226 | 0.46 |
| One-shot baseline | 68 | 68 | 253,260 | 1.00 |

**The agent spent 14 times fewer tokens than the baseline**, and fewer than one
model call per criterion. Not a tuning result: the baseline is handed the entire
patient record on every call because it has no tools, while the agent sends one
proposition and the facts a tool returned for it. Most criteria never reach the
model at all — the deterministic Unknown Reason table answers them first, which
is why calls per criterion is below one.

Cost is published beside the grounding number it purchased. Here the cheaper
variant is also the better-grounded one, which is not a general law and should
not be read as one.

## What a real run cost that the authored one hid

Recording this exposed a defect in the harness that authored transcripts could
never have shown, because the same hand wrote the answers and the checks.

**27 of 68 baseline replies were unusable, and it was the prompt's fault.** The
schema shown to the model listed the fields but never stated three rules the
domain enforces: that `reason` is set exactly when the state is `unknown`, that
`clinical_time` is a date copied from the record with no "unknown" option, and
that `code` is copied from the record. The model broke all three. After the
rules were written into the prompt, the same run produced **0 unusable replies
of 68**.

Publishing the first number as "the baseline fails 40% of the time" would have
been blaming a model for a contract nobody told it. The superseded transcripts
are kept as `*-hosted-baseline-v1.json` so the before and after can both be
read.

The agent's prompt had no such failures — 31 calls, 0 unusable. It asks for less:
a state from three options and which fact ids support it, with every code, date
and precision filled in by code. Everything a model can get wrong about the
record is not asked of the model.

## The held-out half has not been assessed

Deliberately. It is assessed once, at the end, and reported separately. The
machinery takes an explicit argument — `eval_cases(Partition.HELD_OUT)` has no
default — so reaching the held-out half is something someone has to write down.

The two-axis split means the held-out set is larger than the development one: 16
of the 24 scenario-trial pairs, because a development scenario against a
held-out trial is held out too.

## The authored transcripts, for comparison

The previous version of this document reported these, and said in its second
paragraph that they measured the harness rather than a model. That caveat was
correct, and the size of the gap is the argument for never publishing the second
kind of number as the first.

| Measure | Authored | Recorded |
| --- | --- | --- |
| Agent citation validity before correction | 6 of 6 (100%) | 1 of 6 (16.7%) |
| Corrections spent | 0 of 6 | 5 of 6 |
| Verification-induced `unknown` | 0 of 120 | 4 of 120 |
| Agent `met` | 9 of 9 | 6 of 9 |
| Agent `not_met` | 1 of 1 | 0 of 1 |
| Baseline citation validity | 120 of 120 (100%) | 97 of 120 (80.8%) |

The authored agent was perfect on every axis, because the script that produced
its answers read the packet the loop had already built. The recorded agent is
not, and the verifier is the reason its output still holds.

Reproduce either with `uv run python scripts/score_run.py hosted` or
`... development`.

## Limitations that belong beside any of these numbers

**Terminology coverage.** The reviewed mapping covers eight concepts; the four
trials name roughly thirty. Every criterion naming an uncovered concept reports
`missing_evidence`, which is a property of the authoring budget and not of the
patient. It also means no development scenario meets an exclusion criterion of a
development trial, so no development pair produces a blocker.

**Scope refusals.** Line-of-therapy derivation, regimen grouping, cross-unit
conversion, and TNM-to-stage derivation are out of scope and yield `unknown`. A
reader comparing this system against one that answers those criteria is
comparing against a system that guesses at them.

**One run.** Every number above is a single pass with decoding unpinned — the
model rejects the `temperature` parameter, so the run cannot be made greedy.
Reproducibility here is the committed transcript, not a seed, and nothing above
should be read as an expected value across runs.
