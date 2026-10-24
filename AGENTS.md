> **CLOSED / 開発・運用停止（2026-10-25 JST）**
> ユーザー決定により停止。コード・資料・データは保管。明示的な再開指示なしに開発・スケジューラ登録・公開を再開しない。詳細: [CLOSED.md](CLOSED.md)。

# Repository AI Adapter

Common operating rules: `~/projects/knowledge/kb-ai-operating-rules.md`.
Read them before implementation, Git writes, route decisions, or destructive/production operations.

investsite-specific entry points:

- work breakdown: `docs/05-work-breakdown.md`
- data schema: `docs/07-data-schema.md`
- observed gotchas: `docs/gotchas.md`
- detailed repo rules: `docs/AI_REPO_RULES.md`

Critical invariants: keep the product informational rather than investment-advice execution; do not mix incompatible source definitions in percentile calculations; published numeric metrics require source/definition context.

Load `docs/AI_REPO_RULES.md` when the task touches data acquisition, metrics, analysis, or scheduled daily updates.
