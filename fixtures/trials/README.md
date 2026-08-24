# Frozen trial fixtures — Gate 1

Four real ClinicalTrials.gov records, frozen so the core path has trial data
before retrieval exists (specification sections 4.1 and 4.3). Loaded by
`ctma.adapters.trial_fixtures`.

| NCT | Partition | Why it is here |
| --- | --- | --- |
| [NCT07349537](https://clinicaltrials.gov/study/NCT07349537) | development | The only age criterion, and `ECOG 0 or 1` as an `any_of` |
| [NCT07185997](https://clinicaltrials.gov/study/NCT07185997) | development | The conditional criterion: an adjuvant-therapy washout that does not apply to a patient who had none |
| [NCT05920356](https://clinicaltrials.gov/study/NCT05920356) | held out | A four-part `all_of` with a nested stage `any_of`, and an actionability criterion that is out of scope |
| [NCT07100080](https://clinicaltrials.gov/study/NCT07100080) | held out | Two EGFR variants as an `any_of`, and line-of-therapy reasoning that is out of scope |

Two development and two held out, which keeps the two-axis partition of the
measurement gate intact. Together they cover all five supported Criterion
Categories, `unsupported`, and every supported expression form.

## What is frozen

Each file holds the trial metadata, the verbatim eligibility text, its SHA-256,
and one authored record per published criterion — including the criteria that are
out of scope, which are authored as `unsupported` rather than dropped.

"Every published criterion" is the honest bound. Some records publish a summary
list — NCT07185997 heads its section "Key Eligibility Criteria", and NCT07100080
ends with "Other protocol-defined inclusion/exclusion criteria apply", which is
authored as `unsupported` rather than ignored. The full protocol criteria are not
public, so the system is measured against what the record says.

Criterion spans are not stored. The adapter locates each criterion by searching
the eligibility text for its own text, so an authored paraphrase fails to load
instead of loading with a span that points at something else. The hash ties the
recorded review to a particular wording: editing the eligibility text makes the
record fail to load until it is reviewed again.

## Refreshing a record

Don't, unless the review is redone. These are frozen artifacts, and the held-out
pair must not change at all. A trial's published criteria do change over time —
that is what `last_update_posted` records, and a frozen record that quietly
tracked them could not reproduce a past run.
