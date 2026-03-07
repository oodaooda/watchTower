# Spec: LLM Usage and Cost Observability

## Purpose

Track LLM usage, token consumption, errors, cache behavior, and estimated cost across watchTower features.

## Scope

- Usage event persistence
- Model pricing configuration
- Usage summary APIs
- Usage UI

## Goals

- Make LLM spend visible by feature and model
- Support near-real-time operational monitoring
- Allow pricing updates without code changes

## Non-Goals

- Full billing-system replacement
- Provider-side reconciliation
- Forecasting future spend from incomplete usage data

## Core Contracts

- Every LLM call persists a usage event when instrumentation is available.
- Pricing is stored by model and used for deterministic cost calculation.
- Summary APIs expose interval rollups and model breakdowns.
- Pricing APIs are secured.

## Key Outputs

- Total cost
- Total tokens
- Request counts
- Cache hit or related provider telemetry where available
- Time-bucketed trends
- Model-level cost breakdown

## Risks

- Missing instrumentation on new call paths
- Stale pricing leading to inaccurate cost estimates
- Manual UI verification lagging behind backend instrumentation changes
