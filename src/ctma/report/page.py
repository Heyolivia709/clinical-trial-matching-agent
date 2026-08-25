"""The Trace Report: one self-contained page, generated from frozen artifacts.

Specification section 15 and ADR 0009. Three things about the shape of it.

**Verdict-first, not pipeline order.** The sections carrying the claim — the
worked criterion, the verifier catch, the baseline comparison — come before any
setup. A document that presents the pipeline in execution order fails the
five-minute constraint however complete it is, because the reader stops before
the interesting part.

**Colour and shape encode Criterion Impact, never Criterion State.** An
exclusion criterion assessed `met` means the statement holds *and* the patient
is excluded; colouring that green because "met is good" inverts the semantics.
State is text. The verifier gets its own process colour, because "the verifier
rejected something" and "this counts against the match" are different signals.

**Self-contained.** No network fetch at view time: the stylesheet is inline, the
fonts are whatever the reader already has, and the only interactivity is
`<details>`, which is the browser's. A report that needs the network is not
offline-viewable, and offline-viewable is the one hard constraint on the
surface.
"""

from __future__ import annotations

import html
import json
from collections.abc import Iterable, Sequence

from ctma.domain.assessment import (
    AssessedCriterion,
    CriterionAssessment,
    PropositionAssessment,
    SkippedCriterion,
    TrialAssessment,
    UnexpressedCriterion,
    UnknownAssessment,
)
from ctma.domain.enums import (
    CandidateStatus,
    CriterionImpact,
    CriterionState,
    UnknownReason,
)
from ctma.domain.evidence import PatientEvidence
from ctma.domain.expression import EligibilityCriterion
from ctma.domain.run import MatchingRun
from ctma.domain.timeline import MedicationExposure, TimelineFact
from ctma.domain.trace import ToolOutcome
from ctma.report.inputs import DISCLAIMER, FaultRow, ReportInputs

STATE_LABEL: dict[CriterionState, str] = {
    CriterionState.MET: "Supported",
    CriterionState.NOT_MET: "Contradicted",
    CriterionState.UNKNOWN: "Unknown",
    CriterionState.NOT_APPLICABLE: "Not applicable",
}
"""Specification section 7 fixes the interface wording. "Not Supported" is
prohibited: it reads contradiction and missing evidence as the same thing."""

IMPACT_MARK: dict[CriterionImpact, str] = {
    CriterionImpact.SATISFIED: "■",
    CriterionImpact.BLOCKING: "▲",
    CriterionImpact.UNRESOLVED: "◆",
    CriterionImpact.NEUTRAL: "○",
}
"""Shapes carry the encoding so it survives greyscale and colour blindness.
Colour is never the only channel."""

NOT_ASSESSED_MARK = "⬚"

SECTIONS = (
    ("s1", "1. What this run says"),
    ("s2", "2. The worked criterion"),
    ("s3", "3. The verifier catch"),
    ("s4", "4. Agent against the one-shot baseline"),
    ("s5", "5. Candidate trials"),
    ("s6", "6. Every criterion, per trial"),
    ("s7", "7. The patient timeline"),
    ("s8", "8. Across the scenario set"),
    ("s9", "9. What the run cost"),
    ("s10", "10. Reproducibility"),
)

STYLE = """
:root {
  --ink: #16181d; --muted: #5c6370; --rule: #d8dbe2; --ground: #ffffff;
  --panel: #f6f7f9; --quote: #eef1f6;
  --blocking: #a33a1f; --unresolved: #2f5aa8; --process: #6b3fa0; --pass: #1f6b3a;
  --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--ground); color: var(--ink);
       font-family: var(--sans); font-size: 15px; line-height: 1.55; }
.layout { display: grid; grid-template-columns: 15rem minmax(0, 1fr); gap: 2.5rem;
          max-width: 78rem; margin: 0 auto; padding: 2rem 1.5rem 6rem; }
nav.index { position: sticky; top: 2rem; align-self: start; font-family: var(--mono);
            font-size: 12px; line-height: 2; }
nav.index a { color: var(--muted); text-decoration: none; display: block; }
nav.index a:hover { color: var(--ink); }
nav.index .title { color: var(--ink); font-weight: 600; margin-bottom: .75rem; }
section { border-top: 1px solid var(--rule); padding-top: 1.25rem; margin-bottom: 3rem; }
section > h2 { font-size: 15px; margin: 0 0 .25rem; letter-spacing: .01em; }
.meta { font-family: var(--mono); font-size: 11px; color: var(--muted); }
p { max-width: 46rem; }
.strip { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1rem 0;
         font-family: var(--mono); font-size: 12px; }
.strip div span { display: block; color: var(--muted); font-size: 11px; }
table { border-collapse: collapse; width: 100%; font-family: var(--mono); font-size: 12px; }
th, td { text-align: left; padding: .4rem .6rem; border-bottom: 1px solid var(--rule);
         vertical-align: top; }
th { color: var(--muted); font-weight: 500; }
code, .mono { font-family: var(--mono); font-size: 12px; }
.enum { color: var(--muted); font-family: var(--mono); font-size: 11px; }
.mark { font-family: var(--mono); }
.satisfied, .neutral { color: var(--muted); }
.blocking { color: var(--blocking); }
.unresolved { color: var(--unresolved); }
.verifier { color: var(--process); }
.pass { color: var(--pass); }
.fail { color: var(--blocking); }
blockquote.source { margin: .75rem 0; padding: .6rem .9rem; background: var(--quote);
                    border-left: 3px solid var(--muted); font-family: var(--mono);
                    font-size: 12px; }
blockquote.source .label { display: block; color: var(--muted); font-size: 11px;
                           margin-bottom: .3rem; }
.panel { background: var(--panel); padding: .9rem 1rem; margin: 1rem 0; }
.disclaimer { border: 1px solid var(--rule); padding: .8rem 1rem; margin: 1.25rem 0;
              font-size: 13px; color: var(--muted); max-width: 46rem; }
details { margin: .5rem 0; }
details > summary { cursor: pointer; font-family: var(--mono); font-size: 12px;
                    color: var(--muted); }
ol.calls { font-family: var(--mono); font-size: 12px; padding-left: 1.2rem; }
ol.calls li { margin-bottom: .4rem; }
.legend { font-family: var(--mono); font-size: 11px; color: var(--muted); margin-top: .75rem; }
@media (max-width: 52rem) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: 1.25rem; padding: 1.25rem 1rem 4rem; }
  nav.index { position: static; border-bottom: 1px solid var(--rule); padding-bottom: .75rem;
              display: flex; flex-wrap: wrap; gap: .3rem .9rem; }
  nav.index .title { width: 100%; margin-bottom: .1rem; }
  nav.index a { display: inline; font-size: 11px; }
  table { display: block; overflow-x: auto; }
  blockquote { margin-left: 0; }
}
@media print {
  .layout { display: block; max-width: none; padding: 0; }
  nav.index { display: none; }
  details { display: block; }
  details > summary { display: none; }
  section { break-inside: avoid; }
  .disclaimer { border: 1px solid #000; }
}
"""


def render(inputs: ReportInputs) -> str:
    """One page, ordered verdict-first."""
    body = "\n".join(
        (
            _summary(inputs),
            _worked_criterion(inputs),
            _verifier(inputs),
            _comparison(inputs),
            _candidates(inputs),
            _criterion_tables(inputs),
            _timeline(inputs),
            _results(inputs),
            _cost(inputs),
            _reproducibility(inputs),
        )
    )
    title = f"Trace Report — {esc(inputs.run.identities.scenario_id)}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="layout">
{_index()}
<main>
<h1 style="font-size:18px;margin:0 0 .25rem">{title}</h1>
<p class="meta">Screening workflow labels for research coordinator review. Generated from a
frozen Matching Run.</p>
{body}
</main>
</div>
</body>
</html>
"""


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _index() -> str:
    links = "\n".join(f'<a href="#{key}">{esc(title)}</a>' for key, title in SECTIONS)
    return f'<nav class="index"><div class="title">Sections</div>{links}</nav>'


def _section(key: str, title: str, meta: str, body: str) -> str:
    return (
        f'<section id="{key}"><h2>{esc(title)}</h2><p class="meta">{esc(meta)}</p>{body}</section>'
    )


def _disclaimer() -> str:
    return f'<div class="disclaimer">{esc(DISCLAIMER)}</div>'


# --- section 1 ---------------------------------------------------------------


def _summary(inputs: ReportInputs) -> str:
    run = inputs.run
    rows = "".join(
        f"<tr><td>{esc(assessment.nct_id)}</td>"
        f"<td>{esc(_conclusion_words(assessment))}</td>"
        f"<td>{_counts_cell(assessment)}</td></tr>"
        for assessment in run.trial_assessments
    )
    worked = inputs.demonstrative_criterion_id
    body = f"""
<p>{esc(inputs.plain_language)}</p>
<p>This page shows one screening run: a synthetic patient record compared against
frozen public trial records, one eligibility criterion at a time. Every judgment below
points at the exact line of the patient record and the exact words of the trial text it
came from, and a deterministic check re-reads both before the judgment is allowed to
stand.</p>
<table><thead><tr><th>Trial</th><th>Conclusion</th><th>Criteria</th></tr></thead>
<tbody>{rows}</tbody></table>
<p>The criterion worked through in full below is <code>{esc(worked)}</code>. Sections 2
to 4 are the ones that carry the claim; everything after them is detail.</p>
{_disclaimer()}
"""
    return _section(
        "s1",
        "1. What this run says",
        f"scenario {run.identities.scenario_id} · assessed as of {run.identities.assessment_as_of}",
        body,
    )


def _conclusion_words(assessment: TrialAssessment) -> str:
    return {
        "potential_match": "Worth a coordinator's time",
        "insufficient_information": "Someone needs to check the chart",
        "unlikely_match": "A criterion rules this patient out",
    }[assessment.conclusion.value]


def _counts_cell(assessment: TrialAssessment) -> str:
    counts = assessment.counts
    return (
        f"{counts.satisfied} satisfied · {counts.blocking} blocking · "
        f"{counts.unresolved} unresolved · {counts.not_assessed} not assessed"
    )


# --- section 2 ---------------------------------------------------------------


def _worked_criterion(inputs: ReportInputs) -> str:
    found = _find_criterion(inputs)
    if found is None:
        return _section("s2", "2. The worked criterion", "not present in this run", "")
    criterion, assessed = found
    propositions = "".join(_proposition_row(item, criterion) for item in assessed.propositions)
    calls = _tool_calls(assessed.propositions)
    body = f"""
<blockquote class="source"><span class="label">Trial source text, verbatim
({esc(criterion.criterion_id)}, {esc(criterion.polarity.value)}, characters
{criterion.span_start} to {criterion.span_end})</span>{esc(criterion.source_text)}</blockquote>
<div class="strip">
  <div><span>Criterion state</span>{esc(STATE_LABEL[assessed.state])}
       <span class="enum">{esc(assessed.state.value)}</span></div>
  <div><span>Impact on the match</span>{_impact(assessed.impact)}</div>
  <div><span>Expression</span>{esc(criterion.expression.kind)} over
       {len(criterion.propositions)} propositions</div>
</div>
<table><thead><tr><th>Proposition</th><th>State</th><th>Evidence cited</th></tr></thead>
<tbody>{propositions}</tbody></table>
{calls}
<p class="legend">{_impact_legend()}</p>
"""
    return _section(
        "s2",
        "2. The worked criterion",
        f"{criterion.criterion_id} · aggregated by code from the propositions below",
        body,
    )


def _proposition_row(assessment: PropositionAssessment, criterion: EligibilityCriterion) -> str:
    authored = next(
        (
            item
            for item in criterion.propositions
            if item.proposition_id == assessment.proposition_id
        ),
        None,
    )
    reason = (
        f' <span class="enum">{esc(assessment.reason.value)}</span>'
        if isinstance(assessment, UnknownAssessment)
        else ""
    )
    return (
        f"<tr><td>{esc(assessment.proposition_id)}<br>"
        f"<span class='enum'>{esc(authored.statement if authored else '')}</span></td>"
        f"<td>{esc(STATE_LABEL[assessment.state])}"
        f" <span class='enum'>{esc(assessment.state.value)}</span>{reason}</td>"
        f"<td>{_citations(assessment.patient_evidence)}</td></tr>"
    )


def _citations(evidence: Sequence[PatientEvidence]) -> str:
    if not evidence:
        return '<span class="enum">nothing cited</span>'
    return "<br>".join(
        f"<code>{esc(fact.resource_type)}/{esc(fact.resource_id)}</code> "
        f"at <code>{esc(fact.json_path)}</code> "
        f'<span class="enum">{esc(item.relation.value)}'
        f"{', ' + esc(fact.value) if fact.value else ''}"
        f"{', ' + esc(fact.clinical_time) if fact.clinical_time else ''}</span>"
        for item in evidence
        for fact in item.facts
    )


def _tool_calls(assessments: Sequence[PropositionAssessment]) -> str:
    calls = [(item.proposition_id, call) for item in assessments for call in item.tool_calls]
    if not calls:
        return (
            '<p class="enum">No tool was called: the criterion resolved before the '
            "record was queried.</p>"
        )
    items = "".join(
        f"<li><code>{esc(call.tool)}</code> "
        f'<span class="enum">for {esc(proposition_id)}</span><br>'
        f"<span class='enum'>arguments {esc(call.arguments_json)}</span><br>"
        f"<span class='enum'>{esc(_outcome(call.outcome))}</span></li>"
        for proposition_id, call in calls
    )
    return (
        f"<details open><summary>Tool calls, in order ({len(calls)})</summary>"
        f'<ol class="calls">{items}</ol></details>'
    )


def _outcome(outcome: ToolOutcome) -> str:
    if outcome.outcome == "failed":
        return f"the tool failed: {outcome.failure.detail}"
    payload: object = json.loads(outcome.result_json)
    rendered = json.dumps(payload, sort_keys=True)
    return rendered if len(rendered) <= 320 else rendered[:320].rsplit(", ", 1)[0] + ", …}"


# --- section 3 ---------------------------------------------------------------


def _verifier(inputs: ReportInputs) -> str:
    organic = _organic_corrections(inputs.run)
    faults = "".join(
        f"""<div class="panel">
<p class="mono"><span class="verifier">Injected fault {esc(fault.fault_id)}</span> —
{esc(fault.intent)}</p>
<p class="enum">Cited: {esc(fault.cited)}</p>
<p class="mono"><span class="verifier">Rejected: {esc(fault.rejection)}</span></p>
<p class="enum">{esc(fault.detail)}</p>
{_corrected(fault)}
</div>"""
        for fault in inputs.faults
    )
    body = f"""
<p>A citation can point at something real and still not establish what it is cited for.
An order for a drug is not a record that the drug was taken; a withdrawn result is not a
result. The check below re-reads every citation against the patient record and the trial
text, and rejects the ones that cannot carry the claim.</p>
<p class="enum">These faults are injected deliberately, so that the catch is reproducible
rather than dependent on a model happening to make the mistake. Organic catches from this
run, if any, follow.</p>
{faults}
{organic}
"""
    return _section(
        "s3",
        "3. The verifier catch",
        "deterministic, and run again offline when the results are graded",
        body,
    )


def _corrected(fault: FaultRow) -> str:
    if fault.corrected_to is None:
        return ""
    return f'<p class="enum">After one correction: {esc(fault.corrected_to)}</p>'


def _organic_corrections(run: MatchingRun) -> str:
    rows = [
        (criterion.criterion_id, assessment)
        for trial in run.trial_assessments
        for criterion in trial.criteria
        if isinstance(criterion, AssessedCriterion)
        for assessment in criterion.propositions
        if len(assessment.verification) > 1
    ]
    if not rows:
        return '<p class="enum">This run produced no verifier rejection of its own.</p>'
    listed = "".join(
        f"<li><code>{esc(criterion_id)}/{esc(assessment.proposition_id)}</code>: "
        f'<span class="verifier">rejected</span> '
        f"({esc(', '.join(item.value for item in assessment.verification[0].rejections))}), "
        f"corrected, then {esc(assessment.verification[-1].verdict.value)}</li>"
        for criterion_id, assessment in rows
    )
    return f'<p class="mono">Caught in this run:</p><ol class="calls">{listed}</ol>'


# --- section 4 ---------------------------------------------------------------


def _comparison(inputs: ReportInputs) -> str:
    if not inputs.baseline:
        return _section("s4", "4. Agent against the one-shot baseline", "not run", "")
    rows = "".join(
        f"<tr><td>{esc(row.proposition_id)}<br><span class='enum'>{esc(row.statement)}</span></td>"
        f"<td>{esc(STATE_LABEL[row.agent_state])}"
        f"{_reason(row.agent_reason)}<br>"
        f"<span class='enum'>{esc(' · '.join(row.agent_citations) or 'nothing cited')}</span></td>"
        f"<td>{esc(STATE_LABEL[row.baseline_state]) if row.baseline_state else '—'}"
        f"{_reason(row.baseline_reason)}<br>"
        f"<span class='enum'>{esc(' · '.join(row.baseline_citations) or 'nothing cited')}</span>"
        f"{_rejections(row.baseline_rejections)}</td></tr>"
        for row in inputs.baseline
    )
    body = f"""
<p>The baseline is handed the criterion, the authored expression, and <em>the entire
patient record</em> in one prompt, with no tools. It sees more of the patient than the
agent does, which only ever sees what its tool calls returned. So any advantage the agent
shows here comes from grounding discipline rather than from access.</p>
<p class="enum">Both columns are graded by the same verifier, with the same
configuration, after the fact. Only the agent was allowed to consult it while
answering.</p>
<table><thead><tr><th>Proposition</th><th>Agent</th><th>One-shot baseline</th></tr></thead>
<tbody>{rows}</tbody></table>
"""
    return _section(
        "s4",
        "4. Agent against the one-shot baseline",
        f"{inputs.demonstrative_criterion_id} · same criterion, same patient",
        body,
    )


def _reason(reason: UnknownReason | None) -> str:
    return f' <span class="enum">{esc(reason.value)}</span>' if reason is not None else ""


def _rejections(rejections: Sequence[str]) -> str:
    if not rejections:
        return ""
    return f'<br><span class="verifier mono">verifier: {esc(", ".join(rejections))}</span>'


# --- section 5 ---------------------------------------------------------------


def _candidates(inputs: ReportInputs) -> str:
    order = {
        assessment.nct_id: position
        for position, assessment in enumerate(inputs.run.trial_assessments, start=1)
    }
    rows = "".join(
        f"<tr><td>{candidate.retrieval_rank}</td>"
        f"<td>{esc(order.get(candidate.nct_id, '—'))}</td>"
        f"<td><code>{esc(candidate.nct_id)}</code></td>"
        f"<td>{esc(candidate.status.value)}</td>"
        f"<td>{esc(_title(inputs, candidate.nct_id))}</td></tr>"
        for candidate in inputs.run.candidates.candidates
    )
    body = f"""
<p>Candidate order is authored and fixed: this project does not rank trials, so
Retrieval Rank is a position in a frozen list. Review Priority is the order a coordinator
should read them in, derived from each trial's conclusion. The two are shown separately
and never merged.</p>
<table><thead><tr><th>Retrieval rank</th><th>Review priority</th><th>Trial</th>
<th>Status</th><th>Title</th></tr></thead><tbody>{rows}</tbody></table>
"""
    return _section(
        "s5",
        "5. Candidate trials",
        f"{len(inputs.run.candidates.candidates)} candidates · {_assessed_count(inputs)} assessed",
        body,
    )


def _assessed_count(inputs: ReportInputs) -> int:
    return sum(
        1
        for candidate in inputs.run.candidates.candidates
        if candidate.status is CandidateStatus.ASSESSED
    )


def _title(inputs: ReportInputs, nct_id: str) -> str:
    trial = inputs.trial_for(nct_id)
    return trial.brief_title if trial else ""


# --- section 6 ---------------------------------------------------------------


def _criterion_tables(inputs: ReportInputs) -> str:
    blocks = "".join(
        _trial_block(inputs, assessment) for assessment in inputs.run.trial_assessments
    )
    body = f"""
<p>Every criterion of every assessed trial, including the ones the system could not
answer. Nothing is dropped: a criterion with no usable evidence is reported as Unknown
with the reason it could not be resolved, which is what tells a coordinator whether to go
and look.</p>
{blocks}
{_disclaimer()}
"""
    return _section("s6", "6. Every criterion, per trial", "collapsed by default", body)


def _trial_block(inputs: ReportInputs, assessment: TrialAssessment) -> str:
    trial = inputs.trial_for(assessment.nct_id)
    by_id = {criterion.criterion_id: criterion for criterion in trial.criteria} if trial else {}
    rows = "".join(
        _criterion_row(criterion, by_id.get(criterion.criterion_id))
        for criterion in assessment.criteria
    )
    return f"""<details><summary>{esc(assessment.nct_id)} — {esc(_conclusion_words(assessment))}
({_counts_cell(assessment)})</summary>
<table><thead><tr><th>Criterion</th><th>Polarity</th><th>State</th><th>Impact</th>
<th>Source text</th></tr></thead><tbody>{rows}</tbody></table></details>"""


def _criterion_row(criterion: CriterionAssessment, authored: EligibilityCriterion | None) -> str:
    text = esc(authored.source_text) if authored else ""
    if isinstance(criterion, SkippedCriterion):
        return (
            f"<tr><td><code>{esc(criterion.criterion_id)}</code></td>"
            f"<td>{esc(criterion.polarity.value)}</td>"
            f"<td>Not assessed <span class='enum'>reporting status, not a state</span></td>"
            f'<td class="mark neutral">{NOT_ASSESSED_MARK} not assessed</td>'
            f"<td>{text}</td></tr>"
        )
    reason = (
        f" <span class='enum'>{esc(criterion.unknown_reason.value)}</span>"
        if isinstance(criterion, AssessedCriterion) and criterion.unknown_reason
        else (
            " <span class='enum'>expression_unavailable</span>"
            if isinstance(criterion, UnexpressedCriterion)
            else ""
        )
    )
    return (
        f"<tr><td><code>{esc(criterion.criterion_id)}</code></td>"
        f"<td>{esc(criterion.polarity.value)}</td>"
        f"<td>{esc(STATE_LABEL[criterion.state])}"
        f" <span class='enum'>{esc(criterion.state.value)}</span>{reason}</td>"
        f"<td>{_impact(criterion.impact)}</td>"
        f"<td>{text}</td></tr>"
    )


def _impact(impact: CriterionImpact) -> str:
    return f'<span class="mark {impact.value}">{IMPACT_MARK[impact]} {esc(impact.value)}</span>'


def _impact_legend() -> str:
    marks = " · ".join(f"{IMPACT_MARK[impact]} {impact.value}" for impact in IMPACT_MARK)
    return (
        f"Shape and colour encode impact on the match, never the criterion state: "
        f"{marks} · {NOT_ASSESSED_MARK} not assessed."
    )


# --- section 7 ---------------------------------------------------------------


def _timeline(inputs: ReportInputs) -> str:
    timeline = inputs.timeline
    facts = "".join(_fact_row(fact) for fact in timeline.facts)
    exposures = "".join(_fact_row(exposure) for exposure in timeline.exposures)
    unsupported = "".join(
        f"<tr><td><code>{esc(item.resource_type)}/{esc(item.resource_id)}</code></td>"
        f"<td colspan='3'>{esc(item.reason.value)}</td>"
        f"<td><code>{esc(item.json_path)}</code></td></tr>"
        for item in timeline.unsupported_content
    )
    body = f"""
<p>Every fact the system could read, with the resource it came from and the path inside
the Bundle. The last block is content the system met and did not interpret — it is listed
so that "the parser skipped it" cannot look the same as "the record never mentioned
it".</p>
<details><summary>Facts and exposures
({len(timeline.facts) + len(timeline.exposures)})</summary>
<table><thead><tr><th>Fact</th><th>Status</th><th>Value</th><th>Clinical time</th>
<th>Path</th></tr></thead><tbody>{facts}{exposures}</tbody></table></details>
<details><summary>Not interpreted ({len(timeline.unsupported_content)})</summary>
<table><thead><tr><th>Resource</th><th colspan="3">Why</th><th>Path</th></tr></thead>
<tbody>{unsupported}</tbody></table></details>
"""
    return _section(
        "s7",
        "7. The patient timeline",
        f"{esc(timeline.scenario_id)} · normalization {esc(timeline.normalization_version)}",
        body,
    )


def _fact_row(item: TimelineFact | MedicationExposure) -> str:
    coding = item.code if isinstance(item, TimelineFact) else item.medication
    value = ""
    if isinstance(item, TimelineFact) and item.value is not None:
        value = (
            item.value.text
            if item.value.kind == "coded"
            else f"{item.value.comparator or ''}{item.value.value} {item.value.unit or ''}"
        )
    when = ""
    if item.time is not None:
        when = f"{item.time.start} ({item.time.start_precision.value})"
    return (
        f"<tr><td><code>{esc(item.fact_id)}</code><br>"
        f"<span class='enum'>{esc(item.display)} [{esc(coding.code)}]</span></td>"
        f"<td>{esc(item.status)}</td><td>{esc(value)}</td><td>{esc(when)}</td>"
        f"<td><code>{esc(item.json_path)}</code></td></tr>"
    )


# --- section 8 ---------------------------------------------------------------


def _results(inputs: ReportInputs) -> str:
    results = inputs.results
    if results is None:
        return _section("s8", "8. Across the scenario set", "not computed for this build", "")
    invariants = "".join(
        f"<tr><td>{esc(row.name)}</td>"
        f'<td class="{"pass" if row.passed else "fail"}">{"pass" if row.passed else "FAIL"}</td>'
        f"<td>{esc(row.detail)}</td></tr>"
        for row in results.invariants
    )
    counts = "".join(
        f"<tr><td>{esc(row.label)}</td><td>{esc(row.agent)}</td>"
        f"<td>{esc(row.baseline or '—')}</td>"
        f"<td><span class='enum'>{esc(row.note or '')}</span></td></tr>"
        for row in results.counts
    )
    failures = "".join(f"<li>{esc(item)}</li>" for item in results.worked_failures)
    body = f"""
<p><strong>This section is not a fact about the run above it.</strong> It is a count
across the whole scenario set, which is a different kind of claim, and it is here rather
than in a second document because two artifacts for one demonstration cost a reader more
than the separation buys.</p>
<h3 class="mono">Release gates</h3>
<p class="enum">Deterministic properties the implementation controls. Pass or fail, not a
percentage: one violation is a failure.</p>
<table><thead><tr><th>Invariant</th><th>Result</th><th>Detail</th></tr></thead>
<tbody>{invariants}</tbody></table>
<h3 class="mono">Reported counts</h3>
<table><thead><tr><th>Measure</th><th>Agent</th><th>One-shot baseline</th><th>Note</th>
</tr></thead><tbody>{counts}</tbody></table>
<p class="enum">{esc(results.sample_sentence)}</p>
{_block("Worked failures", failures)}
{_disclaimer()}
"""
    return _section("s8", "8. Across the scenario set", "run-independent", body)


# --- sections 9 and 10 -------------------------------------------------------


def _cost(inputs: ReportInputs) -> str:
    rows = "".join(
        f"<tr><td><code>{esc(assessment.nct_id)}</code></td>"
        f"<td>{assessment.measurements.model_calls}</td>"
        f"<td>{assessment.measurements.prompt_tokens}</td>"
        f"<td>{assessment.measurements.completion_tokens}</td>"
        f"<td>{assessment.measurements.latency_ms}</td></tr>"
        for assessment in inputs.run.trial_assessments
    )
    total = inputs.run.measurements
    body = f"""
<p>What the run spent, beside what it bought. Published including when the ratio is
unfavourable.</p>
<table><thead><tr><th>Trial</th><th>Model calls</th><th>Prompt tokens</th>
<th>Completion tokens</th><th>Latency (ms)</th></tr></thead><tbody>{rows}
<tr><td><strong>run</strong></td><td>{total.model_calls}</td>
<td>{total.prompt_tokens}</td><td>{total.completion_tokens}</td>
<td>{total.latency_ms}</td></tr></tbody></table>
"""
    return _section("s9", "9. What the run cost", "per trial assessment", body)


def _reproducibility(inputs: ReportInputs) -> str:
    run = inputs.run
    identities = run.identities
    configuration = run.configuration
    warnings = "".join(
        f"<li><code>{esc(item.code)}</code> {esc(item.detail)}</li>" for item in run.warnings
    )
    failures = "".join(
        f"<li><code>{esc(item.kind.value)}</code> {esc(item.detail)}</li>" for item in run.failures
    )
    rows = _definition_rows(
        (
            ("run id", run.run_id),
            ("scenario", identities.scenario_id),
            ("bundle sha256", identities.bundle_sha256),
            ("snapshot", identities.snapshot_id),
            ("snapshot sha256", identities.snapshot_sha256),
            ("assessment as of", identities.assessment_as_of),
            ("partition", identities.partition.value),
            ("model adapter", configuration.model.adapter.value),
            ("model", f"{configuration.model.model_id} ({configuration.model.revision})"),
            (
                "decoding",
                f"temperature {configuration.model.temperature}, top_p {configuration.model.top_p}",
            ),
            ("prompt version", configuration.model.prompt_version),
            ("schema version", configuration.model.schema_version),
            ("tool version", configuration.tool_version),
            ("evaluator version", configuration.evaluator_version),
            ("supervisor", _supervisor(run)),
            ("seed", configuration.seed),
            ("hardware", configuration.hardware_profile),
        )
    )
    body = f"""
<table><tbody>{rows}</tbody></table>
{_block("Warnings", warnings)}
{_block("Infrastructure failures", failures)}
<p class="enum">Infrastructure failures are recorded here and are never scored as
uncertainty about a patient.</p>
"""
    return _section("s10", "10. Reproducibility", "identities, hashes, frozen versions", body)


def _block(title: str, items: str) -> str:
    if not items:
        return ""
    return f'<h3 class="mono">{esc(title)}</h3><ol class="calls">{items}</ol>'


def _supervisor(run: MatchingRun) -> str:
    supervisor = run.configuration.supervisor
    return (
        f"order_criteria {'on' if supervisor.order_criteria else 'off'}, "
        f"early_termination {'on' if supervisor.early_termination else 'off'}"
    )


def _definition_rows(rows: Iterable[tuple[str, object]]) -> str:
    return "".join(
        f"<tr><th>{esc(label)}</th><td><code>{esc(value)}</code></td></tr>" for label, value in rows
    )


def _find_criterion(
    inputs: ReportInputs,
) -> tuple[EligibilityCriterion, AssessedCriterion] | None:
    for assessment in inputs.run.trial_assessments:
        trial = inputs.trial_for(assessment.nct_id)
        if trial is None:
            continue
        for criterion in assessment.criteria:
            if criterion.criterion_id != inputs.demonstrative_criterion_id:
                continue
            if not isinstance(criterion, AssessedCriterion):
                return None
            authored = next(
                item for item in trial.criteria if item.criterion_id == criterion.criterion_id
            )
            return authored, criterion
    return None
