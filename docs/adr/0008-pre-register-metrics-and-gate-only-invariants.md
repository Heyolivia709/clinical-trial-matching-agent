# Pre-register metrics and gate only deterministic invariants

Release gates are restricted to deterministic invariants — reference validity, aggregation correctness, verifier catch rate on injected faults, criterion coverage, zero post-cutoff citations, zero infrastructure failures scored as uncertainty. Every model-behavior measurement, including criterion-state macro F1 and every cost figure, is a reported result with a confidence interval rather than a gate.

Threshold gates on statistics were rejected. At roughly 80 held-out atomic propositions, a target such as "macro F1 at least 70%" or "at least 5 percentage points over the control" creates pressure to reach a number on data that must never inform optimization, and the interval around it is wide enough that the threshold would be close to arbitrary. Invariants are different in kind: they are software-correctness properties the implementation controls, so gating on them commits to nothing but correctness.

The accuracy comparison against the expression-aware control is instead a pre-registered, two-sided hypothesis test with no minimum effect size, accompanied by a power statement declaring in advance that differences below roughly 8–12 percentage points will be reported as inconclusive. Metrics, comparison units, cost-value pairing, statistical procedure, and a falsification condition are committed before the first held-out run, and the published report cites that commit hash. Declaring the protocol afterward was rejected because a cost-value claim whose metric is chosen after the numbers exist is unfalsifiable.

The consequence, accepted deliberately, is that the project can pass every release gate and still fail its central claim. The gates certify software correctness; the pre-registered comparison certifies architectural value, and a null result there is published as the headline.

**Revised 2026-08-23.** The decision stands; two figures cited above do not, and are retained here only as the record of what was believed at the time.

"Roughly 80 held-out atomic propositions" is not a quantity this dataset produces. The dataset yields 40 held-out scenario-trial pairs carrying roughly 280–400 graded observations, and proposition, observation, and cluster are three different units. See [`../evaluation/pre-registration.md`](../evaluation/pre-registration.md) section 5.1.

"Differences below roughly 8–12 percentage points" understates the band by treating propositions as independent, which the clustered resampling design in the same protocol exists to reject. Effective sample size is the cluster count. The band is provisionally 15–25 points and is now recomputed from development data and committed as a dated amendment before the held-out run, rather than asserted in advance. See pre-registration section 5.3.

Both corrections strengthen the original argument rather than weakening it: if the resolvable difference is wider than v1 believed, threshold gates on statistics at this sample size would have been even more arbitrary than this ADR claimed.
