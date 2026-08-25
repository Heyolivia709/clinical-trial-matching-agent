"""Score a recorded run and print every number the measurement plan asks for.

    uv run python scripts/score_run.py hosted          # the recorded model run
    uv run python scripts/score_run.py development     # the authored transcripts

Takes a suffix rather than a flag so the two are named the same way everywhere,
and so a table can never be printed without saying which transcripts produced it.
"""

from __future__ import annotations

import sys

from ctma.adapters.model import REPLAY_CONFIGURATION
from ctma.adapters.transcripts import load_transcript
from ctma.domain.enums import Partition
from ctma.evaluation.cases import eval_cases
from ctma.evaluation.counts import corrections_attempted, validity_before_correction
from ctma.evaluation.grading import Variant
from ctma.evaluation.lab import VariantResult, run_agent, run_one_shot, totals

SUFFIXES = {
    "hosted": ("hosted", "hosted-baseline"),
    "development": ("development", "baseline"),
}

which = sys.argv[1] if len(sys.argv) > 1 else "hosted"
agent_suffix, baseline_suffix = SUFFIXES[which]
cases = eval_cases(Partition.DEVELOPMENT)


def replay(scenario_id: str, suffix: str) -> object:
    return load_transcript(f"{scenario_id.lower()}-{suffix}").replay(REPLAY_CONFIGURATION)


agent: list[VariantResult] = [
    run_agent(case, model=replay(case.scenario_id, agent_suffix))  # type: ignore[arg-type]
    for case in cases
]
baseline: list[VariantResult] = [
    run_one_shot(case, model=replay(case.scenario_id, baseline_suffix))  # type: ignore[arg-type]
    for case in cases
]

agent_counts = totals(agent, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
baseline_counts = totals(baseline, variant=Variant.BASELINE, partition=Partition.DEVELOPMENT)
graded = tuple(item for result in agent for item in result.graded)

print(f"transcripts: {agent_suffix} / {baseline_suffix}")
print(agent_counts.sample_sentence())
print()

print("Track 1: release gates")
names = [item.invariant for item in agent[0].invariants]
for name in names:
    results = [item for case in agent for item in case.invariants if item.invariant is name]
    failed = [item for item in results if not item.passed]
    mark = "pass" if not failed else "FAIL"
    print(f"  {mark}  {name.value}  ({len(results) - len(failed)} of {len(results)} pairs)")
    for item in failed[:2]:
        print(f"        {item.detail}")

print("\nTrack 2: grounding")
grounding = (
    ("citation validity, agent before correction", validity_before_correction(graded)),
    ("citation validity, baseline", baseline_counts.reference_validity),
    ("unsupported assessments, agent", agent_counts.unsupported_assessments),
    ("unsupported assessments, baseline", baseline_counts.unsupported_assessments),
    ("verification-induced unknown, agent", agent_counts.verification_induced_unknown),
    ("corrections attempted, agent", corrections_attempted(graded)),
)
for label, count in grounding:
    print(f"  {label:44}{count.rendered()}")

print("\nTrack 3: accuracy, per expected state")
for state in agent_counts.state_agreement:
    a = agent_counts.state_agreement[state]
    b = baseline_counts.state_agreement[state]
    print(f"  {state.value:16} agent {a.rendered():18} baseline {b.rendered()}")
print(
    f"  {'reason agreement':16} agent {agent_counts.reason_agreement.rendered():18} "
    f"baseline {baseline_counts.reason_agreement.rendered()}"
)

print("\nTrack 4: cost")
for label, counts in (("agent", agent_counts), ("baseline", baseline_counts)):
    cost = counts.cost
    tokens = cost.prompt_tokens + cost.completion_tokens
    print(
        f"  {label:9} {cost.criterion_assessments} criterion assessments, "
        f"{cost.model_calls} model calls, {tokens} tokens, "
        f"{cost.calls_per_criterion} calls per criterion"
    )
