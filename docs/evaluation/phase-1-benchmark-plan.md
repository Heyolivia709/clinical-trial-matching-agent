# Phase 1 Benchmark Plan

**Status:** Frozen
**Scope:** Synthetic evidence consistency and software reasoning, not clinical validity

## Evaluation Principles

- Evaluate criterion parsing, candidate retrieval, and criterion reasoning/grounding independently.
- Use deterministic grading against reviewed gold data for all primary metrics and release gates.
- Keep held-out partitions frozen and inaccessible to prompt, model, retrieval, or rule optimization.
- Report state support, category support, confidence intervals, operational cost, and failure cases alongside averages.
- Keep every parsed criterion visible even when it is Coverage-Only or resolves to `unknown`.

## Gold-Labeling Policy

Scenario facts come deterministically from the hidden Scenario Manifest. Criterion-expression and expected-state labels use a written guide, initial annotation, independent second-pass review for held-out data, and adjudication.

The report records reviewer background and pre-adjudication agreement. Without oncology-qualified review, semantic scoring is restricted to explicit, operationalizable criteria. Ambiguous criteria remain visible but become Coverage-Only Assessments or conservative `unknown` results.

Evidence equivalence sets may identify multiple FHIR facts as equally valid. Free-form rationale is not a primary metric.

## Track 1: Criterion Parsing

### Dataset

- 200 source-aligned criteria
- At least 30 distinct NSCLC trials
- 140 development and 60 held-out criteria
- No NCT ID in both partitions
- Representative conjunctions, disjunctions, conditional clauses, temporal rules, numeric thresholds, malformed bullets, and unsupported clauses

### Baselines

- B0: section-heading detection plus bullet or line splitting
- Full: versioned model-assisted expression parsing with source preservation

### Metrics and Gates

| Metric | Gate |
| --- | ---: |
| Source criterion coverage | 100% |
| Inclusion/exclusion polarity accuracy | ≥ 98% |
| Atomic-proposition span F1 | ≥ 90% |
| Exact expression-tree accuracy | ≥ 85% |
| Invented or untraceable source spans | 0 |

## Track 2: Candidate Retrieval

### External Dataset

- TREC Clinical Trials 2021 for development
- TREC Clinical Trials 2022 as held-out external evaluation
- Respect pooled-judgment limitations; unjudged trials are not automatic negatives

### Product Dataset

- 30 Authored Synthetic Scenarios against the frozen NSCLC corpus
- 20 development and 10 held-out scenarios
- Explicit relevant target trials and hard negatives

### Baselines and Variants

- B0: Candidate Filters plus lexical retrieval
- B1: Candidate Filters plus dense retrieval
- B2: trial-level lexical+dense reciprocal-rank fusion
- B3: trial- and criterion-level hybrid retrieval
- Full: B3 plus constrained reranking
- TrialGPT: exact reproduction only when code, data, prompts, and model configuration are actually reproduced; otherwise label the row inspired or reported

### Metrics and Gates

| Metric | Gate |
| --- | ---: |
| Filter-induced loss of known relevant trials | 0 |
| NSCLC Recall@20 | ≥ 90% |
| NSCLC Recall@5 | ≥ 70% |
| Held-out TREC nDCG@10 improvement over lexical B0 | ≥ 5% relative |
| Recall@100 change versus best high-recall baseline | No worse than -2 percentage points |

Also report `P@10`, per-channel recall, fusion gain, reranker gain, and filter loss separately.

## Track 3: Criterion Reasoning and Grounding

### Dataset

- At least 40 patient-trial pairs
- At least 12 distinct trials
- At least 500 labeled Atomic Propositions overall
- Development, validation, and test partitions separated by trial ID and scenario family
- At least 100 held-out Atomic Propositions
- At least 15 held-out examples for each Criterion State
- Largest-to-smallest state-support ratio no greater than 3:1
- Report support by state and Criterion Category

### Baselines

- B0: deterministic structured-field checks; unsupported semantics become `unknown`
- B1: one-shot model over a flattened patient summary and raw criterion text
- Full: Patient Timeline, Criterion Expressions, strategy routing, Evidence Packets, verification, and one bounded correction

### Full-System Ablations

- Replace Patient Timeline with flattened summary
- Remove criterion decomposition
- Remove deterministic reasoning tools
- Remove evidence verification
- Remove the correction/re-plan
- Post-MVP: replace plain Python with LangGraph behind the same interface
- Post-MVP: multi-agent variant under the same resource budget

### Metrics and Gates

| Metric | Gate |
| --- | ---: |
| Criterion Coverage | 100% |
| Deterministic aggregation accuracy | 100% |
| Patient and trial reference validity | 100% |
| Criterion-state macro F1 | ≥ 75% |
| `unknown` recall | ≥ 85% |
| Patient-evidence precision | ≥ 90% |
| Patient-evidence recall | ≥ 80% |
| Unsupported-assessment rate | ≤ 2% |
| Match Conclusion accuracy | ≥ 80% |
| Macro-F1 gain over one-shot B1 | ≥ 5 percentage points |
| Unsupported-assessment reduction versus B1 | ≥ 30% |

Context-selection recall measures whether the agent retrieved gold Patient Evidence before assessment. Report performance by Criterion Category so demographic results cannot mask biomarker, treatment, laboratory, or temporal failures.

## End-to-End Held-Out Suite

Run 10 held-out patient scenarios through the complete top-20 retrieval and top-5 assessment workflow. Treat this as system evaluation, not evidence of broad clinical generalization.

The suite verifies Candidate Set completeness, immutable Retrieval Rank, assessed/unassessed labeling, 100% Criterion Coverage for assessed trials, blocker and unresolved counts, Match Conclusion, provenance validity, snapshot warnings, trace completeness, and operational measurements.

## Evaluator Policy

Primary scoring is deterministic. Criterion states, expression aggregation, Match Conclusions, source validity, evidence overlap, retrieval metrics, and cost never depend on an uncalibrated LLM judge.

An optional LLM judge may later analyze rationale quality or failure themes only after calibration against human ratings. It must report model, version, prompt, agreement, false-pass rate, and false-fail rate. Generator-as-judge results require an independently reported control.

## Reproducibility and Operations

Each evaluation run records patient and trial hashes, dataset partition, parser, terminology, embeddings, reranker, model, prompt/schema, decoding, reasoning configuration, evaluator code, seed, latency, tokens, estimated cost, and hardware profile.

Token and latency budgets are calibrated on development data and frozen before held-out evaluation. There is at most one correction per Atomic Proposition. Hidden SDK or provider retries are prohibited in evaluation runs.

Report bootstrap confidence intervals and representative failures. Infrastructure failures are separate from semantic `unknown` and cannot improve uncertainty metrics.
