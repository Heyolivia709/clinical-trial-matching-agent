# MVP Dependency-Ordered Implementation Sequence

**Status:** Frozen sequence
**Supersedes:** the twelve-gate v1 sequence
**Scheduling rule:** No calendar estimates. Progression depends only on acceptance criteria.

Gate scope classification and the cut order under schedule pressure are defined in [`../specs/phase-1-mvp-specification.md`](../specs/phase-1-mvp-specification.md) section 19.

## Gate 1: Contracts and Fixtures — Core

Implement core types, state semantics, Boolean aggregation, polarity-to-impact mapping, Match Conclusion, and test fixtures. Freeze four source-aligned trial records with human-reviewed Criterion Expressions so later core gates do not depend on additive retrieval and retain two-axis partitioning.

The four trials are selected for coverage, not convenience: together they must exercise all four Criterion Categories and all supported expression forms, and split cleanly into two development and two held-out trials. Four is the minimum that keeps the Gate 6 trial-and-scenario partition intact if Gate 3 is cut; with six scenarios this yields eight development and sixteen held-out scenario-trial pairs.

Types: `PatientTimeline`, `TrialRecord`, `EligibilityCriterion`, `CriterionExpression`, `AtomicProposition`, `PatientEvidence`, `TrialEvidence`, `PropositionAssessment`, `CriterionAssessment`, `TrialAssessment`, `CandidateSet`, `MatchingRun`, `ReasoningTrace`, `ScenarioManifest`, `EvalCase`.

**Exit criteria**

- Deterministic tests for all four Criterion States and for `not_assessed` as a distinct reporting status
- `all_of`, `any_of`, and conditional truth tables pass exhaustively, including all-`not_applicable` cases
- Inclusion and exclusion impact mapping and Match Conclusion derivation pass, including the early-termination rule
- Every model round-trips through JSON without loss of provenance fields
- Four frozen trial fixtures contain source-aligned criteria and reviewed expressions, partitioned two development and two held-out
- The four fixtures collectively cover all four Criterion Categories and all supported expression forms, including at least one conditional expression capable of producing `not_applicable`
- Criteria outside the supported categories are authored as `unsupported` rather than omitted

## Gate 2: Patient Timeline and Timeline Tools — Core

Parse the four evidence-bearing FHIR R4 resource types into the Patient Timeline. Recognize `MedicationRequest` as Unsupported Patient Content. Preserve provenance, status, and Temporal Precision. Implement the five Timeline Tools. Author six synthetic scenarios with hidden manifests and Planted Distractors.

**Exit criteria**

- Six scenarios build correctly and reproducibly from frozen Bundles
- Every timeline fact traces to a FHIR resource type, ID, and JSON path
- `MedicationRequest` is preserved as Unsupported Patient Content and never treated as exposure
- All seven Planted Distractor kinds are present across the scenario set and each is covered by a test asserting it does not produce a confident assessment
- Missing, conflicting, post-`assessment_as_of`, `preliminary`, and `entered-in-error` facts never yield `met` or `not_met`
- Each tool has deterministic tests including empty-result and ambiguous-result paths

## Gate 3: Trial Snapshot and Hybrid Retrieval — Additive

Ingest and freeze 200–500 NSCLC trials. Enforce corpus membership. Implement candidate filters, BM25, dense retrieval, and reciprocal-rank fusion. Author criterion expressions for 10–12 trials after retrieval configuration is frozen.

**Exit criteria**

- Snapshot rebuilds offline from cached payloads with matching hashes
- Corpus membership tests cover study type, recruiting status, normalized NSCLC metadata, and recruiting US sites
- Every source criterion of every authored trial is preserved with exact span and ordinal
- Retrieval returns an immutable top 20 per scenario with per-channel ranks and scores retained
- Candidate filters cause zero loss of known relevant trials, verified per scenario
- BM25-only, dense-only, and RRF configurations each run reproducibly and report Recall@5 and Recall@20
- Authored expressions carry authoring provenance and human-review status; trials lacking expressions report `expression_unavailable`

**Fallback if cut:** the four frozen core trial fixtures from Gate 1, which preserve the two-axis partition, with retrieval declared out of scope in the report.

## Gate 4: Criterion Agent and Evidence Verifier — Core

Implement the per-proposition agent loop, tool selection, structured output, the deterministic Evidence Verifier, exactly one targeted correction, and deterministic aggregation into Criterion Assessments.

**Exit criteria**

- Fabricated resource IDs, altered values, wrong statuses, out-of-range trial spans, mismatched span text, missing evidence relations, and post-`assessment_as_of` citations are all rejected by injected-fault fixtures, with 100% catch rate
- `met` and `not_met` without patient evidence are rejected
- Incorrect expression aggregation is rejected
- At most one correction occurs per proposition; a second failure yields `unknown` with `verification_failed`
- Deterministic and model disagreement yields `unknown` with `reasoning_conflict`
- Infrastructure Failures are recorded separately and never scored as uncertainty
- Every run emits a readable Evidence Trajectory
- An injected-fault trace reproducibly shows verifier rejection and correction; organic catches are committed when observed

## Gate 5: Trial Supervisor — Additive

Implement trial-level assessment strategy: criterion ordering, early termination, and cross-criterion evidence reuse. All three are flags, default off.

**Exit criteria**

- Flags off reproduces Gate 4 results exactly
- `early_termination` marks skipped criteria `not_assessed`, never `unknown`, and adjusts Match Conclusion per specification section 7.2
- Assessment order is deterministic given a fixed configuration and seed
- Reused evidence records its originating criterion ID
- Token, model-call, and latency deltas are measured per flag against the flags-off baseline
- Reuse-induced error propagation is detected and reported separately

**Fallback if cut:** single-turn per-criterion assessment only, with concurrency retained.

## Gate 6: Evaluation and Baselines — Core

Derive gold labels deterministically from Scenario Manifests. Commit the pre-registration. Implement the deterministic baseline, both one-shot baselines, and the core ablation matrix. Publish metrics per the benchmark plan.

**Exit criteria**

- The pre-registration is committed before the first held-out run, and the report cites its commit hash
- Gold expected states are computed by code from manifest and expression, with no model judgment anywhere in grading
- Development and held-out partitions are separated by both trial ID and scenario, and held-out artifacts never inform configuration
- The raw-text and expression-aware one-shot baselines use the same patient evidence boundary, output schema, model family, and cost accounting as Full; their deliberate context differences are reported
- The offline grading verifier scores every variant with identical code and configuration; only Full receives verifier feedback and a correction opportunity
- Citation validity is reported at three points: B2, Full before correction, Full after correction
- Core ablations run: no deterministic tools and no verifier
- Supervisor-only ablations run only if Gate 5 is built: no evidence reuse and early termination
- Every deterministic release gate in benchmark plan Track 1 passes, or the failure is published with analysis
- Accuracy and grounding results carry bootstrap confidence intervals, per-state support, and the pre-registered two-sided test with no minimum threshold; inconclusive results are labeled inconclusive
- Cost is published per criterion assessment beside the value it purchased, including when the ratio is unfavorable
- At least three cases where Full beats the expression-aware one-shot B2 control, and at least two genuine failure cases, are documented with traces
- The falsification condition is evaluated and its outcome published

## Gate 7: Trace Report and Portfolio Demo — Core

Generate the self-contained static Trace Report from frozen runs. Publish the hosted demo and the written results.

**Exit criteria**

- The report renders offline from a frozen trace with no server, credentials, or network access
- All eight demonstration-goal items in specification section 3 are visible within five minutes
- Citations link to the cited FHIR JSON path and the exact trial source span
- Verifier rejection and correction are visible, not merely logged
- Full, expression-aware one-shot, and raw-text one-shot results appear side by side on the same criterion
- Latency, model calls, tokens, and cost are shown per assessment
- Every quantitative claim in the writeup links to a reproducible run artifact
- Clinical limitations, benchmark construction, and the derived-gold methodology are stated explicitly

## Sequencing Constraints

- Gate 1 freezes four trial fixtures and expressions for the core path. Gate 3 freezes retrieval configuration before expanding the authored set to 10–12 trials, so the additional assessed trials are known before their expressions are authored.
- Gate 6 commits the pre-registration before the first held-out run. Nothing in Gate 6 may consult held-out output before that commit exists.
- Gate 7 is built from frozen traces and must not become a dependency of any reasoning module.
- Held-out scenarios and trials stay untouched until Gate 6.

## Out of Scope

Automatic criterion parsing, TREC tracks, PostgreSQL and pgvector, cross-encoder reranking, per-facet retrieval decomposition, HAPI FHIR, LangGraph, multi-agent orchestration, fine-tuning, and clinical validity work. See specification section 18.
