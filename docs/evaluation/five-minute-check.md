# The five-minute check

Specification section 3 requires a reviewer opening the report to observe eight
things within five minutes. Section 15 makes that a hard constraint on the
interface rather than an aspiration, which is why the report is ordered
verdict-first: a document in pipeline order fails the constraint however
complete it is, because the reader stops before the interesting part.

This file records what has been checked, and what has not.

## Checked mechanically

`tests/test_report.py` asserts, on a generated page:

| # | Demonstration goal | Where it is |
| --- | --- | --- |
| 1 | A patient timeline with per-fact provenance | section 7 |
| 2 | Candidate selection with the assessed set visible | section 5 |
| 3 | A criterion decomposed into atomic propositions | section 2 |
| 4 | The agent choosing and calling timeline tools | section 2, tool call list |
| 5 | Dates, numbers, and aggregation handled by code | section 2, `compare_numeric` in the call list and the aggregation line |
| 6 | A structured judgment citing patient evidence and exact trial text | section 2, and the verbatim quote above it |
| 7 | The verifier rejecting a citation and triggering one correction | section 3 |
| 8 | A side-by-side comparison against a one-shot baseline | section 4 |

The same tests assert the constraints a reader would only notice when they
fail: no network fetch at view time, print styles with the disclaimer, a
persistent section index and no other chrome, colour and shape keyed to
Criterion Impact rather than Criterion State, a separate process colour for the
verifier, verbatim trial text, and no score, percentage, gauge, or rating
anywhere.

Items 3, 4, 6, 7 and 8 sit in sections 2 to 4, which is the first thing after
the plain-language summary. Items 1 and 2 are further down, in sections 5 and 7.

## Not checked

**No reader has been timed.** Section 3 asks for the eight items to be verified
against someone who has not seen the project, and that has not happened. The
mechanical check above proves the items are present and reachable; it does not
prove they are *understood*, and those are different claims.

What a real check would need: one person with no clinical or agent-engineering
vocabulary, the hosted page, a stopwatch, and a record of which of the eight
they found, which they misread, and where they stopped. The result belongs in
this file whether or not it is flattering.

## Publishing

The reports are generated into `docs/demo/`:

```
uv run python scripts/build_reports.py docs/demo
```

Hosting them is one repository setting — GitHub Pages, serving from `docs/` on
the default branch — and it has not been switched on here, because publishing is
the repository owner's call rather than the build's.

The pages are self-contained either way: opening `docs/demo/index.html` from a
local checkout gives exactly what the hosted copy would.
