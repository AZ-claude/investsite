# 09. 本番ドメイン移行(invest.rakusetsu.com)

最終更新: 2026-07-17

## 背景・決定事項

- invest.rakusetsu.com には現在 WordPress が導入されているだけで未使用。
- **決定(2026-07-17 ユーザー承認)**: WordPress は使わず、既存の Astro + GitHub Pages
  静的サイト構成をそのまま invest.rakusetsu.com に載せる。WordPress は将来的に削除想定
  (削除自体はホスティング側の操作でありこのタスクの対象外・未実施)。
- ユーザーから「アプリケーションパスワード」(WordPress REST API認証用、書式:
  `xxxx xxxx xxxx xxxx xxxx xxxx`)を受領したが、**WordPressを使わない方針のため今回は不要**。
  リポジトリ・メモリのどこにも保存していない。今後もWP REST APIを使う計画がなければ、
  ユーザー側でこのアプリケーションパスワードを無効化してもらうのが安全。

## DNS調査結果(2026-07-17時点、無害な読み取りのみ実施)

- `rakusetsu.com` / `invest.rakusetsu.com` とも現状 A レコードで `160.251.148.126` を指す
  (おそらくワイルドカード的にホスティングサーバーへ向いている)。
- ネームサーバー: `ns-rs1.gmoserver.jp`, `ns-rs2.gmoserver.jp`
  → GMO系レンタルサーバー(お名前.com など)でドメイン管理・DNS設定されている可能性が高い。
  ユーザーは「やり方が分からない」とのことなので、次回セッションで具体的な操作手順を
  スクリーンショット付きで案内する想定。

## リポジトリ側で完了した変更

- `site/astro.config.mjs`: `site: 'https://invest.rakusetsu.com'`, `base: '/'` に変更
  (旧: GitHub Pagesのプロジェクトページ用に `base: '/investsite'`)。
- `site/public/CNAME` を新規作成、内容 `invest.rakusetsu.com`。
- ローカル `npm run build` で21ページ生成成功、`dist/CNAME` に反映、内部リンクが
  `/investsite/...` ではなく `/...` のルート相対パスになっていることを確認済み。
- **未コミット・未push**(本番公開に関わる変更のため、ユーザー承認後にcommit/pushする)。

## 実施結果(2026-07-17完了)

- **DNS**: `invest.rakusetsu.com` には既に MX/TXT(SPF)/TXT(DKIM)レコードが設定済みで
  メールに使われていたため、CNAMEではなく**Aレコード4本**(GitHub Pages公式IP:
  `185.199.108.153` / `.109.153` / `.110.153` / `.111.153`)に変更する方式を採用。
  お名前.com Navi の「ドメイン→DNS」から実施。メール関連レコードは無変更。
- **リポジトリ**: commit & push 済み(コミット `8de6172` ※リベース後ハッシュ変わる場合あり)。
  途中、リモートに日次データ更新の自動コミットがあったため rebase して解消。
  作業中にあった無関係な未コミット変更(CLAUDE.md, docs/05-work-breakdown.md,
  pipeline/spikes/out/run_log.txt, docs/gotchas.md)は stash → pop で退避・復元し、
  このタスクのコミットには含めていない。
- **GitHub Pages カスタムドメイン**: `gh api repos/AZ-claude/investsite/pages -X PUT -f cname=...`
  で設定済み。
- **動作確認**: `http://invest.rakusetsu.com/` で200応答・`Server: GitHub.com` を確認済み
  (Google Public DNS 8.8.8.8でも新IPへの反映を確認)。
- **HTTPS**: 証明書はGitHub側で自動発行待ち(`https_enforced: false`)。数分〜1時間程度で
  自動的に有効化される見込み。次回セッションで
  `gh api repos/AZ-claude/investsite/pages` の `https_enforced` を確認すること。

## 残タスク

1. HTTPS自動発行の確認(`https_enforced: true` になったか)
2. WordPressの扱いを最終決定(放置/削除)— ユーザーの意向を別途確認
3. サイトタイトル・ロゴなどブランディング(下記「デザイン・ロゴ」参照)

## デザイン・ロゴ(別フェーズ、未着手)

- ユーザーからデザイン・ロゴは一任されている。金融情報サイトと分かる方向性。
- 着手時は `brainstorming` スキルを使い、方向性をすり合わせてから実装する。
- 現状サイトタイトルは仮の "investsite" のまま(`site/src/layouts/Layout.astro` 等)。
  ブランディング確定時にあわせて変更する。

## このファイルの扱い

移行が完了し運用が安定したら、このファイルの内容は `docs/gotchas.md` 等へ要点のみ
統合し、本ファイルは削除してよい。
