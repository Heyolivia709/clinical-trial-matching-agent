"""What a Timeline Tool found, as the situation the section 8.0 table reads.

Without this step every caller decides for itself what "the tool found nothing"
means, and the decisions drift. A retracted PD-L1 result is the case to keep in
view: `find_patient_facts` returns it under `disqualified` with `qualifying`
empty, and a caller that only counts `qualifying` reports `missing_evidence` —
"nobody tested this patient" — about a patient who was tested and whose result
was withdrawn. The coordinator reading the first goes and orders the test; the
second sends them to the pathology report that is already there.

So the translation happens once, here, and the section 8.0 table stays the only
thing that names a reason.
"""

from __future__ import annotations

from ctma.agent.unknown_reason import EvidenceSituation
from ctma.domain.enums import CriterionCategory
from ctma.domain.expression import TemporalWindow
from ctma.timeline.tools import ExposureQuery, FactQuery, LatestObservation

ToolResult = FactQuery | LatestObservation | ExposureQuery


def situation_from(
    result: ToolResult,
    *,
    category: CriterionCategory,
    window: TemporalWindow | None = None,
) -> EvidenceSituation:
    """Summarize one tool result for the Unknown Reason table.

    `window` is the authored window the proposition carries, and it is read for
    one thing only: whether the criterion's anchor can be resolved at all. A
    window naming "the first dose of study drug" with no declared substitution
    describes an event that has not happened, so whatever the lookup returned
    was placed against an anchor nobody authorized, and the proposition is
    `ambiguous_criterion` rather than anything the facts could say.
    """
    if window is not None and not window.anchor_is_resolvable:
        return EvidenceSituation(category=category, anchor_was_not_operationalized=True)
    if not result.mapped:
        return EvidenceSituation(category=category, concept_is_not_in_the_mapping=True)

    match result:
        case FactQuery():
            return EvidenceSituation(
                category=category,
                qualifying_facts=len(result.qualifying),
                facts_with_disqualifying_status=len(result.disqualified),
            )
        case LatestObservation():
            conflicting = len(result.conflicting)
            return EvidenceSituation(
                category=category,
                qualifying_facts=conflicting or int(result.latest is not None),
                qualifying_facts_conflict=conflicting > 0,
                facts_with_disqualifying_status=len(result.disqualified),
            )
        case ExposureQuery():
            return _from_exposure(result, category)


def _from_exposure(result: ExposureQuery, category: CriterionCategory) -> EvidenceSituation:
    """An exposure query, which carries the window findings the others do not.

    `orders_only` says the record holds an order for the drug and no
    administration, and it is the boundary row of the table — but only when
    there is nothing inside the boundary to look at. A `not-done`
    administration alongside the order is a fact with a disqualifying status,
    and it is a better account of why the proposition did not resolve than the
    order is.
    """
    qualifying = len(result.matched) + len(result.outside_window) + len(result.undecidable)
    return EvidenceSituation(
        category=category,
        only_candidate_facts_are_outside_the_boundary=result.orders_only
        and not result.disqualified,
        qualifying_facts=qualifying,
        facts_with_disqualifying_status=len(result.disqualified),
        precision_is_coarser_than_required=bool(result.undecidable) and not result.matched,
        qualifying_facts_are_all_out_of_window=bool(result.outside_window)
        and not result.matched
        and not result.undecidable,
    )
