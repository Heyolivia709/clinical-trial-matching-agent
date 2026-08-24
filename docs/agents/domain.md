# Domain Docs

How the engineering skills consume this repo's domain documentation. `AGENTS.md` states the rules that bind humans and agents alike; this file only adds what a skill needs on top of them.

## Before exploring, read these

`AGENTS.md` already requires `CONTEXT.md` and `docs/specs/phase-1-mvp-specification.md` before any change to MVP behaviour, and it already binds identifiers to the glossary. Read both. Then add:

- **`docs/adr/`**: the ADRs touching the area you are about to work in. Several of them are rejections, so an idea that looks new may already have been declined with a reason.
- **`docs/plans/`** for gate sequencing and **`docs/evaluation/`** for the pre-registration and the benchmark plan, when the work touches either.

If a file above does not exist, proceed silently. Do not flag its absence or propose creating it upfront. `/domain-modeling` creates these lazily, when a term or a decision actually gets resolved.

## File structure

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root, over `src/ctma/`.

A root `CONTEXT-MAP.md` would signal a move to per-context glossaries. There is none, and one package per deep module under `src/ctma/` is not a reason to add one.

## Flag conflicts rather than overriding

If your output contradicts an ADR, say so instead of quietly winning:

> _Contradicts ADR 0004 (hand-author criterion expressions), but worth reopening because…_

If it contradicts the specification, that is a specification change and not an implementation detail. `AGENTS.md` requires recording it explicitly rather than introducing it during implementation.
