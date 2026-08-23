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

The labeled set is small by design. The binding constraint is not the number of graded observations but the number of independent clusters: 40 held-out scenario-trial pairs, defined in [`pre-registration.md`](pre-registration.md) section 5.1. Because the analysis resamples whole clusters, criterion-state macro F1 carries a confidence interval wide enough that anything short of a large difference is noise.

Release gates are therefore restricted to deterministic invariants — properties the implementation controls, listed in specification section 20. Every model-behavior measurement is a reported result rather than a gate, because gating on a statistic at this sample size invites optimizing toward the threshold.

Grounding metrics carry the primary claim, because each citation is an observation and they are far better powered than per-proposition classification accuracy. Macro F1 is reported with its confidence interval and support, and is read as a pre-registered comparison against the expression-aware one-shot B2 control rather than as an absolute capability claim.

Metrics, comparison units, statistical procedure, power, and the falsification condition are fixed in advance in [`pre-registration.md`](pre-registration.md), which is committed before any held-out run. The published report cites its commit hash.

## Benchmark Construction and Its Limits

Patient scenarios and criterion expressions are both authored by the project, so expected states are computable rather than judged. This removes LLM-grades-LLM circularity and removes large-scale manual labeling.

It also means the benchmark does not test clinical judgment on real-world ambiguous criteria. What it tests is whether the agent finds the right evidence, cites it validly, and applies the stated logic correctly.

Difficulty comes from Planted Distractors — specification section 8.3 — not from clinical subtlety. This limitation is stated in the published report, not implied away.

## Dataset

**Scenarios:** 6 authored synthetic patients. S1–S4 development, S5–S6 held-out.

**Trials with authored expressions:** 10–12. T1–T8 development, T9–T12 held-out.

**Corpus:** 200–500 recruiting NSCLC trials, used for retrieval; only authored trials are assessed.

**Partitions:** development evaluation uses development scenarios against development trials. The held-out set is every pair in which the scenario or the trial is held out, which exercises generalization on both axes and yields more held-out observations than a scenario-only split.

**Labeled volume:** 80–120 authored atomic propositions across all trials, roughly 7–10 per trial. Evaluated against scenarios these yield 72 scenario-trial pairs in total, of which **40 are held out**, carrying roughly 280–400 held-out graded observations.

The three counts are different quantities and are never used interchangeably. Proposition, observation, and cluster are defined in [`pre-registration.md`](pre-registration.md) section 5.1; the cluster count is what governs every interval in this plan.

**Balance requirement:** at least 8 held-out examples per Criterion State, and at least one held-out example per Unknown Reason. Because expressions and scenarios are authored, this is a design obligation on Gate 2 and Gate 3, not an outcome to hope for. Largest-to-smallest state support ratio no greater than 3:1.

## Baselines and Variants

| Variant | Description |
| --- | --- |
| B0 | Deterministic structured-field checks only; unsupported semantics become `unknown` |
| B1 | Raw-text one-shot model over the permitted patient evidence and source criterion text; measures the end-to-end improvement over a conventional prompt |
| B2 | Expression-aware one-shot model over the same permitted patient evidence and Authored Criterion Expression as Full, but without tool selection, deterministic routing, verification, or correction; isolates the orchestration contribution |
| Full | Patient Timeline, authored expressions, tool selection, deterministic routing, verification, one correction |

B1 and B2 use the same model family, patient-evidence boundary, output schema, decoding policy, and cost accounting as Full. B1 deliberately receives raw criterion text while B2 and Full receive the authored expression; results label that difference rather than claiming identical inputs.

**A shared boundary is not shared context.** What each variant actually receives in its prompt is fixed in [`pre-registration.md`](pre-registration.md) section 2.1 and is not left to implementation. The consequence declared there governs how every result in this plan is read: B2 is handed the complete Patient Timeline, while Full sees only what its tool calls return, so **Full is the information-disadvantaged arm** and must win, if it wins, on grounding discipline rather than access.

**B2 is the primary control.** It isolates the contribution of orchestration alone, so every comparison supporting the architectural claim is against B2. B1 is retained as the end-to-end improvement over a conventional prompt and is reported as secondary context: a gain over B1 conflates the value of having a structured expression with the value of orchestration, and must never be substituted for the B2 comparison.

### Verifier Role Separation

One verifier implementation serves two roles, per specification section 8.1. Offline **grading** runs against the final outputs of every variant with identical code and configuration, and never flows back into the system under test. **Feedback** runs inside Full's loop only, where its verdict triggers the single permitted correction.

Baselines are graded by a standard they were never allowed to consult. That asymmetry is the architectural difference under measurement, and it is stated wherever results appear.

Citation validity is consequently reported at three points, so the two mechanisms are separable:

| Measurement point | Attributes value to | Comparable to B2? |
| --- | --- | --- |
| 1. B2 | — (control) | — |
| 2. Full, before correction | Tool-mediated evidence selection and deterministic routing | **Yes** — the only comparable point |
| 3. Full, after correction | The bounded correction loop | No — bounded at 100% by construction |

Point 3 is not a measurement. Specification section 20 gates final-output reference validity at 100%, and the verifier reaches that gate by degrading whatever it cannot verify to `unknown`. Comparing point 3 against B2 compares a result to an architectural guarantee. Every comparison supporting the architectural claim, including the falsification condition below, uses point 2.

Point 3 is reported for one purpose — to quantify what the correction loop converts — and never without the verification-induced `unknown` rate that quantifies its cost.

## Ablations

Each is a configuration flag, not a separate implementation. The first two are core. The supervisor-only ablations are reported only when the additive Trial Supervisor gate is built.

| Ablation | Question it answers |
| --- | --- |
| No deterministic tools | Does routing dates, numbers, and Boolean logic out of the model matter? |
| No verifier | What does evidence verification actually buy? |
| No evidence reuse (supervisor only) | Does cross-criterion reuse reduce cost, and at what accuracy risk? |
| Early termination on (supervisor only) | How much cost does blocker-first termination save, and does the conclusion change? |

## Track 1: Deterministic Invariants — Release Gates

These are the only release gates. Each is a property the implementation controls, reported as pass or fail.

| Invariant | Gate |
| --- | ---: |
| Patient and trial reference validity in final output | 100% |
| Deterministic aggregation accuracy | 100% |
| Verifier catch rate on injected faults | 100% |
| Unsupported assessments surviving verification in final output | 0 |
| Criterion Coverage, supervisor flags off | 100% |
| Citations dated after `assessment_as_of` in final output | 0 |
| Infrastructure Failures scored as `unknown` | 0 |

Reference validity is measured per citation across every variant, using the offline grading verifier.

The distinction between the fourth invariant and its statistical counterpart matters. Zero unsupported assessments in final output is an invariant, structurally guaranteed by the verifier. The **pre-correction unsupported-assessment rate** is a model-behavior statistic, reported in Track 2 with a confidence interval and never gated.

## Track 2: Grounding — Primary Reported Results

These carry the architectural claim. Each citation is an observation, so they are better powered than state accuracy.

| Metric | Unit of observation | Reported |
| --- | --- | --- |
| Patient-reference validity | Per citation | B2, Full pre-correction, Full post-correction |
| Trial-reference validity | Per citation | B2, Full pre-correction, Full post-correction |
| Unsupported-assessment rate before correction | Per `met`/`not_met` proposition | All variants |
| Patient-evidence precision | Per cited item | All variants |
| Patient-evidence recall | Per gold item | All variants |
| Context-selection recall | Per proposition | Full and ablations |
| **Verification-induced `unknown` rate** | Per proposition committed before correction | Full |

Context-selection recall measures whether the agent's tool calls retrieved the gold Patient Evidence before assessing. All values carry bootstrap confidence intervals. No threshold applies.

The verification-induced `unknown` rate is the proportion of propositions on which Full held `met` or `not_met` before correction and returned `unknown` after it. It exists because the verifier's cost is otherwise invisible: a verifier that rejected every assessment would report perfect final citation validity and be worthless. It is published in the same table and at the same prominence as post-correction citation validity, never separately.

## Track 3: Criterion State Accuracy — Reported, Not Gated

Criterion-state macro F1, per-state precision and recall, `unknown` recall, and Match Conclusion accuracy. No metric in this track carries a threshold.

Results are reported per Criterion Category so demographic performance cannot mask biomarker, treatment, or temporal failures, and per state so imbalance stays visible.

### Statistical Procedure

Fixed in advance in [`pre-registration.md`](pre-registration.md):

- **Design:** paired over held-out observations; every variant sees the identical observation set.
- **Test:** paired bootstrap, 10,000 resamples, resampled at the cluster level — whole scenario-trial pairs, with all their observations travelling together. A cluster-level permutation test accompanies the primary grounding comparison.
- **Direction:** two-sided. Full may be worse than B2, and that outcome is reportable.
- **Threshold:** none. Effect size and 95% confidence interval are published regardless of significance.
- **Precision:** governed by the 40 held-out clusters, not by the 280–400 observations inside them. The provisional detectable band is roughly 15–25 percentage points in macro F1, and it is **recomputed from development-set discordance and intra-cluster correlation, and committed as a dated amendment, before the held-out run begins**. Differences below the committed band are reported as inconclusive — neither equivalence nor improvement.
- **Multiplicity:** the primary comparison is Full-before-correction versus B2 on grounding metrics. Everything else is labeled exploratory and cannot support the architectural claim.

## Track 4: Cost and Value

Measured from run traces, never estimated by hand. Reported per criterion assessment, never per model call: B2 issues one call per criterion while Full issues one or more per proposition plus verification and any correction, so per-call comparison would flatter Full and is prohibited.

- Model calls, input and output tokens, and wall-clock latency per criterion assessment
- Estimated cost per matching run
- Token and model-call reduction from `evidence_reuse`, if Gate 5 is built
- Token and latency reduction from `early_termination`, with any Match Conclusion changes reported alongside

**Declared in advance:** Full is expected to cost several times B2 per criterion assessment. This is a consequence of per-proposition assessment, not a defect, and the ratio is published whether or not it is favorable.

Every cost figure appears beside the grounding metric it purchased, in one paired table. No cost figure is published without its value figure, and none without its cost.

Budgets are calibrated on development data and frozen before held-out evaluation. At most one correction per proposition. Hidden SDK or provider retries are prohibited; constrained-decoding retries are recorded explicitly.

## Falsification Condition

Declared before any held-out run:

> If **Full before correction** shows no detectable difference from B2 in patient-reference validity, trial-reference validity, or the unsupported-assessment rate over held-out observations, the central claim of this project is unsupported, and that conclusion is published as the headline result.

The measurement point is named deliberately. Anchored to post-correction citation validity the condition could never fire, because that quantity is 100% by construction; a falsification condition that cannot fail produces the appearance of a passed test. The correction loop is evaluated separately and cannot rescue a null.

Full matching B2 on macro F1 while exceeding it on grounding metrics does **not** falsify the claim, since the claim is primarily about grounding trustworthiness. That outcome is reported plainly as a grounding gain without an accuracy gain.

Passing every deterministic release gate while failing this condition is a possible outcome. The gates certify software correctness, not architectural value.

## Track 5: Retrieval — Additive

Reported only if Gate 3 is built.

| Invariant | Gate |
| --- | ---: |
| Filter-induced loss of known relevant trials | 0 |

Filter loss is a deterministic invariant and is gated. Recall figures are reported without thresholds: Recall@5 and Recall@20 over authored target trials, as three rows for BM25-only, dense-only, and RRF, plus per-channel contribution and fusion gain. The intended headline is concrete, for example how many target trials RRF placed in the top five that neither channel reached alone.

Retrieval metrics stay separate from criterion-state metrics. No blended score is reported.

## End-to-End Held-Out Suite

Run the held-out pairs through the complete pipeline: retrieval, top-5 presentation, top-3 assessment, verification, and report generation.

The suite verifies Candidate Set completeness, immutable Retrieval Rank, assessed and unassessed labeling, Criterion Coverage, blocker and unresolved and not-assessed counts, Match Conclusion derivation, citation validity, snapshot warnings, trace completeness, and operational measurements.

This is system evaluation. It is not evidence of clinical generalization.

## Failure Analysis

Publish a failure taxonomy with at least two genuine failure cases carrying full traces, and at least three cases where Full beats the expression-aware one-shot B2 control. For each failure, record the category, the proximate cause, whether the verifier caught it, and whether the correction cycle helped.

Null, inconclusive, and unfavorable results are published with the same prominence as favorable ones, including any case where B2 matches or beats Full.

## Reproducibility

Each run records patient and trial hashes, partition, embedding model, language model and revision, prompt and schema versions, decoding configuration, tool and supervisor configuration, evaluator code version, seed, latency, tokens, estimated cost, and hardware profile.

Frozen outputs can be re-graded without rerunning the model. Every published number links to a reproducible run artifact and cites the pre-registration commit hash.

Configuration is frozen before the first held-out run. If a held-out run exposes a defect requiring a configuration change, the report states what changed, why, and that affected results were re-run and labeled as a second held-out pass.

## Optional Later Work

An LLM judge may analyze rationale quality or cluster failure themes only after calibration against human ratings, reporting model, version, prompt, agreement, false-pass rate, and false-fail rate. Generator-as-judge results require an independently reported control. Such analysis never becomes a primary metric or a release gate.
