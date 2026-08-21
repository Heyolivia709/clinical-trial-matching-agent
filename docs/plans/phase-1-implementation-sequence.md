# Phase 1 Dependency-Ordered Implementation Sequence

**Status:** Frozen sequence
**Scheduling rule:** No calendar estimates. Progression depends only on acceptance criteria.

## Gate 1: Domain Contracts and Evaluation Schemas

Define typed models for Patient Timeline, Trial, Trial Record, Eligibility Criterion, Criterion Expression, Atomic Proposition, evidence references, Criterion Assessment, Trial Assessment, Candidate Set, Matching Run, Reasoning Trace, Scenario Manifest, and Eval Case.

Exit when state semantics, Boolean truth tables, polarity-to-impact mapping, Match Conclusion, version identity, and serialization round trips have deterministic tests.

## Gate 2: Gold-Labeling Guide and Benchmark Skeleton

Create annotation guidance, dataset manifests, partition rules, evidence-equivalence representation, deterministic metric implementations, and frozen-output grading fixtures.

Exit when a small hand-checked fixture can be graded end to end without network or model credentials.

## Gate 3: Versioned NSCLC Corpus and Parser Baseline

Ingest full ClinicalTrials.gov JSON or API v2 records, enforce Corpus Membership, preserve source payloads, split eligibility sections, and build the lexical/parser B0 baselines.

Exit when snapshot manifests are reproducible, every source criterion is preserved, and corpus membership tests cover status, study type, normalized NSCLC metadata, and recruiting U.S. sites.

## Gate 4: Patient Timeline and Authored FHIR Scenarios

Validate supported FHIR R4 resources, normalize them into the Patient Timeline, preserve provenance and Temporal Precision, and implement controlled scenario augmentations plus hidden manifests.

Exit when demographic, disease, biomarker, ECOG, treatment, laboratory, missing, temporal, and conflicting facts survive round-trip provenance tests.

## Gate 5: Retrieval Baselines

Implement conservative Candidate Filters, Patient Retrieval Profile facets, lexical B0, dense B1, the TREC adapter, and channel-level metrics.

Exit when filter-loss attribution and lexical/dense benchmark runs are reproducible.

## Gate 6: Hybrid Retrieval and Reranking

Add trial- and criterion-level indexes, per-facet retrieval, reciprocal-rank fusion, trial aggregation, constrained reranking, and immutable top-20 Candidate Sets.

Exit when each channel's contribution is traceable and development-set retrieval evaluation is reproducible. Held-out retrieval remains untouched until Gate 11.

## Gate 7: Deterministic Criterion Reasoning

Implement expression aggregation, age and sex comparisons, laboratory arithmetic, temporal windows, reviewed concept mappings, treatment episodes, Criterion Impact, and Match Conclusion.

Exit when deterministic truth tables and supported category fixtures achieve exact expected results.

## Gate 8: One-Shot Reasoning Baseline

Build the flattened-summary and raw-criterion B1 with frozen structured output and operational tracing.

Exit when B1 runs on the reasoning benchmark and exposes unsupported assessments, evidence errors, tokens, and latency.

## Gate 9: Evidence Verifier

Validate FHIR references, values, times, trial spans, evidence relations, required evidence, and deterministic aggregation. Separate verification failures from infrastructure failures.

Exit when adversarial fixtures prove invented or modified evidence cannot produce a supported state.

## Gate 10: Bounded Criterion Reasoning Agent

Implement the typed Python classification, Evidence Packet construction, targeted timeline queries, strategy routing, model reasoning, verification, and one correction cycle.

Exit when trajectories are inspectable, correction is bounded, and invalid results degrade to structured `unknown`.

## Gate 11: Held-Out Evaluation and Ablations

Freeze the selected local model, prompt, embeddings, reranker, reasoning configuration, and operational budgets. Run parser, retrieval, reasoning, end-to-end, and one-capability-at-a-time ablations.

Exit when all results, confidence intervals, state/category support, and failures are published without held-out optimization.

## Gate 12: Failure Analysis and Portfolio Documentation

Publish the architecture, benchmark cards, data provenance, limitations, failure taxonomy, representative traces, reproducible commands, DTSS differentiation, and accurate resume-ready results.

Exit when every quantitative claim links to a reproducible run artifact and every clinical limitation is explicit.

## Optional Post-Evaluation Work

Only after all required gates:

- Coordinator review interface
- HAPI FHIR adapter
- LangGraph implementation behind the Criterion Reasoner interface
- Equal-budget multi-agent ablation
- Broader disease areas

Optional work must not retroactively alter frozen Phase 1 held-out results.
