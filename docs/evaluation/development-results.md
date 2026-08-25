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
| Citation validity where the variant committed to an answer | 7 of 7 | 100 of 120 (83.3%) |
| Assessments resting on a citation that cannot establish them | 0 of 120 | 0 of 120 |
| Verification-induced `unknown` | 0 of 120 | not applicable |
| Corrections spent | 0 of 7 | not applicable |

Seven of seven, over seven propositions. That denominator is the number to look at:
the agent commits to an answer only where code has established that the record
can answer, so almost everything here is `unknown` and only six propositions
were ever citable.

**The first recorded run scored 1 of 6, and every one of those five failures was
this repository's fault.** The section below has the details; the short version
is that the prompt printed a fact as `Condition/cond-nsclc` and said "cite by
fact id" without saying which part was the id, and the verifier answered the
resulting mistake with "met cites no patient evidence" — a true statement about
the symptom and the wrong diagnosis, which sent the one correction at the wrong
thing five times.

The baseline's 97 of 120 is the same measurement without a verifier in the way:
**23 invalid citations would have reached a coordinator**. Both denominators are
stated and they differ — the agent commits only where the record can answer, and
refuses the rest with a reason.

Post-correction reference validity is not compared. It is 100% because the
verifier degrades whatever it cannot verify, so comparing it against a variant
with no verifier would report an architectural difference as a finding. The
harness raises rather than computing that comparison.

## Track 3: accuracy

Per state, never as one aggregate.

| Expected state | Agent | One-shot baseline |
| --- | --- | --- |
| `met` | 10 of 10 | 6 of 10 |
| `not_met` | 1 of 1 | 1 of 1 |
| `unknown` | 109 of 109 | 78 of 109 |
| `not_applicable` | 0 of 0 | 0 of 0 |

| | Agent | One-shot baseline |
| --- | --- | --- |
| Unknown Reason agreement, over propositions either variant could look up | 53 of 53 | **15 of 53** |
| Propositions neither variant could look up | 56 of 109 | 56 of 109 |

The agent agrees with gold on all 120 propositions. Two things stop that from
being the headline it looks like.

**The denominators are tiny.** Ten `met` and one `not_met` across four
scenarios. A system that answered every citable proposition correctly out of ten
attempts has not been measured against much.

**The first recorded run scored 6 of 9 and 0 of 1**, and the difference is not a
better model — it is the same model given a prompt that says what an id is. A
number that moves this far on a prompt edit is a number about the prompt.

**The reason denominator is 50, not 110, and both variants share it.** 60 of the
110 expected-`unknown` propositions name a concept outside the reviewed
terminology mapping, so nothing looked them up. Gold describes the record and
knows nothing about what this system covers, so there is no diagnosis to compare
— one side is talking about a patient and the other about a terminology table.
Those 60 are dropped from the reason denominator for **both** variants and
counted on their own line, because dropping them from only the variant that
reports the limit would compare two different question sets.

That exclusion made the comparison harsher, not kinder. Over the 50 propositions
that were actually looked up, the baseline gets the diagnosis right **14 times**.
Its earlier 46 of 110 was carried by easy `missing_evidence` calls on concepts
nobody could look up. The agent is 50 of 50 — it never gave a right answer for a
wrong reason, on the propositions where a reason could be checked.

`not_applicable` has no observations, and that is a finding rather than a gap:
an expected `not_applicable` needs a conditional whose antecedent is
*contradicted*, and the only conditional in the development trials has an
exposure antecedent. Absence of exposure yields `missing_evidence` rather than a
confident negative, so the branch is unreachable by construction. Shown as
`0 of 0` rather than `0%`, because a percentage there would read as a result.

## Track 4: cost

| | Criterion assessments | Model calls | Tokens | Calls per criterion |
| --- | --- | --- | --- | --- |
| Agent | 68 | 27 | 13,825 | 0.40 |
| One-shot baseline | 68 | 68 | 253,260 | 1.00 |

**The agent spent 18 times fewer tokens than the baseline**, and fewer than one
model call per criterion. Not a tuning result: the baseline is handed the entire
patient record on every call because it has no tools, while the agent sends one
proposition and the facts a tool returned for it. Most criteria never reach the
model at all — the deterministic Unknown Reason table answers them first, which
is why calls per criterion is below one.

Cost is published beside the grounding number it purchased. Here the cheaper
variant is also the better-grounded one, which is not a general law and should
not be read as one.

## What the real run found, all of it in this repository

Three defects, none of them about the model. Every one was invisible to the
authored transcripts, because the same hand wrote the answers and the checks.

### The prompt never said what a fact id was

The assessment prompt printed a fact as

```
- Condition/cond-nsclc: Non-small cell lung cancer [254637007], status confirmed, ...
```

and then said "Cite by fact id". Nothing said which part of that line *was* the
id. The model tried `cond-nsclc` three times, `Condition/cond-nsclc` once, and
once quoted a computed sentence — `"age at 2026-08-04 is 64 years"` — as though
it were an id.

### The rejection named the symptom instead of the cause

An id that matches no fact is dropped before a proposal is built, so what
reached the verifier was an assessment citing nothing, and the correction prompt
said **"met cites no patient evidence"**. That is true and useless: the model had
cited evidence, with the wrong identifier. Told it had cited nothing, it
re-sent the same id with a reworded rationale — and in one case changed
`contradicts` to `supports`, making the answer worse.

Five of six corrections were spent this way. The rejection vocabulary already
had `nonexistent_reference` for exactly this; the loop threw away the
information before the verifier could use it.

### One proposition had nothing to cite at all

Age is computed from the birth date by code, and the `Patient` resource is not
reachable by any tool. The demographics path asked the model for citations from
a fact list that was always empty, then discarded whatever came back and
attached its own reference. So the model either invented an id or, once the
prompt honestly said computations are not citable, returned an empty list and
failed the schema. Both are the same bug: asking for something unusable.

### What the fixes were worth

Same model, same scenarios, same corpus. The prompt now names the id and says
what is not citable; the verifier reports `nonexistent_reference` with the id in
it; the demographics path asks only for a state.

| | `agent-prompts-v1` | `agent-prompts-v2` |
| --- | --- | --- |
| Citation validity before correction | 1 of 6 (16.7%) | 6 of 6 |
| Corrections spent | 5 of 6 | 0 of 6 |
| Verification-induced `unknown` | 4 of 120 | 0 of 120 |
| `met` | 6 of 9 | 9 of 9 |
| `not_met` | 0 of 1 | 1 of 1 |
| Model calls | 31 | 26 |
| Tokens | 18,226 | 13,235 |

The superseded transcripts are kept as `*-hosted-v1.json`, so both runs can be
read. **This is what a benchmark number is worth before anyone has looked at the
prompts**: the earlier table would have been published as an agent that
mis-cites five times out of six, and the finding would have been about a model.

### The same thing happened to the baseline

27 of 68 baseline replies failed schema validation, and the schema block never
stated three rules the domain enforces: that `reason` is set exactly when the
state is `unknown`, that `clinical_time` is a date copied from the record with
no "unknown" option, and that `code` is copied too. Writing them into the prompt
took the same run to **0 of 68**. Those transcripts are kept as
`*-hosted-baseline-v1.json`.

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
trials name thirty-one. A criterion naming an uncovered concept now reports
`concept_not_in_mapping` — 60 of 110 expected-`unknown` propositions — which is a
property of the authoring budget and not of the patient.

Until this run it reported `missing_evidence` instead, and that was worse than
imprecise. It told a coordinator to search a chart nothing had searched, and it
hid a real hole: a record that *does* hold the finding produces the same label
and the same silence, so a scenario planting an exclusion the mapping misses
would have scored as correctly resolved with no test failing.
`test_an_unmapped_concept_reports_that_nothing_looked_rather_than_that_nothing_exists`
now covers that seam.

Expanding the mapping alone would not move any number here: none of the four
scenarios contained a fact for any of the sixteen uncovered concepts, so a
lookup that ran would find nothing and report `missing_evidence` anyway. **What
is binding is scenario content, not terminology coverage** — and that was tested
rather than argued.

Until this run no development scenario met an exclusion criterion, so no
development pair had ever produced a blocker and the blocking half of the impact
model was exercised only by unit tests. SCN-03 now carries a confirmed primary
brain tumour and `PRIMARY_CNS_TUMOR` was added to the mapping. That pair
concludes `unlikely_match`, and its report is the first to say **"A criterion
rules this patient out"**.

It took **one concept and one recorded fact** — not the twenty-three the
coverage gap suggested — because the gap was never what was stopping it.

**Scope refusals.** Line-of-therapy derivation, regimen grouping, cross-unit
conversion, and TNM-to-stage derivation are out of scope and yield `unknown`. A
reader comparing this system against one that answers those criteria is
comparing against a system that guesses at them.

**One run.** Every number above is a single pass with decoding unpinned — the
model rejects the `temperature` parameter, so the run cannot be made greedy.
Reproducibility here is the committed transcript, not a seed, and nothing above
should be read as an expected value across runs.
