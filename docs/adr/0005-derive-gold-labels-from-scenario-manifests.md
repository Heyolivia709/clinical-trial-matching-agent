# Derive gold labels from scenario manifests

Expected criterion states are computed by deterministic code from the hidden Scenario Manifest and the authored Criterion Expression. Both model-generated labels and large-scale manual labeling were rejected.

Model-generated labels were rejected because grading a model with a model measures agreement rather than correctness, and the circularity invalidates every downstream metric. Manual labeling at the v1 scale of 500 propositions was rejected as unaffordable and, for authored scenarios, unnecessary: because the project authors the patient facts, the expected state of a supported proposition is computable rather than a matter of judgment.

The consequence is that benchmark difficulty cannot come from clinical subtlety. It must come instead from deliberately planted evidence hazards — error-status results, orders without administrations, post-assessment dates, conflicting values, insufficient date precision, preliminary results, and near-miss concepts. The published report states plainly that the benchmark tests evidence retrieval, citation validity, and logic application, not clinical judgment.

Propositions that cannot be operationalized this way remain visible as Coverage-Only Assessments and are excluded from accuracy metrics.
