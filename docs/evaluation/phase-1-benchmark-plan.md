# Measurement Plan

**Status:** Frozen. Supersedes the v6 benchmark plan, which specified inferential
statistics this project does not perform. See
[ADR 0014](../adr/0014-cut-the-research-grade-evaluation-protocol.md).

What gets measured, how the expected answers are produced, and what the numbers
are and are not allowed to claim.

## Principles

Gold labels are derived by code from the hidden Scenario Manifest and the
authored Criterion Expression. No model produces a label, and no model grades
another model's output.

Release gates are deterministic invariants only — properties the implementation
controls. Every model-behaviour number is a reported result. Specification
section 20 lists both.

Held-out scenarios and trials are assessed once, at the end, and are never used
while tuning prompts, tools, or configuration.

## Dataset

Six authored synthetic scenarios against four frozen trial records: two
development trials and two held out, four development scenarios and two held out.
That is at most 24 scenario-trial pairs, of which the assessed set makes fewer,
and a few dozen graded propositions inside them.

**This is a demonstration set, not a benchmark.** It is large enough to show that
each planted hazard resolves to the Unknown Reason it was planted for, and far
too small to support a claim about how the architecture performs in general. The
report states that where the numbers appear.

## Variants

| Variant | What it gets | What it shows |
| --- | --- | --- |
| Agent | Criterion text, the authored expression, and tool results | The system under test |
| One-shot baseline | Criterion text, the authored expression, and the entire patient timeline in one prompt | What the orchestration is worth |
| Agent, no verifier | As the agent, with verification and correction disabled | What the verifier is worth |

The baseline is handed **more** patient information than the agent, which sees
only what its tool calls return. Any advantage the agent shows therefore comes
from grounding discipline, not from access. That asymmetry is stated wherever the
comparison is published.

### The verifier has two roles, and they stay apart

Offline grading scores the final output of every variant with the same code and
configuration. Runtime feedback — the verdict that triggers one correction —
reaches only the agent. Conflating them would make the comparison meaningless,
because the baseline would be graded against a standard it was allowed to consult.

## Track 1: invariants, gated

Reported pass or fail, per specification section 20. These are absolute: a single
violation is a failure, not a percentage.

## Track 2: grounding, reported

- Patient and trial reference validity, at three points: the baseline, the agent
  before correction, and the agent after correction.
- Unsupported assessments — `met` or `not_met` whose citation cannot establish
  it — at the same three points.
- The verification-induced `unknown` rate: propositions the agent committed to
  before correction and returned as `unknown` after it. Published beside
  post-correction validity, at equal prominence. A verifier that rejected
  everything would report perfect validity and be worthless; this number is what
  separates the two.

## Track 3: accuracy, reported

Criterion State agreement with the derived gold label, per state, as a count over
a stated denominator. Per-state counts are shown because an aggregate over four
states with a dozen observations each hides which state the system is bad at.

Unknown Reason agreement is reported separately: getting `unknown` right for the
wrong reason is a different failure from getting the state wrong, and the whole
reason the taxonomy exists is that a coordinator acts differently on each.

## Track 4: cost

Model calls, prompt and completion tokens, latency, and estimated cost, per
criterion assessment, for every variant. Published beside the grounding number it
purchased — including when the ratio is unfavourable.

## What the numbers may not be used for

No confidence interval, hypothesis test, or effect size. At this sample size an
interval would be wider than any difference worth claiming, and computing one
would dress a demonstration up as a study. Counts, denominators, and a sentence
about what they cannot support.

A result that goes against the architecture is published as it stands.
