# T-11 レスポンシブ・アクセシビリティ確認表

実施日: 2026-07-10 / 担当: Sonnetサブエージェント(T-11)
検証方法: 開発サーバ(astro dev, localhost:4321)上で、同一オリジンiframe(幅375px/1280px)に全21ページを読み込み、
`documentElement.scrollWidth > clientWidth + 1` で横スクロールを機械判定。iframe内の実効クライアント幅は
スクロールバー分を差し引いた 360px / 1265px(=指定ビューポートよりさらに厳しい条件)。
はみ出し要素の有無は `getBoundingClientRect()` の全要素走査で確認。

## 1. ページ×ビューポート マトリクス(横スクロール・崩れ)

判定: OK = 横スクロールなし・ビューポート外にはみ出す要素なし

| ページ | 375px(モバイル) | 1280px(デスクトップ) |
|---|---|---|
| / (トップ) | OK | OK |
| /markets/jp/ | OK | OK |
| /markets/us/ | OK | OK |
| /factors/ (一覧) | OK | OK |
| /factors/value/ | OK | OK |
| /factors/momentum/ | OK | OK |
| /factors/dividend/ | OK | OK |
| /factors/quality/ | OK | OK |
| /factors/size/ | OK | OK |
| /factors/margin-trading/ | OK | OK |
| /screener/ | OK | OK |
| /learn/ (一覧) | OK | OK |
| /learn/per/ | OK | OK |
| /learn/pbr/ | OK | OK |
| /learn/roe/ | OK | OK |
| /learn/margin-ratio/ | OK | OK |
| /learn/technical-indicators-gap/ | OK | OK |
| /learn/analyst-forecast-contrarian/ | OK | OK |
| /about/ | OK | OK |
| /disclaimer/ | OK | OK |
| /dev/catalog/ (開発用カタログ) | OK | OK |

計21ページ × 2ビューポート = 42ケース全てOK(トークン修正後に再実行して確認済み)。

## 2. 表のはみ出し対策(既存実装の確認)

以下のページの表は既に `overflow-x: auto` のラッパー(`__table-wrap`)内にあり、
モバイルでは表内スクロールで完結する(ページ全体の横スクロールは発生しない)ことを実測確認:

- /screener/ … `.screener-page__table-wrap`(表3つ、`min-width: 640px` の表を内包)
- /markets/jp/ /markets/us/ … `.market-page__table-wrap`
- /factors/{slug}/ … `.factor-page__table-wrap`

→ 追加修正不要(仕様どおり)。

## 3. アクセシビリティ修正内容

### (a) コントラスト比(WCAG AA: 通常テキスト 4.5:1)

ライトモードで2トークンが不合格だったため修正(`site/src/styles/tokens.css`。
`:root` 既定値と `:root[data-theme="light"]` の両方。ダークモードは実測4.85〜8.9:1で合格のため変更なし):

| トークン | 修正前 | 実測比(修正前) | 修正後 | 実測比(修正後) |
|---|---|---|---|---|
| --text-muted(「データ蓄積中」「データ不足」等の淡色テキスト) | #898781 | 3.41:1(page)/ 3.50:1(card) | #6b6a64 | 5.15:1 / 5.23:1 |
| --color-reference-accent(「需給参考」バッジ・未確認注記) | #b9852a | 3.09:1(page)/ 2.78:1(reference-soft背景) | #8a5f16 | 5.34:1 / 4.81:1 |

コントラスト比はブラウザ内で WCAG 相対輝度式により実測(検証コードで算出)。

### (b) SVGチャート・PercentileBar の代替テキスト

- PercentileBar: 既に `role="img"` + 値/欠損を区別する `aria-label` あり → 変更不要(確認のみ)
- ファクター個別ページのスパークラインSVG(`site/src/pages/factors/[slug].astro`):
  `aria-label` が汎用文言(「直近1ヶ月リターンの推移」)だったため、
  ファクター名・データ日数・値域を含む具体的な文言に改善。
  注: 現データでは factor_return_1m が全null(T-17バックフィル待ち)のためSVG自体は非表示で、
  「データ蓄積中」テキスト表示が正常系。コードパスはビルド成功で確認
- 上記以外にサイト内のSVGチャートは存在しないことを grep で確認

### (c) ナビゲーションのモバイル対応

- 現状確認: ヘッダーナビは `overflow-x: auto` + `white-space: nowrap` の横スクロール方式(既存実装)。
  375pxで nav.scrollWidth=463 > clientWidth=211 のスクロール状態で全7項目に到達可能、
  ページ全体の横スクロールは発生しないことを実測 → ハンバーガー化は不要と判断(タスク指示どおり)
- 改善1: 現在ページのナビ項目に `aria-current="page"` を付与(トップは完全一致、
  他は前方一致で配下ページにも現在地表示)+ 視覚スタイル(下線+太字)を追加
- 改善2: ナビリンクのタップ領域を拡大(`display: inline-block` + 縦パディング)

## 4. 検証ログ(抜粋)

- `npm run build`: **成功、21ページ生成**(2026-07-10 18:09、7.39s)
- ビルド後CSSに修正トークンが含まれることを確認: `#6b6a64` ×2箇所、`#8a5f16` ×2箇所
- ビルドHTMLで aria-current を確認: `/factors/value/` → 「ファクター」、`/` → 「ダッシュボード」に付与
- 横スクロール判定はトークン・レイアウト修正後に全42ケースを再実行して全OK

## 5. スクリーンショット(モバイル375px、フルページ)

- docs/09-design-system-screenshots/T-11-mobile-375-top.png
- docs/09-design-system-screenshots/T-11-mobile-375-factors-value.png
- docs/09-design-system-screenshots/T-11-mobile-375-screener.png

## 6. 非スコープ(未実施)

- 新機能・デザイン変更(トークン範囲外)・SEO
- pipeline/ と data/ への変更(T-17担当が並行作業中のため一切触っていない)
- スクリーンリーダー実機テスト(機械判定のみ)
