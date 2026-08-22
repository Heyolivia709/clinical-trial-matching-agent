# Deliver a static trace report as the demonstration surface

The demonstration surface is a self-contained static report generated from a frozen Matching Run, publishable as a hosted page and viewable offline without a server, credentials, or network access.

An interactive application was rejected as the primary surface because reviewers do not clone repositories or install dependencies, and because a live run of dozens of criterion assessments cannot complete inside a five-minute review window. Having no interface at all was also rejected: an unseen result is not a portfolio result.

The report shows the agent trace rather than a clinical report. A polished trial-summary card demonstrates nothing distinctive; what does is the proposition decomposition, the tool call sequence with arguments and results, clickable citations resolving to FHIR JSON paths and exact trial spans, the verifier rejecting a citation and triggering its single correction, the side-by-side one-shot baseline, and per-assessment cost.

Because the report is generated from traces, it is built last and is never a dependency of any reasoning module. An optional live mode may run a single new patient-trial pair locally.
