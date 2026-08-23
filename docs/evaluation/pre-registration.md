# Pre-Registration: Cost and Value Reporting Protocol

**Status:** Must be committed before any held-out run
**Version:** 2
**Date:** 2026-08-23 (v1: 2026-08-22)
**Binding rule:** The published report cites this document's commit hash. Any revision after the first held-out run is a new document with the change and its reason recorded, and both versions are published.

**Revision note (v2).** No held-out run has occurred and no implementation exists, so v1 is revised in place rather than superseded. Three defects were corrected: v1 never defined what B2 actually receives in its prompt (§2), v1's falsification condition was anchored to a measurement point that cannot fail (§6), and v1's power statement asserted a sample size inconsistent with the benchmark plan and a precision inconsistent with its own clustered resampling design (§5). One metric was added: the verification-induced `unknown` rate (§4.2), without which the verifier's cost is invisible.

This protocol fixes what will be measured, how it will be compared, and what result would falsify the project's claim — before the numbers exist. Without it, "the agent is worth its cost" is unfalsifiable, because the metric can always be chosen after the fact.

## 1. Claim Under Test

Bounded agent orchestration — per-proposition tool selection, deterministic routing of dates, numbers, and Boolean logic, evidence verification, and one targeted correction — produces more trustworthy grounded assessments than a single model call given the same criterion expression and the same patient evidence boundary.

The claim is about grounding trustworthiness first and state accuracy second. It is not a claim about clinical validity.

## 2. Primary Control

**B2, the expression-aware one-shot baseline**, is the primary control. It receives the same Authored Criterion Expression, the same permitted patient evidence, the same output schema, the same model family, and the same decoding policy as Full, but has no tool selection, no deterministic routing, no verification, and no correction.

B2 therefore isolates the contribution of orchestration alone. Any comparison used to support the claim in section 1 is against B2.

B1, the raw-text one-shot baseline, is retained and reported as the end-to-end improvement over a conventional prompt. It is a secondary, contextual number and must not be substituted for B2 when stating the architectural claim, because a gain over B1 conflates the value of having a structured expression with the value of orchestration.

B0, the deterministic baseline, is retained as the floor.

### 2.1 Prompt Contents per Variant

"The same patient-evidence *boundary*" fixes what each variant is permitted to see. It does not fix what each variant is actually given. Those are different quantities and the headline comparison depends on the difference, so both are fixed here.

| Variant | Patient input actually placed in context | Criterion input | Tools | Verifier |
| --- | --- | --- | --- | --- |
| B0 | Patient Timeline, structured comparable fields only | Authored Criterion Expression | none — deterministic field checks | grading only |
| B1 | Raw FHIR Bundle entries for the four evidence-bearing resource types, unnormalized | Verbatim source criterion text, no expression | none | grading only |
| B2 | The complete normalized Patient Timeline for the scenario, rendered in the prompt | Authored Criterion Expression and verbatim source text | none | grading only |
| Full | Timeline Tool results only, per atomic proposition | Authored Criterion Expression and verbatim source text | the five Timeline Tools | grading and feedback |

No variant receives the Scenario Manifest, the full trial record, or unsupported patient content beyond its identity inventory.

**Declared consequence: B2 has strictly more patient context in-prompt than Full has at any single step.** Full sees only what its tool calls return; B2 is handed the whole timeline. The comparison is therefore *selective retrieval under verification* versus *full context in one pass*, not *less information* versus *more information*. Full is the information-disadvantaged arm by construction, and any win must come from grounding discipline rather than from access.

**Declared expectation, before any run.** Authored scenarios carry roughly 30–45 evidence-bearing facts. At that size B2 is not context-limited, so a criterion-state macro F1 difference between B2 and Full is *not* expected, and under the precision stated in section 5 it would most likely be reported as inconclusive even if present. This is why section 1 places grounding trustworthiness first and state accuracy second, and why section 6 falsifies on grounding metrics. An inconclusive macro F1 result is a predicted outcome of this design, not a disappointment discovered afterwards.

A corollary for scope: if the project later wants to claim that orchestration improves accuracy and not only grounding, the honest way to earn it is a scenario with a substantially larger timeline, not a larger statistical apparatus over these six.

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
| **Verification-induced `unknown` rate** | Per proposition Full assessed `met` or `not_met` before correction |

Citation validity is reported at three points so the two mechanisms are separable:

1. B2
2. Full, before correction
3. Full, after correction

The B2-to-Full-before-correction difference attributes value to tool-mediated evidence selection and deterministic routing. The Full-before-to-after difference attributes value to the correction loop.

**Only measurement points 1 and 2 are comparable.** Point 3 is bounded at 100% by construction: specification section 20 gates final-output reference validity at 100%, and the verifier reaches that gate by degrading every assessment it cannot verify to `unknown` with reason `verification_failed`. Publishing point 3 against B2 would compare a measurement to an architectural guarantee. Point 3 is reported only to quantify what the correction loop converts, and never as evidence for the section 1 claim.

**The verification-induced `unknown` rate is what point 3 costs.** It is the proportion of propositions on which Full held a committed state before correction and returned `unknown` after it. A verifier that rejected everything would score 100% final citation validity and be useless; this metric is the only thing standing between that degenerate configuration and a favourable-looking report.

**Pairing rule.** Post-correction citation validity is never published without the verification-induced `unknown` rate beside it, in the same table and at the same prominence. This obligation has the same force as the cost-value pairing in section 4.5.

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
variant | model calls | tokens | citation validity | unsupported rate | verification-induced unknown | macro F1
```

Cost columns are per criterion assessment, per section 4.4. Citation validity for Full appears at both measurement points, labelled, per section 4.2.

No cost figure is published without its paired value figure, and no value figure without its paired cost.

## 5. Statistical Procedure

### 5.1 Units

Three quantities were conflated in v1 and are separated here. Every sample-size statement in this project names which one it means.

| Term | Definition |
| --- | --- |
| **Atomic proposition** | An authored proposition belonging to a trial's Criterion Expression. A property of the trial, independent of any patient. |
| **Observation** | One graded assessment: an atomic proposition evaluated against one scenario. The unit of accuracy metrics. Grounding metrics observe citations nested inside observations. |
| **Cluster** | One scenario-trial pair. The resampling unit, because propositions within a pair share a patient, a trial, and a single agent run, and are therefore correlated. |

Derived from the benchmark plan dataset — 6 scenarios with S1–S4 development and S5–S6 held out, and 12 authored trials with T1–T8 development and T9–T12 held out:

| Quantity | Count |
| --- | --- |
| Atomic propositions authored | 80–120 across all trials, roughly 7–10 per trial |
| Scenario-trial pairs, total | 72 |
| Development clusters (development scenario **and** development trial) | 32 |
| **Held-out clusters** (scenario **or** trial held out) | **40** |
| Held-out observations | roughly 280–400 |

If the authored set lands at 10 trials rather than 12, the held-out cluster count falls to 28 and every interval widens accordingly. The realised counts are published beside the results.

### 5.2 Procedure

**Design.** Paired over held-out observations: every variant is evaluated on the identical observation set.

**Test.** Paired bootstrap, 10,000 resamples, **resampled at the cluster level** — whole scenario-trial pairs are drawn with replacement and all observations inside a drawn pair travel with it. A permutation test, also permuting at the cluster level, is reported alongside for the primary grounding comparison.

**Direction.** Two-sided. Full may be worse than B2, and that outcome is reportable.

**Threshold.** None. There is no minimum effect size that constitutes success. Effect size and its 95% confidence interval are published regardless of significance.

**Multiplicity.** The primary comparison is Full versus B2 on grounding metrics at measurement point 2, per section 4.2. All other comparisons are secondary and labeled exploratory; no correction is applied to them and they are not used to support the section 1 claim.

### 5.3 Precision

**What v1 got wrong.** v1 stated that roughly 80 held-out propositions would resolve differences of 8–12 percentage points in macro F1. Two errors. First, 80 held-out propositions is not a quantity this dataset produces; the benchmark plan elsewhere says 40–60, and the correct figures are 40 held-out clusters carrying 280–400 observations. Second and more seriously, a precision of 8–12 points is what you obtain by treating each proposition as independent — which is exactly the assumption the cluster-level resampling in section 5.2 exists to reject. v1's power statement and v1's test contradicted each other.

**Effective sample size is the cluster count, not the observation count.** With 40 held-out clusters and a plausible discordance rate, the standard error of a paired difference in a proportion-like metric is on the order of 0.07–0.09, so the smallest difference this design can reliably resolve is roughly **15–25 percentage points**, not 8–12. Adding observations inside a cluster does not narrow this; only adding scenarios or trials does.

**This is a provisional band and may not be cited as final.** The discordance rate that determines it cannot be known before data exists. Therefore:

1. Before the first held-out run, the realised discordance rate and intra-cluster correlation are computed **on development data only**, for each primary metric.
2. The detectable-difference band is recomputed from those development quantities and committed as a dated amendment to this document, cited by its own commit hash.
3. The held-out run does not begin until that amendment exists.
4. Observed differences below the committed band are reported as **inconclusive** — neither equivalence nor improvement — regardless of the sign of the point estimate or the p-value.

Fixing the procedure in advance and the number from development data is stricter than fixing a number in advance that was never derived from anything.

**Consequence, accepted.** At this cluster count the study is powered to detect large architectural effects and is not powered to detect modest ones. Grounding metrics are the better-powered family — citations are more numerous than propositions and the verifier grades them deterministically — but they are clustered too, and cluster-level resampling caps their precision by the same 40. The project's evaluation claim is the discipline of the protocol and the transparency of the intervals, not the resolving power of six authored patients.

**No optimization on held-out data.** Configuration is frozen before the first held-out run. If a held-out run reveals a defect requiring a configuration change, the report states what changed, why, and that the affected results are re-run and labeled as a second held-out pass.

## 6. Falsification Condition

Declared in advance:

> If **Full before correction** shows no detectable difference from the expression-aware one-shot control B2 in patient-reference validity, trial-reference validity, or the unsupported-assessment rate over held-out observations, the central claim of this project is unsupported, and that conclusion is published as the headline result.

**Why the measurement point is named.** v1 falsified on "citation validity" without saying which of the three points in section 4.2 it meant. Read as the post-correction point, the condition could never fire: final-output reference validity is 100% by construction and gated as an invariant, so Full exceeds B2 there by architecture rather than by result. A falsification condition that cannot fail is worse than none, because it produces the appearance of a passed test. The condition is therefore anchored to measurement point 2, the only point at which Full and B2 are doing comparable work.

**The correction loop is evaluated separately and cannot rescue a null.** Its effect is the point-2-to-point-3 difference, published beside the verification-induced `unknown` rate it costs, per section 4.2. If the falsification condition above fires, the correction loop's contribution is reported as a property of the verifier rather than as evidence for orchestration, and the headline stands.

A secondary null — Full matching B2 on criterion-state macro F1 while exceeding it on grounding metrics — does not falsify the claim, because the claim is primarily about grounding trustworthiness. That outcome is reported plainly as a grounding gain without an accuracy gain, and per section 2.1 it is the predicted outcome rather than a surprise.

Passing every deterministic release gate while failing this falsification condition is a possible outcome. The gates certify software correctness, not architectural value.

## 7. Reporting Obligations

- Publish the pre-registration commit hash beside every quantitative claim, and the section 5.3 precision-amendment commit hash beside every interval.
- Publish null, inconclusive, and unfavorable results with the same prominence as favorable ones.
- Publish at least two genuine failure cases with full traces.
- State the realised cluster count, observation count, and per-state support beside every average. "n" alone is ambiguous under section 5.1 and is not an acceptable label.
- Publish post-correction citation validity only beside the verification-induced `unknown` rate, per section 4.2.
- State, wherever B2 appears, that B2 receives more in-prompt patient context than Full, per section 2.1.
- Separate Infrastructure Failures from semantic `unknown` in every table.
- Record any deviation from this protocol, with its reason, in the published report.
