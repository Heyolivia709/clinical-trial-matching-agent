# Clinical Trial Matching

This context describes evidence-grounded comparison of an authored synthetic patient record with public clinical trial criteria, for research coordinator review. Clinical trial matching is the carrier domain; agent engineering is the subject.

Terms removed in the v2 rescope — Parsed Criterion Representation, Treatment Episode, Retrieval Facet, Retrieval Expansion as a terminology concept — are superseded by the entries below. Terms removed with the v7 scope cut — Candidate Retrieval, Patient Retrieval Profile, Candidate Filter, Retrieval Signal, Corpus Membership, Patient-Specific Matching Fact, Pre-Registration, Falsification Condition, Resampling Cluster, Evidence Reuse, Component Control, Evaluation Report — name work this project does not do; see ADR 0014.

This glossary binds identifiers as well as prose. Types, fields, and enum members in `src/` use these terms, and the `_Avoid_` lists stay out of the codebase. When a name in code and a name here disagree, one of them is wrong.

## Language

### Criteria

**Eligibility Criterion**:
A source-aligned inclusion or exclusion criterion that preserves the original trial language, ordinal, and provenance. Its internal logic may be represented by a Criterion Expression.
_Avoid_: Atomic proposition, rewritten criterion

**Criterion Expression**:
A machine-interpretable representation of the Boolean or conditional semantics within an Eligibility Criterion, composed of Atomic Propositions without replacing the source text.
_Avoid_: Paraphrased criterion, flat checklist

**Authored Criterion Expression**:
A versioned, human-reviewed Criterion Expression with recorded authoring provenance.
_Avoid_: Parsed criterion, ground truth, model output

**Atomic Proposition**:
The smallest independently assessable clinical statement within a Criterion Expression.
_Avoid_: Eligibility criterion, source bullet

**Criterion Category**:
The clinical reasoning category assigned to an Atomic Proposition: `demographic`, `disease`, `biomarker`, `prior_therapy`, `performance_status`, or `unsupported`. `unsupported` is a value rather than an absence of one, so a proposition outside the supported set never acquires a misleading category.
_Avoid_: Criterion polarity, retrieval facet

**Criterion Polarity**:
The classification of an Eligibility Criterion as inclusion or exclusion. Polarity determines trial-level impact but never changes the truth semantics of its Criterion State.
_Avoid_: Positive result, negative result

### Trials and Corpus

**Trial**:
A clinical study whose stable public identity is its NCT identifier.
_Avoid_: Trial record, candidate trial

**Trial Corpus Snapshot**:
The versioned, immutable set of public trial records one matching run compares against — four of them, captured once and frozen. Retrieval over a larger corpus is out of scope, so this is the candidate list rather than a search universe.
_Avoid_: Live trial list, search index

**Trial Record**:
The immutable representation of a Trial captured in one Trial Corpus Snapshot, including the hash of the eligibility text it was reviewed against and its record-specific authored artifacts.
_Avoid_: Trial, live study

**Stale Snapshot**:
A Trial Corpus Snapshot whose ClinicalTrials.gov data timestamp is older than the freshness threshold. Staleness produces a warning but never mutates or invalidates historical Matching Runs.
_Avoid_: Invalid snapshot, outdated result

### Time

**Assessment Time**:
The explicit instant at which a matching run evaluates age, current state, and relative clinical time windows.
_Avoid_: Current time, run time

**Clinical Time**:
The effective onset, occurrence, or administration time of a clinical fact, distinct from ingestion, storage, or processing time.
_Avoid_: Record timestamp, database time

**Temporal Precision**:
The source-supported granularity of a clinical date or interval. Reasoning must preserve this granularity rather than inventing a more precise instant.
_Avoid_: Normalized timestamp

**Prospective Anchor**:
An anchor a criterion names that does not exist at screening time, such as the first dose of study drug or randomization. It cannot be resolved from the patient record because the event has not happened.
_Avoid_: Assessment time, index date

**Anchor Substitution**:
An explicit, authored, reviewed replacement of a Prospective Anchor by Assessment Time, recording the source phrase and the rationale, and displayed beside the criterion wherever the assessment appears. It is a screening-time proxy declared once at authoring, never a runtime inference and never chosen by the model. Without a declared substitution the proposition is `unknown` with `ambiguous_criterion`.
_Avoid_: Silent re-anchoring, default to now

### Patient

**Patient Timeline**:
A longitudinal representation of patient facts derived from a FHIR R4 Bundle while preserving clinical time, status, value, code, and provenance to the source resource.
_Avoid_: Patient summary, profile

**Medication Exposure**:
A provenance-preserving representation of documented treatment exposure derived from valid `MedicationAdministration` resources. Regimen grouping, line-of-therapy derivation, and treatment-failure inference are out of scope.
_Avoid_: Medication order, treatment line, inferred therapy

**Biomarker Evidence**:
Structured Patient Evidence for an explicitly tested biomarker result with reviewed concept mapping and sufficient variant, score, and temporal context for the claimed interpretation.
_Avoid_: Actionability inference, uncovered-panel inference

**Unsupported Patient Content**:
Patient-record content preserved for provenance but not interpreted as Patient Evidence, because its structure, status, or temporal semantics are unsupported. `MedicationRequest` is unsupported content, because order intent is not exposure.
_Avoid_: Missing evidence, ignored data

**Normalized Concept**:
A source term linked through a versioned, provenance-preserving reviewed mapping to a canonical concept the Timeline Tools query by.
_Avoid_: Model synonym, replacement source code

**Authored Synthetic Scenario**:
A reproducible synthetic patient case: one frozen FHIR R4 Bundle with controlled, standards-conformant content for benchmark coverage, plus the Assessment Time it is screened at. Six of them, four development and two held out.
_Avoid_: Real patient, untouched Synthea patient

**Scenario Manifest**:
Evaluator-only ground truth describing the authored facts, the Planted Distractors, and the design intent of an Authored Synthetic Scenario. It carries no expected Criterion State: those are derived by code from these facts and the Authored Criterion Expression. It is never available to the matching system.
_Avoid_: Patient input, model context, expected assessments

**Planted Distractor**:
A deliberately authored evidence hazard — an error-status result, an order without an administration, a post-assessment date, a conflicting value, insufficient date precision, a preliminary result, or a near-miss concept — that supplies benchmark difficulty in place of clinical subtlety.
_Avoid_: Noise, data quality issue

### Evidence

**Patient Evidence**:
A provenance-preserving reference to one or more facts in the Patient Timeline with usable clinical status and time semantics that support, contradict, or qualify a Criterion Assessment.
_Avoid_: Explanation, model rationale

**Trial Evidence**:
A provenance-preserving reference to the exact source text of an Eligibility Criterion within a versioned ClinicalTrials.gov record.
_Avoid_: Paraphrase, model interpretation

**Evidence Relation**:
The explicit classification of cited Patient Evidence as supporting or contradicting an Atomic Proposition.
_Avoid_: Relevance score

**Evidence Verifier**:
The deterministic check that rejects nonexistent references, altered values, invalid spans, missing evidence relations, incorrect aggregation, unsupported states, post-assessment citations, and citations that resolve cleanly but cannot establish the claimed state. One implementation serves two roles: offline grading of every variant, and runtime feedback inside the full agent loop only.
_Avoid_: Model self-check, confidence filter

**Offline Grading**:
The verifier role that scores the final outputs of every variant with identical code and configuration, never flowing results back into the system under test. Distinct from the runtime feedback role, which only the full agent receives.
_Avoid_: Self-evaluation, verifier loop

**One-Shot Baseline**:
The single control variant: the criterion, its authored expression, and the entire Patient Timeline in one prompt. A shared evidence boundary is not shared context — the baseline is handed the whole timeline while the agent sees only its tool results, so the agent is the information-disadvantaged arm and any advantage it shows comes from grounding discipline rather than access.
_Avoid_: End-to-end baseline, gold standard

**Release Gate**:
A deterministic invariant the implementation controls, reported as pass or fail. Model-behavior statistics are never release gates, because gating a statistic invites optimizing toward its threshold on data reserved from optimization.
_Avoid_: Target metric, success threshold

**Injected Fault**:
A deliberately corrupted assessment used to prove the Evidence Verifier catches fabricated or altered citations, independent of whether the model happens to produce such errors organically.
_Avoid_: Bug, regression case

**Rationale**:
Model-generated explanatory text that helps a coordinator understand an assessment but never counts as Patient Evidence or Trial Evidence.
_Avoid_: Evidence, provenance

### Candidates

**Candidate Trial**:
A trial in the candidate set, presented for review or assessment. Candidate status indicates nothing about clinical eligibility.
_Avoid_: Eligible trial, matched trial

**Candidate Set**:
The immutable ordered collection of Candidate Trials for one run, each carrying explicit retained, presented, or assessed status.
_Avoid_: Match results, eligible trials

**Retrieval Rank**:
The immutable position of a Candidate Trial in the authored candidate order, preserved independently from any later criterion assessment. It keeps its name because the Matching Policy is written against a ranked list and would take one unchanged.
_Avoid_: Match rank, eligibility rank

**Review Priority**:
A presentation ordering for assessed Candidate Trials based on Match Conclusion and then Retrieval Rank. It never replaces Retrieval Rank.
_Avoid_: Match score, eligibility score

**Assessed Set**:
The three highest-ranked presented Candidate Trials that have an Authored Criterion Expression. A presented candidate without one is reported as `expression_unavailable` at its own Retrieval Rank and the next presented candidate takes its place; backfill never reaches past the presented candidates. Expression coverage is an artifact of the authoring budget, not a property of a trial, so it never silently shrinks the set.
_Avoid_: Top three, eligible set

**Unassessed Candidate**:
A Candidate Trial returned by retrieval that has not received criterion-level assessment and must not be presented as an assessed match.
_Avoid_: Potential match, rejected trial

### Agent

**Criterion Reasoning Agent**:
The bounded reasoning process that interprets Atomic Propositions, selects Timeline Tools, and produces provenance-verified Proposition Assessments.
_Avoid_: General agent harness, eligibility engine

**Timeline Tool**:
A typed, read-only Python function the agent may call to query the Patient Timeline or perform a deterministic comparison. Tool calls, arguments, and results are recorded in the Reasoning Trace.
_Avoid_: Plugin, skill, retrieval call

**Trial Supervisor**:
The thin layer above the Criterion Reasoning Agent that owns criterion ordering and Early Termination within one trial.
_Avoid_: Orchestrator framework, multi-agent coordinator

**Early Termination**:
A supervisor budget that stops assessment after a blocker is confirmed and marks the remaining criteria `not_assessed`. It trades Criterion Coverage for measured token and latency reduction.
_Avoid_: Short circuit as a default, criterion skipping

**Correction**:
A targeted revision requested after the Evidence Verifier rejects a Proposition Assessment.
_Avoid_: Retry loop, self-healing

### Assessment

**Proposition Assessment**:
The evidence-grounded judgment for one Atomic Proposition, including its Criterion State, cited patient and trial evidence, tool calls, and verifier outcome.
_Avoid_: Criterion Assessment, eligibility decision

**Criterion Assessment**:
The deterministically aggregated judgment for one Eligibility Criterion, composed from its Proposition Assessments through its Criterion Expression.
_Avoid_: Eligibility decision, clinical decision

**Criterion State**:
One of `met`, `not_met`, `unknown`, or `not_applicable`, describing whether patient evidence supports an Atomic Proposition or, after deterministic aggregation, an Eligibility Criterion. The state does not by itself describe overall trial eligibility.
_Avoid_: Eligibility status, pass/fail

**Met**:
Patient evidence supports the semantic statement expressed by an Eligibility Criterion, regardless of whether the criterion is inclusive or exclusive. For an exclusion criterion, `met` counts against a potential match.
_Avoid_: Eligible, passed

**Not Met**:
Patient evidence contradicts the proposition expressed by an Eligibility Criterion. It is not a synonym for missing evidence.
_Avoid_: Not supported, failed

**Unknown**:
The available patient evidence is missing, unusable by status, insufficiently precise, stale, conflicting, ambiguous, unsupported, or unverifiable, so the criterion proposition cannot be determined.
_Avoid_: Not met, not supported

**Not Applicable**:
A conditional Eligibility Criterion does not apply because its explicit antecedent is false. It is not a substitute for missing information.
_Avoid_: Unknown, skipped

**Not Assessed**:
A reporting status, not a Criterion State, marking a criterion the Trial Supervisor deliberately skipped under Early Termination. It must never be merged into `unknown`.
_Avoid_: Unknown, skipped criterion, unresolved

**Unknown Reason**:
A structured explanation for an `unknown` Criterion State, one of `missing_evidence`, `unusable_status`, `insufficient_precision`, `conflicting_evidence`, `stale_evidence`, `ambiguous_criterion`, `unsupported_evidence_type`, `expression_unavailable`, `verification_failed`, or `reasoning_conflict`. Assigned by deterministic code from a decision table, never chosen by the model. A disqualified fact, an imprecise date, and no fact at all are three different diagnoses and never share a reason.
_Avoid_: Free-form uncertainty

**Unresolved Criterion**:
An Eligibility Criterion whose Criterion State is `unknown`, for any of the Unknown Reasons. Distinct from Not Assessed, which was never attempted.
_Avoid_: Failed criterion, skipped criterion

**Criterion Impact**:
One of `satisfied`, `blocking`, `unresolved`, or `neutral`, derived deterministically from Criterion State and Criterion Polarity.
_Avoid_: Criterion state, model score

**Match Conclusion**:
One of `potential_match`, `insufficient_information`, or `unlikely_match`, derived deterministically from Criterion Impacts as a screening workflow label rather than a clinical eligibility decision.
_Avoid_: Eligibility decision, enrollment decision

**Trial Assessment**:
The complete set of Criterion Assessments, Criterion Impacts, blocker, unresolved, and not-assessed counts, and Match Conclusion for one assessed Candidate Trial.
_Avoid_: Eligibility determination, retrieval result

**Criterion Coverage**:
The proportion of authored inclusion and exclusion criteria represented by a Criterion Assessment, including criteria that resolve to `unknown`. Reported per supervisor configuration, since Early Termination reduces it by design.
_Avoid_: Evaluated-only coverage

**Verification-Induced Unknown**:
A proposition the full agent committed to before correction and returned as `unknown` after it, because the Evidence Verifier could not verify the citation. Its rate is what final-output citation validity costs, and is published wherever that validity is published. A verifier that rejected everything would report perfect validity and be worthless; this quantity is what separates the two.
_Avoid_: Verifier catch, model uncertainty

**Infrastructure Failure**:
A matching-run failure caused by unavailable or malformed system dependencies rather than uncertainty in patient or trial evidence. It is never scored as a correct `unknown` state.
_Avoid_: Unknown reason, unresolved criterion

### Runs, Evaluation, and Reporting

**Matching Run**:
A reproducible comparison of one synthetic Patient Timeline at an Assessment Time against one Trial Corpus Snapshot under frozen retrieval, expression, tool, supervisor, and model configurations.
_Avoid_: Consultation, clinical screening

**Reasoning Trace**:
An immutable diagnostic account of retrieval, tool calls, reasoning, verification, correction, supervisor decisions, and cost within a Matching Run. It is not workflow state, an authorization log, or a resumable checkpoint.
_Avoid_: Audit log, execution state

**Evidence Trajectory**:
The coordinator-facing subset of a Reasoning Trace that explains which criterion, patient evidence, tools, and verification steps produced an assessment.
_Avoid_: Raw trace, chain of thought

**Trace Report**:
The self-contained static artifact generated from one frozen Matching Run, viewable offline with no server, credentials, or network fetch. It shows the agent trace rather than a clinical report, is ordered verdict-first rather than in pipeline order, and is built last from frozen traces. Counts across the scenario set sit in one labelled section, because a number over the whole set is a different kind of claim from a fact about the run above it.
_Avoid_: Web app, dashboard, coordinator workflow

**Eval Case**:
An immutable benchmark item that binds versioned inputs, derived expected outputs, dataset partition, and grading rules without exposing hidden ground truth to the matching system.
_Avoid_: Demo case, prompt example

**Derived Gold Label**:
An expected Criterion State derived from the Scenario Manifest and the Authored Criterion Expression.
_Avoid_: Annotation, human label, LLM judgment

**Scorable Assessment**:
A Criterion Assessment whose expected state can be operationalized from the authored expression and scenario facts, and which may therefore contribute to accuracy metrics.
_Avoid_: Clinically validated assessment

**Coverage-Only Assessment**:
A Criterion Assessment that remains visible for Criterion Coverage but is excluded from accuracy metrics because an authoritative expected state cannot be derived.
_Avoid_: Dropped criterion, negative example

**Graded Observation**:
One Atomic Proposition evaluated against one Authored Synthetic Scenario. The unit of accuracy metrics, and distinct from the proposition itself, which is a property of a trial and carries no patient. Not to be confused with a FHIR `Observation`.
_Avoid_: Proposition, sample, data point

**State Support**:
The number of labeled assessments for each Criterion State. Reported per state, because an aggregate over four states with a dozen observations each hides which state the system is bad at.
_Avoid_: Overall sample count

**Coordinator Review**:
The research coordinator's inspection of Candidate Trials, Criterion Assessments, evidence, blockers, and unresolved criteria without delegating a clinical or enrollment decision to the system.
_Avoid_: Human approval, clinical validation
