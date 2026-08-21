# Clinical Trial Matching Agent: Frozen Phase 1 MVP Specification

**Status:** Frozen source of truth
**Frozen on:** 2026-08-21
**Change policy:** Any scope or semantic change must be recorded explicitly in this specification and, when appropriate, an ADR. Held-out evaluation results must never drive optimization.

## 1. Objective

Build a research-coordinator decision-support prototype that compares a genuine synthetic FHIR R4 patient record with a broad, versioned corpus of public NSCLC clinical trials. The system retrieves candidate trials, assesses every parsed inclusion and exclusion criterion, and returns machine-verifiable patient evidence and exact trial-source citations.

The project exists to demonstrate agent cognition and orchestration, longitudinal FHIR modeling, hybrid retrieval, criterion-level reasoning, evidence grounding, and benchmark-first evaluation. It is not a chatbot, ordinary RAG demo, generic agent harness, or clinical product.

## 2. Claims and Safety Boundary

The system produces screening workflow labels for research coordinator review. It does not diagnose, recommend treatment, determine clinical eligibility, enroll patients, contact sites, or demonstrate clinical validity.

Phase 1 uses only public trial records and authored synthetic patient scenarios. It does not accept real PHI, connect to a live EHR, use MIMIC, claim HIPAA compliance, or make external write operations.

All reports must state that current recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## 3. Phase 1 Inputs

### 3.1 Trial Corpus Snapshot

The search universe is an immutable, versioned snapshot of full ClinicalTrials.gov records satisfying all of these study-wide conditions:

- Interventional study
- Overall status `RECRUITING`
- NSCLC identified through normalized condition or MeSH metadata rather than literal string matching alone
- At least one recruiting site in the United States

Corpus membership never uses patient-specific age, sex, biomarker, stage, histology, performance status, geography, or treatment history.

Each snapshot records the ClinicalTrials.gov `dataTimestamp`, ingestion configuration, source payload hashes, parser configuration, terminology mappings, index configuration, and derived-artifact versions. Refreshing creates a new snapshot and never mutates an existing Matching Run.

A snapshot older than seven days receives a `stale_snapshot` warning. It remains usable for reproducible historical evaluation.

### 3.2 Patient Input

The product input is a Synthea-compatible FHIR R4 `Bundle` plus an explicit `assessment_as_of` timestamp. The system derives a canonical Patient Timeline while preserving source resource identity, JSON path, codes, values, clinical status, Clinical Time, Temporal Precision, and provenance.

TREC narrative topics enter only through a retrieval-benchmark adapter. They are not converted into artificial FHIR and cannot support longitudinal-reasoning claims.

### 3.3 Authored Synthetic Scenarios

Benchmark patients begin with reproducibly generated Synthea Bundles and may receive controlled, standards-conformant FHIR augmentations for histology, stage, biomarkers, ECOG, treatments, laboratories, progression, and missing or conflicting facts.

A hidden Scenario Manifest records authored ground truth and transformation provenance. The matching system never receives this manifest.

## 4. FHIR Reasoning Boundary

Phase 1 reasons over:

- `Patient`
- `Condition`
- `Observation`
- `DiagnosticReport`
- `MedicationRequest`
- `MedicationAdministration`
- `Procedure`

`Encounter` and `Specimen` are context and provenance resources. Unsupported documents, notes, imaging pixels, care plans, and arbitrary extensions remain preserved but cannot establish a confident assessment.

Only facts with usable status and temporal semantics qualify as Patient Evidence. Medication orders and documented administrations remain distinct.

### 4.1 Temporal Policy

- Ignore events after `assessment_as_of`.
- Use clinical effective, onset, performed, or administration time rather than ingestion or update time.
- Preserve intervals and source date precision.
- Anchor relative windows to `assessment_as_of` unless the criterion names another anchor.
- Treat interval endpoints as inclusive unless the source criterion says otherwise.
- Missing precision for a required temporal comparison yields `unknown`.
- Conflicting current evidence yields `unknown` when deterministic precedence cannot resolve it.

### 4.2 Laboratory Policy

- Preserve raw value, comparator, unit, reference range, status, and Clinical Time.
- Normalize only through reviewed UCUM-compatible mappings.
- Evaluate numeric comparators and compatible unit conversions deterministically.
- ULN or LLN rules require the applicable reference range for that observation and patient context.
- Corrected or amended results supersede prior versions while retaining full provenance.
- Preliminary results cannot establish `met` or `not_met`; entered-in-error results are ignored.
- Qualitative values are never converted to numbers without a reviewed mapping.

### 4.3 Treatment-History Policy

- Valid `MedicationAdministration` resources establish exposure; `MedicationRequest` establishes intent only.
- Treatment Episodes preserve source, agent, route, dose when available, status, interval, and Clinical Time.
- Regimen and line-of-therapy derivation uses explicit scenario facts or versioned deterministic rules with defined grouping and precedence.
- Ambiguous grouping, line number, or exposure yields `unknown`.
- Washout uses the clinically relevant end of actual exposure or procedure interval.
- Progression after therapy establishes temporal ordering only, not treatment failure or causality.

### 4.4 Biomarker Policy

Phase 1 supports explicit positive or negative results, reviewed gene and variant mappings, and structured quantitative biomarkers such as PD-L1 when score type, assay, specimen context, and time are sufficient.

Assay-coverage inference, actionability inference, unsupported specimen interpretation, and complex discordant-test resolution are out of scope and yield `unknown`. A negative panel supports absence only for explicitly covered targets.

### 4.5 Stage and Histology Policy

Phase 1 uses explicitly represented and reviewed NSCLC diagnosis, histology, stage, progression, and recurrence facts. It does not derive stage from TNM, infer histology from treatment, or upgrade approximate disease labels. Staging system, version, Clinical Time, status, and provenance remain visible.

## 5. Terminology Boundary

The system preserves every original coding system, code, display, and source location. Versioned reviewed normalization is limited to ClinicalTrials.gov condition/MeSH metadata, ICD-10-CM codes present in Synthea, RxNorm medication concepts, LOINC laboratory and biomarker observations, and a small reviewed NSCLC synonym set.

Full SNOMED CT and UMLS are not Phase 1 dependencies. Model-proposed synonyms may expand retrieval queries but cannot independently establish `met` or `not_met`.

## 6. Criterion Representation

An Eligibility Criterion remains aligned to its original inclusion or exclusion source text, ordinal, and span. A versioned offline parser derives a Parsed Criterion Representation containing polarity, parser provenance, confidence, failure reason, and a Criterion Expression.

A Criterion Expression preserves `all_of`, `any_of`, and conditional structure over Atomic Propositions. Runtime matching consumes the frozen parsed representation and never reparses a trial per patient. Failed or low-confidence parsing leaves the source criterion visible and produces `unknown`.

Every parsed criterion appears in the output. Administrative, unsupported, and ambiguous criteria are never silently dropped.

## 7. Criterion Truth and Aggregation

Criterion State describes whether the patient satisfies the semantic statement of the criterion, regardless of inclusion or exclusion polarity:

- `met`: evidence supports the semantic statement.
- `not_met`: evidence contradicts the semantic statement.
- `unknown`: evidence is missing, stale, ambiguous, conflicting, unsupported, unparsed, or unverifiable.
- `not_applicable`: an explicit conditional antecedent is demonstrably false.

UI labels, if implemented, are Supported, Contradicted, Unknown, and Not Applicable. “Not Supported” is prohibited because it conflates contradiction with missing evidence.

### 7.1 Expression Truth Tables

For `all_of`, any `not_met` yields `not_met`; otherwise any `unknown` yields `unknown`; otherwise all applicable children `met` yields `met`. `not_applicable` children are ignored unless every child is `not_applicable`.

For `any_of`, any `met` yields `met`; otherwise any `unknown` yields `unknown`; otherwise all applicable children `not_met` yields `not_met`. `not_applicable` children are ignored unless every child is `not_applicable`.

For a conditional expression, antecedent `not_met` yields `not_applicable`, antecedent `met` yields the consequent state, and antecedent `unknown` yields `unknown`.

Models never perform Boolean aggregation.

### 7.2 Criterion Impact and Match Conclusion

| Polarity | `met` | `not_met` | `unknown` | `not_applicable` |
| --- | --- | --- | --- | --- |
| Inclusion | `satisfied` | `blocking` | `unresolved` | `neutral` |
| Exclusion | `blocking` | `satisfied` | `unresolved` | `neutral` |

Match Conclusion is derived deterministically:

- Any blocking impact: `unlikely_match`
- No blocker and at least one unresolved impact: `insufficient_information`
- No blocker and no unresolved impact: `potential_match`

Every Trial Assessment exposes blocker and unresolved counts. These conclusions are screening workflow labels, not clinical eligibility decisions.

## 8. Evidence Contract

Every `met` or `not_met` atomic assessment cites exact Trial Evidence and one or more Patient Evidence references with an explicit `supports` or `contradicts` relation.

Every `unknown` includes a structured reason such as `missing_evidence`, `conflicting_evidence`, `stale_evidence`, `ambiguous_criterion`, `unsupported_evidence_type`, `unparsed_criterion`, `verification_failed`, or `reasoning_conflict`.

Every `not_applicable` result cites the Patient Evidence establishing that the conditional antecedent is false.

Patient references contain FHIR resource type and ID, JSON path, Clinical Time, status, code/value, and a source-derived display. Trial references contain snapshot ID, NCT ID, polarity section, criterion ordinal/span, and exact source text.

A deterministic verifier rejects nonexistent references, changed values, invalid spans, missing evidence relations, incorrect expression aggregation, and `met` or `not_met` results without patient evidence. Model rationale is explanatory only and never counts as evidence.

## 9. Candidate Retrieval

The Patient Retrieval Profile prioritizes disease/histology, biomarkers, stage, and prior therapies as semantic facets. Demographic and geographic handling remains structured and conservative.

Patient-specific Candidate Filters are limited to deterministically comparable structured age, administrative sex, and explicit geography. Unknown values never remove trials. Biomarkers, stage, histology, performance status, and treatment history remain recoverable Retrieval Signals.

Retrieval uses two granularities:

- Trial-level title, conditions/MeSH, summary, interventions, and metadata
- Source-aligned criterion-level inclusion and exclusion chunks

Lexical and dense retrieval run independently per facet. Deterministic reciprocal-rank fusion combines channels, criterion hits aggregate to trial IDs, and a constrained local reranker processes the high-recall shortlist.

Candidate Retrieval returns an immutable top 20 with per-channel ranks and scores. The top five by Retrieval Rank receive full criterion assessment. A separate Review Priority orders assessed trials by Match Conclusion and then Retrieval Rank without overwriting the original rank. Ranks 6–20 remain visible Unassessed Candidates.

No blended “AI match score” combines retrieval and eligibility reasoning.

## 10. Criterion Reasoning Agent

Phase 1 uses one bounded, framework-independent typed Python agent loop:

1. Interpret the frozen Criterion Expression.
2. Classify Atomic Propositions by Criterion Category.
3. Build a source-backed Evidence Packet.
4. Select targeted read-only Patient Timeline queries and reasoning strategies.
5. Route structured arithmetic, dates, units, and Boolean logic to deterministic code.
6. Use the model for semantic interpretation, reviewed-concept alignment, and evidence selection.
7. Verify provenance and deterministic invariants.
8. Permit one targeted correction or re-plan.
9. Return a verified result or conservative `unknown`.

The model receives the exact criterion, frozen expression, polarity/provenance, and criterion-specific Evidence Packet—not the full Bundle, full trial record, or Scenario Manifest.

If correction still fails, the result is `unknown` with `verification_failed`. A conflict between deterministic and semantic results becomes `unknown` with `reasoning_conflict`. Infrastructure failures remain failures and are never scored as correct uncertainty.

There are no hidden model retries in evaluation. No cross-patient memory, generic agent harness, durable state machine, authorization flow, or action execution exists.

## 11. Architecture

Phase 1 contains five deep modules:

| Module | Interface | Owned complexity |
| --- | --- | --- |
| Corpus Builder | `build(snapshot_request) -> TrialCorpusSnapshot` | ClinicalTrials.gov ingestion, corpus membership, source preservation, parsing, version manifests, indexing |
| Patient Timeline Builder | `build(fhir_bundle, assessment_time) -> PatientTimeline` | FHIR validation, supported-resource interpretation, terminology, temporal precision, provenance |
| Candidate Retriever | `retrieve(patient_timeline, snapshot_id, retrieval_config) -> CandidateSet` | Candidate Filters, facets, lexical/dense channels, RRF, criterion aggregation, reranking, retrieval trace |
| Criterion Reasoner | `assess(patient_timeline, trial_record) -> TrialAssessment` | Evidence packets, strategy routing, deterministic/model reasoning, correction, verification, aggregation |
| Evaluation Lab | `run(eval_manifest, system_variant) -> EvalReport` | Parser, retrieval, reasoning, ablation, cost, and reproducibility evaluation |

`match(request) -> MatchingRun` is a thin application entry point rather than a core domain module. A small pure Matching Policy owns the top-20/top-5 and Review Priority rules. UI and HTTP transport remain outside the domain-module model.

ClinicalTrials.gov has HTTP/full-JSON and fixture adapters. Model inference has local, frozen-test, and optional hosted-upper-bound adapters. PostgreSQL and pgvector remain internal to the owning modules. Direct FHIR parsing stays concrete until a second source such as HAPI creates a real seam.

## 12. Core Data Model

### Patient Timeline

- Patient/scenario identity
- Source Bundle hash and normalization version
- Assessment Time
- Demographics and geography
- Time-ordered clinical facts with code/value/status/interval/precision
- Treatment Episodes
- Provenance references and unsupported-content inventory

### Trial and Trial Record

- Stable NCT trial identity
- Snapshot-scoped record identity and source payload hash
- Recruiting status, sites, source URL, and update date
- Conditions/MeSH, interventions, summaries, and structured eligibility metadata
- Source-aligned Eligibility Criteria and Parsed Criterion Representations

### Eligibility Criterion

- Version-scoped criterion ID
- Inclusion/exclusion polarity
- Source section, ordinal/span, exact text
- Criterion Expression and Atomic Propositions
- Parser provenance, confidence, and failure reason

### Criterion Assessment

- Criterion and atomic-proposition identities
- Criterion Category, Criterion State, and Criterion Impact
- Patient Evidence, Trial Evidence, and Evidence Relations
- Unknown Reason when applicable
- Deterministic computations, verifier outcome, and non-evidentiary rationale

### Trial Assessment

- Candidate Trial identity and immutable Retrieval Rank
- Complete Criterion Assessments
- Blocker and unresolved counts
- Match Conclusion and Review Priority
- Evidence Trajectory and operational measurements

### Matching Run

- Patient Timeline, Trial Corpus Snapshot, and Assessment Time identities
- Frozen parser, terminology, embedding, reranker, model, prompt, reasoning, and evaluator versions
- Candidate Set containing top 20 and explicit assessed/unassessed status
- Top-five Trial Assessments
- Reasoning Trace, warnings, latency, tokens, cost estimate, and hardware profile

### Eval Case

- Immutable versioned inputs and hidden expected outputs
- Dataset partition and scenario family
- Scorable and Coverage-Only Assessments
- Evidence equivalence sets
- Grading rules and expected operational behavior

## 13. Reproducibility and Trace

The Reasoning Trace records filter decisions, per-channel retrieval ranks, parser provenance, proposition classification, reasoning strategy, Patient Timeline queries, evidence IDs, deterministic computations, model metadata, verifier outcomes, correction reason, final states, tokens, latency, and configuration versions.

It is a read-only diagnostic artifact, not execution state, an authorization log, or a resumable checkpoint. Evaluation may re-grade frozen outputs. The coordinator-facing Evidence Trajectory contains only concise source and decision provenance, never hidden chain-of-thought or Scenario Manifest data.

## 14. Model Policy

Local embeddings, a local reranker, and a local instruction model are the default. Exact model, revision, quantization, runtime, prompts, schemas, decoding, and hardware are selected using development data, then frozen before held-out evaluation.

A hosted model may appear only as a separately labeled synthetic-data upper bound. There is no hosted fallback during a frozen local evaluation. Model licenses and limitations must be recorded.

Plain typed Python is the Phase 1 orchestration baseline. A later LangGraph implementation may be compared behind the same Criterion Reasoner interface. It may replace the baseline only after measurable improvement. Multi-agent remains a later equal-budget ablation.

## 15. Optional Post-Evaluation Coordinator Interface

The coordinator interface is not a Phase 1 implementation gate. If built after benchmark completion, it provides a structured review workflow rather than chat:

1. Select an Authored Synthetic Scenario and Trial Corpus Snapshot.
2. Inspect the Patient Timeline and Assessment Time.
3. Run matching and inspect the immutable top-20 retrieval table.
4. Review top-five Trial Assessments in Review Priority order while preserving Retrieval Rank.
5. Expand criteria, Atomic Propositions, evidence, unknown reasons, blockers, unresolved counts, and concise Evidence Trajectories.
6. Open cited FHIR resources and trial source spans.
7. Export a read-only reproducibility report.

A hosted public interface accepts only bundled synthetic scenarios and never arbitrary patient uploads. Local development may accept explicitly synthetic FHIR R4 Bundles.

## 16. Phase 1 Stop Line

Phase 1 excludes real PHI, live EHRs, MIMIC, HAPI FHIR, full SNOMED CT/UMLS, unstructured-note reasoning, imaging interpretation, full TNM staging, assay-actionability inference, clinical validation, chat, external writes, permissions, approval workflows, HITL, idempotency, durable execution, MCP, generic agent harnesses, LangGraph, multi-agent, fine-tuning, and required UI work.

Phase 1 is complete only through benchmark and failure-analysis gates; no calendar schedule governs implementation.
