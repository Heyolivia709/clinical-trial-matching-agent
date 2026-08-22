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
- [Benchmark plan](docs/evaluation/phase-1-benchmark-plan.md) — deterministic grading, invariant gates, and ablations
- [Pre-registration](docs/evaluation/pre-registration.md) — metrics, statistical procedure, and falsification condition, fixed before any held-out run
- [Product and technical constraints](docs/requirements/product-and-technical-constraints.md)
- [Trace report design](docs/design/) — interface design, semantic encoding rules, and known gaps
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

## Evaluation Discipline

Release gates are restricted to deterministic invariants — properties the implementation controls, such as citation validity and aggregation correctness. No model-behavior statistic is gated, because a threshold on a small held-out sample invites optimizing toward the number.

The architectural claim is tested against an expression-aware one-shot control that receives the same criterion expression and the same patient evidence as the full agent, isolating the contribution of orchestration rather than of having a structured expression at all. One verifier implementation grades every variant offline with identical configuration; only the full agent is allowed to consult it and correct.

Metrics, comparison units, cost-value pairing, the statistical procedure, a power statement, and a falsification condition are committed before the first held-out run, and the published report cites that commit hash:

> If the control shows no detectable difference from the full agent in citation validity or unsupported-assessment rate, the central claim of this project is unsupported, and that conclusion is published as the headline result.

Passing every release gate while failing that condition is a possible outcome. The gates certify software correctness, not architectural value.
