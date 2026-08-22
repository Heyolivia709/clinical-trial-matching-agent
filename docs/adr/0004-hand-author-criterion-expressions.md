# Hand-author criterion expressions instead of building a parser

Criterion Expressions are hand-authored as versioned JSON for 10–12 trials, optionally AI-drafted and always human-reviewed. Building an automatic criterion parser was rejected: the subject under test is how the runtime agent finds, cites, and verifies evidence, not how well a model parses clinical prose. A parser would have consumed a large share of the budget and produced an NLP result rather than an agent-engineering result.

The cost is that criterion interpretation quality is an authored input rather than a measured capability, so the project makes no parsing claim. The coupling risk is that retrieval configuration determines which trials need expressions, so retrieval is frozen before authoring, and any trial without an authored expression reports `expression_unavailable` rather than disappearing from output.
