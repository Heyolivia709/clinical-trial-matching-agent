# Project Instructions

## Language

All repository content for this project must be written in English. This includes documentation, source code, identifiers, comments, docstrings, tests, fixtures, configuration descriptions, commit-oriented artifacts, and user-facing text.

Do not add Chinese or bilingual repository content unless the user explicitly revokes this rule for a specific artifact.

## Product Boundary

This project is a research-coordinator decision-support prototype for matching synthetic or public patient information to clinical trials. It must not claim to diagnose, determine clinical eligibility, enroll patients automatically, or demonstrate clinical effectiveness.

Before changing Phase 1 behavior, read `CONTEXT.md` and `docs/specs/phase-1-mvp-specification.md`. The specification is frozen as the Phase 1 source of truth. Record scope changes explicitly rather than introducing them implicitly during implementation.

## Differentiation

Keep the implementation centered on agent cognition and orchestration, longitudinal FHIR patient modeling, hybrid or advanced retrieval, criterion-level reasoning, evidence grounding, and benchmark-first evaluation.

Do not turn the project into a chat UI, ordinary retrieval-augmented generation demo, generic agent harness, skill collection, action-execution system, permission workflow, approval flow, or external write-operation system.

Phase 1 implementation is acceptance-criteria-driven and has no calendar-based delivery plan. The coordinator review interface is optional until all benchmark and failure-analysis gates are complete.
