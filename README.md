# Clinical Trial Matching Agent

An evidence-grounded research prototype for matching synthetic longitudinal FHIR R4 patient records to public NSCLC clinical trials.

Phase 1 focuses on hybrid candidate retrieval, source-aligned eligibility criteria, bounded criterion reasoning, machine-verifiable patient and trial evidence, and benchmark-first evaluation. It does not diagnose, determine clinical eligibility, recommend treatment, or enroll patients.

## Current Status

The Phase 1 MVP design is frozen. Implementation proceeds through acceptance-criteria-driven gates without a calendar-based schedule.

- [Phase 1 MVP specification](docs/specs/phase-1-mvp-specification.md)
- [Benchmark plan](docs/evaluation/phase-1-benchmark-plan.md)
- [Implementation sequence](docs/plans/phase-1-implementation-sequence.md)
- [Domain glossary](CONTEXT.md)

## Data Boundary

The project uses public ClinicalTrials.gov records and authored synthetic FHIR R4 scenarios. It does not use real PHI, MIMIC, or live EHR data in Phase 1.
