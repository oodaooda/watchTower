# Spec: Data Assistant

## Purpose

The Data Assistant answers finance and company questions using grounded database results, guarded SQL, and limited general-context synthesis.

## Scope

- `/qa` endpoint behavior
- Entity resolution
- Grounded, general, and hybrid response modes
- SQL planning and traceability
- News-backed explanatory responses

## Goals

- Answer factual company questions with grounded data
- Support conceptual finance questions without forcing a ticker
- Explain why a stock moved using metrics plus relevant news context
- Show a readable execution trace for debugging and trust

## Non-Goals

- Autonomous write access to the database
- Unbounded SQL generation
- Unattributed numeric claims from general model knowledge

## Core Contracts

- Entity resolution is deterministic and confidence-scored.
- Numeric claims tied to company data must come from grounded database results.
- SQL execution is read-only, single-statement, allowlisted, row-limited, and timeout-limited.
- If planning or validation fails, the system falls back to deterministic action paths.
- Low-confidence entity matches return clarification-required behavior instead of random guessing.

## Response Shape

Responses may include:

- Answer text
- Plan summary
- Query trace
- Sources
- News citations
- Resolver diagnostics

## Risks

- Ambiguous entity names
- Incorrect metric targeting when multiple similar fields are available
- Overly broad prompts that mix conceptual and company-specific intent

## Open Follow-Ups

- Improve variable-specific targeting such as "last close price"
- Formalize intent-to-field mapping in docs
- Expand regression coverage for multi-company trace behavior
