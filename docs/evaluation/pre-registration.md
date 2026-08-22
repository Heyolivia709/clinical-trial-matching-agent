# Pre-Registration: Cost and Value Reporting Protocol

**Status:** Must be committed before any held-out run
**Date:** 2026-08-22
**Binding rule:** The published report cites this document's commit hash. Any revision after the first held-out run is a new document with the change and its reason recorded, and both versions are published.

This protocol fixes what will be measured, how it will be compared, and what result would falsify the project's claim — before the numbers exist. Without it, "the agent is worth its cost" is unfalsifiable, because the metric can always be chosen after the fact.

## 1. Claim Under Test

Bounded agent orchestration — per-proposition tool selection, deterministic routing of dates, numbers, and Boolean logic, evidence verification, and one targeted correction — produces more trustworthy grounded assessments than a single model call given the same criterion expression and the same patient evidence boundary.

The claim is about grounding trustworthiness first and state accuracy second. It is not a claim about clinical validity.

## 2. Primary Control

**B2, the expression-aware one-shot baseline**, is the primary control. It receives the same Authored Criterion Expression, the same permitted patient evidence, the same output schema, the same model family, and the same decoding policy as Full, but has no tool selection, no deterministic routing, no verification, and no correction.

B2 therefore isolates the contribution of orchestration alone. Any comparison used to support the claim in section 1 is against B2.

B1, the raw-text one-shot baseline, is retained and reported as the end-to-end improvement over a conventional prompt. It is a secondary, contextual number and must not be substituted for B2 when stating the architectural claim, because a gain over B1 conflates the value of having a structured expression with the value of orchestration.

B0, the deterministic baseline, is retained as the floor.

## 3. Verifier Role Separation

One verifier implementation, two call sites:

- **Grading.** Runs offline against the final outputs of every variant with identical code and configuration. Results never flow back into the system under test.
- **Feedback.** Runs inside Full's loop only, where its verdict triggers the single permitted correction.

Baselines are graded by a standard they were never allowed to consult. This asymmetry is the architectural difference being measured and is stated wherever results appear.

## 4. Pre-Registered Metrics

### 4.1 Deterministic invariants — release gates

Reported as pass or fail. These are software-correctness properties, listed in specification section 20.

### 4.2 Grounding metrics — primary reported results

| Metric | Unit of observation |
| --- | --- |
| Patient-reference validity | Per citation |
| Trial-reference validity | Per citation |
| Unsupported-assessment rate before correction | Per `met` or `not_met` proposition assessment |
| Patient-evidence precision | Per cited evidence item |
| Patient-evidence recall | Per gold evidence item |
| Context-selection recall | Per proposition |

Citation validity is reported at three points so the two mechanisms are separable:

1. B2
2. Full, before correction
3. Full, after correction

The B2-to-Full-before-correction difference attributes value to tool-mediated evidence selection and deterministic routing. The Full-before-to-after difference attributes value to the correction loop.

### 4.3 Accuracy metrics — reported with intervals, not gated

Criterion-state macro F1, per-state precision and recall, `unknown` recall, per-category breakdown, and Match Conclusion accuracy. All are reported with bootstrap confidence intervals and per-state support.

### 4.4 Cost metrics

| Metric | Unit |
| --- | --- |
| Model calls | Per criterion assessment |
| Input and output tokens | Per criterion assessment |
| Wall-clock latency | Per criterion assessment |
| Estimated cost | Per matching run |

**Comparison unit.** All cost comparisons are per criterion assessment, never per model call. B2 issues one call per criterion; Full issues one or more per atomic proposition plus verification and any correction. Per-call comparison would flatter Full and is prohibited.

**Expected direction, declared in advance.** Full is expected to cost several times B2 per criterion assessment. This is a design consequence of per-proposition assessment, not a defect. The ratio is published whether or not it is favorable.

### 4.5 Paired cost-value table

Every cost figure is published beside the grounding metric it purchased, in a single table, with the cost ratio stated explicitly:

```
variant | model calls | tokens | citation validity | unsupported rate | macro F1
```

No cost figure is published without its paired value figure, and no value figure without its paired cost.

## 5. Statistical Procedure

**Design.** Paired over held-out atomic propositions: every variant is evaluated on the identical proposition set.

**Test.** Paired bootstrap over propositions, 10,000 resamples, resampling by scenario-trial pair to respect within-pair correlation. A permutation test is reported alongside for the primary grounding comparison.

**Direction.** Two-sided. Full may be worse than B2, and that outcome is reportable.

**Threshold.** None. There is no minimum effect size that constitutes success. Effect size and its 95% confidence interval are published regardless of significance.

**Power.** With roughly 80 held-out atomic propositions in a paired design, this study can reliably detect differences of approximately 8–12 percentage points in criterion-state macro F1. Differences smaller than that will be reported as inconclusive rather than as evidence of either equivalence or improvement. Grounding metrics are better powered because each citation is an observation.

**Multiplicity.** The primary comparison is Full versus B2 on citation validity. All other comparisons are secondary and labeled exploratory; no correction is applied to them and they are not used to support the section 1 claim.

**No optimization on held-out data.** Configuration is frozen before the first held-out run. If a held-out run reveals a defect requiring a configuration change, the report states what changed, why, and that the affected results are re-run and labeled as a second held-out pass.

## 6. Falsification Condition

Declared in advance:

> If the expression-aware one-shot control B2 shows no detectable difference from Full in citation validity or unsupported-assessment rate on held-out propositions, the central claim of this project is unsupported, and that conclusion is published as the headline result.

A secondary null — Full matching B2 on criterion-state macro F1 while exceeding it on grounding metrics — does not falsify the claim, because the claim is primarily about grounding trustworthiness. That outcome is reported plainly as a grounding gain without an accuracy gain.

Passing every deterministic release gate while failing this falsification condition is a possible outcome. The gates certify software correctness, not architectural value.

## 7. Reporting Obligations

- Publish the pre-registration commit hash beside every quantitative claim.
- Publish null, inconclusive, and unfavorable results with the same prominence as favorable ones.
- Publish at least two genuine failure cases with full traces.
- State sample size and per-state support beside every average.
- Separate Infrastructure Failures from semantic `unknown` in every table.
- Record any deviation from this protocol, with its reason, in the published report.
