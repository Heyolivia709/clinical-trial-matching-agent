# Post-MVP Dependency-Ordered Implementation Sequence

**Status:** Frozen sequence
**Scheduling rule:** No calendar estimates. Progression depends only on acceptance criteria.
**Precondition:** MVP Gates 1 through 7 complete, with the Evaluation Report published.

Gate numbering continues the MVP sequence in [`phase-1-implementation-sequence.md`](phase-1-implementation-sequence.md). Nothing here reorders or reopens Gates 1 through 7.

## Relationship to the MVP

The specification in [`../specs/phase-1-mvp-specification.md`](../specs/phase-1-mvp-specification.md) stays frozen. Post-MVP work adds no Criterion State, no Unknown Reason, no truth-table change, and no reporting status. It does not reopen a held-out partition, and it never restates an MVP result as its own.

Every gate below is either a variant behind an interface the specification already defines, or a surface the specification already declared optional. Nothing replaces an MVP baseline without a measured reason.

## The Post-MVP Question

The MVP asks whether a bounded agent loop produces more trustworthy grounded assessments than one model call, and whether that is worth its cost.

Post-MVP asks three narrower questions the MVP left open by design:

1. Does the structural defense the verifier provides hold against adversarial trial text, which the MVP accepts into model context but never attacks?
2. Is plain typed Python actually the right orchestration baseline, given that specification section 16 calls it a baseline and never compares it to one?
3. Does the optional live mode of specification section 15.3 work, given that it sits at the bottom of the cut list and will likely be cut?

## Admission Filter

A component enters this sequence only if it answers a question the project already owes an answer to. A component that only demonstrates familiarity with a named technology is rejected, and the rejection is recorded rather than left implicit.

Each gate below names the specification section that owes the answer. Rejected candidates are listed at the end with their reasons.

The core and additive classification of specification section 19 is deliberately not used here. It is defined against the MVP's claim, and no gate below is required for that claim: the MVP is complete and honest with none of them built. Under pressure, cut in reverse order — Gate 11, then 10, then 8 — and keep Gate 9, which is the only one that tests a property the MVP already asserts.

## Gate 8: Live Mode as a Deployed Service

Specification section 15.3 permits an optional live mode that runs a new patient-trial pair and produces a Trace Report. Section 19 places it fourth in the cut order, so the MVP will most likely ship without it. Gate 8 builds it.

The service is a typed HTTP transport over `match(patient, snapshot)`, containerized, built in CI. It performs validation and serialization only; no domain logic moves into it. The static Trace Report and Evaluation Report remain the primary delivery surface, and [ADR 0007](../adr/0007-deliver-a-static-trace-report.md) stands: this is an operational envelope for a single run, not a replacement demonstration surface.

**Exit criteria**

- A live run produces a Trace Report byte-identical to the offline generator's output for the same scenario, snapshot, and `assessment_as_of`
- `tests/test_architecture.py` forbids the transport package from being imported by any reasoning module, and the domain suite passes with the transport absent
- Input is restricted to bundled synthetic scenarios and explicitly declared synthetic Bundles; any other input is refused at the boundary, with a test per refusal path
- The container runs report generation with no network fetch, matching the section 15.3 offline constraint
- No credential, PHI, or free-text patient path exists anywhere in the surface

## Gate 9: Adversarial Trial Text

Criterion source text is third-party content that reaches model context verbatim, and specification section 15.3 requires it stay verbatim. The MVP's injected-fault fixtures in Gate 4 attack the *citation*: fabricated resource IDs, altered values, a `MedicationRequest` cited as exposure. None of them attacks the *prompt*.

The verifier should already bound this class of attack, because an assessment whose citations do not verify degrades to `unknown` with `verification_failed` regardless of why the model produced it. That is a structural claim the MVP never tests. Gate 9 tests it, and reports what the defense costs.

**Exit criteria**

- Fixtures place instruction-like content inside criterion source text, covering at minimum: a directive to return a specific Criterion State, a directive to skip a criterion, a directive to cite a named resource, a directive to ignore the expression, and content impersonating system or verifier output
- No fixture changes a Criterion State, produces an unsupported assessment surviving verification, suppresses a criterion from output, or reduces Criterion Coverage below 100% with supervisor flags off
- No fixture causes a citation to a resource outside the evidence-bearing boundary to survive verification
- Every injection attempt is visible in the Reasoning Trace, attributable to the criterion ordinal and span it came from
- The verification-induced `unknown` rate under injection is reported beside the clean-run rate, per the pairing rule in pre-registration section 4.2
- Trial source text stays verbatim in output; no fixture is sanitized, rewritten, or truncated to pass
- Injection attempts scored as semantic `unknown` rather than as an attack: zero. They are reported as their own category

## Gate 10: Orchestration Variant — LangGraph

Specification section 16 names plain typed Python the orchestration baseline and places LangGraph out of scope. Calling something a baseline without ever comparing it leaves the choice unexamined. Gate 10 implements the comparison.

The variant implements `assess(timeline, trial) -> TrialAssessment` with no interface change, the same five Timeline Tools, the same prompts, the same model adapter and decoding, the same verifier, the same single-correction bound, and the same supervisor flags.

**The primary result is behavioral equivalence and cost, not accuracy.** Reimplementing the same logic in a graph runtime should produce the same assessments; if it does not, that is a defect to explain rather than a finding. Accuracy differences at this cluster count are unresolvable — see [`../evaluation/post-mvp-evaluation-addendum.md`](../evaluation/post-mvp-evaluation-addendum.md).

**Exit criteria**

- Both implementations pass the Gate 1 and Gate 4 suites with identical fixtures and identical results
- With supervisor flags off and a fixed seed against the frozen-replay model adapter, the two implementations produce identical Proposition Assessments, identical aggregation, and identical Unknown Reasons; any divergence is enumerated and explained
- Tokens, model calls, and wall-clock latency are reported per criterion assessment for both, per pre-registration section 4.4
- Lines of code, dependency count, and trace fidelity are reported for both
- The result is published including when it is a null result or unfavourable to the variant. Replacing the plain-Python baseline requires a reason stated in an ADR

## Gate 11: Multi-Agent Variant

Specification section 18 places multi-agent orchestration out of scope, and [ADR 0006](../adr/0006-gate-multi-turn-behavior-behind-flags.md) established the pattern for admitting a multi-turn behavior: make it a flag, measure the delta, publish it as an ablation row. Gate 11 applies that pattern to decomposition.

The decomposition follows the five supported Criterion Categories of specification section 6 — `demographic`, `disease`, `biomarker`, `prior_therapy`, `performance_status` — with a coordinator that routes Atomic Propositions by category and collects Proposition Assessments. Propositions in the `unsupported` category route nowhere and resolve as they do today.

Deterministic aggregation is unchanged and stays outside every agent. The coordinator does not choose a Criterion State, does not perform Boolean aggregation, and does not aggregate across criteria.

**Exit criteria**

- No agent performs Boolean aggregation, arithmetic, unit comparison, or date arithmetic; enforced by the same tests that hold this for the single-agent path
- Category routing is deterministic given a fixed configuration, and routing accuracy against the authored category labels is reported
- Token, model-call, and latency deltas are reported per criterion assessment against the single-agent path at equal budget
- Coordinator overhead is reported separately from specialist cost
- Accuracy is reported per Criterion Category with intervals and realised cluster counts, and differences below the committed precision band are labelled inconclusive
- The published result states whether the decomposition earned its cost, including when it did not

## Optional Gates

These run only after Gates 8 through 11 and carry no claim.

### Gate 12: Tool Transport over MCP

Specification section 18 places MCP out of scope. The five Timeline Tools are already typed and read-only, so exposing them over MCP tests one narrow property: whether that tool surface is a real interface or five Python functions with a table around them.

This gate makes no claim about agent quality and produces no benchmark row. Read-only tools only; no write tool, no action execution, no Scenario Manifest access.

**Exit criteria**

- An external client reproduces a Proposition Assessment's tool-call sequence and results through the MCP interface alone
- The `evaluation` package remains the only package permitted to read a Scenario Manifest, per the layering test
- Zero write or action-executing tools exposed

### Gate 13: Second Retrieval Index Backend

Specification section 12 states that the retrieval index sits behind a single interface so a larger backend can replace the in-process implementation without touching callers. That seam currently has one implementation, which makes it an untested claim. This gate adds a second and reports whether any caller changed.

Requires Gate 3 to have been built. Exit when retrieval results are identical across backends for every scenario, per-channel ranks and scores included, and no caller outside the retrieval module changed.

## Rejected

- **Experiment-tracking tooling such as MLflow.** Run metadata, hashes, seeds, configuration versions, and cost are already recorded per specification section 14, and reproducibility is already enforced by the pre-registration commit-hash obligation. A tracking service would re-house existing records without changing a result or answering a question.
- **Knowledge-graph or GraphRAG retrieval.** See [ADR 0012](../adr/0012-reject-knowledge-graph-retrieval.md).
- **Cross-run agent memory.** See [ADR 0013](../adr/0013-reject-cross-run-agent-memory.md).
- **A hosted model adapter as new work.** Specification section 16 already places hosted inference behind the model adapter and permits headline results from a hosted model. There is nothing to add.
- **A second agent framework beyond LangGraph.** Gate 10 answers whether the orchestration runtime matters. Repeating it with another framework answers the same question again.
- **A retrieval framework wrapper such as LlamaIndex.** The retrieval pipeline is the artifact under evaluation in Gate 3; wrapping it removes the part being measured.
- **A vector database as a dependency.** Specification section 18 excludes PostgreSQL and pgvector. Gate 13 exercises the index seam without adding a service dependency.
- **Budget-triggered early termination.** This is a fourth member of the Trial Supervisor flag family in specification section 11, not a separate gate, and `not_assessed` already covers the reporting status. If it is built, it belongs to Gate 5.

## Completion

Post-MVP work is complete when Gates 8 through 11 have passed, each comparison is published with its cost figures and its stated power limitation, and every MVP result remains byte-identical to its original publication.
