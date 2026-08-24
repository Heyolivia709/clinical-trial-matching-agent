# Scenario Manifests

Hidden ground truth for the six Authored Synthetic Scenarios: what was authored
into each Bundle, which facts are planted hazards, and what each hazard is for.

They are in their own directory rather than beside the Bundles because the
matching system must never receive one (specification section 4.4). Only
`ctma.evaluation` reads this directory, nothing may import `ctma.evaluation`, and
`tests/test_architecture.py` fails if another package so much as names the
directory. That is the whole guarantee — not review, not care.

A manifest carries no expected Criterion State. Expected states are derived by
code from these facts and the authored Criterion Expression, which is ADR 0005:
a manifest that carried answers would let a labelling judgement in through the
back door.

Each manifest records the SHA-256 of the Bundle it was authored against, and
every authored fact records the JSON path it sits at. Loading checks both, so a
manifest can never describe a patient the Bundle no longer contains.

**Provenance.** Drafted by the assistant with AI assistance; reviewed by rendong
on 2026-08-24, recorded in each file.
