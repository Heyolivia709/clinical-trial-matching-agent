# Keep the MVP read-only and cognition-focused

The MVP is restricted to read-only candidate retrieval, criterion reasoning, evidence grounding, and evaluation. Action execution, authorization, approval flows, HITL, idempotency, durable state, MCP, generic agent harnesses, LangGraph, and multi-agent orchestration are excluded because they would duplicate DTSS signals or displace the benchmark-first cognition work that this project exists to demonstrate.

Revised 2026-08-22: the original decision also excluded all UI work. A read-only static trace report is now in scope, because a result no reviewer sees is not a portfolio result. See ADR 0007. The exclusion still holds for interactive workflow, chat, authoring, and any write-capable interface.
