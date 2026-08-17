# investsite — 個人投資家向け指標インサイトサイト

> 2026-07-12 全体整理: フォルダ構成の正本は `~/projects/STRUCTURE.md`、事業計画の正本は `~/projects/masterplan/plan.md`。本ファイルはスリム化済みで、ハマりどころ詳細は [docs/gotchas.md](docs/gotchas.md) へ移動した(内容は削除していない)。

## プロジェクトゴール
「株価はどこでも見れる」時代に、**どの指標がどれだけ株価に効くのか(寄与度)** を軸に据えた
個人投資家向けの日次更新サイト(invest.rakusetsu.com)を作る。閲覧者が「なんとなく売買」から「基準を持った売買」へ移行できることが提供価値。

## 確定済みの意思決定(2026-07-10 ユーザー確認済み)
| 項目 | 決定 |
|---|---|
| 対象市場 | 日米両方 |
| データコスト | 無料の範囲のみ(yfinance等)。価値確認後に有料化検討 |
| 公開形態 | 静的サイト+日次バッチ自動更新(GitHub Pages/Vercel無料枠) |
| 分析の深さ | 文献ベース+代表指標のみ簡易バックテスト |
| 非スコープ | 投資助言(金商法。「情報提供」に徹する)、リアルタイム更新、有料データ |

## 体制
- 戦略立案・レビュー: マネージャ(Fable/Opus)。実作業: Sonnetサブエージェント(docs/05-work-breakdown.md のタスク単位)

## 必ず守るルール(要点)
- データ源は日米とも yfinance(**1.5.1以上必須**、日本株は `XXXX.T`)。J-Quants無料は12週遅延で不採用
- 異なるソースの指標値を混ぜてパーセンタイル計算しない(定義差があるため)
- サイトに出す数値には出典・定義注記を必ず添える
- 長時間Pythonのバックグラウンド実行は `python -u` +ログファイル書き出し
- **上記を含む全ハマりどころの詳細(429対策、JPX PDFパース、日経コード英字、単位系の罠など)は [docs/gotchas.md](docs/gotchas.md) を実装前に必ず参照**

## ドキュメント構成
- docs/01-strategy.md(戦略) / 02-research/(調査) / 03-metrics-ranking.md(指標ランキング) / 04-site-design.md(設計) / 05-work-breakdown.md(作業リスト) / 07-data-schema.md(スキーマ) / gotchas.md(ハマりどころ実証記録)

## 参照すべきナレッジ
~/projects/knowledge/ の kb-data-collection.md、kb-markdown-datastore.md、kb-skill-pipeline.md を実装フェーズで参照。

codex-runnerを使用する場合、実装・テスト・レビューはLuna/Terraが担当し、
あなた(Claude)は要件対話・Task Spec作成(仕様・境界・Acceptance Criteria)・
エスカレーション判断・merge承認の取り次ぎに専念すること。実行開始前および
終端状態(BLOCKED_SPEC等)の処理前に ~/.codex-runner/CLAUDE_ESCALATION.md を読むこと。

実装に影響する要件・設計判断は `~/projects/knowledge/kb-ai-development-workflow.md` に従い、
Phase-gate approval(要件確定・設計確定・実装開始)を得てからGitへ確定反映すること。
