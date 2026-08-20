# investsite — detailed repository rules

This file preserves project-specific operating rules that should not inflate the always-loaded `AGENTS.md`.

## Goal / scope

investsite is a daily-updated investor insight site focused on how much metrics contribute to price behavior, for Japan and US markets.

Confirmed scope:

- Japan + US markets
- free data sources unless the product decision changes
- static site + daily batch update
- information/analysis product, not investment advice
- no real-time requirement

## Data / analysis invariants

- Primary price/fundamental source is yfinance; project knowledge requires yfinance >= 1.5.1 and Japanese tickers in `XXXX.T` format.
- Do not mix indicator values from materially different source definitions into one percentile calculation.
- Published numeric metrics must include source/definition context.
- Read `docs/gotchas.md` before implementation touching data acquisition/parsing/metrics; it records observed issues including 429 behavior, JPX PDF parsing, ticker/code edge cases, and unit traps.
- Long-running Python background jobs should use unbuffered output (`python -u`) and log-file output when required by the runbook.

## Canonical project docs

- strategy: `docs/01-strategy.md`
- research: `docs/02-research/`
- metric ranking: `docs/03-metrics-ranking.md`
- site design: `docs/04-site-design.md`
- work breakdown: `docs/05-work-breakdown.md`
- data schema: `docs/07-data-schema.md`
- observed gotchas: `docs/gotchas.md`

Reusable cross-project guidance lives under `~/projects/knowledge/`; load only the child KB relevant to the task.
