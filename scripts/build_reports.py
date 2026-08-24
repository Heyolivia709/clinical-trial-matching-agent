"""Build the Trace Reports from frozen artifacts.

This script is the one place that may see both halves. Nothing in `src/ctma`
imports `ctma.report`, and nothing imports `ctma.evaluation`; a report that
needs the run-independent counts therefore has to be assembled from outside
both, which is what this is.

Usage:

    uv run python scripts/build_reports.py [output-directory]

Every development scenario gets a report, plus one for a run in which the
system fails, which specification section 15 requires at least one report to
cover.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from ctma.adapters.injected_faults import load_injected_faults
from ctma.adapters.model import REPLAY_CONFIGURATION
from ctma.adapters.scenario_bundles import load_scenario_input
from ctma.adapters.transcripts import load_transcript
from ctma.adapters.trial_fixtures import load_trial_fixtures
from ctma.agent.verifier import verify
from ctma.domain.assessment import AssessedCriterion, UnknownAssessment
from ctma.domain.enums import Partition
from ctma.domain.evidence import PatientEvidence
from ctma.domain.proposal import ProposedCitation
from ctma.domain.run import MatchingRun
from ctma.domain.timeline import PatientTimeline
from ctma.domain.trial import TrialRecord
from ctma.evaluation.baseline import one_shot
from ctma.evaluation.cases import EvalCase, eval_cases
from ctma.evaluation.counts import ReportedCounts, validity_before_correction
from ctma.evaluation.grading import Variant, grade_baseline
from ctma.evaluation.lab import VariantResult, run_agent, run_one_shot, timeline_for, totals
from ctma.match import match
from ctma.report.inputs import (
    BaselineRow,
    CountRow,
    FaultRow,
    InvariantRow,
    ReportInputs,
    ResultsSection,
)
from ctma.report.page import render

DEMONSTRATIVE = "NCT07349537:INC-2"
NCT = DEMONSTRATIVE.split(":")[0]

PLAIN_LANGUAGE = (
    "This system reads a patient's medical record and a clinical trial's entry "
    "requirements, and says, one requirement at a time, whether the record supports it, "
    "contradicts it, or does not say — and shows exactly which line of the record it "
    "read."
)

FAILING_TRANSCRIPT = "scn-04-failing"


def main(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    cases = eval_cases(Partition.DEVELOPMENT)
    results = _results_section(cases)
    written: list[Path] = []
    for scenario_id in sorted({case.scenario_id for case in cases}):
        written.append(_write(scenario_id, results, output))
    written.append(_write("SCN-04", results, output, transcript=FAILING_TRANSCRIPT))
    for path in written:
        print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


def _write(
    scenario_id: str,
    results: ResultsSection,
    output: Path,
    *,
    transcript: str | None = None,
) -> Path:
    name = transcript or f"{scenario_id.lower()}-development"
    run = _run(scenario_id, name)
    timeline = timeline_for(scenario_id)
    trials = load_trial_fixtures(Partition.DEVELOPMENT)
    inputs = ReportInputs(
        run=run,
        timeline=timeline,
        trials=trials,
        demonstrative_criterion_id=DEMONSTRATIVE,
        plain_language=PLAIN_LANGUAGE,
        baseline=_baseline_rows(scenario_id, run, timeline, trials),
        faults=_faults(scenario_id, timeline, trials),
        results=results,
    )
    path = output / f"{name}.html"
    path.write_text(render(inputs), encoding="utf-8")
    return path


def _run(scenario_id: str, transcript: str) -> MatchingRun:
    scenario = load_scenario_input(scenario_id)
    return match(
        scenario_id=scenario_id,
        bundle_json=scenario.bundle_json,
        assessment_as_of=scenario.assessment_as_of,
        trials=load_trial_fixtures(Partition.DEVELOPMENT),
        model=load_transcript(transcript).replay(REPLAY_CONFIGURATION),
        partition=Partition.DEVELOPMENT,
        run_id=transcript,
    )


def _baseline_rows(
    scenario_id: str,
    run: MatchingRun,
    timeline: PatientTimeline,
    trials: tuple[TrialRecord, ...],
) -> tuple[BaselineRow, ...]:
    """The same criterion, answered by the agent and by the one-shot baseline."""
    trial = next(item for item in trials if item.nct_id == NCT)
    criterion = next(item for item in trial.criteria if item.criterion_id == DEMONSTRATIVE)
    case = next(
        item
        for item in eval_cases(Partition.DEVELOPMENT)
        if item.scenario_id == scenario_id and item.nct_id == NCT
    )
    answers = one_shot(
        criterion,
        timeline=timeline,
        trial=trial,
        model=load_transcript(f"{scenario_id.lower()}-baseline").replay(REPLAY_CONFIGURATION),
    )
    graded = {
        item.proposition_id: item
        for item in grade_baseline([answers], case=case, timeline=timeline, trial=trial)
    }
    assessed = next(
        (
            item
            for assessment in run.trial_assessments
            for item in assessment.criteria
            if item.criterion_id == DEMONSTRATIVE and isinstance(item, AssessedCriterion)
        ),
        None,
    )
    if assessed is None:
        return ()
    by_id = {item.proposition_id: item for item in criterion.propositions}
    rows: list[BaselineRow] = []
    for assessment in assessed.propositions:
        answer = next(
            (
                item
                for item in answers.assessments
                if item.proposition_id == assessment.proposition_id
            ),
            None,
        )
        outcome = graded.get(assessment.proposition_id)
        rows.append(
            BaselineRow(
                proposition_id=assessment.proposition_id,
                statement=by_id[assessment.proposition_id].statement,
                agent_state=assessment.state,
                agent_reason=(
                    assessment.reason if isinstance(assessment, UnknownAssessment) else None
                ),
                agent_citations=_cited(assessment.patient_evidence),
                baseline_state=answer.state if answer else None,
                baseline_reason=answer.reason if answer else None,
                baseline_citations=_cited(answer.patient_evidence) if answer else (),
                baseline_rejections=(
                    tuple(item.value for item in outcome.grading.rejections) if outcome else ()
                ),
            )
        )
    return tuple(rows)


def _cited(
    evidence: Sequence[PatientEvidence] | Sequence[ProposedCitation],
) -> tuple[str, ...]:
    return tuple(
        f"{fact.resource_type}/{fact.resource_id}" for item in evidence for fact in item.facts
    )


def _faults(
    scenario_id: str, timeline: PatientTimeline, trials: tuple[TrialRecord, ...]
) -> tuple[FaultRow, ...]:
    """The injected fault this scenario can demonstrate, verified here and now."""
    rows: list[FaultRow] = []
    by_id = {trial.nct_id: trial for trial in trials}
    for fault in load_injected_faults().citations:
        if fault.scenario_id != scenario_id or fault.nct_id not in by_id:
            continue
        outcome = verify(fault.proposal, timeline=timeline, trial=by_id[fault.nct_id])
        if not outcome.rejections:
            continue
        cited = ", ".join(
            f"{fact.resource_type}/{fact.resource_id}"
            for citation in fault.proposal.patient_evidence
            for fact in citation.facts
        )
        rows.append(
            FaultRow(
                fault_id=fault.fault_id,
                intent=fault.intent,
                cited=cited or "nothing",
                rejection=", ".join(item.value for item in outcome.rejections),
                detail=outcome.detail or "",
            )
        )
    return tuple(rows)


def _results_section(cases: tuple[EvalCase, ...]) -> ResultsSection:
    """The run-independent counts, computed once for every report."""
    agent = [
        run_agent(
            case,
            model=load_transcript(f"{case.scenario_id.lower()}-development").replay(
                REPLAY_CONFIGURATION
            ),
        )
        for case in cases
    ]
    baseline = [
        run_one_shot(
            case,
            model=load_transcript(f"{case.scenario_id.lower()}-baseline").replay(
                REPLAY_CONFIGURATION
            ),
        )
        for case in cases
    ]
    agent_counts = totals(agent, variant=Variant.AGENT, partition=Partition.DEVELOPMENT)
    baseline_counts = totals(baseline, variant=Variant.BASELINE, partition=Partition.DEVELOPMENT)
    graded = tuple(item for result in agent for item in result.graded)
    invariants = _invariant_rows(agent)
    return ResultsSection(
        sample_sentence=agent_counts.sample_sentence(),
        invariants=invariants,
        counts=(
            CountRow(
                label="Citation validity where the variant committed to an answer",
                agent=validity_before_correction(graded).rendered(),
                baseline=baseline_counts.reference_validity.rendered(),
                note="different denominators, and both are stated: the agent commits only "
                "where the record can answer, the baseline answers everything. The agent "
                "figure is before its correction — after correction it is structural and is "
                "not compared",
            ),
            CountRow(
                label="Assessments resting on a citation that cannot establish them",
                agent=agent_counts.unsupported_assessments.rendered(),
                baseline=baseline_counts.unsupported_assessments.rendered(),
            ),
            CountRow(
                label="Verification-induced unknown",
                agent=agent_counts.verification_induced_unknown.rendered(),
                baseline="not applicable",
                note="what the citation guarantee costs, published beside it",
            ),
            *_state_rows(agent_counts, baseline_counts),
            CountRow(
                label="Unknown Reason agreement",
                agent=agent_counts.reason_agreement.rendered(),
                baseline=baseline_counts.reason_agreement.rendered(),
                note="reported apart from the state: a right state for the wrong reason "
                "sends a coordinator to the wrong place",
            ),
            CountRow(
                label="Model calls per criterion assessment",
                agent=str(agent_counts.cost.calls_per_criterion),
                baseline=str(baseline_counts.cost.calls_per_criterion),
                note="cost beside the grounding it purchased",
            ),
            CountRow(
                label="Coverage-Only propositions, excluded from accuracy",
                agent=str(agent_counts.coverage_only_propositions),
                baseline=str(baseline_counts.coverage_only_propositions),
            ),
        ),
        worked_failures=(
            "Both variants replay authored transcripts rather than a recorded model run, "
            "so these counts measure the harness and not a model. A published result is "
            "recorded from the hosted or local adapter.",
            "No development scenario meets an exclusion criterion of a development trial, "
            "because the reviewed terminology mapping does not cover the conditions those "
            "trials exclude. Every criterion naming an uncovered concept reports "
            "missing_evidence, which is a property of the authoring budget rather than of "
            "the patient.",
        ),
    )


def _invariant_rows(agent: Sequence[VariantResult]) -> tuple[InvariantRow, ...]:
    """One row per invariant, over every case rather than over the first one.

    This section is run-independent, so a detail naming one scenario would read
    as a claim about the set.
    """
    names = [item.invariant for item in agent[0].invariants]
    rows: list[InvariantRow] = []
    for name in names:
        results = [item for case in agent for item in case.invariants if item.invariant is name]
        failed = [item for item in results if not item.passed]
        rows.append(
            InvariantRow(
                name=name.value,
                passed=not failed,
                detail=(
                    f"held on all {len(results)} scenario-trial pairs"
                    if not failed
                    else f"{len(failed)} of {len(results)} pairs violate it: {failed[0].detail}"
                ),
            )
        )
    return tuple(rows)


def _state_rows(agent: ReportedCounts, baseline: ReportedCounts) -> tuple[CountRow, ...]:
    return tuple(
        CountRow(
            label=f"Criterion State agreement — {state.value}",
            agent=count.rendered(),
            baseline=baseline.state_agreement[state].rendered(),
            note="per state, never one aggregate",
        )
        for state, count in agent.state_agreement.items()
        if count.denominator
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("build/reports"))
