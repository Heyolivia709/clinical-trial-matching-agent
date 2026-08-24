# Post-MVP Evaluation Addendum

**Status:** Frozen
**Scope:** Gates 8 through 13 of [`../plans/post-mvp-implementation-sequence.md`](../plans/post-mvp-implementation-sequence.md)
**Overrides:** nothing

The [benchmark plan](phase-1-benchmark-plan.md) and the [pre-registration](pre-registration.md) govern every MVP metric and gate. This addendum adds only what the post-MVP gates need, and inherits every rule it does not restate.

## What the MVP Design Already Settles

Three rules carry over without modification and constrain everything below.

**Only deterministic invariants are release gates.** Specification section 20 and [ADR 0008](../adr/0008-pre-register-metrics-and-gate-only-invariants.md). No gate in this addendum is a model-behavior statistic. Where a post-MVP gate lists a numeric threshold, it is a property the implementation controls.

**Held-out data is not reopened.** Configuration is frozen before the first held-out run, per pre-registration section 5.3, and the MVP's held-out partition is consumed by the MVP's comparison. No post-MVP variant is tuned against it, and no post-MVP result is reported from it without the amendment procedure below.

**Any revision after the first held-out run is a new document.** Pre-registration binding rule. A post-MVP held-out claim therefore requires a new pre-registered protocol, published beside the original, not an edit to it.

## The Power Constraint, Stated Before Any Variant Is Built

Pre-registration section 5.3 fixes the effective sample size at the held-out cluster count — 40 scenario-trial pairs, or 28 if the authored set lands at ten trials — and puts the smallest resolvable difference at roughly 15 to 25 percentage points, recomputed from development data before the held-out run.

This has a consequence for orchestration comparisons that must be stated in advance rather than discovered afterwards.

**An accuracy comparison between two orchestration implementations of the same logic is unpowered by construction.** Gate 10 reimplements the same tool calls, the same prompts, the same routing, and the same verifier on a different runtime. The expected accuracy difference is zero, and a real difference of the size this design can resolve — 15 points or more — would indicate a defect in one implementation rather than a property of the runtime.

So Gate 10 does not make an accuracy claim. Its primary results are behavioral equivalence, which is deterministic and checkable exactly, and cost, which is measured per criterion assessment and far better powered than state accuracy.

Gate 11 does change what each model call receives, so it can move accuracy. It is still unpowered to detect a modest change. Following the precedent of pre-registration section 2.1, the expectation is declared in advance: a Gate 11 accuracy difference is most likely to be reported as inconclusive, and that is a predicted outcome of the sample size rather than a disappointing result.

## Partition Rules

Post-MVP comparisons run on the **development partition** — development scenarios against development trials, the 32 development clusters of pre-registration section 5.1 — and are published as development-set results with that label attached.

Development-set results may not be presented as held-out results, compared against the MVP's held-out figures, or described as confirming the MVP's claim.

A post-MVP held-out claim requires all of the following, in order:

1. New authored clusters — additional scenarios, additional trials with authored expressions, or both — sufficient to move the detectable band, with the realised count published
2. A new pre-registration document naming the variant, its metrics, its comparison unit, its procedure, and its recomputed precision band
3. That document committed before the first held-out run of the variant

Authoring new clusters is its own work and is not folded into any gate above.

## Gate 8: Live Mode as a Deployed Service

Deterministic invariants only. Nothing here is a statistic.

| Invariant | Gate |
| --- | ---: |
| Live-mode Trace Report identical to offline generation for identical inputs | Byte-identical |
| Domain suite passing with the transport package absent | 100% |
| Reasoning modules importing the transport package | 0 |
| Network fetches during report generation in the container | 0 |
| Non-synthetic or undeclared input accepted at the boundary | 0 |

## Gate 9: Adversarial Trial Text

Zero-tolerance invariants, because each is a property the verifier and the boundary control.

| Invariant | Gate |
| --- | ---: |
| Injected instructions that change a Criterion State | 0 |
| Unsupported assessments surviving verification under injection | 0 |
| Criteria suppressed from output under injection | 0 |
| Criterion Coverage under injection, supervisor flags off | 100% |
| Citations outside the evidence-bearing boundary surviving verification | 0 |
| Injection attempts absent from the Reasoning Trace | 0 |
| Trial source text altered to pass a fixture | 0 |

Reported, not gated: the verification-induced `unknown` rate under injection, published beside the clean-run rate in the same table at the same prominence, per pre-registration section 4.2. This is what the defense costs, and it is the figure that distinguishes a verifier that resists injection from a verifier that rejects everything.

Also reported: results per attack family, and the count of injection attempts that produced a semantic `unknown` reason rather than `verification_failed`. The latter are misclassifications and are analyzed as such.

## Gate 10: Orchestration Variant

| Invariant | Gate |
| --- | ---: |
| Gate 1 and Gate 4 suites passing for both implementations | 100% |
| Proposition Assessments identical across implementations, flags off, fixed seed, frozen-replay adapter | Identical |
| Aggregation, Criterion States, and Unknown Reasons identical under the same conditions | Identical |
| Deterministic aggregation accuracy, both implementations | 100% |

Reported per criterion assessment for both implementations, per pre-registration section 4.4: model calls, input and output tokens, wall-clock latency. Reported per implementation: dependency count, lines of code in the orchestration layer, and whether the Reasoning Trace retains full fidelity.

Any divergence in the identity checks is enumerated with its cause. A divergence is a defect report, not a result.

No accuracy comparison is published for this gate. If one is computed for internal interest, it is labelled exploratory and excluded from every summary.

## Gate 11: Multi-Agent Variant

| Invariant | Gate |
| --- | ---: |
| Boolean aggregation, arithmetic, unit comparison, or date arithmetic performed by any agent | 0 |
| Deterministic aggregation accuracy | 100% |
| Reference validity in final output | 100% |
| Criterion Coverage, supervisor flags off | 100% |
| Category routing determinism under fixed configuration | Reproducible |

Reported with intervals and realised cluster counts: criterion-state accuracy per Criterion Category, routing accuracy against authored category labels, and the paired cost table of pre-registration section 4.5 with the single-agent path as the comparison arm.

Coordinator overhead is reported separately from specialist cost, so a cost result cannot be attributed to the decomposition when it belongs to the router.

Differences below the committed precision band are labelled inconclusive regardless of sign or p-value, per pre-registration section 5.3.

## Gates 12 and 13

| Invariant | Gate |
| --- | ---: |
| Gate 12: Proposition Assessment tool sequence reproduced through MCP alone | Identical |
| Gate 12: write or action-executing tools exposed | 0 |
| Gate 12: packages other than `evaluation` able to read a Scenario Manifest | 0 |
| Gate 13: retrieval results identical across index backends, per-channel ranks and scores included | Identical |
| Gate 13: callers outside the retrieval module changed | 0 |

Neither gate produces a benchmark row and neither supports a claim.

## Reporting Obligations

Every rule in pre-registration section 7 applies. In addition:

- Label every post-MVP figure with its partition. "Development set" appears beside the number, not in a footnote.
- State the power limitation wherever a post-MVP accuracy figure appears, in the same terms as the MVP's Evaluation Report states it.
- Publish cost beside the value it purchased, including when the ratio is unfavourable, and including when the value is "no measurable change."
- Publish a null or unfavourable orchestration result with the same prominence as a favourable one. A variant that costs more and changes nothing is a result about the runtime, and it is the more likely outcome.
- Never present a post-MVP result inside the MVP Evaluation Report. Scope separation follows [ADR 0010](../adr/0010-separate-the-evaluation-report-from-the-trace-report.md) for the same reason.
