# ADR 0014: Cut the research-grade evaluation protocol and candidate retrieval

**Status:** Accepted, 2026-08-24. Supersedes ADR 0008 in part and ADR 0010 entirely.

This project exists to show that its author can build an agent. Around that, v6 of the specification had grown an evaluation protocol built for a different purpose: a pre-registered two-sided test against three baselines, cluster-level bootstrap resampling over scenario-trial pairs, a precision amendment committed before the held-out run, a falsification condition as the published headline, and a separate benchmark artifact to carry the result. Alongside it sat a hybrid retrieval stack — BM25, local embeddings, reciprocal-rank fusion, candidate filters — over a corpus of two to five hundred trials.

Every one of those decisions was defensible on its own terms, and none of them demonstrates tool selection, controlled reasoning, evidence verification, or bounded failure recovery. They demonstrate familiarity with experimental method and with retrieval engineering, which are different claims, and they were the largest remaining share of the work: eleven of the twenty-seven unbuilt tickets.

They are cut. Retrieval goes entirely; the candidate set is the four frozen trial records. Inferential statistics go entirely; reported results are counts and percentages over stated denominators with the sample size shown. Three baselines become one. Two artifacts become one. Evidence Reuse goes, because measuring the error propagation it introduces was the expensive half of the feature.

## Why this is not a loss of rigour

The rigour that mattered is the part that is cheap and stays: gold labels derived by code from hidden manifests rather than judged by a model, release gates restricted to deterministic invariants, the verifier's two roles kept apart, a held-out pair of trials and scenarios assessed once at the end, and every reported number published as it came out.

What goes is the apparatus for claiming a *statistically supported* difference between two architectures. At forty scenario-trial pairs that claim was never available: v6 said as much itself, predicting no detectable accuracy difference and pre-committing to publish the null. An interval computed to demonstrate that it is too wide to be useful is ceremony. Saying "twelve of fourteen, on six scenarios and four trials, and that is too few to generalise from" is the same information, in a sentence a reader can check.

## Why retrieval in particular

Retrieval was already marked additive with a documented fallback, and the fallback is what the core path has used since Gate 1. Building it would add a second corpus, an embedding model, a fusion rule, and per-channel provenance to the report — and the criterion agent, which is the subject, would behave identically. A reader who wants to see hybrid retrieval has thousands of examples to look at; the thing this project has that they do not is a verifier that rejects a citation and an agent that has to answer for it.

## What was considered instead

Keeping retrieval and cutting the agent's verifier work was never on the table: it inverts the claim. Keeping the statistics and cutting the report was rejected because an unseen result is not a portfolio result. Keeping everything and shipping later was rejected on the evidence of the schedule: seven tickets took the time they took, and twenty-seven more at that rate is not a portfolio piece, it is an unfinished one.

## Consequence

Specification v7 records the cut. Issues #21, #22, #23, #24, #31, #35, #37, #38, #39, #43 and #44 are closed as descoped rather than left open, so the tracker stops implying work that will not happen. The remaining path is: authored scenarios, the verifier, the agent loop with one correction, `match()`, deterministic grading against one baseline, and one report.
