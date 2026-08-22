# Gate multi-turn behavior behind flags

The Trial Supervisor's multi-turn behaviors — criterion ordering, early termination on a confirmed blocker, and cross-criterion evidence reuse — are configuration flags that default off, not baseline behavior.

Making them default was rejected because each one confounds the correctness benchmark. Early termination forfeits full Criterion Coverage, ordering and reuse introduce order dependence, and reuse can propagate a single incorrect reading across several criteria. Omitting them entirely was also rejected, because blocker-first termination and evidence reuse are the only multi-turn behaviors in this domain whose value can be measured rather than merely asserted, in tokens, model calls, and latency.

As flags they become ablation rows: correctness benchmarks run with flags off, cost benchmarks run with flags on, and the delta is the result. Skipped criteria report `not_assessed` rather than `unknown`, assessment order is deterministic given a fixed configuration and seed, reused evidence records its originating criterion, and reuse-induced error propagation is reported separately.
