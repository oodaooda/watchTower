# Spec: OpenClaw API Integration

## Purpose

Expose watchTower QA capabilities to OpenClaw through a controlled, read-only HTTP integration.

## Scope

- `POST /openclaw/qa`
- Auth and access controls
- Response compatibility for QA and news-backed answers
- Settings UI and API-key lifecycle expectations

## Goals

- Allow OpenClaw to invoke watchTower QA over HTTP only
- Prevent direct database access from external systems
- Enforce authentication and basic abuse controls

## Non-Goals

- Bidirectional syncing
- Shared database access
- Unauthenticated internal-only shortcuts

## Core Contracts

- Requests require Bearer token authentication.
- IP allowlisting is supported where configured.
- Rate limits apply to external traffic.
- The integration remains read-only.
- Response payloads include compatible answer and news-link structures.
- OpenClaw API keys are shown in full only at creation time.
- Existing-key views expose identifying metadata only, such as name, prefix, short identifier, timestamps, and status.
- The settings admin token is write-only from the UI perspective and must not be returned by any read endpoint.

## Operational Requirements

- Keys are generated and managed through settings flows.
- Tokens come from environment-backed configuration or persisted settings controls.
- Failed auth and rate-limit events must be observable in logs.
- Settings flows must support token rotation without requiring the old secret to remain visible in the UI.
- Any UI persistence of the admin token is a development convenience only and must not redisplay the full token after save.

## Risks

- Misconfigured allowlist rules
- Token leakage
- External consumers depending on undocumented payload fields

## Security Notes

- If an admin token or API key appears in logs, screenshots, chat transcripts, or browser-visible plaintext after creation, it should be treated as compromised and rotated.
- Debugging workflows should prefer redacted summaries over full config dumps, especially for `.env`, request headers, and settings pages.
