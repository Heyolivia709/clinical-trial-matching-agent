# Clinical Trial Matching

This context describes evidence-grounded comparison of an authored synthetic patient record with public clinical trial criteria, for research coordinator review. Clinical trial matching is the carrier domain; agent engineering is the subject.

Terms removed in the v2 rescope — Parsed Criterion Representation, Treatment Episode, Retrieval Facet, Retrieval Expansion as a terminology concept — are superseded by the entries below.

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
A versioned, immutable collection of public clinical trial records that defines the complete search universe for one matching run. Deliberately larger than the assessed subset so that retrieval is non-trivial.
_Avoid_: Candidate list, live trial list

**Trial Record**:
The immutable representation of a Trial captured in one Trial Corpus Snapshot, including its full source payload hash and record-specific authored artifacts.
_Avoid_: Trial, live study

**Corpus Membership**:
Whether a public trial belongs in a Trial Corpus Snapshot, determined only from study-wide facts such as study type, recruiting status, recruiting-site geography, and normalized disease-area metadata.
_Avoid_: Patient matching, eligibility filtering

**Stale Snapshot**:
A Trial Corpus Snapshot whose ClinicalTrials.gov data timestamp is older than the freshness threshold. Staleness produces a warning but never mutates or invalidates historical Matching Runs.
_Avoid_: Invalid snapshot, outdated result

**Patient-Specific Matching Fact**:
A patient attribute such as age, sex, biomarker status, disease stage, or treatment history that may affect retrieval or criterion assessment but never Corpus Membership.
_Avoid_: Corpus filter

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
A source term linked through a versioned, provenance-preserving reviewed mapping to a canonical concept used for retrieval or deterministic reasoning.
_Avoid_: Model synonym, replacement source code

**Authored Synthetic Scenario**:
A reproducible synthetic patient case created from a Synthea FHIR R4 Bundle plus controlled, standards-conformant FHIR augmentations for benchmark coverage.
_Avoid_: Real patient, untouched Synthea patient

**Scenario Manifest**:
Evaluator-only ground truth describing the authored facts, transformations, Planted Distractors, and expected assessments for an Authored Synthetic Scenario. It is never available to the matching system.
_Avoid_: Patient input, model context

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

**Component Control**:
A baseline that shares the full system's evidence boundary but lacks one architectural component, isolating that component's contribution. The expression-aware one-shot baseline is the primary component control; the raw-text one-shot baseline measures end-to-end improvement instead. A shared boundary is not shared context: the control is handed the whole Patient Timeline while the full agent sees only its tool results, so the full agent is the information-disadvantaged arm.
_Avoid_: Ablation, end-to-end baseline

**Release Gate**:
A deterministic invariant the implementation controls, reported as pass or fail. Model-behavior statistics are never release gates, because gating a statistic invites optimizing toward its threshold on data reserved from optimization.
_Avoid_: Target metric, success threshold

**Pre-Registration**:
The protocol fixing metrics, comparison units, per-variant prompt contents, statistical procedure, precision, cost-value pairing, and falsification condition, committed before the first held-out run and cited by commit hash in the published report. Precision is stated as a procedure recomputed from development data, not as a number asserted in advance.
_Avoid_: Evaluation plan, methodology section

**Falsification Condition**:
The result, declared in advance, that would show the project's central claim to be unsupported. Its outcome is published as the headline regardless of direction.
_Avoid_: Risk, limitation

**Injected Fault**:
A deliberately corrupted assessment used to prove the Evidence Verifier catches fabricated or altered citations, independent of whether the model happens to produce such errors organically.
_Avoid_: Bug, regression case

**Rationale**:
Model-generated explanatory text that helps a coordinator understand an assessment but never counts as Patient Evidence or Trial Evidence.
_Avoid_: Evidence, provenance

### Retrieval

**Candidate Retrieval**:
The process of finding and ranking potentially relevant trials from a Trial Corpus Snapshot before criterion-level assessment.
_Avoid_: Eligibility screening, trial selection

**Patient Retrieval Profile**:
A retrieval-oriented view of the Patient Timeline covering disease, biomarkers, stage, prior therapy, demographics, and geography, without replacing the source timeline. Per-facet query decomposition is out of scope.
_Avoid_: Patient summary, eligibility profile

**Candidate Filter**:
A deterministic, patient-specific comparison that may remove a trial before ranking only when both the patient value and the trial constraint are structured and known.
_Avoid_: Semantic filter, inferred exclusion

**Retrieval Signal**:
A patient or trial fact that influences candidate ranking without irreversibly removing a trial from consideration.
_Avoid_: Hard filter, eligibility result

**Candidate Trial**:
A trial returned by Candidate Retrieval for further review or assessment. Candidate status indicates retrieval relevance, not clinical eligibility.
_Avoid_: Eligible trial, matched trial

**Candidate Set**:
The immutable ranked collection returned by Candidate Retrieval, including channel-level provenance and explicit assessed or unassessed status.
_Avoid_: Match results, eligible trials

**Retrieval Rank**:
The immutable position assigned to a Candidate Trial by Candidate Retrieval, preserved independently from any later criterion assessment.
_Avoid_: Match rank, eligibility rank

**Review Priority**:
A presentation ordering for assessed Candidate Trials based on Match Conclusion and then Retrieval Rank. It never replaces Retrieval Rank.
_Avoid_: Match score, eligibility score

**Assessed Set**:
The three highest-ranked presented Candidate Trials that have an Authored Criterion Expression. A presented candidate without one is reported as `expression_unavailable` at its own Retrieval Rank and the next presented candidate takes its place; backfill never reaches past the presented top five. Expression coverage is an artifact of the authoring budget, not a property of a trial, so it never silently shrinks the set.
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
The strategy layer above the Criterion Reasoning Agent that owns criterion ordering, Early Termination, and Evidence Reuse within one trial.
_Avoid_: Orchestrator framework, multi-agent coordinator

**Early Termination**:
A supervisor budget that stops assessment after a blocker is confirmed and marks the remaining criteria `not_assessed`. It trades Criterion Coverage for measured token and latency reduction.
_Avoid_: Short circuit as a default, criterion skipping

**Evidence Reuse**:
Reuse of already-verified Patient Evidence across criteria within the same trial, carrying the originating criterion ID. Reuse-induced error propagation is measured, not assumed absent.
_Avoid_: Memory, cache, cross-patient state

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
The self-contained static artifact generated from one frozen Matching Run, viewable offline with no server, credentials, or network fetch. It shows the agent trace rather than a clinical report, is ordered verdict-first rather than in pipeline order, and is built last from frozen traces. Scoped to a single run: benchmark statistics belong to the Evaluation Report.
_Avoid_: Web app, dashboard, coordinator workflow, benchmark summary

**Evaluation Report**:
The separate self-contained static artifact scoped to the benchmark rather than to any run, carrying invariant gates and reported results in distinct tables, the paired cost-value table, the pre-registered comparison, and the failure taxonomy. It is never a section of a Trace Report, because a corpus-scoped statistic and a run-scoped fact are different kinds of claim.
_Avoid_: Trace report section, results appendix

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

**Resampling Cluster**:
One scenario-trial pair. The unit the bootstrap resamples, because propositions within a pair share a patient, a trial, and a single agent run. Interval width is governed by the number of clusters, not by the number of Graded Observations inside them, so adding criteria to a trial does not buy precision.
_Avoid_: Sample size, n

**State Support**:
The number of labeled assessments for each Criterion State in an evaluation partition.
_Avoid_: Overall sample count

**Coordinator Review**:
The research coordinator's inspection of Candidate Trials, Criterion Assessments, evidence, blockers, and unresolved criteria without delegating a clinical or enrollment decision to the system.
_Avoid_: Human approval, clinical validation
