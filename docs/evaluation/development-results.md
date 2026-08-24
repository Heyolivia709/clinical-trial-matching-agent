# Development results

Every number the [measurement plan](phase-1-benchmark-plan.md) asks for, on the
four development scenarios against the two development trials. Counts over
stated denominators, and nothing else: no interval, no test, no effect size.

**Read the caveat first.** Both variants here replay authored transcripts rather
than a recorded model run — a scripted answerer reading the packets and replying
by rule, described in `fixtures/transcripts/README.md`. These numbers therefore
measure the harness, not a model. They are published because the harness is what
Gate 4 built and because the shape of the tables is the deliverable; a reported
result about model behaviour is recorded from the hosted or local adapter, and
every run records which adapter produced it.

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
| Verifier catch rate on injected faults | pass, 9 of 9 faults caught by the check each was authored to trip |
| Unsupported assessments surviving verification | pass, 8 of 8 |
| Criterion Coverage with early termination off | pass, 8 of 8 |
| Citations dated after the Assessment Time | pass, 8 of 8 |
| Infrastructure Failures scored as `unknown` | pass, 8 of 8 |

## Track 2: grounding

| Measure | Agent | One-shot baseline |
| --- | --- | --- |
| Citation validity where the variant committed to an answer | 6 of 6 (100%) | 120 of 120 (100%) |
| Assessments resting on a citation that cannot establish them | 0 of 120 | 2 of 120 (1.7%) |
| Verification-induced `unknown` | 0 of 120 | not applicable |
| Corrections spent | 0 of 6 | not applicable |

The two denominators differ and both are stated. The agent commits to an answer
only where code has established that the record can answer — 6 propositions of
120 — and refuses the rest with a reason. The baseline answers everything.

Post-correction reference validity is not compared. It is 100% because the
verifier degrades whatever it cannot verify, so comparing it against a variant
with no verifier would report an architectural difference as a finding. The
harness raises rather than computing that comparison.

## Track 3: accuracy

Per state, never as one aggregate.

| Expected state | Agent | One-shot baseline |
| --- | --- | --- |
| `met` | 9 of 9 | 5 of 9 |
| `not_met` | 1 of 1 | 0 of 1 |
| `unknown` | 110 of 110 | 95 of 110 |
| `not_applicable` | 0 of 0 | 0 of 0 |

Unknown Reason agreement, reported separately because a right state for the wrong
reason sends a coordinator to the wrong place:

| | Agent | One-shot baseline |
| --- | --- | --- |
| Reason agreement over expected `unknown` | 110 of 110 | 51 of 110 |

`not_applicable` has no observations, and that is a finding rather than a gap in
the tables: an expected `not_applicable` needs a conditional whose antecedent is
*contradicted*, and the only conditional in the development trials has an
exposure antecedent. Absence of exposure yields `missing_evidence` rather than a
confident negative, so the branch is unreachable by construction. The count is
shown as `0 of 0` rather than as `0%`, because a percentage there would read as
a result.

## Track 4: cost

Model calls, tokens, and latency are all zero in these runs: a replayed
transcript spends nothing. The unit is fixed at the criterion assessment (68 of
them here), and cost is published beside the grounding number it purchased, so
this table is a placeholder shape until a recorded run fills it.

## The held-out half has not been assessed

Deliberately. It is assessed once, at the end, and reported separately — and
spending that once on a replayed authored transcript would spend it on a
measurement of the harness. The machinery is there and takes an explicit
argument: `eval_cases(Partition.HELD_OUT)` has no default, so reaching the
held-out half is something someone has to write down.

It is worth assessing when there is a recorded model run to assess it with. The
two-axis split means the held-out set is larger than the development one: 16 of
the 24 scenario-trial pairs, because a development scenario against a held-out
trial is held out too.

## What these numbers do not support

The agent agrees with gold on every scorable proposition. That is not a claim
about a model: the agent transcript was produced by a script that reads the
packet the loop built, so it is consistent with the loop by construction. What
the run does demonstrate is that the pipeline holds its invariants end to end and
that the harness computes what the plan asks for.

Two limitations belong beside any future numbers:

**Terminology coverage.** The reviewed mapping covers eight concepts; the four
trials name roughly thirty. Every criterion naming an uncovered concept reports
`missing_evidence`, which is a property of the authoring budget and not of the
patient. It also means no development scenario meets an exclusion criterion of a
development trial, so no development pair produces a blocker.

**Scope refusals.** Several criteria are unanswerable by design rather than by
accident: line-of-therapy derivation, regimen grouping, cross-unit conversion,
and TNM-to-stage derivation are all out of scope and yield `unknown`. A reader
comparing this system against one that answers those criteria is comparing
against a system that guesses at them.
