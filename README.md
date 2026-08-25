# Clinical Trial Matching Agent

An agent-engineering portfolio system that demonstrates tool selection, controlled reasoning, evidence verification, and bounded failure recovery — using synthetic FHIR R4 patients and four real public NSCLC clinical trials as the carrier domain.

Clinical trial matching is the vehicle. Agent engineering is the subject.

## What It Demonstrates

1. A patient timeline built from a synthetic FHIR R4 Bundle with per-fact provenance.
2. Four frozen trial records, with every published criterion preserved at its exact source span.
3. Source-aligned trial criteria represented by human-reviewed expressions over independently assessable atomic propositions.
4. An agent selecting and calling typed patient-timeline tools per proposition, followed by deterministic criterion aggregation.
5. Dates, numbers, and Boolean aggregation routed to deterministic code, not the model.
6. Structured judgments citing patient evidence and exact trial source text.
7. A deterministic verifier rejecting fabricated citations and triggering exactly one correction.
8. A measured comparison against a one-shot baseline that is handed the whole patient timeline, and against the same agent with its verifier switched off.

It does not diagnose, determine clinical eligibility, recommend treatment, or enroll patients.

## Current Status

All five gates are built: the domain types and the deterministic aggregation and
Unknown Reason table, the FHIR parser and the five Timeline Tools, six authored
synthetic scenarios with hidden manifests, the bounded agent loop with its
deterministic verifier and single correction, `match()` end to end, gold
derivation and the offline grading harness with the one-shot baseline, and the
Trace Report.

The reports at
[heyolivia709.github.io/clinical-trial-matching-agent](https://heyolivia709.github.io/clinical-trial-matching-agent/)
are generated from frozen artifacts and open offline. They replay **authored transcripts** rather than a recorded model
run, so the counts in their section 8 measure the harness rather than a model —
`fixtures/transcripts/README.md` says so, and a published result is recorded from
the hosted or local adapter with the run naming which one produced it.

Specification v7 cut candidate retrieval and the inferential-statistics
apparatus. Both were defensible and neither demonstrated an agent; see
[ADR 0014](docs/adr/0014-cut-the-research-grade-evaluation-protocol.md).

- **[Live demo](https://heyolivia709.github.io/clinical-trial-matching-agent/)** — five Trace Reports, one per run, generated from frozen artifacts and viewable offline
- [Development results](docs/evaluation/development-results.md) — every count, with its denominator
- [MVP specification](docs/specs/phase-1-mvp-specification.md) — source of truth
- [Implementation sequence](docs/plans/phase-1-implementation-sequence.md) — five gates, core and additive scope marked
- [Measurement plan](docs/evaluation/phase-1-benchmark-plan.md) — deterministic grading, invariant gates, and what the counts may not claim
- [Product and technical constraints](docs/requirements/product-and-technical-constraints.md)
- [Report design](docs/design/) — interface design, semantic encoding rules, and known gaps
- [Domain glossary](CONTEXT.md)
- [Decision records](docs/adr/)

## Architecture

```
Synthetic FHIR patient  +  assessment_as_of        Four frozen trial records
        |                                                    |
        v                                                    v
Patient Timeline  ───────────────────┐          Matching Policy: presented,
        |                            │ read-only     assessed, Review Priority
        |                            │ tools                  |
        v                            v                        v
Criterion Reasoning Agent  <─────────┴────────────────────────┘
   |- selects timeline tools
   |- routes dates/numbers/logic to deterministic code
   |- produces structured judgment with citations
   `- corrects once if verification fails
        |
        v
Evidence Verifier
        |
        v
Frozen run artifacts  ──>  one static report, verdict-first
```

Three deep modules behind small interfaces:

| Module | Interface |
| --- | --- |
| Patient Timeline | `build(bundle, as_of) -> PatientTimeline` |
| Criterion Agent | `assess(timeline, trial) -> TrialAssessment` |
| Evaluation Lab | `run(manifest, variant) -> EvalReport` |

The application entry point stays thin: `match(patient, trials) -> MatchingRun`.

## Scope Boundaries

Target scope: four evidence-bearing FHIR resource types, five supported criterion
categories plus an explicit unsupported one, hand-authored criterion expressions,
a bounded per-proposition agent loop with one correction, a deterministic
verifier, Early Termination as the one multi-turn behaviour, deterministic
grading against one baseline, and one static report.

Out of scope: candidate retrieval of any kind and the corpus it would rank,
inferential statistics, automatic criterion parsing, UCUM unit conversion,
line-of-therapy inference, TNM derivation, HAPI FHIR, LangGraph, multi-agent
orchestration, fine-tuning, and clinical validation. See specification sections
18 and 19, and [ADR 0014](docs/adr/0014-cut-the-research-grade-evaluation-protocol.md).


## Data Boundary

Public ClinicalTrials.gov records and authored synthetic FHIR R4 scenarios only. No real PHI, no MIMIC, no live EHR connectivity.

Benchmark gold labels are derived deterministically from hidden scenario manifests rather than judged by a model, so no LLM grades another LLM. The benchmark tests evidence retrieval, citation validity, and logic application — not clinical judgment.

## Evaluation Discipline

Release gates are restricted to deterministic invariants — properties the
implementation controls, such as citation validity and aggregation correctness. No
model-behaviour number is gated, because a threshold invites optimizing toward it.

The architectural claim is measured against a one-shot baseline that receives the
same criterion, the same authored expression, and the entire patient timeline in
one prompt. The agent sees only what its tool calls return, so it is the
information-disadvantaged arm and any advantage has to come from grounding
discipline rather than access. One verifier implementation grades both variants
offline with identical configuration; only the agent is allowed to consult it and
correct.

Final-output citation validity is 100% by construction, since the verifier
degrades whatever it cannot verify to `unknown`, so comparisons use the agent
*before* correction and publish what the correction cost in
converted-to-`unknown` assessments.

Every number is a count over a stated denominator, with the scenarios, trials,
and propositions behind it shown. There are no confidence intervals, hypothesis
tests, or effect sizes: this is a demonstration set of a few dozen observations,
and an interval over it would be wider than any difference worth claiming. A
result that goes against the architecture is published as it stands.

Passing every release gate while showing no advantage is a possible outcome. The
gates certify software correctness, not architectural value.
