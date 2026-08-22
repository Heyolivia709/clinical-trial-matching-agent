# Trace Report — Interface Design

**Status:** Structural design accepted; visual register superseded, see [ADR 0009](../adr/0009-adopt-the-trace-inspector-visual-register.md)
**Implements:** [MVP specification](../specs/phase-1-mvp-specification.md) §15
**Delivered by:** Gate 7 (see [implementation sequence](../plans/phase-1-implementation-sequence.md))

The repository contained documentation only when these mockups were produced, so the interface was designed from specification §15 rather than recreated from source. Nothing here is generated output — the real report is rendered from frozen traces by Gate 7 code.

## What this interface is

A single self-contained document that can be read offline, printed, and archived — not an application.

The system's value proposition is auditability: every screening conclusion traces to a specific FHIR resource in the patient record and a specific character span in the trial source text. Application chrome — breadcrumbs, back buttons, in-page tabs, per-screen headers — fragments that chain into pieces a reader must click to reassemble. A single document lets a reviewer read start to finish, print to PDF for the record, and cite "§6, second paragraph" in a review meeting.

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

| Section | Specification source |
| --- | --- |
| §1 Run overview | §4, §14, §15; [product constraints](../requirements/product-and-technical-constraints.md) |
| §2 Patient timeline | §4.2, §5, §5.1–§5.4, §8.3 |
| §3 Retrieval | §9, §12 — **conditional on Gate 3** |
| §4 Candidate list | §7.2, §9, §13 — **conditional on Gate 3** |
| §5 Trial assessment | §6, §7, §7.1, §7.2, §8 |
| §6 Criterion detail | §7, §8, §10, §10.1, §15 |
| §7 Verifier and correction | §8.1, §8.2, §8.3, §20 |
| §8 Baseline comparison | §11, §16, §17 |
| §9 Evaluation | §16, §17, §18, §19, §20 |

Gate 3 is additive. If it is cut, §3 and §4 are removed, §1 records retrieval as out of scope, and §4's candidate list degrades to the four frozen trial fixtures from Gate 1. See specification §19.

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

No breadcrumbs, no back buttons, no in-page tabs, no per-screen headers. Content occupies the full width.

## Disclaimer

An independent block, not a legend footnote, appearing in §1, §6, and §9, and present in print output. Fixed wording:

> Screening workflow labels only. This report does not diagnose, determine clinical eligibility, recommend treatment, or enrol patients. Recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## Known gaps

Recorded so Gate 7 does not inherit them silently.

1. **§9 contradicts specification §20 and [ADR 0008](../adr/0008-pre-register-metrics-and-gate-only-invariants.md).** The mockup presents a "release gates · pre-registered thresholds" table gating model-behaviour statistics — macro F1 ≥ 0.75, unknown correctness ≥ 0.70, latency ≤ 120 s — which v4 abolished. It also shows citation validity of 0.94 in final output, which the architecture makes impossible: the verifier rejects every invalid citation and degrades to `unknown`, so final-output validity is 100% by construction. §9 must be rebuilt as two separate tables, invariant gates and reported results, before Gate 7 implements it.
2. **No plain-language summary layer.** §1 is a reproducibility header written entirely in domain and system vocabulary. A non-specialist reader has no entry point. A §0 summary is needed: one sentence of what the system does, three or four headline numbers with non-jargon labels, and one worked example.
3. **No at-rest state for §6.** Only the fully expanded state is designed, but the collapsed state is what a reader lands on.
4. **No confidence intervals or per-state support in §9**, both mandatory under the benchmark plan.
5. **Cost is never paired with the value it purchased**, required by the [pre-registration](../evaluation/pre-registration.md) §4.5, with the comparison unit fixed to per criterion assessment.
6. **Print styles are unimplemented.** The disclaimer must appear in print and the specification requires an exportable report, so this is a requirement rather than a refinement.
7. **Visual register is superseded.** See ADR 0009. The structural content above remains valid; the surface treatment does not.
8. Failure taxonomy sits inside §9 rather than as its own section, and the patient scenario is fixed to SCN-03.
