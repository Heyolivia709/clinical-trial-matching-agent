# Clinical Trial Matching Agent

An agent-engineering portfolio system that demonstrates tool selection, controlled reasoning, evidence verification, bounded failure recovery, and measured evaluation — using synthetic FHIR R4 patients and real public NSCLC clinical trials as the carrier domain.

Clinical trial matching is the vehicle. Agent engineering is the subject.

## What It Demonstrates

1. A patient timeline built from a synthetic FHIR R4 Bundle with per-fact provenance.
2. Hybrid retrieval over a frozen trial snapshot, with per-channel rank attribution.
3. Source-aligned trial criteria represented by human-reviewed expressions over independently assessable atomic propositions.
4. An agent selecting and calling typed patient-timeline tools per proposition, followed by deterministic criterion aggregation.
5. Dates, numbers, and Boolean aggregation routed to deterministic code, not the model.
6. Structured judgments citing patient evidence and exact trial source text.
7. A deterministic verifier rejecting fabricated citations and triggering exactly one correction.
8. A measured comparison against deterministic, raw-text one-shot, and expression-aware one-shot baselines, plus applicable ablations.

It does not diagnose, determine clinical eligibility, recommend treatment, or enroll patients.

## Current Status

The MVP design is frozen. Implementation proceeds through acceptance-criteria-driven gates with no calendar schedule.

- [MVP specification](docs/specs/phase-1-mvp-specification.md) — frozen source of truth
- [Implementation sequence](docs/plans/phase-1-implementation-sequence.md) — seven gates, with core and additive scope marked
- [Benchmark plan](docs/evaluation/phase-1-benchmark-plan.md) — deterministic grading, gates, and ablations
- [Product and technical constraints](docs/requirements/product-and-technical-constraints.md)
- [Domain glossary](CONTEXT.md)
- [Decision records](docs/adr/)

## Architecture

```
Synthetic FHIR patient  +  assessment_as_of
        |
        v
Patient Timeline  ──────────────────────┐
        |                               │ read-only tools
        v                               │
Hybrid Trial Retrieval (BM25 + dense + RRF)
        |
        v
Criterion Reasoning Agent  <────────────┘
   |- selects timeline tools
   |- routes dates/numbers/logic to deterministic code
   |- produces structured judgment with citations
   `- retries once if verification fails
        |
        v
Evidence Verifier
        |
        v
Static Trace Report  +  Reproducible Run Artifacts
```

Four deep modules behind small interfaces:

| Module | Interface |
| --- | --- |
| Patient Timeline | `build(bundle, as_of) -> PatientTimeline` |
| Trial Retrieval | `retrieve(timeline, snapshot, k) -> CandidateSet` |
| Criterion Agent | `assess(timeline, trial) -> TrialAssessment` |
| Evaluation Lab | `run(manifest, variant) -> EvalReport` |

The application entry point stays thin: `match(patient, snapshot) -> MatchingRun`.

## Scope Boundaries

Target scope: four evidence-bearing FHIR resource types, four criterion categories, hand-authored criterion expressions, two retrieval channels with fusion, a bounded per-proposition agent loop with one correction, a flag-gated multi-turn trial supervisor, deterministic evaluation, and a static trace report. Retrieval and the supervisor are additive gates with explicit fallbacks; the criterion agent, verifier, evaluation, and trace report are core.

Out of scope: automatic criterion parsing, TREC benchmark tracks, PostgreSQL and pgvector, cross-encoder reranking, UCUM unit conversion, line-of-therapy inference, TNM derivation, HAPI FHIR, LangGraph, multi-agent orchestration, fine-tuning, and clinical validation. See specification sections 18 and 19.

## Data Boundary

Public ClinicalTrials.gov records and authored synthetic FHIR R4 scenarios only. No real PHI, no MIMIC, no live EHR connectivity.

Benchmark gold labels are derived deterministically from hidden scenario manifests rather than judged by a model, so no LLM grades another LLM. The benchmark tests evidence retrieval, citation validity, and logic application — not clinical judgment.
