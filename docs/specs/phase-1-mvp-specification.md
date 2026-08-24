# Clinical Trial Matching Agent: MVP Specification (v7)

**Status:** Provisionally frozen — see freeze policy below
**Frozen on:** 2026-08-24

**Supersedes:** v6 (frozen 2026-08-23). Version 7 cuts scope rather than adding any. The project is a portfolio piece demonstrating agent engineering, and v6 had specified a research-grade evaluation around it: a pre-registered two-sided test, cluster-level bootstrap resampling, a committed precision amendment, three baselines with two supervisor ablations, a separate benchmark artifact, and a hybrid retrieval stack over a corpus of hundreds of trials. Each was defensible in isolation and none of them demonstrates an agent. Version 7 removes:

- Candidate retrieval entirely — BM25, dense embeddings, reciprocal-rank fusion, candidate filters, and the corpus they would rank. The candidate set is the four frozen trial records of section 4.1. Sections 9, 12, 14 and 18 change accordingly.
- Inferential statistics. Reported results are counts and percentages over stated denominators, with the sample size shown. No interval, test, or effect size, and no pre-registration document to fix one in advance. Section 20 states why, and the report says it where the numbers appear.
- Two of three baselines and both supervisor-only ablations. One one-shot baseline carries the comparison; the no-verifier configuration remains as a reported row.
- The separate Evaluation Report. One report, with the run-independent counts in a labelled section, supersedes ADR 0010.
- Evidence Reuse, whose error-propagation measurement was the expensive half of the feature.

See [ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md).

**Superseded:** v5 (frozen 2026-08-23). Version 6 closes five gaps that the interface design surfaced by being forced to render behaviour the specification had not defined. Each was resolved silently in a mockup, which is the wrong place for a semantic decision.

- Section 5.1 governs prospective anchors — "within 14 days prior to the first dose of study drug" — through an authored, recorded substitution, never a runtime one.
- Section 6 adds `performance_status` as a fifth supported Criterion Category and `unsupported` as an explicit sixth value, so ECOG stops being filed under `disease`.
- Section 8.0 adds a deterministic Unknown Reason decision table, and two reasons — `unusable_status` and `insufficient_precision` — without which three distinct planted hazards all surface as `missing_evidence`.
- Section 8.1 adds the verifier check for citations that resolve but cannot establish the claimed state. The section 3 demonstration already depended on it.
- Section 9 defines the assessed set when a top-three candidate has no authored expression, with backfill bounded at the presented rank 5.

**Change policy:** Any scope or semantic change must be recorded explicitly here and, when it reverses a rejected alternative, in an ADR. Held-out evaluation results must never drive optimization.

**Freeze policy.** Sections 1–3, 16–20 and the safety boundary are frozen: they are commitments about claims and discipline, and evidence will not change them. Sections 5–13 were provisionally frozen and are re-frozen now that Gates 1 and 2 have exercised them in code — the resource boundary, the tool surface, the Unknown Reason vocabulary, and the truth tables all have implementations and tests behind them. Section 9 is the exception and is settled by the cut above rather than by evidence.

## 1. Objective

Build a portfolio system that demonstrates agent engineering: tool selection, controlled reasoning, evidence verification, bounded failure recovery, bounded multi-turn cost control, and honest measurement against a one-shot baseline.

Clinical trial matching is the carrier domain, not the subject. The system compares an authored synthetic FHIR R4 patient record against four frozen public NSCLC trial records, assesses individual eligibility criteria, and returns structured judgments with machine-verified patient evidence and exact trial source citations.

The project is not a chatbot, an ordinary retrieval-augmented generation demo, a generic agent harness, a clinical text parser, or a clinical product.

## 2. Claims and Safety Boundary

The system produces screening workflow labels for research coordinator review. It does not diagnose, recommend treatment, determine clinical eligibility, enroll patients, contact sites, or demonstrate clinical validity.

Inputs are public ClinicalTrials.gov records and authored synthetic patient scenarios only. The system does not accept real PHI, connect to a live EHR, use MIMIC, or claim HIPAA compliance. It performs no external write operations.

Every report states that recruiting status, site availability, and actual eligibility must be verified through ClinicalTrials.gov and the study team.

## 3. Demonstration Goal

A reviewer opening the hosted trace report, or running the project locally, must be able to observe all of the following within five minutes:

1. A patient timeline built from a synthetic FHIR R4 Bundle with per-fact provenance.
2. Candidate selection from the frozen trial records, with the assessed set and its bounded backfill visible.
3. A trial criterion decomposed into atomic propositions.
4. The agent choosing and calling timeline tools per proposition.
5. Dates, numbers, and Boolean aggregation handled by deterministic code rather than the model.
6. A structured judgment citing patient evidence and exact trial source text.
7. The verifier rejecting a fabricated or incorrect citation and triggering exactly one correction.
8. A side-by-side comparison against a one-shot baseline showing where the agent design pays off, or where it does not.

Requirement 7 must be reproducibly demonstrable from an injected-fault fixture. Organic verifier catches are published when observed, but a model happening to make a particular mistake is not an acceptance criterion.

Five minutes is a hard constraint on the interface, not an aspiration. Requirements 3 through 8 are the ones that carry the claim, so section 15 orders the report to reach them first and demotes reproducibility metadata and the full timeline to the back. A document that presents the pipeline in execution order fails this requirement no matter how complete it is, because the reviewer stops reading before the interesting part.

## 4. Inputs

### 4.1 Frozen Trial Records

Four public ClinicalTrials.gov records, captured once and frozen: identity, recruiting status, sites, source URL, update date, conditions and MeSH terms, interventions, summaries, and the verbatim eligibility text with every published criterion preserved at its exact span and ordinal.

Selection is by coverage, not convenience. The four together exercise all five supported Criterion Categories, the `unsupported` value, and every supported expression form, and they split two development and two held out.

Each record carries the SHA-256 of the eligibility text it was reviewed against, so editing the text without a new review makes the record fail to load. A record whose ClinicalTrials.gov data has since changed is not silently refreshed: published criteria do change, and a frozen artifact that quietly tracks them cannot reproduce a past run.

Four is the minimum that keeps a two-axis partition of trials and scenarios intact. Growing the set is authoring work, not engineering work, and section 18 puts the retrieval this would feed out of scope.

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
- Precision coarser than a comparison requires yields `unknown` with `insufficient_precision`.
- Conflicting current evidence yields `unknown` with `conflicting_evidence` when deterministic precedence cannot resolve it.

#### Prospective anchors

Many real exclusion criteria anchor to an event that has not happened at screening time: "within 14 days prior to the first dose of study drug", "since randomization", "prior to cycle 1 day 1". Such an anchor is named by the criterion, so the default rule above does not apply, and it cannot be resolved from the patient record because the event does not exist yet.

Substituting `assessment_as_of` silently is prohibited. It is the right proxy in practice — screening is done before enrollment, so "now" is what a coordinator uses — but it changes the semantics of the criterion, and an unrecorded semantic change is the thing this project exists not to do.

The substitution is therefore made once, at authoring time, and never at runtime:

- The Criterion Expression may declare an explicit anchor substitution, recording the source anchor phrase, the substituted anchor, and the authoring rationale. Authoring provenance and review status apply as to any other authored content.
- A declared substitution is surfaced beside the criterion wherever the assessment is reported, not buried in the trace.
- If the criterion names an unresolvable anchor and the expression declares no substitution, the proposition yields `unknown` with `ambiguous_criterion`.
- The model never selects, proposes, or infers an anchor.

Every declared substitution is a screening-time proxy and is listed as such in the limitations section of the published report.

### 5.2 Observation Policy

- Preserve raw value, comparator, unit, reference range, status, and Clinical Time.
- Evaluate numeric comparators deterministically within a single unit.
- Corrected or amended results supersede prior versions while retaining provenance.
- `preliminary` results cannot establish `met` or `not_met`; `entered-in-error` results are ignored. Where such a result is the only fact for the concept, the proposition yields `unknown` with `unusable_status` rather than `missing_evidence`: a disqualified fact and no fact at all are different diagnoses and the output distinguishes them.
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

Five Criterion Categories are supported, and a sixth value marks everything else:

| Category | Examples |
| --- | --- |
| `demographic` | age, administrative sex |
| `disease` | NSCLC diagnosis, stage |
| `biomarker` | EGFR, ALK, PD-L1 explicit results |
| `prior_therapy` | documented exposure to a named agent |
| `performance_status` | ECOG |
| `unsupported` | everything outside the five above |

Performance status is a supported category rather than a member of `disease`. Section 5 already places ECOG inside the evidence-bearing boundary, an ECOG criterion is a numeric comparison over a structured `Observation` — the case the deterministic tools handle best — and filing it under `disease` mislabels it in every per-category breakdown the benchmark plan reports.

`unsupported` is a category value, not an absence of one. Without it a proposition outside the supported set has no legal category and acquires a misleading one; the mockups filed interstitial lung disease under `disease` for exactly this reason, so the output claimed the system had assessed a disease criterion when it had not.

Supported expression forms: `all_of`, `any_of`, simple conditional expressions, simple date windows, and simple numeric comparisons.

Any criterion outside these categories or expression forms is authored as an `unsupported` proposition, carries category `unsupported`, remains visible in output, and resolves to `unknown` with reason `unsupported_evidence_type`. Criteria are never silently dropped.

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

Every `unknown` Proposition Assessment carries a structured Unknown Reason: `missing_evidence`, `unusable_status`, `insufficient_precision`, `conflicting_evidence`, `stale_evidence`, `ambiguous_criterion`, `unsupported_evidence_type`, `expression_unavailable`, `verification_failed`, or `reasoning_conflict`.

### 8.0 Unknown Reason Assignment

The reason is chosen by deterministic code from the timeline and the criterion, never by the model, and the choice is reproducible. Assignment runs in three stages.

**Stage 1, before assessment.** A trial with no authored Criterion Expression yields `expression_unavailable` for every one of its criteria.

**Stage 2, from the evidence.** The first matching row wins; rows are evaluated top to bottom.

| Condition at `assessment_as_of` | Reason |
| --- | --- |
| The proposition is authored `unsupported`, or the only candidate fact sits in a resource type the boundary does not treat as evidence-bearing | `unsupported_evidence_type` |
| The criterion names an anchor, threshold, or concept the authored expression could not operationalize, and declares no substitution | `ambiguous_criterion` |
| No fact for the concept exists, including where the nearest fact is a semantically near but distinct concept, and including where the only occurrence is dated after `assessment_as_of` and therefore excluded | `missing_evidence` |
| A fact for the concept exists but its status disqualifies it under section 5.2 | `unusable_status` |
| Two or more qualifying facts disagree and deterministic precedence cannot resolve them | `conflicting_evidence` |
| A qualifying fact exists but its temporal precision is coarser than the comparison requires | `insufficient_precision` |
| A qualifying fact exists but falls outside the window the criterion requires, and no in-window fact exists | `stale_evidence` |

**Stage 3, after the agent loop.** `verification_failed` and `reasoning_conflict` replace whatever stage 2 assigned. A second verification failure is the reason regardless of what the evidence looked like.

Two of these reasons exist because collapsing them into `missing_evidence` would have made the benchmark unreadable. Section 8.3 plants a `preliminary` result and a year-only date as distinct hazards; if both surface as "evidence is missing", the failure taxonomy cannot tell them apart from a concept the agent simply never looked for, and the Unknown Reason stops being diagnostic. Each planted distractor kind maps to exactly one reason, and that mapping is what the Gate 2 tests assert.

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
- **Citations that resolve but cannot establish the claimed state** — a resource type outside the evidence-bearing boundary cited as evidence, or a fact whose status section 5.2 disqualifies cited as establishing `met` or `not_met`
- Incorrect expression aggregation
- Evidence dated after `assessment_as_of`

The sixth check is distinct from the fifth and is not implied by it. A `MedicationRequest` cited as treatment exposure resolves cleanly: the resource exists, the JSON path is valid, the agent is named correctly, and the date is real. Every other check passes. What fails is that order intent is not exposure, so the citation is not Patient Evidence and the assessment has no evidentiary basis. This is the check the injected-fault demonstration in section 3 turns on, and section 8.3 plants the corresponding hazard.

Verification failure triggers exactly one targeted correction. A second failure yields `unknown` with `verification_failed`. Disagreement between deterministic computation and model interpretation yields `unknown` with `reasoning_conflict`.

The verifier has two distinct roles, served by one implementation at two call sites. Conflating them would make the grounding comparison meaningless.

| Role | Applies to | Effect |
| --- | --- | --- |
| Grading | Both variants: the agent and the one-shot baseline | Scores final outputs offline. Results never flow back into the system under test. |
| Feedback | Full only | Its verdict triggers the single correction inside the agent loop. |

Offline grading runs the same code with the same configuration across both variants. Only the agent receives verifier feedback and a correction opportunity; the baseline is graded by the same standard it was never allowed to consult. This asymmetry is the measured architectural difference, not a confound, and it is stated wherever the comparison is published.

Because the agent's final outputs have passed through one correction, citation validity is reported at three points — the baseline, the agent before correction, and the agent after correction — so the contribution of tool-mediated evidence selection is separable from the contribution of the correction loop.

### 8.2 Failure Separation

Infrastructure Failures — unavailable model endpoint, malformed snapshot, tool exception — are recorded as failures and are never scored as correct uncertainty.

### 8.3 Planted Distractors

Benchmark difficulty comes from deliberately planted evidence hazards rather than clinical subtlety. Scenarios must collectively include all of:

| # | Hazard | Correct Unknown Reason |
| --- | --- | --- |
| 1 | An `entered-in-error` biomarker or stage result | `unusable_status` |
| 2 | A `MedicationRequest` with no corresponding `MedicationAdministration` | `unsupported_evidence_type` |
| 3 | An observation dated after `assessment_as_of` | `missing_evidence` |
| 4 | Two conflicting results for the same concept | `conflicting_evidence` |
| 5 | A date with year-only precision where the criterion requires a finer window | `insufficient_precision` |
| 6 | A `preliminary` result relevant to a threshold comparison | `unusable_status` |
| 7 | A semantically near but non-matching concept, such as ALK expression versus ALK rearrangement | `missing_evidence` |

The right-hand column is a test obligation, not documentation. Gate 2 asserts it per hazard. Two hazards sharing a reason is acceptable where they share a nature — 1 and 6 are both disqualifying statuses, 3 and 7 both leave no qualifying fact — but a hazard resolving to a reason other than the one listed is a defect in either the timeline or the assignment table, and is treated as one.

## 9. Candidate Trials

The candidate set is the frozen trial records of section 4.1, in a fixed authored order. Retrieval is out of scope for this project (section 18), so no ranking is computed, and Retrieval Rank is the position in that authored order — immutable, and never merged with Review Priority.

Every candidate is presented. Review Priority orders assessed trials by Match Conclusion and then Retrieval Rank without overwriting Retrieval Rank.

**The assessed set is the three highest-ranked presented candidates that have an authored Criterion Expression.** Where a candidate in the top three has none, it is reported as `expression_unavailable` at its own rank and the next presented candidate with an expression takes its place. Backfill never reaches past the presented set. Where fewer than three presented candidates have expressions, fewer are assessed and the report says how many and why.

The alternative, assessing strictly the top three and returning two results when one lacks an expression, was rejected as needlessly opaque. Expression coverage is an artifact of this project's authoring budget under ADR 0004, not a property of the trial, so allowing it to shrink the assessed set would report a budget decision as though it were a finding.

The policy keeps the top-20 and top-5 shape it was written against, so the same rules apply unchanged if a larger candidate list ever arrives.

No blended "AI match score" combines candidate order with eligibility reasoning.

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

A thin layer above the Criterion Reasoning Agent, owning trial-level assessment strategy. Every behavior is a configuration flag, default off.

| Flag | Behavior | Measured effect |
| --- | --- | --- |
| `order_criteria` | Assess likely-blocking exclusion criteria first | Time to first blocker |
| `early_termination` | Stop after a blocker is confirmed; mark the remainder `not_assessed` | Token and latency reduction |

Flags are off for correctness measurement and on for cost measurement, so multi-turn behavior appears as its own row rather than as a confound.

Known hazards, which must be measured rather than assumed away:

- `early_termination` forfeits full Criterion Coverage. Skipped criteria are reported as `not_assessed`, never `unknown`.
- `order_criteria` introduces order dependence. Assessment order is deterministic given a fixed configuration and seed.

Evidence Reuse across criteria was specified in earlier versions and is cut: it buys model calls at the cost of a new error-propagation path to measure, and the propagation measurement is the expensive half.

## 12. Architecture

Three deep modules, each hiding substantial complexity behind a small stable interface:

| Module | Interface | Owned complexity |
| --- | --- | --- |
| Patient Timeline | `build(bundle, as_of) -> PatientTimeline` | FHIR validation, supported-resource interpretation, terminology, temporal precision, provenance, tool surface |
| Criterion Agent | `assess(timeline, trial) -> TrialAssessment` | Tool selection, model reasoning, deterministic computation, verification, correction, supervisor strategy, aggregation |
| Evaluation Lab | `run(manifest, variant) -> EvalReport` | Gold derivation, the baseline, metrics, cost accounting, failure analysis |

The application entry point stays thin:

```
match(patient, trials) -> MatchingRun
```

A small pure Matching Policy owns which candidates are presented and which are assessed, including the assessed-set rule of section 9 and its bounded backfill. Unknown Reason assignment under section 8.0 is likewise pure and deterministic, and belongs to the Criterion Agent module rather than to the model. Parser, terminology, and evidence-packet construction are module-internal and have no separate public interface.

ClinicalTrials.gov has a fixture adapter. Model inference has hosted, local, and frozen-replay adapters.

## 13. Core Data Model

**Patient Timeline** — scenario identity; source Bundle hash and normalization version; Assessment Time; demographics and geography; time-ordered facts with code, value, status, interval, and precision; documented medication exposures; provenance references; unsupported-content inventory.

**Trial Record** — stable NCT identity; record identity and source text hash; recruiting status, sites, source URL, update date; conditions and MeSH, interventions, summaries; source-aligned Eligibility Criteria; authored Criterion Expressions with authoring provenance.

**Eligibility Criterion** — version-scoped ID; polarity; source section, ordinal, span, exact text; Criterion Expression and Atomic Propositions; authoring provenance and review status.

**Proposition Assessment** — proposition identity and category; Criterion State; Patient Evidence, Trial Evidence, and Evidence Relations; Unknown Reason; tool calls; deterministic computations; verifier outcome; correction record; non-evidentiary rationale.

**Criterion Assessment** — criterion identity and polarity; complete Proposition Assessments; deterministically aggregated Criterion State and Impact; aggregation trace; coverage status.

**Trial Assessment** — candidate identity and immutable Retrieval Rank; complete Criterion Assessments; blocker, unresolved, and not-assessed counts; Match Conclusion; Review Priority; Evidence Trajectory; operational measurements.

**Matching Run** — timeline, trial-record, and Assessment Time identities; frozen model, prompt, tool, supervisor, and evaluator versions; Candidate Set with assessed and unassessed status; Trial Assessments; Reasoning Trace; warnings; latency, model calls, tokens, cost estimate, hardware profile.

**Eval Case** — immutable versioned inputs; derived expected outputs; partition and scenario family; Scorable and Coverage-Only assessments; evidence equivalence sets; grading rules.

## 14. Trace and Reproducibility

The Reasoning Trace records expression provenance, proposition classification, tool calls with arguments and results, deterministic computations, model metadata, verifier outcomes, correction reason, supervisor decisions, final states, tokens, latency, and configuration versions.

It is a read-only diagnostic artifact, not execution state, an authorization log, or a resumable checkpoint. Frozen traces can be re-graded and replayed offline.

The coordinator-facing Evidence Trajectory is the concise subset explaining which criterion, evidence, tools, and verification steps produced an assessment. It never exposes hidden chain-of-thought or Scenario Manifest content.

Each run records patient and trial hashes, partition, model, prompt and schema, decoding, tool and supervisor configuration, evaluator code version, seed, latency, tokens, estimated cost, and hardware profile.

## 15. Delivery Surface

The delivery surface is **one** self-contained static artifact, publishable as a hosted page and viewable offline without credentials, a server, or any network fetch. It is generated from frozen run artifacts, so it is built last and never becomes a dependency of a reasoning module.

Ordered verdict-first, not in pipeline order. The three sections carrying the engineering claim are the criterion detail, the verifier catch, and the baseline comparison; a reader must reach them before any setup material.

| Order | Content |
| --- | --- |
| 1 | Plain-language summary: one sentence on what the system does, the run's conclusions, and the single worked criterion that demonstrates the claim. Written for a reader with no domain or system vocabulary. |
| 2 | The demonstrative criterion in full: source text, atomic propositions, state, impact, evidence, tool call sequence with arguments and results |
| 3 | Verifier outcome for that criterion, including the rejected citation and the resulting correction |
| 4 | Side-by-side agent and one-shot baseline results on that same criterion |
| 5 | The four candidate trials, with the assessed ones in Review Priority order |
| 6 | Per-trial criterion tables: state, impact, and Unknown Reason for every criterion |
| 7 | The patient timeline with per-fact provenance |
| 8 | Results across the scenario set: the invariant gates as pass or fail, the reported counts beside them, and the two worked failures |
| 9 | Per-assessment latency, model calls, tokens, and cost |
| 10 | Reproducibility header: identities, hashes, frozen configuration versions, and warnings |

Citations link to the cited FHIR JSON path and the exact trial source span. Sections with a collapsed and an expanded state are specified in both; the collapsed state is what a reader lands on and is designed first.

A persistent section index is required. It is wayfinding for a long single document, not application chrome, and it does not reintroduce breadcrumbs, back buttons, in-page tabs, or per-screen headers.

Every scenario with a Matching Run gets a report. At least one report covers a run in which the system fails.

Section 8 is the only run-independent part of the document, and it says so where it sits: a count across the scenario set is a different kind of claim from a fact about the run above it. An earlier version of this specification made it a second artifact for that reason; one page with a labelled section is enough at this scale, and two artifacts for one demonstration cost a reader more than the separation buys. See [ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md).

### 15.1 Constraints

- Self-contained: no network fetch at view time, fonts and assets included. A report that needs the network is not offline-viewable.
- Print styles implemented; the disclaimer appears in print output.
- No blended score, no match percentage, no progress bar, gauge, or star rating.
- Colour and shape encode Criterion Impact, never Criterion State.
- Retrieval Rank and Review Priority are both shown and never merged.
- Trial source text is verbatim, never rewritten, truncated, or paraphrased.
- No Scenario Manifest content and no model chain-of-thought.

## 16. Model Policy

Model inference sits behind an adapter with hosted, local, and frozen-replay implementations. Headline results may come from a hosted small model; the adapter interface, not the model choice, is the engineering claim. Local execution is reported when available.

A deliberately modest model is acceptable and arguably preferable: higher fabrication rates make verifier value larger and more measurable.

Exact model, revision, prompts, schemas, decoding, and hardware are recorded with every run and frozen before the held-out scenarios are assessed. Structured output uses constrained decoding or schema validation with recorded, non-hidden retries. Model licenses and limitations are recorded.

Plain typed Python is the orchestration baseline. LangGraph, multi-agent execution, and fine-tuning are out of scope.

## 17. Authoring Policy

AI assistance is permitted for drafting criterion expressions, synthetic scenario resources, distractor designs, code, tests, and documentation. Every AI-drafted artifact is human-reviewed before freezing, and its authoring provenance and review status are recorded.

AI-generated expected-state labels are prohibited. Using a model to produce the ground truth that scores a model measures agreement, not correctness.

Expected states are instead derived deterministically by code from the hidden Scenario Manifest and the authored Criterion Expression. Because scenario facts are authored, the expected state for a supported proposition is computable rather than a matter of judgment.

Propositions whose semantics cannot be operationalized this way remain visible as Coverage-Only Assessments and are excluded from accuracy counts.

This makes the benchmark a test of evidence retrieval, citation validity, and logic application — not of clinical judgment. The specification states this limitation explicitly rather than implying broader validity.

## 18. Scope Line

Excluded from this MVP: real PHI, live EHRs, MIMIC, HAPI FHIR, full SNOMED CT and UMLS, automatic criterion parsing, unstructured-note reasoning, imaging interpretation, TNM derivation, UCUM unit conversion, line-of-therapy inference, assay-actionability inference, **candidate retrieval of any kind — lexical, dense, or fused — and the trial corpus it would rank**, cross-encoder reranking, PostgreSQL and pgvector, TREC benchmark tracks, manual gold labeling at scale, **inferential statistics: hypothesis tests, confidence intervals, bootstrap resampling, and pre-registered effect sizes**, clinical validation, chat interfaces, external writes, permissions, approval workflows, human-in-the-loop workflows, idempotency, durable execution, MCP, generic agent harnesses, LangGraph, multi-agent orchestration, and fine-tuning.

Progress is governed by acceptance criteria, not a calendar.

## 19. Core and Additive Scope

Not every gate is essential. If time is constrained, cut from the bottom of this list.

**Core** — without these the project does not demonstrate its claim:

- Gate 1 Contracts and fixtures
- Gate 2 Patient Timeline, Timeline Tools, and authored scenarios
- Gate 3 Criterion Agent and Evidence Verifier
- Gate 4 Measurement against the one-shot baseline
- Gate 5 Trace Report, because an unseen result is not a portfolio result

**Additive** — real value, but the project remains complete and honest without them:

- Early Termination, the one supervisor behaviour kept. Fallback: single-turn per-criterion assessment.

**Cut order under schedule pressure:**

1. Early Termination
2. Scenarios from six to four
3. The failure-taxonomy section of the report, keeping the two worked failures

Cutting a stage requires deleting its claims from the report as well. Reduced scope stated plainly is stronger than scope implied but unmeasured.

## 20. Release Gates and Reported Results

Only deterministic invariants are release gates. These are properties the implementation controls, so gating on them is a statement about software correctness:

- Patient and trial reference validity in final output: 100%
- Deterministic aggregation accuracy: 100%
- Verifier catch rate on injected faults: 100%
- Unsupported assessments surviving verification in final output: 0
- Criterion Coverage with Early Termination off: 100%
- Citations dated after `assessment_as_of` in final output: 0
- Infrastructure Failures scored as `unknown`: 0

Every model-behavior measurement is a reported result, not a gate: criterion-state accuracy per state, patient-evidence precision, the pre-correction unsupported-assessment rate, the verification-induced `unknown` rate, and every cost figure. Gating on them would invite optimizing toward a threshold on a sample far too small to carry one.

**The first invariant is structural, and that has a consequence for how it may be used.** Reference validity in final output reaches 100% because the verifier degrades every assessment it cannot verify to `unknown` with reason `verification_failed`. It is a statement about the implementation, not a measurement of model behavior, and it may never be compared against the baseline: a variant with no verifier has no such guarantee, so the comparison would report an architectural difference as a result. Comparisons use the agent *before* correction.

**What the guarantee costs is itself a reported result.** The verification-induced `unknown` rate — propositions the agent committed to before correction and returned as `unknown` after it — is published wherever post-correction validity is published, at equal prominence. A verifier that rejected everything would satisfy every invariant above and produce a worthless system; this number is what distinguishes the two.

**Reported numbers are counts, not estimates.** Every accuracy and grounding figure is published as a raw count and a percentage over a stated denominator, with the number of scenarios, trials, and propositions behind it. No confidence interval, hypothesis test, or effect size is computed: at this sample size an interval would be wider than any difference worth claiming, and computing one would dress a demonstration up as a study. The report says so in the results section rather than leaving a reader to infer it.

**A result that goes the wrong way is published as it stands.** If the agent shows no advantage over the one-shot baseline in citation validity, that is the finding, and the report states it plainly beside what the architecture cost to build.

