# Adopt the trace-inspector visual register

The Trace Report is styled after agent trace inspectors — the standalone site produced by `inspect view bundle` in Inspect AI, a promptfoo HTML eval report, a Langfuse trace waterfall — rather than after an academic paper, a clinical dashboard, or a chat transcript.

The first implementation drifted into a journal-article register: serif headings, `§` section marks, a cream paper ground, and a methods-style framing paragraph per section. That was rejected. The brief asked for an engineering archive, and the paper register reads slowly, gives every element similar visual weight so no conclusion is ever foregrounded, and invites the association "this person writes papers" where "this person has debugged agents" is the one worth earning. A clinical dashboard register was rejected earlier and for a different reason: dashboards derive legibility from aggregation, and aggregation destroys exactly the per-citation traceability this artifact exists to demonstrate.

Concretely the register means monospace-dominant data with sans prose, serif reserved for nothing, verdict-first layout, status chips instead of label-value grids, disclosure rows collapsed at rest, and tool calls rendered as a span waterfall with duration bars. The waterfall carries an argument for free: the deterministic temporal check is a few milliseconds beside multi-second model calls, so routing computation out of the model becomes a visible fact rather than a claim.

Quoted trial source text keeps its distinct treatment through a label, a left rule, and a background shift rather than through a typeface, so the "verbatim, never rewritten" semantic no longer depends on serif.

The change is confined to surface treatment. Section structure, field inventory, the impact-not-state encoding rule, the separate verifier process colour, specification §7 label wording, and the single-document information architecture are all unaffected. Duration bars use a neutral tone: the process colour stays reserved for verifier and provenance signals and must not be diluted into ordinary data.
