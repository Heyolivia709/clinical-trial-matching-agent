# Project Instructions

## Language

All repository content for this project must be written in English. This includes documentation, source code, identifiers, comments, docstrings, tests, fixtures, configuration descriptions, commit-oriented artifacts, and user-facing text.

Do not add Chinese or bilingual repository content unless the user explicitly revokes this rule for a specific artifact.

## Product Boundary

This project is a research-coordinator decision-support prototype for matching synthetic or public patient information to clinical trials. It must not claim to diagnose, determine clinical eligibility, enroll patients automatically, or demonstrate clinical effectiveness.

Before changing MVP behavior, read `CONTEXT.md` and `docs/specs/phase-1-mvp-specification.md`. The specification is the source of truth and is frozen in stages: claims and discipline are settled, while the sections describing behaviour no implementation has yet exercised re-freeze at the exit of Gate 2. Record scope changes explicitly rather than introducing them implicitly during implementation.

## Subject of the Project

Clinical trial matching is the carrier domain. Agent engineering is the subject: tool selection, controlled reasoning, deterministic routing, evidence verification, bounded failure recovery, multi-turn cost control, and measured evaluation.

When a change would deepen the clinical domain at the expense of agent-engineering signal, prefer the agent-engineering signal or record the trade explicitly.

Do not turn the project into a chat UI, an ordinary retrieval-augmented generation demo, a generic agent harness, a skill collection, a clinical text parser, an action-execution system, a permission workflow, or an external write-operation system.

## Non-Negotiable Invariants

- Models never perform Boolean aggregation, arithmetic, unit comparison, or date arithmetic. Those route to deterministic code.
- `met` and `not_met` always cite verified patient evidence and exact trial source text.
- `unknown` always carries a structured reason.
- `not_assessed` is a reporting status for deliberately skipped criteria and must never be merged into `unknown`.
- Infrastructure failures are never scored as correct uncertainty.
- No criterion is silently dropped from output.
- No blended score combines retrieval relevance with eligibility reasoning.

## Evaluation Discipline

Gold expected states are derived deterministically from the hidden Scenario Manifest and the authored Criterion Expression. Never generate expected-state labels with a model, and never let an LLM judge produce a primary metric.

Held-out scenarios and trials stay frozen and must not influence prompts, models, retrieval, tools, or supervisor configuration.

Only deterministic invariants are release gates. Never add a threshold gate on a model-behavior statistic; report it with a confidence interval instead. The accuracy comparison against the expression-aware control is a pre-registered two-sided test with no minimum effect size, and null results are published as results.

The verifier has two roles that must not be conflated: offline grading of every variant with identical configuration, and runtime feedback inside the full agent loop only.

Report sample size, per-state support, and confidence intervals with every accuracy number. Small-sample results are stated as such. Publish cost beside the value it purchased, including when the ratio is unfavorable.

## AI-Assisted Authoring

AI assistance is permitted for drafting criterion expressions, synthetic scenario resources, distractor designs, corpus normalization, code, tests, and documentation. Every AI-drafted artifact must be human-reviewed before freezing, with authoring provenance and review status recorded.

## Engineering Conventions

Anything a tool can check lives in `pyproject.toml` and CI, not here. This section is only for what a linter cannot see. If a rule below becomes mechanically checkable, move it into configuration and delete it from this file.

**Toolchain.** Python 3.12, uv for dependencies, ruff for lint and format, pyright in strict mode, pytest. CI runs all four on every pull request. Add a dependency only with a reason recorded in the pull request; the specification names several things this project deliberately does not use.

**Layout.** `src/ctma/`, one package per deep module in specification section 12.

| Package | Owns | Gate |
| --- | --- | --- |
| `domain` | Core types, Criterion State semantics, aggregation, impact mapping | 1 |
| `timeline` | Patient Timeline and the five Timeline Tools | 2 |
| `retrieval` | Corpus, filters, BM25, embeddings, fusion | 3 |
| `agent` | Tool selection, verification, correction | 4 |
| `supervisor` | Flag-gated multi-turn strategy | 5 |
| `evaluation` | Gold derivation, baselines, ablations, metrics | 6 |
| `report` | Trace Report and Evaluation Report generation | 7 |
| `adapters` | ClinicalTrials.gov, model inference, retrieval index | as needed |
| `policy.py` | The pure Matching Policy: top-20, top-5, assessed set, Review Priority | 1 |
| `match.py` | The thin entry point | 1 |

Layering is enforced by `tests/test_architecture.py`. Two consequences worth stating in words: nothing may import `report`, because it is generated from frozen artifacts and must never become a dependency of a reasoning module; and nothing may import `evaluation`, which is the only package permitted to read a Scenario Manifest. That import rule is what keeps the manifest out of the matching system — not care, not review.

Parser, terminology, evidence-packet construction, and index internals are module-private. They have no public interface and no test that imports them directly.

**Types.** Pydantic v2, frozen. Immutability is a requirement of the design rather than a preference: snapshots, expressions, retrieval ranks, and runs are all specified as immutable, and a Gate 1 exit criterion is that every model round-trips through JSON without losing a provenance field. Pydantic covers that and the schema validation of model output with one set of definitions.

**Make illegal states unrepresentable, in preference to testing for them.** An Infrastructure Failure must never be scored as `unknown`, and that is a release gate. The cheapest way to hold it is a tool return type that has no `unknown` variant, so the mistake cannot be written. Prefer this shape of guarantee wherever a release gate can be turned into a type. Do not catch a broad exception and degrade it to a Criterion State.

**Names come from `CONTEXT.md`.** It is the project glossary, so it binds identifiers too. Use its terms for types, fields, and enum members, and keep its `_Avoid_` list out of the codebase entirely. When a name in code and a name in the glossary drift apart, one of the two is wrong and it is usually the code.

**Tests.** `tests/` mirrors `src/ctma/`. Determinism is the default: seed anything sampled, freeze any clock, and never let a test depend on a live network or a live model. Fixtures that a gate freezes live under `fixtures/`, versioned, and are read as data rather than constructed in test code.

## Implementation Order

Implementation is acceptance-criteria-driven with no calendar plan. Gate scope is classified as core or additive in specification section 19; cut from the bottom of that list under schedule pressure, and delete the corresponding claims from the report when a stage is cut.

Gates 8 and above are post-MVP and defined in `docs/plans/post-mvp-implementation-sequence.md`. They start only after Gate 7 publishes, add no Criterion State, Unknown Reason, truth table, or reporting status, and never reopen a held-out partition. A component enters that sequence only if it answers a question the specification already owes an answer to; rejected candidates are recorded in an ADR or in the sequence's rejected list rather than dropped silently.

The trace report is generated from frozen traces and is built last. It must never become a dependency of any reasoning module.

## Agent skills

### Issue tracker

Issues live as GitHub issues in `Heyolivia709/clinical-trial-matching-agent`, operated through the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See `docs/agents/domain.md`.
