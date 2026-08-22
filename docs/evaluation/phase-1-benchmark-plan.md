# MVP Benchmark Plan

**Status:** Frozen
**Supersedes:** the v1 three-track plan built on TREC 2021/2022 and 500 manually labeled propositions
**Scope:** Evidence-grounding correctness, agent behavior, and operational cost. Not clinical validity.

## Evaluation Principles

- Grade deterministically. No LLM judge participates in any primary metric.
- Derive gold expected states from the hidden Scenario Manifest and the authored Criterion Expression by code. Never label them with a model.
- Keep held-out partitions frozen and inaccessible to prompt, model, retrieval, tool, or supervisor optimization.
- Report sample size, per-state support, and bootstrap confidence intervals beside every average.
- Keep every criterion visible, including Coverage-Only and `unknown` results.
- Separate Infrastructure Failures from semantic `unknown`.

## Why Grounding Metrics Lead

The labeled set is small by design. At roughly 40–60 held-out atomic propositions, criterion-state macro F1 carries a confidence interval wide enough that small differences are noise.

Primary release gates therefore rest on metrics with many observations per assessment or with hard invariants: citation validity, unsupported-assessment rate, verifier catch rate, and deterministic aggregation correctness. Every citation is an observation, so these metrics are far better supported than per-proposition classification accuracy.

Macro F1 is still reported, always with its confidence interval and support, and is read primarily as a comparison against the expression-aware one-shot B2 control rather than as an absolute capability claim.

## Benchmark Construction and Its Limits

Patient scenarios and criterion expressions are both authored by the project, so expected states are computable rather than judged. This removes LLM-grades-LLM circularity and removes large-scale manual labeling.

It also means the benchmark does not test clinical judgment on real-world ambiguous criteria. What it tests is whether the agent finds the right evidence, cites it validly, and applies the stated logic correctly.

Difficulty comes from Planted Distractors — specification section 8.3 — not from clinical subtlety. This limitation is stated in the published report, not implied away.

## Dataset

**Scenarios:** 6 authored synthetic patients. S1–S4 development, S5–S6 held-out.

**Trials with authored expressions:** 10–12. T1–T8 development, T9–T12 held-out.

**Corpus:** 200–500 recruiting NSCLC trials, used for retrieval; only authored trials are assessed.

**Partitions:** development evaluation uses development scenarios against development trials. The held-out set is every pair in which the scenario or the trial is held out, which exercises generalization on both axes and yields more held-out observations than a scenario-only split.

**Labeled volume:** 80–120 atomic propositions total, at least 40 held out.

**Balance requirement:** at least 8 held-out examples per Criterion State, and at least one held-out example per Unknown Reason. Because expressions and scenarios are authored, this is a design obligation on Gate 2 and Gate 3, not an outcome to hope for. Largest-to-smallest state support ratio no greater than 3:1.

## Baselines and Variants

| Variant | Description |
| --- | --- |
| B0 | Deterministic structured-field checks only; unsupported semantics become `unknown` |
| B1 | Raw-text one-shot model over the permitted patient evidence and source criterion text; measures the end-to-end improvement over a conventional prompt |
| B2 | Expression-aware one-shot model over the same permitted patient evidence and Authored Criterion Expression as Full, but without tool selection, deterministic routing, verification, or correction; isolates the orchestration contribution |
| Full | Patient Timeline, authored expressions, tool selection, deterministic routing, verification, one correction |

B1 and B2 use the same model family, patient-evidence boundary, output schema, decoding policy, and cost accounting as Full. B1 deliberately receives raw criterion text while B2 and Full receive the authored expression; results label that difference rather than claiming identical inputs.

## Ablations

Each is a configuration flag, not a separate implementation. The first two are core. The supervisor-only ablations are reported only when the additive Trial Supervisor gate is built.

| Ablation | Question it answers |
| --- | --- |
| No deterministic tools | Does routing dates, numbers, and Boolean logic out of the model matter? |
| No verifier | What does evidence verification actually buy? |
| No evidence reuse (supervisor only) | Does cross-criterion reuse reduce cost, and at what accuracy risk? |
| Early termination on (supervisor only) | How much cost does blocker-first termination save, and does the conclusion change? |

## Track 1: Grounding and Verification — Primary Gates

| Metric | Gate |
| --- | ---: |
| Patient and trial reference validity | 100% |
| Deterministic aggregation accuracy | 100% |
| Verifier catch rate on injected faults | 100% |
| Unsupported-assessment rate | ≤ 2% |
| Criterion Coverage, flags off | 100% |
| Evidence cited after `assessment_as_of` | 0 |
| Infrastructure Failures scored as `unknown` | 0 |

Reference validity is measured per citation. Unsupported-assessment rate is the share of `met` or `not_met` results whose citations fail verification before correction.

## Track 2: Criterion State Accuracy — Reported with Intervals

| Metric | Gate |
| --- | ---: |
| Criterion-state macro F1 | ≥ 70% |
| `unknown` recall | ≥ 85% |
| Patient-evidence precision | ≥ 90% |
| Patient-evidence recall | ≥ 80% |
| Match Conclusion accuracy | ≥ 80% |
| Macro-F1 gain over expression-aware one-shot B2 | ≥ 5 percentage points |
| Unsupported-assessment reduction versus B2 | ≥ 30% |

All values carry bootstrap confidence intervals. Results are reported per Criterion Category so demographic performance cannot mask biomarker, treatment, or temporal failures.

Context-selection recall measures whether the agent's tool calls retrieved the gold Patient Evidence before assessing.

## Track 3: Retrieval — Additive

Reported only if Gate 3 is built.

| Metric | Gate |
| --- | ---: |
| Filter-induced loss of known relevant trials | 0 |
| Recall@20 over authored target trials | ≥ 90% |
| Recall@5 over authored target trials | ≥ 70% |

Report BM25-only, dense-only, and RRF as three rows, plus per-channel contribution and RRF gain. The intended headline is concrete, for example how many target trials RRF placed in the top five that neither channel reached alone.

Retrieval metrics stay separate from criterion-state metrics. No blended score is reported.

## Track 4: Operational Cost

Measured from run traces, never estimated by hand:

- Latency per criterion assessment and per trial assessment
- Model calls per trial assessment
- Input and output tokens
- Estimated cost per matching run
- Token and model-call reduction from `evidence_reuse`
- Token and latency reduction from `early_termination`, with any Match Conclusion changes reported alongside

Budgets are calibrated on development data and frozen before held-out evaluation. At most one correction per proposition. Hidden SDK or provider retries are prohibited; retries from constrained decoding are recorded explicitly.

## End-to-End Held-Out Suite

Run the held-out pairs through the complete pipeline: retrieval, top-5 presentation, top-3 assessment, verification, and report generation.

The suite verifies Candidate Set completeness, immutable Retrieval Rank, assessed and unassessed labeling, Criterion Coverage, blocker and unresolved and not-assessed counts, Match Conclusion derivation, citation validity, snapshot warnings, trace completeness, and operational measurements.

This is system evaluation. It is not evidence of clinical generalization.

## Failure Analysis

Publish a failure taxonomy with at least two genuine failure cases carrying full traces, and at least three cases where Full beats the expression-aware one-shot B2 control. For each failure, record the category, the proximate cause, whether the verifier caught it, and whether the correction cycle helped.

## Reproducibility

Each run records patient and trial hashes, partition, embedding model, language model and revision, prompt and schema versions, decoding configuration, tool and supervisor configuration, evaluator code version, seed, latency, tokens, estimated cost, and hardware profile.

Frozen outputs can be re-graded without rerunning the model. Every published number links to a reproducible run artifact.

## Optional Later Work

An LLM judge may analyze rationale quality or cluster failure themes only after calibration against human ratings, reporting model, version, prompt, agreement, false-pass rate, and false-fail rate. Generator-as-judge results require an independently reported control. Such analysis never becomes a primary metric or a release gate.
