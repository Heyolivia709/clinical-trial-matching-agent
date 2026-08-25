# Dependency-Ordered Implementation Sequence

**Status:** Frozen sequence
**Supersedes:** the seven-gate v6 sequence, which included candidate retrieval and
a research-grade evaluation gate. Both are cut; see
[ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md).
**Scheduling rule:** No calendar estimates. Progression depends only on
acceptance criteria.

Five gates. Gate scope classification and the cut order under schedule pressure
are in [specification](../specs/phase-1-mvp-specification.md) section 19.

## Gate 1: Contracts and Fixtures — Core ✅

Core types, Criterion State semantics, Boolean aggregation, polarity-to-impact
mapping, Match Conclusion, the Unknown Reason table, the Matching Policy, and
four frozen trial records with human-reviewed Criterion Expressions.

**Exit criteria** — all met, issues #12 through #16.

- Deterministic tests for all four Criterion States and for `not_assessed` as a distinct reporting status
- `all_of`, `any_of`, and conditional truth tables pass exhaustively, including all-`not_applicable` cases
- Impact mapping and Match Conclusion derivation pass, including the early-termination rule
- The Unknown Reason table of specification section 8.0 is pure code, with a test per row and a test asserting row precedence
- Every model round-trips through JSON without loss of provenance fields
- Four frozen trial records, two development and two held out, every published criterion preserved at its exact span
- The four collectively cover all five supported Criterion Categories and every supported expression form, including a conditional capable of producing `not_applicable`
- Criteria outside the supported categories are authored as `unsupported` rather than omitted

## Gate 2: Patient Timeline, Tools, and Scenarios — Core ✅

Parse the four evidence-bearing FHIR R4 resource types into the Patient Timeline.
Recognize `MedicationRequest` as Unsupported Patient Content. Implement the five
Timeline Tools. Author six synthetic scenarios with hidden manifests and all seven
Planted Distractors.

**Exit criteria**

- Six scenarios build reproducibly from frozen Bundles
- Every timeline fact traces to a FHIR resource type, ID, and JSON path
- `MedicationRequest` is preserved as Unsupported Patient Content and never treated as exposure
- All seven Planted Distractor kinds are present across the scenario set, each covered by a test asserting it does not produce a confident assessment **and that it resolves to the Unknown Reason named in specification section 8.3**
- Missing, conflicting, post-`assessment_as_of`, `preliminary`, and `entered-in-error` facts never yield `met` or `not_met`
- A criterion naming a prospective anchor is covered twice: once with an authored substitution, which assesses and displays it, and once without, which yields `ambiguous_criterion`
- Each tool has deterministic tests including the empty-result and ambiguous-result paths

All met, issues #17 through #20.

## Gate 3: Criterion Agent and Evidence Verifier — Core ✅

The bounded per-proposition loop of specification section 10, the deterministic
verifier of section 8.1, exactly one targeted correction, and `match()` end to
end. Early Termination is the one supervisor behaviour kept, and it is additive.

**Exit criteria**

- The agent selects and calls Timeline Tools per proposition and returns schema-valid structured output
- Every `met` and `not_met` in final output cites verified patient evidence and exact trial source text
- The verifier rejects nonexistent references, altered values, invalid spans, missing evidence relations, citations that resolve but cannot establish the claimed state, incorrect aggregation, and evidence dated after `assessment_as_of`
- An injected-fault fixture proves each rejection class, independent of whether the model produces the error organically
- One verification failure triggers exactly one correction; a second yields `unknown` with `verification_failed`
- Deterministic-versus-model disagreement yields `unknown` with `reasoning_conflict`
- `match()` produces a `MatchingRun` that round-trips and can be re-graded offline
- With Early Termination on, skipped criteria are `not_assessed` and never `unknown`

All met, issues #25 through #30.

One limitation this gate surfaced, recorded because the numbers will show it: no
development scenario meets an exclusion criterion of a development trial, because
the reviewed terminology mapping does not cover the conditions those trials
exclude. So no development pair produces a blocker, and `early_termination` is
exercised against a two-criterion trial authored in `tests/builders.py`.

## Gate 4: Measurement — Core ✅

Derive gold labels from the hidden manifests, build the offline grading harness,
run the one-shot baseline and the no-verifier configuration, and compute the
counts of the [measurement plan](../evaluation/phase-1-benchmark-plan.md).

**Exit criteria**

- Expected states are derived by code from manifests and authored expressions; no label is model-produced
- The grading harness scores every variant with identical configuration, and its runtime-feedback role is a separate call site
- Every Track 1 invariant is reported pass or fail
- Grounding, accuracy, and cost are reported as counts over stated denominators, with the number of scenarios, trials, and propositions shown
- The held-out pair is assessed once, after development numbers are settled, and reported separately
- Propositions whose expected state cannot be derived are visible as Coverage-Only and excluded from accuracy counts

All met, issues #32, #33, #34 and #36, with one qualification: the runs replay
authored transcripts rather than a recorded model run, so the published counts
measure the harness. `fixtures/transcripts/README.md` and
[the results](../evaluation/development-results.md) both say so, and a reported
result about model behaviour is recorded from the hosted or local adapter.

## Gate 5: Report — Core ✅

One self-contained static page per run, ordered verdict-first per specification
section 15, published as a hosted page and viewable offline.

**Exit criteria**

- The page opens with a plain-language summary, then the worked criterion, then the verifier catch, then the baseline comparison
- Citations link to the cited FHIR JSON path and the exact trial source span
- The run-independent counts sit in a labelled section that says it is not a fact about the run above it
- At least one report covers a run in which the system fails
- No network fetch at view time; print styles implemented; no blended score anywhere
- A reader with no domain vocabulary can reach the claim within five minutes

Issues #40 through #42 and #45 are met with one exception, recorded rather than
quietly dropped: **the last exit criterion above is not verified.** The eight
items are asserted present and reachable by test, and the report is ordered so
they come first, but no reader who had not seen the project was ever timed
against it. The claim this repository can make is that the page contains the
eight items; the claim it cannot make is that a stranger finds them in five
minutes.

[The five-minute check](../evaluation/five-minute-check.md) carries the mapping,
the protocol for anyone who wants to run it, and that decision.

## What was cut

Candidate retrieval — BM25, dense embeddings, reciprocal-rank fusion, candidate
filters, and the corpus they would rank — and the inferential statistics
apparatus: pre-registration, cluster bootstrap, permutation testing, effect
sizes, and the separate benchmark artifact. Also Evidence Reuse, two of three
baselines, and both supervisor-only ablations. Issues #21, #22, #23, #24, #31,
#35, #37, #38, #39, #43 and #44 are closed as descoped.
