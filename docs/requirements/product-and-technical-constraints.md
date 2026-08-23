# Clinical Trial Matching Agent: Product and Technical Constraints

**Status:** Binding project constraints
**Date:** 2026-08-22
**Primary audience:** Project contributors and portfolio reviewers

The frozen design is specified in [`../specs/phase-1-mvp-specification.md`](../specs/phase-1-mvp-specification.md). Where this document and the specification differ in level of detail, the specification governs behavior. Scope changes must be recorded explicitly.

## Product Definition

The Clinical Trial Matching Agent is an agent-engineering portfolio system. It accepts a synthetic patient record, retrieves candidate studies from a frozen ClinicalTrials.gov snapshot, evaluates individual inclusion and exclusion criteria, and returns evidence-grounded candidate trial reports.

Clinical trial matching is the carrier domain. The demonstrated skills are agent tool selection, controlled reasoning, deterministic routing, evidence verification, bounded failure recovery, multi-turn cost control, and measured evaluation.

It is not a general medical chatbot. Its primary surface is a static trace report, not an open-ended chat interface.

The surface is two artifacts, not one: a Trace Report scoped to a single matching run, and a separate Evaluation Report scoped to the benchmark. Benchmark statistics never appear as a section of a run's trace, because a corpus-scoped number and a run-scoped fact are different kinds of claim and must not share a page as though they were not. See specification section 15.

## Intended Reviewer Journey

Ordered by what the reviewer encounters, which is deliberately not the order the pipeline runs in.

1. A reviewer opens the hosted trace report, or runs the project locally.
2. In plain language, with no domain or system vocabulary: what the system does, what this run concluded, and which single criterion demonstrates the claim.
3. They see that criterion decomposed into atomic propositions and assessed through tool calls, with a structured judgment citing patient evidence and exact trial source text.
4. They see the verifier reproducibly reject an injected bad citation on that criterion and trigger exactly one correction.
5. They see the same criterion assessed by the deterministic, raw-text one-shot, and expression-aware one-shot variants, side by side, with cost.
6. Only then: the remaining criteria, the candidate set, hybrid retrieval with per-channel attribution, the full patient timeline with per-fact provenance, and the reproducibility header.
7. From a separate Evaluation Report: the benchmark results, ablations, invariants, and the pre-registered comparison with its outcome.

Steps 1 through 5 must be reachable within five minutes and must not require credentials or a network connection. Step 6 is the same requirement applied to depth rather than to speed: nothing is omitted, it is merely placed after the argument it supports.

## Primary Portfolio Signals

Ranked by intended emphasis:

- **Agent engineering.** Tool selection per proposition, explicit division of labor between model and deterministic code, bounded correction, structured degradation to `unknown`, flag-gated multi-turn strategy with measured cost effects.
- **Grounding and verification.** Every supported assessment cites machine-verified patient evidence and exact trial source text; a deterministic verifier rejects fabricated or altered citations.
- **Evaluation engineering.** Deterministic grading, derived gold labels, frozen held-out partitions, deterministic and one-shot baselines, core and conditional ablations, confidence intervals, failure taxonomy, and cost accounting from traces.
- **Longitudinal FHIR modeling.** Preservation of clinical time, temporal precision, status, values, provenance, and unsupported content rather than flattening the record.
- **Hybrid retrieval.** Deterministic filters plus lexical and dense channels with reciprocal-rank fusion, evaluated with per-channel attribution.
- **Interface design.** Four deep modules behind small stable interfaces, with a thin application entry point and adapter seams for data sources and model inference.

The project must not derive its value from a chat UI, a conventional vector-search RAG pipeline, installing agent frameworks, or presenting framework names without measurable task improvement.

## Required Outputs

For each assessed candidate trial:

- Trial identity, recruiting status, record timestamp, and source link.
- Retrieval rank and per-channel attribution, kept distinct from the eligibility assessment.
- Source-aligned criteria plus their authored atomic propositions and per-proposition assessments.
- A state for every criterion: `met`, `not_met`, `unknown`, or `not_applicable`.
- `not_assessed` for criteria deliberately skipped under early termination, never merged into `unknown`.
- Patient evidence references with FHIR resource identity, JSON path, clinical time, status, and value.
- Trial evidence references with NCT identifier, section, ordinal, span, and exact clause text.
- The tools the agent called, with arguments and results.
- The verifier outcome and whether a correction occurred.
- Structured reasons for every `unknown`.
- A cautious trial-level conclusion: `potential_match`, `insufficient_information`, or `unlikely_match`.
- Latency, model calls, tokens, and estimated cost.

### Criterion-State Semantics

Criterion state describes whether the proposition expressed by the criterion is true for the patient. It does not directly describe overall eligibility.

- `met`: available evidence supports the criterion proposition.
- `not_met`: available evidence contradicts the criterion proposition.
- `unknown`: evidence is missing, unusable by status, insufficiently precise, stale, conflicting, ambiguous, or unsupported. The structured reason is assigned deterministically by the table in specification section 8.0, never chosen by the model.
- `not_applicable`: a conditional criterion does not apply because its explicit antecedent is false; never a substitute for missing information.

This distinction is essential for exclusion criteria. A `met` exclusion criterion is evidence against a match; a `not_met` exclusion criterion is evidence in favor. Trial-level aggregation accounts for polarity explicitly and deterministically.

## Safety and Claim Boundaries

The project must state prominently that it is a research prototype whose outputs require qualified human review.

It must not:

- Diagnose a condition or recommend treatment.
- Claim that a patient is clinically eligible or ineligible.
- Enroll a patient or contact a trial site.
- Make external write operations.
- Claim clinical validity, clinical effectiveness, regulatory compliance, or production readiness.
- Accept, persist, or transmit real protected health information.

The published demo uses only authored synthetic patients. A real coordinator must verify recruiting status, site availability, and eligibility with the official study record and study team.

## Default Data Sources and Technical Resources

### Required defaults

- ClinicalTrials.gov API v2 or its full JSON download, frozen into a versioned local snapshot of 200–500 trials.
- Synthea-generated FHIR R4 Bundles with controlled, standards-conformant augmentations.
- In-process lexical and vector indexes over the frozen snapshot, behind a single interface.
- A language model behind an adapter with hosted, local, and frozen-replay implementations.
- Structured output enforced by constrained decoding or schema validation, with recorded retries.

### Deliberately not used

- PostgreSQL and pgvector. At this corpus size an in-process index is the correct engineering choice; the index interface allows a larger backend to be substituted without touching callers.
- Cross-encoder reranking.
- TREC Clinical Trials 2021 and 2022. Dropped with the retrieval benchmark track; the cost of dataset and qrels handling outweighed the value at this scope.
- TrialGPT reproduction.
- HAPI FHIR. Direct parsing of Synthea Bundles is the implemented path.
- MIMIC or other credentialed datasets, full SNOMED CT, real PHI, and live EHR connectivity.

### Permitted later additions

Any later addition must not retroactively alter frozen held-out results: a larger index backend, a reranker, retrieval benchmark tracks, broader FHIR coverage, additional disease areas, LangGraph behind the same agent interface, and an equal-budget multi-agent ablation.

## Evaluation Requirements

Evaluation is designed before model or orchestration optimization. At minimum:

- A deterministic structured-field baseline, a raw-text one-shot baseline, and an expression-aware one-shot control. All model variants share the patient-evidence boundary, output schema, model family, decoding policy, and cost accounting; deliberate criterion-context differences are labeled.
- What each variant actually receives in its prompt is fixed in the pre-registration, not left to implementation. A shared evidence *boundary* is not shared *context*: the expression-aware control is handed the whole timeline while the full agent sees only its tool results, so the full agent is the information-disadvantaged arm and this is stated wherever the comparison appears.
- Gold expected states derived deterministically from hidden scenario manifests. No model-generated labels, and no LLM judge in any primary metric.
- Held-out partitions separated by both trial and scenario, frozen against all optimization.
- Release gates restricted to deterministic invariants: citation validity, deterministic aggregation, verifier catch rate on injected faults, zero unsupported assessments surviving verification, criterion coverage, zero post-cutoff citations, and zero infrastructure failures scored as uncertainty. No model-behavior statistic is gated.
- Final-output citation validity is an invariant reached by degrading unverifiable assessments to `unknown`, so it is never used as a comparison against a baseline. Comparisons use the full agent *before* correction, and the verification-induced `unknown` rate is published wherever post-correction validity is, at equal prominence.
- A pre-registration committed before the first held-out run, fixing metrics, comparison units, per-variant prompt contents, statistical procedure, precision, cost-value pairing, and a falsification condition, cited by commit hash in the report. Precision is a procedure recomputed from development data and committed as a dated amendment, not a number asserted in advance.
- One verifier implementation in two separated roles: offline grading of every variant with identical configuration, and runtime feedback for the full agent only.
- Criterion-state macro F1, per-state precision and recall with attention to `unknown`, and per-category breakdown, all reported with bootstrap confidence intervals from cluster-level resampling and with realised cluster and observation counts, compared against the expression-aware control by a two-sided test with no minimum effect size.
- Retrieval metrics reported separately from criterion-state metrics, with per-channel attribution.
- Latency, model calls, token usage, and estimated cost measured from run traces.
- Two core ablations: no deterministic tools and no verifier. If the additive Trial Supervisor is built, also report no evidence reuse and early termination.
- A published failure taxonomy with representative traces.

Small-sample results are stated as such. No number is published without a link to a reproducible run artifact.

## Explicit Non-Goals

The project will not build:

- A general-purpose agent harness or agent-skills platform.
- A generic chat-with-documents application.
- An automatic clinical criterion parser.
- A secure action executor, approval workflow, human-in-the-loop workflow, authorization layer, idempotency mechanism, or external mutation system.
- A production EHR integration or HIPAA compliance claim.
- A comprehensive medical terminology platform.
- A model training or fine-tuning pipeline.
- A clinical decision support system intended for patient care.
- A LangGraph or multi-agent implementation.
- An interactive workflow application. The demonstration surface is a read-only static trace report.
- Calendar-based delivery commitments; implementation proceeds through acceptance-criteria-driven gates.

## Repository Language Rule

All content added to this repository must be written in English. This applies to documents, source code, identifiers, comments, docstrings, tests, fixtures, configuration descriptions, diagrams, authored sample data, and user-facing interface text.
