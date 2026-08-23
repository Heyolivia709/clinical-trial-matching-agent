# Clinical Trial Matching Agent: MVP Specification (v5)

**Status:** Provisionally frozen — see freeze policy below
**Frozen on:** 2026-08-23
**Supersedes:** v4 (frozen 2026-08-22). Version 5 makes four changes. It adds the verification-induced `unknown` rate as a reported grounding result, so the verifier's cost is visible beside its benefit. It anchors the pre-registered falsification condition to Full before correction, because final-output reference validity is 100% by construction and therefore cannot serve as a comparison. It splits the delivery surface into a run-scoped Trace Report and a run-independent Evaluation Report, and reorders the Trace Report verdict-first. It records that what each evaluation variant receives in its prompt is fixed in the pre-registration rather than left to implementation. See [ADR 0010](../adr/0010-separate-the-evaluation-report-from-the-trace-report.md).

**Change policy:** Any scope or semantic change must be recorded explicitly here and, when it reverses a rejected alternative, in an ADR. Held-out evaluation results must never drive optimization.

**Freeze policy.** Sections 1–3, 16–20 and the safety boundary are frozen now: they are commitments about claims and discipline, and evidence will not change them. Sections 5–13 are *provisionally* frozen and re-frozen at the exit of Gate 2. They contain decisions that cannot be validated without an implementation — the resource boundary, the tool surface, per-proposition concurrency, the Unknown Reason vocabulary — and freezing them against no evidence produces either constant change-policy churn or silent divergence. v4 was declared a frozen source of truth with zero lines of code in the repository; v5 declares which parts had earned that status and which had not.

## 1. Objective

Build a portfolio system that demonstrates agent engineering: tool selection, controlled reasoning, evidence verification, bounded failure recovery, multi-turn cost control, and measured evaluation against baselines.

Clinical trial matching is the carrier domain, not the subject. The system compares an authored synthetic FHIR R4 patient record against a frozen snapshot of public NSCLC trials, assesses individual eligibility criteria, and returns structured judgments with machine-verified patient evidence and exact trial source citations.

The project is not a chatbot, an ordinary retrieval-augmented generation demo, a generic agent harness, a clinical text parser, or a clinical product.

## 2. Claims and Safety Boundary

The system produces screening workflow labels for research coordinator review. It does not diagnose, recommend treatment, determine clinical eligibility, enroll patients, contact sites, or demonstrate clinical validity.

Inputs are public ClinicalTrials.gov records and authored synthetic patient scenarios only. The system does not accept real PHI, connect to a live EHR, use MIMIC, or claim HIPAA compliance. It performs no external write operations.

Every report states that recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## 3. Demonstration Goal

A reviewer opening the hosted trace report, or running the project locally, must be able to observe all of the following within five minutes:

1. A patient timeline built from a synthetic FHIR R4 Bundle with per-fact provenance.
2. Candidate selection from the frozen snapshot; when the additive retrieval gate is built, this includes hybrid retrieval with per-channel rank attribution.
3. A trial criterion decomposed into atomic propositions.
4. The agent choosing and calling timeline tools per proposition.
5. Dates, numbers, and Boolean aggregation handled by deterministic code rather than the model.
6. A structured judgment citing patient evidence and exact trial source text.
7. The verifier rejecting a fabricated or incorrect citation and triggering exactly one correction.
8. A side-by-side comparison against deterministic and one-shot baselines showing where the agent design pays off.

Requirement 7 must be reproducibly demonstrable from an injected-fault fixture. Organic verifier catches are published when observed, but a model happening to make a particular mistake is not an acceptance criterion.

Five minutes is a hard constraint on the interface, not an aspiration. Requirements 3 through 8 are the ones that carry the claim, so section 15.1 orders the Trace Report to reach them first and demotes reproducibility metadata, the full timeline, and the retrieval table to the back. A document that presents the pipeline in execution order fails this requirement no matter how complete it is, because the reviewer stops reading before the interesting part.

## 4. Inputs

### 4.1 Trial Corpus Snapshot

An immutable, versioned snapshot of 200–500 full ClinicalTrials.gov records satisfying all study-wide conditions:

- Interventional study
- Overall status `RECRUITING`
- NSCLC identified through normalized condition or MeSH metadata rather than literal string matching alone
- At least one recruiting site in the United States

Corpus membership never uses patient-specific age, sex, biomarker, stage, histology, performance status, geography, or treatment history.

The snapshot records the ClinicalTrials.gov `dataTimestamp`, ingestion configuration, source payload hashes, terminology mappings, index configuration, and derived-artifact versions. Refreshing creates a new snapshot and never mutates an existing Matching Run. A snapshot older than thirty days receives a `stale_snapshot` warning and remains usable for reproducible historical evaluation.

Corpus size is intentionally larger than the assessed subset. A corpus of a few dozen trials would make top-5 retrieval trivial and retrieval ablations uninformative; corpus growth is nearly free because only assessed trials require authored criterion expressions.

### 4.2 Patient Input

A Synthea-compatible FHIR R4 `Bundle` plus an explicit `assessment_as_of` timestamp. The system derives a Patient Timeline preserving source resource identity, JSON path, codes, values, clinical status, Clinical Time, Temporal Precision, and provenance.

### 4.3 Authored Criterion Expressions

Criterion Expressions are hand-authored as versioned JSON for 10–12 trials in the snapshot. Automatic criterion parsing is out of scope: the subject under test is how the runtime agent finds and verifies evidence, not how well a model parses clinical text.

Expressions may be drafted with AI assistance and must be human-reviewed before freezing. Authoring provenance and review status are recorded per expression.

Authoring order matters. Retrieval configuration is frozen before expression authoring, so the trials that surface in the assessed set are known in advance. Trials without authored expressions are reported as `expression_unavailable` and never silently omitted.

### 4.4 Authored Synthetic Scenarios

Six scenarios begin as reproducibly generated Synthea Bundles and receive controlled, standards-conformant FHIR augmentations for demographics, disease, stage, biomarkers, ECOG, and simple treatment history.

Each scenario has a hidden Scenario Manifest recording authored facts, transformations, and Planted Distractors. The matching system never receives the manifest.

Scenarios are designed as a coverage matrix, not as six arbitrary patients. Collectively they must produce every Criterion State, every Unknown Reason, and every Planted Distractor kind defined in section 8.3.

## 5. FHIR Boundary

The system reasons over four evidence-bearing resource types:

- `Patient`
- `Condition`
- `Observation`
- `MedicationAdministration`

This is sufficient for demographics, disease and stage, biomarkers, ECOG, and explicit treatment exposure.

`MedicationRequest` is recognized and preserved as Unsupported Patient Content, but it is not an evidence-bearing resource because order intent is not exposure. Other Bundle content, including notes, imaging, care plans, encounters, specimens, and arbitrary extensions, is inventoried with resource identity when possible but is not semantically normalized and cannot establish a confident assessment.

Only facts with usable status and temporal semantics qualify as Patient Evidence.

### 5.1 Temporal Policy

- Ignore events after `assessment_as_of`.
- Use clinical effective, onset, or administration time rather than ingestion or update time.
- Preserve intervals and source date precision.
- Anchor relative windows to `assessment_as_of` unless the criterion names another anchor.
- Treat interval endpoints as inclusive unless the source criterion says otherwise.
- Missing precision required for a comparison yields `unknown`.
- Conflicting current evidence yields `unknown` when deterministic precedence cannot resolve it.

### 5.2 Observation Policy

- Preserve raw value, comparator, unit, reference range, status, and Clinical Time.
- Evaluate numeric comparators deterministically within a single unit.
- Corrected or amended results supersede prior versions while retaining provenance.
- `preliminary` results cannot establish `met` or `not_met`; `entered-in-error` results are ignored.
- Qualitative values are never converted to numbers without a reviewed mapping.
- Cross-unit conversion, UCUM normalization, and ULN/LLN derivation are out of scope and yield `unknown`.

### 5.3 Treatment-Exposure Policy

- A valid `MedicationAdministration` establishes exposure.
- Exposure preserves source, agent, route, status, interval, and Clinical Time.
- Simple washout windows use the end of documented exposure.
- Regimen grouping, line-of-therapy derivation, and treatment-failure inference are out of scope and yield `unknown`.

### 5.4 Biomarker and Stage Policy

Supported: explicit positive or negative biomarker results with reviewed gene and variant mappings, and structured quantitative biomarkers such as PD-L1 when score type and time are sufficient. Supported stage facts are explicitly represented and reviewed.

Out of scope, yielding `unknown`: assay-coverage inference, actionability inference, discordant-test resolution, TNM-to-stage derivation, and histology inferred from treatment. A negative panel supports absence only for explicitly covered targets.

## 6. Criterion Scope

Four Criterion Categories are supported:

| Category | Examples |
| --- | --- |
| Demographic | age, administrative sex |
| Disease | NSCLC diagnosis, stage |
| Biomarker | EGFR, ALK, PD-L1 explicit results |
| Prior therapy | documented exposure to a named agent |

Supported expression forms: `all_of`, `any_of`, simple conditional expressions, simple date windows, and simple numeric comparisons.

Any criterion outside these categories or expression forms is authored as an `unsupported` proposition, remains visible in output, and resolves to `unknown` with reason `unsupported_evidence_type`. Criteria are never silently dropped.

## 7. Criterion Truth and Aggregation

The model assesses one Atomic Proposition at a time and produces a Proposition Assessment. Deterministic code aggregates Proposition Assessments through the authored Criterion Expression to produce one Criterion Assessment for the source Eligibility Criterion. The model never directly chooses the aggregate Criterion State.

Criterion State describes whether the patient satisfies the semantic statement of an Atomic Proposition or, after deterministic aggregation, the complete Eligibility Criterion. At either level it is independent of inclusion or exclusion polarity:

- `met`: evidence supports the semantic statement.
- `not_met`: evidence contradicts the semantic statement.
- `unknown`: evidence is missing, stale, ambiguous, conflicting, unsupported, or unverifiable.
- `not_applicable`: an explicit conditional antecedent is demonstrably false.

`not_assessed` is a separate reporting status, not a Criterion State. It marks criteria the Trial Supervisor deliberately skipped under an early-termination budget. It must never be merged into `unknown`.

UI labels are Supported, Contradicted, Unknown, Not Applicable, and Not Assessed. "Not Supported" is prohibited because it conflates contradiction with missing evidence.

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

Under early termination, any `not_assessed` criterion forces at least `insufficient_information` unless a blocker is already present. Every Trial Assessment exposes blocker, unresolved, and not-assessed counts. These conclusions are screening workflow labels, not clinical eligibility decisions.

## 8. Evidence Contract

Every `met` or `not_met` Proposition Assessment cites exact Trial Evidence and one or more Patient Evidence references with an explicit `supports` or `contradicts` relation.

Every `unknown` Proposition Assessment carries a structured Unknown Reason: `missing_evidence`, `conflicting_evidence`, `stale_evidence`, `ambiguous_criterion`, `unsupported_evidence_type`, `expression_unavailable`, `verification_failed`, or `reasoning_conflict`.

Every `not_applicable` Proposition Assessment cites the Patient Evidence establishing that the conditional antecedent is false.

Patient references contain FHIR resource type and ID, JSON path, Clinical Time, status, code/value, and a source-derived display. Trial references contain snapshot ID, NCT ID, polarity section, criterion ordinal and span, and exact source text.

Model rationale is explanatory only and never counts as evidence.

### 8.1 Evidence Verifier

A deterministic verifier rejects:

- References to nonexistent FHIR resources or JSON paths
- Cited values, statuses, or times that disagree with the timeline
- Invalid or out-of-range trial spans, or span text that disagrees with the snapshot
- Missing or unlabeled evidence relations
- `met` or `not_met` without patient evidence
- Incorrect expression aggregation
- Evidence dated after `assessment_as_of`

Verification failure triggers exactly one targeted correction. A second failure yields `unknown` with `verification_failed`. Disagreement between deterministic computation and model interpretation yields `unknown` with `reasoning_conflict`.

The verifier has two distinct roles, served by one implementation at two call sites. Conflating them would make the grounding comparison meaningless.

| Role | Applies to | Effect |
| --- | --- | --- |
| Grading | Every variant, including B0, B1, B2, ablations, and Full | Scores final outputs offline. Results never flow back into the system under test. |
| Feedback | Full only | Its verdict triggers the single correction inside the agent loop. |

Offline grading runs the same code with the same configuration across all variants. Only Full receives verifier feedback and a correction opportunity; baselines are graded by the same standard they were never allowed to consult. This asymmetry is the measured architectural difference, not a confound, and it is stated wherever the comparison is published.

Because Full's final outputs have passed through one correction, citation validity is reported at three points — B2, Full before correction, and Full after correction — so the contribution of tool-mediated evidence selection is separable from the contribution of the correction loop.

### 8.2 Failure Separation

Infrastructure Failures — unavailable model endpoint, malformed snapshot, tool exception — are recorded as failures and are never scored as correct uncertainty.

### 8.3 Planted Distractors

Benchmark difficulty comes from deliberately planted evidence hazards rather than clinical subtlety. Scenarios must collectively include all of:

1. An `entered-in-error` biomarker or stage result
2. A `MedicationRequest` with no corresponding `MedicationAdministration`
3. An observation dated after `assessment_as_of`
4. Two conflicting results for the same concept
5. A date with year-only precision where the criterion requires a finer window
6. A `preliminary` result relevant to a threshold comparison
7. A semantically near but non-matching concept, such as ALK expression versus ALK rearrangement

## 9. Candidate Retrieval

The Patient Retrieval Profile is a retrieval-oriented view of the timeline covering disease and histology, biomarkers, stage, prior therapy, demographics, and geography. Per-facet query decomposition is out of scope; the profile produces one query representation per channel.

Patient-specific Candidate Filters are limited to deterministically comparable structured age, administrative sex, and explicit geography. Unknown values never remove trials. Biomarkers, stage, and treatment history remain recoverable Retrieval Signals, never hard filters.

Two channels run independently over trial-level text — title, conditions and MeSH, summary, interventions, and eligibility text:

- Lexical (BM25)
- Dense (local embeddings)

Deterministic reciprocal-rank fusion combines the channels. Cross-encoder reranking is out of scope.

Retrieval returns an immutable top 20 with per-channel ranks and scores. The top five by Retrieval Rank are presented; the top three receive full criterion assessment. Review Priority orders assessed trials by Match Conclusion and then Retrieval Rank without overwriting Retrieval Rank. Ranks 4–20 remain visible Unassessed Candidates.

No blended "AI match score" combines retrieval and eligibility reasoning.

Model-proposed query expansions may improve retrieval but can never independently establish a Criterion State. Whether expansions are produced deterministically or by the model is recorded in the retrieval configuration.

## 10. Criterion Reasoning Agent

One bounded, framework-independent typed Python loop, executed per Atomic Proposition:

1. Read the frozen Criterion Expression.
2. Classify each Atomic Proposition by Criterion Category.
3. Determine which patient information is required.
4. Select and call Timeline Tools.
5. Route dates, numbers, and Boolean logic to deterministic tools.
6. Produce a structured assessment with citations.
7. Run the Evidence Verifier.
8. On failure, perform exactly one targeted correction.
9. On second failure, return a Proposition Assessment of `unknown` with `verification_failed`.
10. Aggregate verified Proposition Assessments through deterministic expression logic to produce the Criterion Assessment.

The model receives the exact criterion text, the frozen expression, polarity and provenance, and tool results. It never receives the full Bundle, the full trial record, or the Scenario Manifest.

Criterion assessments within a trial are independent and executed concurrently unless evidence reuse is enabled.

There are no hidden model retries in evaluation. No cross-patient memory, generic agent harness, durable state machine, authorization flow, or action execution exists.

### 10.1 Timeline Tools

Typed Python tools, all read-only:

| Tool | Purpose |
| --- | --- |
| `find_patient_facts(category, concept)` | Locate timeline facts by category and normalized concept |
| `get_latest_observation(code, as_of)` | Retrieve the most recent qualifying observation |
| `find_medication_exposure(concept, time_window)` | Locate documented administrations within a window |
| `compare_numeric(value, operator, threshold)` | Deterministic numeric comparison |
| `check_temporal_window(event_time, anchor, window)` | Deterministic temporal window evaluation |

Tool calls, arguments, and results are recorded in the Reasoning Trace.

## 11. Trial Supervisor

A multi-turn layer above the Criterion Reasoning Agent, owning trial-level assessment strategy. Every behavior is a configuration flag, default off.

| Flag | Behavior | Measured effect |
| --- | --- | --- |
| `order_criteria` | Assess likely-blocking exclusion criteria first | Time to first blocker |
| `early_termination` | Stop after a blocker is confirmed; mark the remainder `not_assessed` | Token and latency reduction |
| `evidence_reuse` | Reuse verified evidence established for an earlier criterion in the same trial | Model-call reduction |

Flags are off for correctness benchmarks and on for cost benchmarks, so multi-turn behavior appears as an ablation row rather than a confound.

Known hazards, which must be measured rather than assumed away:

- `early_termination` forfeits full Criterion Coverage. Skipped criteria are reported as `not_assessed`, never `unknown`.
- `order_criteria` and `evidence_reuse` introduce order dependence. Assessment order is deterministic given a fixed configuration and seed.
- `evidence_reuse` can propagate one incorrect reading across criteria. Reused evidence carries the originating criterion ID, and reuse-induced error propagation is reported separately.

## 12. Architecture

Four deep modules, each hiding substantial complexity behind a small stable interface:

| Module | Interface | Owned complexity |
| --- | --- | --- |
| Patient Timeline | `build(bundle, as_of) -> PatientTimeline` | FHIR validation, supported-resource interpretation, terminology, temporal precision, provenance, tool surface |
| Trial Retrieval | `retrieve(timeline, snapshot, k) -> CandidateSet` | Ingestion, corpus membership, candidate filters, BM25, embeddings, RRF, retrieval trace |
| Criterion Agent | `assess(timeline, trial) -> TrialAssessment` | Tool selection, model reasoning, deterministic computation, verification, correction, supervisor strategy, aggregation |
| Evaluation Lab | `run(manifest, variant) -> EvalReport` | Gold derivation, baselines, ablations, metrics, cost accounting, failure analysis |

The application entry point stays thin:

```
match(patient, snapshot) -> MatchingRun
```

A small pure Matching Policy owns the top-20, top-5, top-3, and Review Priority rules. Parser, terminology, evidence packet construction, and index internals are module-internal and have no separate public interface.

ClinicalTrials.gov has HTTP and fixture adapters. Model inference has hosted, local, and frozen-replay adapters. The retrieval index sits behind a single interface so a larger backend can replace the in-process implementation without touching callers.

## 13. Core Data Model

**Patient Timeline** — scenario identity; source Bundle hash and normalization version; Assessment Time; demographics and geography; time-ordered facts with code, value, status, interval, and precision; documented medication exposures; provenance references; unsupported-content inventory.

**Trial Record** — stable NCT identity; snapshot-scoped record identity and source payload hash; recruiting status, sites, source URL, update date; conditions and MeSH, interventions, summaries; source-aligned Eligibility Criteria; authored Criterion Expressions with authoring provenance.

**Eligibility Criterion** — version-scoped ID; polarity; source section, ordinal, span, exact text; Criterion Expression and Atomic Propositions; authoring provenance and review status.

**Proposition Assessment** — proposition identity and category; Criterion State; Patient Evidence, Trial Evidence, and Evidence Relations; Unknown Reason; tool calls; deterministic computations; verifier outcome; correction record; non-evidentiary rationale.

**Criterion Assessment** — criterion identity and polarity; complete Proposition Assessments; deterministically aggregated Criterion State and Impact; aggregation trace; coverage status.

**Trial Assessment** — candidate identity and immutable Retrieval Rank; complete Criterion Assessments; blocker, unresolved, and not-assessed counts; Match Conclusion; Review Priority; Evidence Trajectory; operational measurements.

**Matching Run** — timeline, snapshot, and Assessment Time identities; frozen retrieval, embedding, model, prompt, tool, supervisor, and evaluator versions; Candidate Set with assessed and unassessed status; Trial Assessments; Reasoning Trace; warnings; latency, model calls, tokens, cost estimate, hardware profile.

**Eval Case** — immutable versioned inputs; derived expected outputs; partition and scenario family; Scorable and Coverage-Only assessments; evidence equivalence sets; grading rules.

## 14. Trace and Reproducibility

The Reasoning Trace records filter decisions, per-channel retrieval ranks, expression provenance, proposition classification, tool calls with arguments and results, deterministic computations, model metadata, verifier outcomes, correction reason, supervisor decisions, final states, tokens, latency, and configuration versions.

It is a read-only diagnostic artifact, not execution state, an authorization log, or a resumable checkpoint. Frozen traces can be re-graded and replayed offline.

The coordinator-facing Evidence Trajectory is the concise subset explaining which criterion, evidence, tools, and verification steps produced an assessment. It never exposes hidden chain-of-thought or Scenario Manifest content.

Each run records patient and trial hashes, partition, embedding, model, prompt and schema, decoding, tool and supervisor configuration, evaluator code version, seed, latency, tokens, estimated cost, and hardware profile.

## 15. Delivery Surface

The delivery surface is **two** self-contained static artifacts, each publishable as a hosted page and viewable offline without credentials, a server, or any network fetch. Both are generated from frozen artifacts, so they are built last and never become a dependency of the reasoning modules.

The split exists because the two have different scopes. A Trace Report describes one Matching Run. Evaluation results describe the benchmark across every run, and cannot be derived from any single one. Presenting them as one document lets a corpus-scoped statistic sit beside a run-scoped trace as though they were the same kind of claim, which is precisely how a portfolio artifact becomes misleading. See [ADR 0010](../adr/0010-separate-the-evaluation-report-from-the-trace-report.md).

### 15.1 Trace Report — scoped to one Matching Run

Ordered verdict-first, not in pipeline order. The three sections carrying the engineering claim are the criterion detail, the verifier catch, and the per-criterion baseline comparison; a reader must reach them before any setup material.

| Order | Content |
| --- | --- |
| 1 | Plain-language summary: one sentence on what the system does, the run's conclusions, and the single worked criterion that demonstrates the claim. Written for a reader with no domain or system vocabulary. |
| 2 | The demonstrative criterion in full: source text, atomic propositions, state, impact, evidence, tool call sequence with arguments and results |
| 3 | Verifier outcome for that criterion, including the rejected citation and the resulting correction |
| 4 | Side-by-side Full, expression-aware one-shot, and raw-text one-shot results on that same criterion |
| 5 | The top five candidates, with the assessed top three in Review Priority order |
| 6 | Per-trial criterion tables: state, impact, and Unknown Reason for every criterion |
| 7 | The patient timeline with per-fact provenance |
| 8 | The immutable top-20 retrieval table with per-channel ranks and per-channel scores |
| 9 | Per-assessment latency, model calls, tokens, and cost |
| 10 | Reproducibility header: identities, hashes, frozen configuration versions, and warnings |

Citations link to the cited FHIR JSON path and the exact trial source span. Sections with a collapsed and an expanded state are specified in both; the collapsed state is what a reader lands on and is designed first.

A persistent section index is required. It is wayfinding for a long single document, not application chrome, and it does not reintroduce breadcrumbs, back buttons, in-page tabs, or per-screen headers.

Every scenario with a Matching Run gets a Trace Report. At least one report covers a run in which the system fails, per the pre-registration's failure-case obligation.

### 15.2 Evaluation Report — scoped to the benchmark, not to any run

A separate artifact. It opens by stating that its scope is the benchmark rather than a run, and it never appears as a section of a Trace Report.

It presents, per the benchmark plan and the pre-registration:

1. Deterministic invariants as pass or fail, in their own table, labelled release gates
2. Reported results in a separate table, labelled as reported and explicitly not gated, with confidence intervals, realised cluster and observation counts, and per-state support
3. The paired cost-value table, with cost per criterion assessment beside the grounding metric it purchased
4. Citation validity at its comparable measurement points, with the verification-induced `unknown` rate beside the post-correction point
5. The pre-registered two-sided comparison: effect size, interval, and outcome, including inconclusive and unfavourable outcomes
6. The falsification condition and its evaluated result
7. The failure taxonomy, with at least two failure cases linking to their full Trace Reports
8. Its own scope and limitations statement

No release gate in this report is a model-behavior statistic. Nothing in it is presented as a property of a single run.

### 15.3 Constraints binding on both

- Self-contained: no network fetch at view time, fonts and assets included. A report that needs the network is not offline-viewable.
- Print styles implemented; the disclaimer appears in print output.
- No blended score, no match percentage, no progress bar, gauge, or star rating.
- Colour and shape encode Criterion Impact, never Criterion State.
- Retrieval Rank and Review Priority are both shown and never merged.
- Trial source text is verbatim, never rewritten, truncated, or paraphrased.
- No Scenario Manifest content and no model chain-of-thought.

An optional live mode may run a new patient-trial pair locally and produce a Trace Report.

## 16. Model Policy

Model inference sits behind an adapter with hosted, local, and frozen-replay implementations. Headline results may come from a hosted small model; the adapter interface, not the model choice, is the engineering claim. Local execution is reported when available.

A deliberately modest model is acceptable and arguably preferable: higher fabrication rates make verifier value larger and more measurable.

Exact model, revision, prompts, schemas, decoding, and hardware are selected on development data and frozen before held-out evaluation. Structured output uses constrained decoding or schema validation with recorded, non-hidden retries. Model licenses and limitations are recorded.

Plain typed Python is the orchestration baseline. LangGraph, multi-agent execution, and fine-tuning are out of scope.

## 17. Authoring Policy

AI assistance is permitted for drafting criterion expressions, synthetic scenario resources, distractor designs, corpus normalization, code, tests, and documentation. Every AI-drafted artifact is human-reviewed before freezing, and its authoring provenance and review status are recorded.

AI-generated expected-state labels are prohibited. Using a model to produce the ground truth that scores a model measures agreement, not correctness.

Expected states are instead derived deterministically by code from the hidden Scenario Manifest and the authored Criterion Expression. Because scenario facts are authored, the expected state for a supported proposition is computable rather than a matter of judgment.

Propositions whose semantics cannot be operationalized this way remain visible as Coverage-Only Assessments and are excluded from accuracy metrics.

This makes the benchmark a test of evidence retrieval, citation validity, and logic application — not of clinical judgment. The specification states this limitation explicitly rather than implying broader validity.

## 18. Scope Line

Excluded from this MVP: real PHI, live EHRs, MIMIC, HAPI FHIR, full SNOMED CT and UMLS, automatic criterion parsing, unstructured-note reasoning, imaging interpretation, TNM derivation, UCUM unit conversion, line-of-therapy inference, assay-actionability inference, cross-encoder reranking, per-facet retrieval decomposition, PostgreSQL and pgvector, TREC benchmark tracks, manual gold labeling at scale, clinical validation, chat interfaces, external writes, permissions, approval workflows, human-in-the-loop workflows, idempotency, durable execution, MCP, generic agent harnesses, LangGraph, multi-agent orchestration, and fine-tuning.

Progress is governed by acceptance criteria, not a calendar.

## 19. Core and Additive Scope

Not every gate is essential. If time is constrained, cut from the bottom of this list.

**Core** — without these the project does not demonstrate its claim:

- Gate 1 Contracts and fixtures
- Gate 2 Patient Timeline and Timeline Tools
- Gate 4 Criterion Agent and Evidence Verifier
- Gate 6 Evaluation, baselines, and core ablations
- Gate 7 Trace Report and Evaluation Report, because an unseen result is not a portfolio result

**Additive** — real value, but the project remains complete and honest without them:

- Gate 3 Hybrid retrieval. Fallback: the four frozen core trial fixtures selected in Gate 1, which preserve two-axis partitioning, with retrieval declared out of scope.
- Gate 5 Trial Supervisor. Fallback: single-turn per-criterion assessment only.

**Cut order under schedule pressure:**

1. Gate 5 Trial Supervisor entirely, including its two supervisor-only ablations
2. Dense retrieval and RRF, keeping BM25 only
3. Scenarios from six to four
4. Live report mode, keeping the static report
5. Authored trials from twelve to eight

Cutting a stage requires deleting its claims from the report as well. Reduced scope stated plainly is stronger than scope implied but unmeasured.

## 20. Release Gates and Reported Results

Only deterministic invariants are release gates. These are properties the implementation controls, so gating on them is a statement about software correctness:

- Patient and trial reference validity in final output: 100%
- Deterministic aggregation accuracy: 100%
- Verifier catch rate on injected faults: 100%
- Unsupported assessments surviving verification in final output: 0
- Criterion Coverage with supervisor flags off: 100%
- Citations dated after `assessment_as_of` in final output: 0
- Infrastructure Failures scored as `unknown`: 0

Every model-behavior measurement is a reported result, not a gate. This includes criterion-state macro F1, per-state precision and recall, patient-evidence precision and recall, Match Conclusion accuracy, the pre-correction unsupported-assessment rate, the verification-induced `unknown` rate, and every cost figure. Gating on them at this sample size would invite optimizing toward a threshold, and held-out results must never drive optimization.

**The first invariant is structural, and that has a consequence for how it may be used.** Reference validity in final output reaches 100% because the verifier degrades every assessment it cannot verify to `unknown` with reason `verification_failed`. It is therefore a statement about the implementation, not a measurement of model behavior, and it may never be compared against a baseline: a variant with no verifier has no such guarantee, so the comparison would report an architectural difference as a result. Comparisons use Full *before* correction.

**What the guarantee costs is itself a reported result.** The verification-induced `unknown` rate — propositions Full committed to before correction and returned as `unknown` after it — is published wherever post-correction validity is published, at equal prominence. A verifier that rejected everything would satisfy every invariant above and produce a worthless system; this metric is what distinguishes the two.

The comparison against the expression-aware one-shot control B2 is a pre-registered, two-sided hypothesis test with no minimum effect threshold, evaluated on Full before correction. Effect sizes and confidence intervals are published whether or not the test is significant, and a null or negative result is published as such. What each variant receives in its prompt — as distinct from what it is permitted to see — is fixed in the pre-registration and is not an implementation choice.

The pre-registration document — metrics, comparison units, per-variant prompt contents, statistical procedure, precision, and falsification condition — is committed before any held-out run, and the published report cites its commit hash. See [`../evaluation/pre-registration.md`](../evaluation/pre-registration.md).

Precision is stated as a procedure rather than as a number. The detectable-difference band is governed by the count of held-out clusters — scenario-trial pairs — not by the count of graded observations inside them, and it is recomputed from development-set data and committed as a dated amendment before the held-out run begins. A band asserted in advance without being derived from anything constrains nothing.
