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

## 残タスク(次回セッション・要ユーザー作業)

1. **DNS変更(ユーザー作業、要ログイン)**: お名前.com Navi(またはGMO系の該当パネル)で
   `invest` サブドメインに CNAME レコードを追加:
   - ホスト名: `invest`
   - 種別: `CNAME`
   - 値: `az-claude.github.io`
   - 既存の `invest` 用Aレコード(ワイルドカード由来の可能性)があれば、それと競合するので削除が必要な場合あり
2. **リポジトリのcommit & push**(要ユーザー承認 — 実行前に確認を取ること。T-14の申し送り事項と同様の理由)
3. **GitHub Pages設定でカスタムドメインを設定**: リポジトリ `AZ-claude/investsite` の
   Settings → Pages → Custom domain に `invest.rakusetsu.com` を入力し、DNS反映後に
   「Enforce HTTPS」を有効化(要ユーザー承認、gh CLIでの操作も可)
4. DNS反映確認(最大24〜48時間程度かかる場合あり)、HTTPS証明書発行確認
5. WordPressの扱いを最終決定(放置/削除)— ユーザーの意向を別途確認

## デザイン・ロゴ(別フェーズ、未着手)

- ユーザーからデザイン・ロゴは一任されている。金融情報サイトと分かる方向性。
- 着手時は `brainstorming` スキルを使い、方向性をすり合わせてから実装する。
- 現状サイトタイトルは仮の "investsite" のまま(`site/src/layouts/Layout.astro` 等)。
  ブランディング確定時にあわせて変更する。

## このファイルの扱い

移行が完了し運用が安定したら、このファイルの内容は `docs/gotchas.md` 等へ要点のみ
統合し、本ファイルは削除してよい。
