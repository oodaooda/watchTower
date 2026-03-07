# ADR-0002: LLMs Are Advisory, Deterministic Paths Stay Canonical

- Status: Accepted
- Date: 2026-02-28
- Owners: watchTower engineering

## Context

watchTower uses LLMs for QA, planning, synthesis, and modeling support. Those workflows touch financially sensitive outputs and cannot rely on unvalidated free-form generations.

The key architectural choice is whether LLM outputs are authoritative or whether deterministic code paths remain canonical.

## Decision

LLMs are advisory only. Deterministic code paths remain canonical for final system behavior.

This requires:

- Structured outputs with schema validation
- Guardrails for SQL planning and execution
- Deterministic fallbacks when model output is invalid or unavailable
- Logging of requests, responses, tokens, errors, and cost where applicable
- Explicit separation between grounded database claims and general-context commentary

## Consequences

- The system is more reliable and auditable.
- Product behavior remains stable even when model quality varies.
- More implementation work is required for validators, traces, and fallbacks.
- Some user requests may return partial or clarification-needed responses instead of speculative answers.

## Alternatives Considered

- Let the LLM produce final answers without strict validation: rejected due to accuracy, traceability, and financial-risk concerns.
- Limit LLM use to non-user-facing internal tools only: rejected because the product already benefits from QA and synthesis features, but only with explicit controls.
