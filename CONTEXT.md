# Clinical Trial Matching

This context describes evidence-grounded comparison of a synthetic or public patient record with public clinical trial criteria for research coordinator review.

## Language

**Eligibility Criterion**:
A source-aligned inclusion or exclusion criterion that preserves the original trial language, ordinal, and provenance. Its internal logic may be represented by a Criterion Expression.
_Avoid_: Atomic proposition, rewritten criterion

**Criterion Category**:
The clinical reasoning category assigned to an Atomic Proposition, such as demographic, disease, biomarker, performance status, prior therapy, temporal, laboratory, or unsupported.
_Avoid_: Criterion polarity, retrieval facet

**Criterion Expression**:
A machine-interpretable representation of the Boolean or conditional semantics within an Eligibility Criterion, composed of Atomic Propositions without replacing the source text.
_Avoid_: Paraphrased criterion, flat checklist

**Parsed Criterion Representation**:
A versioned, derived interpretation of an Eligibility Criterion containing its polarity, Criterion Expression, parser provenance, confidence, and any parsing failure. The original trial text remains authoritative.
_Avoid_: Source criterion, ground truth

**Atomic Proposition**:
The smallest independently assessable clinical statement within a Criterion Expression.
_Avoid_: Eligibility criterion, source bullet

**Trial Corpus Snapshot**:
A versioned collection of public clinical trial records that defines the complete search universe for one matching run.
_Avoid_: Candidate list, live trial list

**Trial**:
A clinical study whose stable public identity is its NCT identifier.
_Avoid_: Trial record, candidate trial

**Trial Record**:
The immutable representation of a Trial captured in one Trial Corpus Snapshot, including its full source payload hash and record-specific parsed artifacts.
_Avoid_: Trial, live study

**Stale Snapshot**:
A Trial Corpus Snapshot whose ClinicalTrials.gov data timestamp is older than the product freshness threshold. Staleness produces a warning but never mutates or invalidates historical Matching Runs.
_Avoid_: Invalid snapshot, outdated result

**Corpus Membership**:
Whether a public trial belongs in a Trial Corpus Snapshot, determined only from study-wide facts such as study type, recruiting status, recruiting-site geography, and normalized disease-area metadata.
_Avoid_: Patient matching, eligibility filtering

**Patient-Specific Matching Fact**:
A patient attribute such as age, sex, biomarker status, disease stage, or treatment history that may affect retrieval or criterion assessment but never Corpus Membership.
_Avoid_: Corpus filter

**Assessment Time**:
The explicit instant at which a matching run evaluates age, current state, and relative clinical time windows.
_Avoid_: Current time, run time

**Clinical Time**:
The effective onset, occurrence, performance, administration, or result time of a clinical fact, distinct from ingestion, storage, or processing time.
_Avoid_: Record timestamp, database time

**Temporal Precision**:
The source-supported granularity of a clinical date or interval. Reasoning must preserve this granularity rather than inventing a more precise instant.
_Avoid_: Normalized timestamp

**Patient Timeline**:
A longitudinal representation of patient facts derived from a FHIR R4 Bundle while preserving clinical time, status, value, code, and provenance to the source resource.
_Avoid_: Patient summary, profile

**Treatment Episode**:
A provenance-preserving representation of documented treatment exposure derived from valid medication administrations or completed procedures under explicit versioned grouping rules.
_Avoid_: Medication order, inferred treatment line

**Biomarker Evidence**:
Structured Patient Evidence for an explicitly tested biomarker result with reviewed concept mapping and sufficient variant, score, assay, specimen, and temporal context for the claimed interpretation.
_Avoid_: Actionability inference, uncovered-panel inference

**Authored Synthetic Scenario**:
A reproducible synthetic patient case created from a Synthea FHIR R4 Bundle plus controlled, standards-conformant FHIR augmentations for benchmark coverage.
_Avoid_: Real patient, untouched Synthea patient

**Scenario Manifest**:
Evaluator-only ground truth describing the authored facts, transformations, and expected assessments for an Authored Synthetic Scenario. It is never available to the matching system.
_Avoid_: Patient input, model context

**Eval Case**:
An immutable benchmark item that binds versioned inputs, expected outputs, dataset partition, and grading rules without exposing hidden ground truth to the matching system.
_Avoid_: Demo case, prompt example

**State Support**:
The number of held-out labeled assessments for each Criterion State, reported to make imbalance and metric reliability visible.
_Avoid_: Overall sample count

**Scorable Assessment**:
A reviewed Criterion Assessment whose expected state can be operationalized from explicit trial language and synthetic patient facts and may therefore contribute to semantic-accuracy metrics.
_Avoid_: Clinically validated assessment

**Coverage-Only Assessment**:
A Criterion Assessment that remains visible for Criterion Coverage but is excluded from semantic-accuracy metrics because authoritative interpretation is unavailable or ambiguous.
_Avoid_: Dropped criterion, negative example

**Patient Evidence**:
A provenance-preserving reference to one or more facts in the Patient Timeline with usable clinical status and time semantics that support, contradict, or qualify a Criterion Assessment.
_Avoid_: Explanation, model rationale

**Evidence Packet**:
A criterion-specific, source-backed selection of Patient Timeline facts supplied to the Criterion Reasoning Agent, expandable only through targeted read-only timeline queries.
_Avoid_: Patient summary, full patient record

**Unsupported Patient Content**:
Patient-record content preserved for provenance but not interpreted as Patient Evidence by the MVP because its structure, status, or temporal semantics are unsupported.
_Avoid_: Missing evidence, ignored data

**Trial Evidence**:
A provenance-preserving reference to the exact source text of an Eligibility Criterion within a versioned ClinicalTrials.gov record.
_Avoid_: Paraphrase, model interpretation

**Evidence Relation**:
The explicit classification of cited Patient Evidence as supporting or contradicting an Atomic Proposition.
_Avoid_: Relevance score

**Unknown Reason**:
A structured explanation for an `unknown` Criterion State, such as missing, conflicting, stale, unsupported, ambiguous, unparsed, verification-failed, or reasoning-conflict evidence.
_Avoid_: Free-form uncertainty

**Infrastructure Failure**:
A matching-run failure caused by unavailable or malformed system dependencies rather than uncertainty in patient or trial evidence. It is never scored as a correct `unknown` state.
_Avoid_: Unknown reason, unresolved criterion

**Rationale**:
Model-generated explanatory text that helps a coordinator understand an assessment but never counts as Patient Evidence or Trial Evidence.
_Avoid_: Evidence, provenance

**Candidate Retrieval**:
The process of finding and ranking potentially relevant trials from a Trial Corpus Snapshot before criterion-level assessment.
_Avoid_: Eligibility screening, trial selection

**Candidate Filter**:
A deterministic, patient-specific comparison that may remove a trial before ranking only when both the patient value and trial constraint are structured and known.
_Avoid_: Semantic filter, inferred exclusion

**Retrieval Signal**:
A patient or trial fact that influences candidate ranking without irreversibly removing a trial from consideration.
_Avoid_: Hard filter, eligibility result

**Patient Retrieval Profile**:
A retrieval-oriented view of the Patient Timeline organized into distinct clinical and administrative facets without replacing the source timeline.
_Avoid_: Patient summary, eligibility profile

**Retrieval Facet**:
A coherent group of Retrieval Signals, such as disease and histology, biomarkers, stage, prior therapies, demographics, or geography.
_Avoid_: Criterion, hard filter

**Normalized Concept**:
A source term linked through a versioned, provenance-preserving reviewed mapping to a canonical concept used for retrieval or deterministic reasoning.
_Avoid_: Model synonym, replacement source code

**Retrieval Expansion**:
An additional query term, including a model-proposed synonym, that may improve Candidate Retrieval but cannot independently establish a Criterion State.
_Avoid_: Terminology mapping, evidence

**Candidate Trial**:
A trial returned by Candidate Retrieval for further review or assessment. Candidate status indicates retrieval relevance, not clinical eligibility.
_Avoid_: Eligible trial, matched trial

**Retrieval Rank**:
The immutable position assigned to a Candidate Trial by Candidate Retrieval, preserved independently from any later criterion assessment.
_Avoid_: Match rank, eligibility rank

**Review Priority**:
A presentation ordering for assessed Candidate Trials based on Match Conclusion and then Retrieval Rank. It never replaces Retrieval Rank.
_Avoid_: Match score, eligibility score

**Unassessed Candidate**:
A Candidate Trial returned by retrieval that has not received full criterion-level assessment and must not be presented as an assessed match.
_Avoid_: Potential match, rejected trial

**Candidate Set**:
The immutable ranked collection returned by Candidate Retrieval, including channel-level provenance and explicit assessed or unassessed status.
_Avoid_: Match results, eligible trials

**Criterion Assessment**:
The evidence-grounded judgment for one Eligibility Criterion, including its Criterion State and cited patient and trial evidence.
_Avoid_: Eligibility decision, clinical decision

**Criterion Reasoning Agent**:
The bounded reasoning process that interprets Atomic Propositions, selects targeted Patient Evidence, chooses an appropriate reasoning strategy, and produces provenance-verified Criterion Assessments.
_Avoid_: General agent harness, eligibility engine

**Criterion Coverage**:
The proportion of parsed inclusion and exclusion criteria represented by a Criterion Assessment, including criteria that resolve to `unknown`.
_Avoid_: Evaluated-only coverage

**Unresolved Criterion**:
An Eligibility Criterion with an `unknown` state because evidence is missing, stale, ambiguous, conflicting, or of an unsupported type.
_Avoid_: Failed criterion, skipped criterion

**Criterion State**:
One of `met`, `not_met`, `unknown`, or `not_applicable`, describing whether the patient evidence supports the proposition expressed by an Eligibility Criterion. The state does not by itself describe the patient's overall trial eligibility.
_Avoid_: Eligibility status, pass/fail

**Met**:
Patient evidence supports the semantic statement expressed by an Eligibility Criterion, regardless of whether the criterion is inclusive or exclusive. For an exclusion criterion, `met` counts against a potential match.
_Avoid_: Eligible, passed

**Not Met**:
Patient evidence contradicts the proposition expressed by an Eligibility Criterion. It is not a synonym for missing evidence.
_Avoid_: Not supported, failed

**Unknown**:
The available patient evidence is missing, stale, ambiguous, or conflicting, so the criterion proposition cannot be determined.
_Avoid_: Not met, not supported

**Not Applicable**:
A conditional Eligibility Criterion does not apply because its explicit antecedent is false. It is not a substitute for missing information.
_Avoid_: Unknown, skipped

**Criterion Polarity**:
The classification of an Eligibility Criterion as inclusion or exclusion. Polarity determines trial-level impact but never changes the truth semantics of its Criterion State.
_Avoid_: Positive result, negative result

**Criterion Impact**:
One of `satisfied`, `blocking`, `unresolved`, or `neutral`, derived deterministically from Criterion State and Criterion Polarity.
_Avoid_: Criterion state, model score

**Match Conclusion**:
One of `potential_match`, `insufficient_information`, or `unlikely_match`, derived deterministically from Criterion Impacts as a screening workflow label rather than a clinical eligibility decision.
_Avoid_: Eligibility decision, enrollment decision

**Trial Assessment**:
The complete set of Criterion Assessments, Criterion Impacts, blocker and unresolved counts, and Match Conclusion for one assessed Candidate Trial.
_Avoid_: Eligibility determination, retrieval result

**Matching Run**:
A reproducible comparison of one synthetic Patient Timeline at an Assessment Time against one Trial Corpus Snapshot under frozen retrieval, parser, reasoning, and model configurations.
_Avoid_: Consultation, clinical screening

**Reasoning Trace**:
An immutable diagnostic account of retrieval, evidence selection, reasoning, verification, recovery, and cost within a Matching Run. It is not workflow state, an authorization log, or a resumable checkpoint.
_Avoid_: Audit log, execution state

**Evidence Trajectory**:
The coordinator-facing subset of a Reasoning Trace that explains which criterion, patient evidence, and verification steps produced an assessment.
_Avoid_: Raw trace, chain of thought

**Coordinator Review**:
The research coordinator's inspection of Candidate Trials, Criterion Assessments, evidence, blockers, and unresolved criteria without delegating a clinical or enrollment decision to the system.
_Avoid_: Human approval, clinical validation
