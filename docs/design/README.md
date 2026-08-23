# Trace Report — Interface Design

**Status:** Semantic encoding accepted; visual register superseded by [ADR 0009](../adr/0009-adopt-the-trace-inspector-visual-register.md); **section inventory and ordering superseded by specification v5 §15 and [ADR 0010](../adr/0010-separate-the-evaluation-report-from-the-trace-report.md)**
**Implements:** [MVP specification](../specs/phase-1-mvp-specification.md) §15
**Delivered by:** Gate 7 (see [implementation sequence](../plans/phase-1-implementation-sequence.md))

The repository contained documentation only when these mockups were produced, so the interface was designed from specification §15 rather than recreated from source. Nothing here is generated output — the real report is rendered from frozen traces by Gate 7 code.

**Read this first.** The mockups predate specification v5. Three structural decisions in them have since been reversed at the specification level, and the mockups have not been redrawn:

| Mockup assumption | v5 §15 requires |
| --- | --- |
| One document containing §1–§9 | Two artifacts: a run-scoped Trace Report, and a separate run-independent Evaluation Report. Mockup §9 — and the cross-scenario intervals in §8 — belong to the second. |
| Sections in pipeline order, run metadata first | Verdict-first order. Plain-language summary, then the demonstrative criterion, verifier, and baseline comparison; timeline, retrieval, and reproducibility header move to the back. |
| No wayfinding of any kind | A persistent section index is required. |

What survives unchanged: the semantic encoding rules below, the impact-not-state rule, the separate verifier process colour, §7 label wording, and the verbatim treatment of trial source text. Those are the parts worth keeping.

Specification v5 and ADR 0010 arrive on a separate branch, so links to them resolve once it merges.

## What this interface is

A self-contained document that can be read offline, printed, and archived — not an application.

The system's value proposition is auditability: every screening conclusion traces to a specific FHIR resource in the patient record and a specific character span in the trial source text. Application chrome — breadcrumbs, back buttons, in-page tabs, per-screen headers — fragments that chain into pieces a reader must click to reassemble. A single document lets a reviewer read start to finish, print to PDF for the record, and cite "§6, second paragraph" in a review meeting.

That argument was extended too far. It ruled out *all* wayfinding, and a ten-screen document with no index is harder to read start to finish, not easier — every trace inspector named below carries one. A persistent section index is required by v5 §15.1; the rejections of breadcrumbs, back buttons, in-page tabs, and per-screen headers stand.

The genre is an agent trace inspector, not a clinical dashboard and not a chat interface. Comparable artifacts: the standalone site produced by `inspect view bundle` in [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai), a [promptfoo](https://www.promptfoo.dev/docs/usage/web-ui/) HTML eval report, and the trace waterfall in [Langfuse](https://langfuse.com/).

## Files

| Path | Role |
| --- | --- |
| `mockups/01`–`09` | Design reference. Each file is one section of the final single document. |
| `explorations/` | Rejected and superseded alternatives, retained as decision record. |
| `screenshots/` | PNG exports for inline viewing on GitHub, including interactive states. |

These are portable HTML exported from the design tool, which remains the editing source of truth. The design tool's own runtime and project format are deliberately not vendored into this repository.

Section files are static. The five interactive behaviours studied during design — criterion row expansion, citation drawers, tool-call stepping, verifier attempt toggle, baseline column toggle — exist only as screenshots here; Gate 7 implements them.

## Traceability

| Mockup | Specification source | Lands in | v5 order |
| --- | --- | --- | --- |
| §1 Run overview | §4, §14, §15 | Trace Report | 10 — moves to the back |
| §2 Patient timeline | §4.2, §5, §5.1–§5.4, §8.3 | Trace Report | 7 |
| §3 Retrieval | §9, §12 — **conditional on Gate 3** | Trace Report | 8 |
| §4 Candidate list | §7.2, §9, §13 — **conditional on Gate 3** | Trace Report | 5 |
| §5 Trial assessment | §6, §7, §7.1, §7.2, §8 | Trace Report | 6 |
| §6 Criterion detail | §7, §8, §10, §10.1, §15 | Trace Report | 2 — moves to the front |
| §7 Verifier and correction | §8.1, §8.2, §8.3, §20 | Trace Report | 3 |
| §8 Baseline comparison | §11, §16, §17 | **split** | 4 (per-criterion) / Evaluation Report (aggregates) |
| §9 Evaluation | — **no §15 source; see below** | **Evaluation Report** | — |
| *not yet designed* | §3, §15.1 | Trace Report | 1 — plain-language summary |

Two entries need explaining.

**§9 had no specification source.** v4 §15 defined the report as generated from a frozen Matching Run and listed eight run-scoped items, none of them the benchmark; the traceability row above previously cited §16–§20, which are not about the report at all. The section was invented to hold content that had nowhere to live. v5 gives it a home as a separate artifact rather than deleting it. See ADR 0010.

**§8 is two things.** The per-criterion side-by-side on one criterion is run-scoped and stays in the Trace Report. The aggregate table with bootstrap intervals over six scenarios is benchmark-scoped and moves to the Evaluation Report.

Gate 3 is additive. If it is cut, §3 and §4 are removed, the reproducibility header records retrieval as out of scope, and §4's candidate list degrades to the four frozen trial fixtures from Gate 1. See specification §19.

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

Specification §7 fixes the interface labels: Supported, Contradicted, Unknown, Not applicable, Not assessed. The internal enum follows in smaller neutral monospace:

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

**Summary strips must be generated, never hand-set.** Every count in a strip — blockers, unresolved, not assessed — is derivable from the rows beneath it, so in Gate 7 it is computed from them and never authored separately. The mockups demonstrate why: `05-trial-assessment.html` declares one unresolved criterion in its strip and shows two in its table, and §1 and §4 both repeat the strip's figure. A hand-set aggregate is a defect waiting for a reader to find it.

## Disclaimer

An independent block, not a legend footnote, appearing in §1, §6, and §9, and present in print output. Fixed wording:

> Screening workflow labels only. This report does not diagnose, determine clinical eligibility, recommend treatment, or enrol patients. Recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## Known gaps

Recorded so Gate 7 does not inherit them silently. Resolved at the specification level means v5 §15 or the pre-registration now settles the question; the mockups still show the old behaviour and are not authoritative.

### Resolved in specification v5 — redraw against §15

1. **§9 gated model-behaviour statistics**, contradicting specification §20 and [ADR 0008](../adr/0008-pre-register-metrics-and-gate-only-invariants.md): macro F1 ≥ 0.75, unknown correctness ≥ 0.70, latency ≤ 120 s, all abolished in v4. It also showed final-output citation validity of 0.94 — architecturally impossible, since the verifier degrades whatever it cannot verify to `unknown`, making final validity 100% by construction. v5 §15.2 requires invariant gates and reported results in two separate tables, and requires the verification-induced `unknown` rate beside post-correction validity. Note the mockups put 0.94 in **both** §9 and `08-baseline-comparison.html`.
2. **No plain-language summary layer.** v5 §15.1 makes it section 1 of the Trace Report.
3. **Section order was pipeline order**, putting the three sections that carry the claim behind six screens of setup while §3 promises a five-minute read. v5 §15.1 orders verdict-first.
4. **No confidence intervals or per-state support in §9.** v5 §15.2 requires intervals plus realised cluster and observation counts. "Bootstrap 95% over 6 scenarios" in `08` is also the wrong resampling unit — the pre-registration resamples scenario-trial pairs.
5. **Cost was not paired with the value it purchased**, and used the wrong unit: `08` reports per trial, the [pre-registration](../evaluation/pre-registration.md) §4.4 fixes the comparison unit at per criterion assessment.
6. **§9's ground-truth note said labels were hand-authored per criterion**, contradicting specification §17 and [ADR 0005](../adr/0005-derive-gold-labels-from-scenario-manifests.md), which require expected states computed by code from the hidden manifest. This was the most serious error in the set: it described the project's methodology backwards.
7. **No wayfinding.** v5 §15.1 requires a persistent section index.

### Open — nothing upstream settles these

8. **No at-rest state for §6.** Only the fully expanded state is designed; the collapsed state is what a reader lands on, and v5 requires it to be designed first.
9. **Print styles unimplemented**, and the mockups **fetch fonts from the network**, so they are not offline-viewable — a violation of the one hard constraint on the surface. Gate 7 must inline assets.
10. **Visual register is superseded.** See ADR 0009. Also unimplemented from that ADR: tool calls are a plain numbered list, not a span waterfall with duration bars — which is the element that makes "the deterministic check costs milliseconds beside multi-second model calls" a visible fact rather than a claim.
11. **Only SCN-03 is designed.** Five other scenarios have runs and no design, and there is no slot for the two failure traces the pre-registration requires.
12. **`screenshots/` is empty.** Its README lists seven expected PNGs and none exist, so this file's claim that the interactive behaviours "exist only as screenshots here" is currently false.
13. **Hand-set aggregates disagree with their own tables.** `05` declares one unresolved criterion and shows two; `01` orders the run outcome by neither review priority nor retrieval rank while captioning it as review priority. See the note under Section skeleton.
14. **Semantic mislabels to fix before they reach code.** `05` reports a `preliminary` ECOG result as `stale_evidence`, which is not what staleness means; `06` silently re-anchors "within 14 days prior to the first dose of study drug" to `assessment_as_of`, which §5.1 does not authorise; ECOG and interstitial lung disease are both filed under category `disease`, which §6's four categories do not contain. These are specification gaps the design surfaced, and they belong in Gate 1's Unknown Reason decision table rather than in a mockup.
15. **`07` adds an eighth verifier check** — "unsupported evidence types cited as establishing a state" — that specification §8.1 does not list, though the whole EXC-7 demonstration depends on it. It should be written back into §8.1.
16. **`03` shows per-channel ranks but not per-channel scores**, which §9 requires. It also backfills the assessed set to retrieval rank 4 when rank 3 has no authored expression; that rule is reasonable and undefined in §9, and belongs in the Matching Policy.
