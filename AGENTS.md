# Project Instructions

## Language

All repository content for this project must be written in English. This includes documentation, source code, identifiers, comments, docstrings, tests, fixtures, configuration descriptions, commit-oriented artifacts, and user-facing text.

Do not add Chinese or bilingual repository content unless the user explicitly revokes this rule for a specific artifact.

## Product Boundary

This project is a research-coordinator decision-support prototype for matching synthetic or public patient information to clinical trials. It must not claim to diagnose, determine clinical eligibility, enroll patients automatically, or demonstrate clinical effectiveness.

Before changing MVP behavior, read `CONTEXT.md` and `docs/specs/phase-1-mvp-specification.md`. The specification is frozen as the source of truth. Record scope changes explicitly rather than introducing them implicitly during implementation.

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

## Implementation Order

Implementation is acceptance-criteria-driven with no calendar plan. Gate scope is classified as core or additive in specification section 19; cut from the bottom of that list under schedule pressure, and delete the corresponding claims from the report when a stage is cut.

The trace report is generated from frozen traces and is built last. It must never become a dependency of any reasoning module.
