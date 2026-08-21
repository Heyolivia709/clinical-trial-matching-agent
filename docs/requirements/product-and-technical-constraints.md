# Clinical Trial Matching Agent: Product and Technical Constraints

**Status:** Binding project constraints
**Date:** 2026-08-21
**Primary audience:** Project contributors and portfolio reviewers

The frozen Phase 1 design is specified in [`../specs/phase-1-mvp-specification.md`](../specs/phase-1-mvp-specification.md). If this constraints document and the Phase 1 specification differ in level of detail, the specification governs Phase 1 behavior. Scope changes must be recorded explicitly.

## Product Definition

The Clinical Trial Matching Agent is a decision-support prototype for clinical research coordinators. It accepts synthetic or otherwise public patient information, retrieves candidate studies from ClinicalTrials.gov, evaluates inclusion and exclusion criteria individually, and returns evidence-grounded candidate trial reports for coordinator review.

The product is not a general medical chatbot. Its primary interaction is a structured matching workflow and criterion review surface, not an open-ended chat interface.

## Intended User Journey

1. A research coordinator selects or supplies a synthetic or public patient record.
2. The system constructs a longitudinal patient timeline from the available FHIR data.
3. The system retrieves candidate trials from a versioned ClinicalTrials.gov snapshot.
4. The system evaluates each relevant inclusion and exclusion criterion against the patient timeline.
5. The system produces a structured report containing ranked candidate trials, criterion-level assessments, missing information, patient evidence, and exact trial-clause citations.
6. The coordinator independently verifies current trial status and makes all real-world decisions outside this prototype.

A coordinator review interface is an optional post-evaluation portfolio layer, not a required Phase 1 implementation gate.

## Primary Portfolio Signals

The project must demonstrate depth in the following areas:

- Agent cognition and orchestration: decomposition of a matching task into retrieval, criterion interpretation, targeted evidence selection, temporal reasoning, consistency checking, and result synthesis.
- Longitudinal FHIR patient modeling: preservation of clinical events, time intervals, status, values, provenance, and missing information rather than flattening the record into an untraceable summary.
- Hybrid or advanced retrieval: deterministic metadata filters plus lexical and dense retrieval, fusion or reranking, and retrieval evaluation against published benchmarks.
- Criterion-level reasoning: source-aligned inclusion and exclusion criteria represented by Boolean or conditional expressions over atomic propositions.
- Evidence grounding: every supported assessment must cite both the patient evidence and the exact trial criterion from which it was derived.
- Evaluation engineering: public benchmarks, authored synthetic cases, baselines, ablations, failure analysis, reproducible run manifests, and quality/latency/cost reporting.
- Optional post-MVP multi-agent experimentation: multi-agent execution may be tested only after Phase 1, against the single-agent and deterministic baselines under a comparable resource budget.

The project must not derive its value from a chat UI, a conventional vector-search RAG pipeline, installing several agent skills or frameworks, or presenting framework names without measurable task improvement.

## Required Outputs

For each candidate trial, the system must return:

- Trial identity, recruiting status, record version or update timestamp, and source link.
- The retrieval score or ranking explanation, kept distinct from the eligibility assessment.
- Source-aligned inclusion and exclusion criteria plus their parsed atomic propositions.
- One of the following states for every assessed criterion: `met`, `not_met`, `unknown`, or `not_applicable`.
- Patient evidence references with FHIR resource identity, source location, clinical time, and a concise supported excerpt or normalized fact.
- Trial evidence references with NCT identifier, criterion section, criterion ordinal or source span, exact clause text, and record timestamp.
- Missing or conflicting information that caused an `unknown` result.
- A cautious trial-level conclusion such as `potential_match`, `unlikely_match`, or `insufficient_information`.

### Criterion-State Semantics

Criterion state describes whether the proposition expressed by the criterion is true for the patient. It does not directly describe overall eligibility.

- `met`: available evidence supports the criterion proposition.
- `not_met`: available evidence contradicts the criterion proposition.
- `unknown`: evidence is missing, stale, ambiguous, or conflicting.
- `not_applicable`: a conditional criterion does not apply because its explicit antecedent is false; this state must not be used as a substitute for missing information.

This distinction is essential for exclusion criteria. A `met` exclusion criterion is evidence against a trial match, while a `not_met` exclusion criterion is evidence in favor of a match. Trial-level aggregation must account for criterion polarity explicitly.

## Safety and Claim Boundaries

The project must state prominently that it is a research prototype and that its outputs require qualified human review.

It must not:

- Diagnose a condition or recommend treatment.
- Claim that a patient is clinically eligible or ineligible.
- Enroll a patient automatically or contact a trial site on the user's behalf.
- Make external write operations.
- Claim clinical validity, clinical effectiveness, regulatory compliance, or production readiness.
- Accept, persist, or transmit real protected health information in the first release.

The public demo must use only synthetic or public patient descriptions. A real-world coordinator must verify recruiting status, site availability, and eligibility with the official study record and study team.

## Default Data Sources and Technical Resources

### Required defaults

- ClinicalTrials.gov API v2 and/or its full JSON download for trial records.
- Synthea-generated FHIR R4 data for longitudinal synthetic patients.
- PostgreSQL with pgvector for structured metadata, lexical search, vector retrieval, provenance, and evaluation records.
- Local embedding and language models as the default development path.
- TREC Clinical Trials 2021 and 2022 for retrieval and ranking evaluation.
- TrialGPT as a published baseline or comparison point, subject to its repository, model, and dataset terms.

### Optional resources

- A local HAPI FHIR server may be added after Phase 1 as an interoperability adapter. Direct parsing of Synthea FHIR R4 Bundles is the Phase 1 path.
- A stronger hosted model may be used only as a clearly labeled evaluation upper bound on synthetic or public data.
- Multi-agent orchestration may be added only after the single-agent and deterministic baselines are working and reproducible.

### Excluded from the first release

- MIMIC or other credentialed patient datasets.
- A complete SNOMED CT distribution.
- Real PHI or live EHR connectivity.
- Claims based on real patient outcomes.

## Evaluation Requirements

Evaluation must be designed before model or orchestration optimization. At minimum, the project must include:

- A lexical retrieval baseline.
- A naive dense or single-pass RAG baseline.
- A full hybrid retrieval and criterion-reasoning system.
- TREC 2021/2022 ranking metrics such as `nDCG@10`, `P@10`, and `Recall@k`, with pooled-judgment limitations documented.
- An authored Synthea-based criterion benchmark covering temporal windows, laboratory thresholds, prior treatment, medication state, demographics, negation, conditional applicability, missing facts, and conflicting facts.
- Criterion-level macro F1 and per-state precision/recall, with particular attention to `unknown`.
- Patient-evidence and trial-citation precision/recall or validity metrics.
- Trial-level ranking or conclusion metrics kept separate from criterion-state metrics.
- Latency, model-call count, token usage, and estimated cost measured from run traces.
- A published failure taxonomy and representative failure cases.

Ablations should isolate the value of longitudinal timelines, hybrid retrieval, criterion decomposition, deterministic structured reasoning, evidence verification, and orchestration. Any multi-agent experiment must use the same dataset and a comparable resource budget.

## Explicit Non-Goals

The first release will not build:

- A general-purpose agent harness or agent-skills platform.
- A generic chat-with-documents application.
- A secure action executor, approval workflow, human-in-the-loop workflow, authorization layer, idempotency mechanism, or external mutation system.
- A production EHR integration or HIPAA compliance claim.
- A comprehensive medical terminology platform.
- A foundation-model training or fine-tuning pipeline.
- A clinical decision support system intended for patient care.
- A LangGraph or multi-agent implementation during Phase 1.
- A required coordinator UI before benchmark completion.
- Calendar-based delivery commitments; implementation proceeds through acceptance-criteria-driven gates.

## Repository Language Rule

All content added to the Clinical Trial Matching Agent project repository must be written in English. This rule applies to documents, source code, identifiers, comments, docstrings, tests, fixtures, configuration descriptions, diagrams, sample data authored by the project, and user-facing interface text.
