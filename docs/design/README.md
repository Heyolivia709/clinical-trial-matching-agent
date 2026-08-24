# Trace Report — Interface Design

**Status:** Semantic encoding accepted; visual register superseded by [ADR 0009](../adr/0009-adopt-the-trace-inspector-visual-register.md); **section inventory and ordering superseded by specification section 15 and [ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md)**
**Implements:** [MVP specification](../specs/phase-1-mvp-specification.md) section 15
**Delivered by:** Gate 5 (see [implementation sequence](../plans/phase-1-implementation-sequence.md))

The repository contained documentation only when these mockups were produced, so the interface was designed from specification section 15 rather than recreated from source. Nothing here is generated output — the real report is rendered from frozen traces by Gate 5 code.

**Read this first.** The mockups predate the current specification. Four structural decisions in them have since been reversed at the specification level, and the mockups have not been redrawn:

| Mockup assumption | Specification section 15 requires |
| --- | --- |
| Sections in pipeline order, run metadata first | Verdict-first order. Plain-language summary, then the demonstrative criterion, verifier, and baseline comparison; timeline and reproducibility header move to the back. |
| Mockup `09` is a screen of its own | One labelled section near the back, holding the invariant gates, the counts, and two worked failures — and saying it is not a fact about the run above it. |
| Three baseline columns in `08` | One baseline. Specification v7 cut the other two, so the third column goes with them. |
| No wayfinding of any kind | A persistent section index is required. |

What survives unchanged: the semantic encoding rules below, the impact-not-state rule, the separate verifier process colour, section 7 label wording, and the verbatim treatment of trial source text. Those are the parts worth keeping.

## What this interface is

A self-contained document that can be read offline, printed, and archived — not an application.

The system's value proposition is auditability: every screening conclusion traces to a specific FHIR resource in the patient record and a specific character span in the trial source text. Application chrome — breadcrumbs, back buttons, in-page tabs, per-screen headers — fragments that chain into pieces a reader must click to reassemble. A single document lets a reviewer read start to finish, print to PDF for the record, and cite "section 6, second paragraph" in a review meeting.

That argument was extended too far. It ruled out *all* wayfinding, and a ten-screen document with no index is harder to read start to finish, not easier — every trace inspector named below carries one. A persistent section index is required by section 15.1; the rejections of breadcrumbs, back buttons, in-page tabs, and per-screen headers stand.

The genre is an agent trace inspector, not a clinical dashboard and not a chat interface. Comparable artifacts: the standalone site produced by `inspect view bundle` in [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), a [promptfoo](https://www.promptfoo.dev/docs/usage/web-ui/) HTML eval report, and the trace waterfall in [Langfuse](https://langfuse.com/).

## Files

| Path | Role |
| --- | --- |
| `mockups/01`–`09` | Design reference. One file per section, drawn when the surface was still a single document. |
| `explorations/` | Rejected and superseded alternatives, retained as decision record. |
| `screenshots/` | PNG exports for inline viewing on GitHub, including interactive states. |

These are portable HTML exported from the design tool, which remains the editing source of truth. The design tool's own runtime and project format are deliberately not vendored into this repository.

Section files are static. The five interactive behaviours studied during design — criterion row expansion, citation drawers, tool-call stepping, verifier attempt toggle, baseline column toggle — exist only as screenshots here; Gate 5 implements them.

## Traceability

Mockups are identified by file number. Specification sections are written out. The two were previously both written `§N`, which made "§9" mean the evaluation mockup in one sentence and a specification section in the next.

| Mockup | Specification sections | Lands in | Order under section 15 |
| --- | --- | --- | --- |
| `01` Run overview | 4, 14, 15 | Trace Report | 10 — moves to the back |
| `02` Patient timeline | 4.2, 5, 5.1–5.4, 8.3 | report | 7 |
| `03` Retrieval | — **cut with v7** | design record only | — |
| `04` Candidate list | 7.2, 9, 13 | report | 5 |
| `05` Trial assessment | 6, 7, 7.1, 7.2, 8 | report | 6 |
| `06` Criterion detail | 7, 8, 10, 10.1, 15 | report | 2 — moves to the front |
| `07` Verifier and correction | 8.1, 8.2, 8.3, 20 | report | 3 |
| `08` Baseline comparison | 11, 16, 17 | **split** | 4 (per-criterion) / 8 (counts) |
| `09` Evaluation | — **none; see below** | report | 8 |
| *not yet designed* | 3, 15.1 | report | 1 — plain-language summary |

Two entries need explaining.

**Mockup `09` had no specification source.** v4 section 15 defined the report as generated from a frozen Matching Run and listed eight run-scoped items, none of them the benchmark; the traceability row above previously cited sections 16–20, which are not about the report at all. The section was invented to hold content that had nowhere to live. v5 gave it a home as a separate artifact; v7 folds it back into one page as a labelled section, because two artifacts for one demonstration cost a reader more than the separation buys. See [ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md).

**Mockup `08` is two things.** The per-criterion side-by-side on one criterion is run-scoped and stays where it is. The aggregate table over six scenarios belongs in the labelled counts section — without the intervals it draws, which v7 cut.

**Mockup `03` is a record of cut work.** Candidate retrieval is out of scope (specification section 18), so the screen has nothing to render. The file stays as a design study and maps to no section; the candidate list in `04` stands, over the four frozen trial records.

## Semantic encoding rules

These are binding on any implementation, independent of visual style.

### Colour and shape encode Criterion Impact, never Criterion State

The single non-negotiable rule. When an exclusion criterion is assessed `met` — the patient did receive an EGFR TKI — the criterion state is "the statement holds", but for the match it is **negative**. Following the intuition that green means `met` inverts the semantics: a fact that excludes the patient from the trial would be coloured green.

Therefore Impact carries colour and shape; State is text only, with no colour and no icon.

### Impact palette

Only `blocking` and `unresolved` are chromatic. `satisfied` and `neutral` stay neutral. Shapes distinguish all five, so the encoding survives colour blindness, greyscale printing, and low-contrast displays. Colour is never the sole channel.

| Impact | Shape | Meaning |
| --- | --- | --- |
| satisfied | filled square, neutral | favours the match |
| blocking | filled triangle, chromatic | counts against the match |
| unresolved | 45° diamond, chromatic | evidence insufficient |
| neutral | hollow circle, neutral | conditional antecedent false |
| not assessed | dashed square, neutral | deliberately skipped, not unknown |

The shape vocabulary is inherited by the trial-level Match Conclusion, which is derived deterministically from impact counts.

### The verifier uses a separate process colour

Verifier status is process state, not criterion impact. Sharing a colour with `blocking` would merge "counts against the match" and "the verifier rejected something" into one signal. A dedicated process colour covers the verifier panel, rejection text, the `stale_snapshot` warning, and citation drawer highlighting. It never participates in impact encoding.

### UI labels use specification wording; internal enums are secondary

Specification section 7 fixes the interface labels: Supported, Contradicted, Unknown, Not applicable, Not assessed. The internal enum follows in smaller neutral monospace:

```
Supported  met
```

"Not Supported" is prohibited: it conflates contradiction with missing evidence.

### Unknown and Not assessed stay separate

`unknown` is a Criterion State — evidence missing, stale, ambiguous, conflicting, of unsupported type, or unverifiable — and always displays its structured reason. `not assessed` is a reporting status: the trial supervisor skipped the criterion under a budget. It is never merged into `unknown`. Blocker, unresolved, and not-assessed counts appear together wherever either is shown.

### Prohibited

- Any match score or percentage. Conclusions are three discrete labels derived deterministically from impact counts.
- Merging Retrieval Rank with Review Priority. Retrieval rank is immutable and expresses relevance only; both numbers are shown.
- Rewriting, truncating, or paraphrasing trial source text.
- Any wording implying the system determines clinical eligibility.
- Progress bars, gauges, or star ratings implying a single quality score.
- Exposing scenario manifests or model chain-of-thought.

## Section skeleton

Every section follows one skeleton so that hierarchy survives concatenation into the single document:

```
section number  ──  H2 title  ──────────  right-aligned metadata
├─ summary strip: 2–5 cell grid (sections with state)
├─ body: tables / paired panels / evidence cards
└─ footer: legend + disclaimer block (key sections)
```

No breadcrumbs, no back buttons, no in-page tabs, no per-screen headers. Content occupies the full width. A persistent section index is the one permitted navigation affordance.

**Summary strips must be generated, never hand-set.** Every count in a strip — blockers, unresolved, not assessed — is derivable from the rows beneath it, so in Gate 5 it is computed from them and never authored separately. The mockups demonstrate why: `05-trial-assessment.html` declares one unresolved criterion in its strip and shows two in its table, and section 1 and section 4 both repeat the strip's figure. A hand-set aggregate is a defect waiting for a reader to find it.

## Disclaimer

An independent block, not a legend footnote, appearing in section 1, section 6, and section 9, and present in print output. Fixed wording:

> Screening workflow labels only. This report does not diagnose, determine clinical eligibility, recommend treatment, or enrol patients. Recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## Known gaps

Recorded so Gate 5 does not inherit them silently. Resolved at the specification level means the specification now settles the question; the mockups still show the old behaviour and are not authoritative.

### Resolved in the specification — redraw against section 15

1. **Mockup `09` gated model-behaviour statistics**, contradicting specification section 20 and [ADR 0008](../adr/0008-pre-register-metrics-and-gate-only-invariants.md): macro F1 ≥ 0.75, unknown correctness ≥ 0.70, latency ≤ 120 s, all abolished in v4. It also showed final-output citation validity of 0.94 — architecturally impossible, since the verifier degrades whatever it cannot verify to `unknown`, making final validity 100% by construction. Section 15 requires the invariant gates as pass or fail with the reported counts beside them, and requires the verification-induced `unknown` rate beside post-correction validity. Note the mockups put 0.94 in **both** `09` and `08`.
2. **No plain-language summary layer.** Section 15 makes it section 1 of the report.
3. **Section order was pipeline order**, putting the three sections that carry the claim behind six screens of setup while section 3 promises a five-minute read. Section 15 orders verdict-first.
4. **Per-state support is missing in `09`, and the intervals in `08` should not be there at all.** Specification v7 computes no interval and runs no test: "Bootstrap 95% over 6 scenarios" is exactly the ceremony it cut. What section 15 requires instead is a count over a stated denominator, with the scenarios, trials, and propositions behind it shown, and per-state support rather than one aggregate.
5. **Cost was not paired with the value it purchased**, and used the wrong unit: `08` reports per trial, the [measurement plan](../evaluation/phase-1-benchmark-plan.md) fixes the comparison unit at per criterion assessment.
6. **Mockup `09`'s ground-truth note said labels were hand-authored per criterion**, contradicting specification section 17 and [ADR 0005](../adr/0005-derive-gold-labels-from-scenario-manifests.md), which require expected states computed by code from the hidden manifest. This was the most serious error in the set: it described the project's methodology backwards.
7. **No wayfinding.** Section 15.1 requires a persistent section index.
8. **Four behaviours the mockups had to invent** are now defined, and the mockups disagree with all four. `05` reports a `preliminary` result as `stale_evidence`, where section 8.0 assigns `unusable_status`. `06` re-anchors "within 14 days prior to the first dose of study drug" to `assessment_as_of` at runtime, where section 5.1 permits that only as an authored, displayed substitution. ECOG and interstitial lung disease are filed under `disease`, where section 6 now has `performance_status` and `unsupported`. `07` relies on a verifier check section 8.1 did not list, which it now does. `03` backfills the assessed set past a missing expression, which section 9 now defines and bounds at rank 5.

### Open — nothing upstream settles these

9. **No at-rest state for `06`.** Only the fully expanded state is designed; the collapsed state is what a reader lands on, and section 15 requires it to be designed first.
10. **Print styles unimplemented**, and the mockups **fetch fonts from the network**, so they are not offline-viewable — a violation of the one hard constraint on the surface. Gate 5 must inline assets.
11. **Visual register is superseded.** See ADR 0009. Also unimplemented from that ADR: tool calls are a plain numbered list, not a span waterfall with duration bars — which is the element that makes "the deterministic check costs milliseconds beside multi-second model calls" a visible fact rather than a claim.
12. **Only SCN-03 is designed.** Five other scenarios have runs and no design, and there is no slot for the failing run section 15 requires at least one report to cover.
13. **`screenshots/` is empty.** Its README lists seven expected PNGs and none exist, so this file's claim that the interactive behaviours "exist only as screenshots here" is currently false.
14. **Hand-set aggregates disagree with their own tables.** `05` declares one unresolved criterion and shows two; `01` orders the run outcome by neither review priority nor retrieval rank while captioning it as review priority. See the note under Section skeleton.
15. **`03` shows per-channel ranks but not per-channel scores.** Moot: v7 cut retrieval, so neither is rendered anywhere.
