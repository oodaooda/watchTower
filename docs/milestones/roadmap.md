# watchTower Roadmap

This roadmap tracks feature milestones at a high level.

Detailed implementation tasks belong in milestone checklist files under `docs/milestones/` using `M###_slug` naming.

## Milestone Index

- `M001` - Earnings Call Transcripts (`in_progress`)
  - Spec: `../specs/M001_earnings-call-transcripts.md`
  - Checklist: `M001_earnings-call-transcripts-checklist.md`
  - Current focus: follow-up transcript query reliability via conversation context and resolver hardening
- `M002` - Multi-Asset Portfolio Tracking (`planned`)
  - Spec: `../specs/multi-asset-portfolio.md`
  - Checklist: `M002_multi-asset-portfolio-checklist.md`
  - Current focus: expand watchlist support to ETFs, then add position-level portfolio tracking and portfolio-aware QA
- `M003` - Portfolio Lots and Bulk Import (`planned`)
  - Spec: `../specs/portfolio-lots-import.md`
  - Checklist: `M003_portfolio-lots-import-checklist.md`
  - Current focus: allow duplicate ticker lots, grouped summaries, and replace-on-import onboarding
- `M004` - EOD Price History (`planned`)
  - Spec: `../specs/eod-price-history.md`
  - Checklist: `M004_eod-price-history-checklist.md`
  - Current focus: persist daily closes and surface EOD trend views without implying full portfolio performance
- `M005` - Portfolio Market Value Snapshots (`planned`)
  - Spec: `../specs/portfolio-market-value-snapshots.md`
  - Checklist: `M005_portfolio-market-value-snapshots-checklist.md`
  - Current focus: forward-only daily portfolio market value snapshots from stored EOD closes
