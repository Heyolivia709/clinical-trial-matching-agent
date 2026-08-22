# Explorations

Rejected and superseded design alternatives, retained because the reasoning is part of the record.

## Criterion detail — direction A versus B

Two treatments of the most important section were built and compared. Both encoded impact with colour and shape while leaving state as text, both marked trial source text as authoritative and verbatim, and both rendered a planted distractor correctly — the tool call that finds a `MedicationRequest` and reports it as unsupported content because order intent is not exposure.

**Direction A was selected.** Three reasons:

1. **No colour collisions.** Direction B assigned `unresolved` a blue in the same hue family as its link colour, so the channel encoding "evidence insufficient" was also the interactive channel. B also gave the verifier panel the same red as `blocking`, merging "counts against the match" with "the verifier rejected something" into one signal. A kept links, impact, and process state visually disjoint.
2. **A carried the teaching sentence.** "met exclusion counts against a match" states the system's most counter-intuitive rule at the point of confusion. B had no equivalent and left the reader to infer it.
3. **A framed the verifier by outcome.** A showed `PASS · after 1 correction` and put the rejection detail below. B's panel header read `verifier rejected 1 citation`, which is more arresting but misstates the final state.

Three elements were ported from B into A: the four-cell summary strip beneath the title, a highlight on the operative phrase in the trial source text using a colour outside the impact palette, and higher-contrast table headers.

Both files are kept: A as the accepted structure, B for the collisions it demonstrates.

## Superseded visual register

Direction A was built in a journal-article register — serif headings, `§` section marks, cream paper ground, a methods-style framing paragraph per section. This overshot the brief, which asked for an engineering archive.

The target register is now an agent trace inspector. See [ADR 0009](../../adr/0009-adopt-the-trace-inspector-visual-register.md). The structural and semantic decisions in both files survive that change; the typography and surface treatment do not.

## Not retained

A stitched continuity file rendering §5–§7 back to back was used during design to expose repeated headings and broken hierarchy across section boundaries. It was a process check rather than a deliverable and is not committed. The same check should be repeated whenever section structure changes.
