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

## The protocol, ready to run

Everything the check needs except the person. Hand them the link, start a timer,
and say nothing else — a prompt from the person holding the stopwatch is the
fastest way to invalidate the result.

**The brief, read aloud once:** "This is a page about a software system. Read it
however you like for five minutes, then tell me what the system does and what
you saw it do. There is no wrong answer, and I am not going to help you."

**The tick sheet.** Mark each item found, and write the wording the reader used
for it. Their words matter more than the tick: "it checks its own homework" is a
better outcome for item 7 than someone reading the phrase *evidence verifier*
back off the page.

| | Item | Found | What they called it | Time |
| --- | --- | --- | --- | --- |
| 1 | A patient timeline where every fact says where it came from | | | |
| 2 | Which trials were considered, and which were assessed | | | |
| 3 | One requirement broken into smaller checkable statements | | | |
| 4 | The system deciding what to look up, and looking it up | | | |
| 5 | Dates and numbers compared by code rather than by the model | | | |
| 6 | A judgment that points at both a patient fact and trial wording | | | |
| 7 | Something catching a bad answer and forcing a retry | | | |
| 8 | A comparison against a simpler system given the same problem | | | |

**Also record, because these are the findings that change the page:**

- Where they stopped, if they stopped before five minutes.
- Anything they read as a claim the project does not make — a match score, a
  clinical recommendation, a real patient.
- Any term they had to guess at. Every one of those is a rewrite.
- Whether they scrolled past sections 2 to 4 to reach the setup. If they did,
  verdict-first ordering did not work and the fix is layout, not vocabulary.

Write the result into the section below whether or not it is flattering.

## Result

Not yet run.

## Publishing

The reports are generated into `docs/demo/`, with a landing page at
`docs/index.html`:

```
uv run python scripts/build_reports.py docs/demo
```

GitHub Pages serves `docs/` from the default branch. `.nojekyll` is present so
the HTML is served exactly as generated rather than passed through a site
builder.

The pages are self-contained either way: opening `docs/index.html` from a local
checkout gives exactly what the hosted copy does.
