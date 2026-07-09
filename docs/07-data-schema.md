# 07. データスキーマ確定(T-03)

最終更新: 2026-07-10 / 作成: 実作業員(Sonnet, T-03担当)
インプット: docs/06-spikes/T-01-jp-data.md, docs/06-spikes/T-02-us-data.md, docs/03-metrics-ranking.md 3節, docs/04-site-design.md, kb-markdown-datastore.md
非スコープ: 指標計算モジュールの実装(T-04)、蓄積CLI(T-05)。本ドキュメントは「契約(スキーマ)」のみを定義する。

## 0. マネージャ決定事項の反映

| 決定事項 | 本スキーマでの反映 |
|---|---|
| データ源は日米ともyfinance(日本は`XXXX.T`) | `daily/{jp,us}.json` の `source.provider = "yfinance"` に統一。T-01/T-02の結論通り |
| PERは trailing(実績)ベースを正とする | フィールド名を `per_trailing`(会社予想PERと明確に区別できる命名)とし、`source.note` に「会社予想ベースとは定義が異なる」旨を明記。サイト表示時もこの注記をそのまま使う前提 |
| ユニバース初期値: 日本=日経225、米国=S&P500(拡張可能) | `data/universe/{jp,us}.json` を独立ファイル化し、`daily/*.json` 側は `universe` フィールドで参照するのみ(銘柄リストを二重管理しない)。TOPIX500等を追加する場合は `data/universe/` に新規ファイルを追加すればよい設計 |

## 1. 全体設計方針

- **2層構成**: `data/daily/YYYY-MM-DD/{jp|us}.json`(銘柄別・日次スナップショット)と `data/factors/{factor}.json`(ファクター単位の時系列集計)。kb-markdown-datastore.mdの「時系列出力+集計を分ける」パターンに準拠
- **市場体温計は`data/factors/market-thermometer.json`として「ファクターに準じる特殊ファイル」に位置づける**。指数レベルの集計であり個別銘柄ファクターではないが、「日次で追記され時系列化される集計データ」という点で`data/factors/`層の構造をそのまま流用できるため、新たな第3層は作らない
- **銘柄マスタ(ユニバース)は`data/universe/{jp|us}.json`に分離**。日次データが銘柄リストを毎回コピーしないようにし、ユニバース拡張(TOPIX500追加等)を独立変更にする
- **欠損は`null`、フィールド自体は残す**(T-01/T-02で実測済みの欠損率: JP `trailingPE`欠損6.2%、US `PER`欠損5.0%、`PBR`欠損0.2%等)。各銘柄に`data_quality.missing_fields`を持たせ、後続の指標計算(T-04)が欠損銘柄をスキップ/除外する判定に使えるようにする
- **命名は定義を名前に含める**: `per_trailing`(実績PER)、`momentum_12_1`(12-1ヶ月モメンタム)、`margin_ratio_seido`(制度信用ベース信用倍率)等。同じ「PER」でも定義が割れるリスクをフィールド名レベルで防ぐ

## 2. Layer 1: `data/daily/YYYY-MM-DD/{jp|us}.json`

### 2.1 トップレベル

| フィールド | 型 | 説明 |
|---|---|---|
| `date` | string(YYYY-MM-DD) | スナップショット対象日(株価は前営業日終値ベース。T-01/T-02参照) |
| `market` | `"jp"` \| `"us"` | 市場区分 |
| `universe` | string | 参照ユニバース名(`"NIKKEI225"` \| `"SP500"`)。`data/universe/{market}.json`のindexと対応 |
| `generated_at` | string(ISO8601, JST) | 生成日時 |
| `source` | object | `provider`(データ提供元), `library_version`, `note`(定義上の注記。PER実績ベース等) |
| `stocks` | array | 銘柄別レコードの配列(2.2節) |

### 2.2 `stocks[]`(銘柄別レコード)

| フィールド | 型 | 説明 | 実測欠損率(T-01/T-02) |
|---|---|---|---|
| `ticker` | string | `"7203.T"` / `"AAPL"` 形式 | - |
| `name` | string | 銘柄名(yfinance `shortName`) | - |
| `currency` | string | `"JPY"` \| `"USD"` | - |
| `price` | number | 株価(前営業日終値ベース) | JP 0% / US 0% |
| `market_cap` | number | 時価総額。**精度に留保あり(3節参照)** | JP 0% / US 0% |
| `shares_outstanding` | number | 発行済株式数(yfinance `sharesOutstanding`) | - |
| `per_trailing` | number\|null | 実績PER(`trailingPE`)。**会社予想PERとは別定義** | JP 6.2% / US 5.0% |
| `pbr` | number\|null | PBR(`priceToBook`) | JP 0% / US 0.2% |
| `dividend_yield_pct` | number\|null | 配当利回り(%) | 実測: サンプル5銘柄中JPは3銘柄null(後述4節) |
| `roe` | number\|null | ROE(`returnOnEquity`) | 未実測(T-04で全銘柄検証要) |
| `trailing_eps` | number\|null | 実績EPS(PER算出根拠の開示用) | - |
| `book_value_per_share` | number\|null | 1株当たり純資産(PBR算出根拠の開示用) | - |
| `momentum_12_1` | number\|null | 12-1ヶ月モメンタム。直近1ヶ月(約21営業日)を除く過去12ヶ月(約231営業日前〜21営業日前)の騰落率 | サンプル10/10銘柄で算出成功 |
| `percentile_in_universe` | object | 各指標のユニバース内パーセンタイル(0〜1、当日クロスセクション)。**個別指標カードの「歴史的位置」表示に使う想定フィールド**(算出はT-04) | - |
| `data_quality.missing_fields` | array\<string\> | 当該銘柄で欠損したフィールド名一覧 | - |
| `margin`(JPのみ、存在する銘柄のみ) | object | 2.3節参照。信用倍率(参考枠)用 | JPXデータ未取得銘柄は省略(キー自体がない) |

### 2.3 `stocks[].margin`(日本株のみ、週次更新)

信用倍率はyfinanceでは取得不可(T-01では未検証項目だった)。本タスクで調査した結果、**JPX公式サイトが週次・無料・PDF形式で銘柄別残高を公表している**ことを確認した(5節「信用倍率データ源の調査結果」参照)。

| フィールド | 型 | 説明 |
|---|---|---|
| `as_of_week` | string(YYYY-MM-DD) | 週末残高の申込日基準日(前週金曜) |
| `outstanding_sales_shares` / `outstanding_purchases_shares` | number | 信用売残・買残合計(株) |
| `seido_sales_shares` / `seido_purchases_shares` | number | 制度信用の売残・買残(株) |
| `ippan_sales_shares` / `ippan_purchases_shares` | number | 一般信用の売残・買残(株) |
| `margin_ratio_seido` | number | 制度信用ベースの信用倍率(買残÷売残)。**サイト表示の主指標** |
| `margin_ratio_total` | number | 制度+一般合算ベースの信用倍率(参考) |
| `source` | string | 出典URL |

日次スナップショット(`daily/YYYY-MM-DD/jp.json`)には**その時点で最新公表済みの週次値をそのまま保持**する(週内は値が変わらない=同じ`as_of_week`が複数日連続で入る)。これはkb-markdown-datastore.mdの「鮮度管理」方針に沿い、`as_of_week`で鮮度を明示する。

## 3. Layer 2: `data/factors/{factor}.json`

対象6ファクター: `value` / `momentum` / `dividend` / `quality` / `size`(Tier1) + `margin-trading`(参考枠)。

### 3.1 共通構造(Tier1の5ファクター)

| フィールド | 型 | 説明 |
|---|---|---|
| `factor` | string | スラッグ(`value`等、04-site-design.mdのURLパスと一致) |
| `label` | string | 表示名 |
| `markets` | array | `["jp","us"]` |
| `definition` | string | 指標定義の短文(サイト解説文の元ネタ) |
| `evidence` | array | `{claim, source, confirmed}`。factor-evidence.mdをSSOTとし出典・未確認注記を保持 |
| `history` | array | 日次追記される時系列。各要素: `{date, factor_return_1m, factor_return_3m, factor_return_1y, screen_count}`。`factor_return_*`は分位ポートフォリオの超過リターン(T-04算出)。**ファクター天気図・過去推移チャート・注目シグナルの日次差分は全てこの配列から算出できる** |
| `today_screen` | object | `{jp: [...], us: [...]}`。各要素`{ticker, rank, quantile, metric_value}`。個別ページの「本日の該当銘柄リスト」と`/screener/`の元データ |

### 3.2 `margin-trading.json`(参考枠、日本のみ、週次)

Tier1と異なり `frequency: "weekly"` と `data_source`(取得方法の詳細、5節参照)を持つ。`today_screen.jp[]`の各要素は`margin_ratio_seido`降順ランキング。

### 3.3 `market-thermometer.json`(市場体温計、指数レベル)

トップページ「市場体温計」用。個別ファクターではないため`factor`キーは持たず、`jp` / `us` の指数レベル情報を直接持つ。

| フィールド(`jp`/`us`共通) | 型 | 説明 |
|---|---|---|
| `index` | string | `"NIKKEI225"` \| `"SP500"` |
| `index_level` | number | 指数終値 |
| `index_change_pct_1d` | number | 前日比%(トップページ「ひとこと状況」の数値根拠) |
| `index_per` / `index_pbr` | number\|null | 指数PER/PBR(時価総額加重平均。**全銘柄集計が必要でT-04スコープ**、本サンプルはnull) |
| `index_per_percentile_5y` / `index_pbr_percentile_5y` | number\|null | 過去5年に対する歴史的パーセンタイル(帯グラフの元データ) |

`jp`のみ追加: `margin_market_total`(信用倍率の市場全体版。5節のJPX Excelから取得、実測値あり)。

`history`配列で日次蓄積し、`index_per_percentile_5y`等はこの蓄積が5年分溜まってから算出可能になる(初期は`null`のまま運用し、蓄積が進むにつれて埋まる設計)。

## 4. `data/universe/{jp|us}.json`(ユニバース定義、拡張可能設計)

| フィールド | 型 | 説明 |
|---|---|---|
| `index` | string | ユニバース名 |
| `as_of` | string | 構成銘柄リストの取得日 |
| `source` | string | 取得元(日経平均プロフィルCSV / Wikipedia S&P500テーブル) |
| `count_total` | number | 銘柄数 |
| `tickers_sample` \| `tickers` | array | `{ticker, name}` |

**拡張方法**: TOPIX500等を追加する場合、`data/universe/topix500.json`を新規追加し、`daily/*.json`の`universe`フィールドに`"TOPIX500"`を指定するだけでよい。既存ファイルの改修は不要。

## 5. 時価総額乖離の調査結果(トヨタ19%乖離の原因調査)

### 検証方法

`pipeline/spikes/t03_marketcap_check.py` を作成し、yfinanceの`marketCap`と`sharesOutstanding × price`を6銘柄(乖離が観測されたトヨタ、対照群のSBG/ソニー、追加検証の3銘柄)で突合した。実行ログ: `pipeline/spikes/out/t03_marketcap_check_log.txt`。

### 結果(実測)

全6銘柄で **`marketCap` = `sharesOutstanding × price` が完全に一致(差0.00%)** した。

```
7203.T: marketCap=3.344e+13  sharesOutstanding×price=3.344e+13  差=+0.00%
9984.T: marketCap=3.281e+13  sharesOutstanding×price=3.281e+13  差=-0.00%
6758.T: marketCap=2.002e+13  sharesOutstanding×price=2.002e+13  差=-0.00%
8306.T: marketCap=3.850e+13  sharesOutstanding×price=3.850e+13  差=+0.00%
9432.T: marketCap=1.213e+13  sharesOutstanding×price=1.213e+13  差=-0.00%
8035.T: marketCap=3.232e+13  sharesOutstanding×price=3.232e+13  差=+0.00%
```

トヨタについて `sharesOutstanding`(yfinance) = 11,841,052,480株 に対し、T-01調査時点でのYahoo!ファイナンスJP表示の発行済株式数は 14,594,987,460株 だった(乖離 -18.87%、観測された19%乖離とほぼ一致)。SBG・ソニーの発行済株式数はyfinance値とYahoo!表示値がほぼ一致(差1〜2%以内)していた。

### 結論(切り分けはできたが根本原因は未特定)

- **確定した事実**: yfinanceの`marketCap`は内部で`sharesOutstanding × price`という一貫した式で計算されている(marketCap自体の計算ロジックに問題はない)。**乖離の原因は`sharesOutstanding`(発行済株式数)の値そのものがYahoo!ファイナンスJP表示と異なることに完全に絞り込めた**
- **仮説として残るもの(優先度順、未検証)**:
  1. **自己株式控除の有無**: yfinanceの`sharesOutstanding`が自己株式(トヨタは大規模な自社株買いを継続実施)を控除した実質発行済株式数を採用し、Yahoo!ファイナンスJP表示は控除前の総発行株式数を採用している可能性(最有力の仮説)
  2. **データ鮮度**: yfinanceの`sharesOutstanding`スナップショットが古く、直近の大規模自社株買いを反映できていない可能性
  3. SBG・ソニーで乖離が小さいのは、両社が同期間に大規模な自己株式取得・消却を行っていない(トヨタほど自己株式比率が大きくない)ため、という説明とも整合する
- **未特定**: EDINET等の一次資料(有価証券報告書の「発行済株式総数」「自己株式数」)との突合までは本タスクのスコープ内で完了できなかった(T-01の非スコープ、本タスクでも追加の一次資料照会は行っていない)。したがって**仮説1(自己株式控除差)が最有力だが確定はしていない**
- **サイトへの反映方針**: 時価総額は出典(yfinance)と定義上の留保(「発行済株式数の算出方法がYahoo!ファイナンス等の表示と異なる場合がある」)を注記して掲載する。`daily/*.json`の`source.note`および将来のサイトフッター「データ出典」にこの注記を含める運用とする

## 6. 信用倍率データ源の調査結果(結論)

**取得方法を確定した。yfinanceでは取得不可のため、JPX公式サイトの週次公表データを採用する。**

| 項目 | 内容 |
|---|---|
| 銘柄別データ | 「銘柄別信用取引週末残高」(JPX公式, https://www.jpx.co.jp/markets/statistics-equities/margin/05.html)。**毎週第2営業日(火曜)16:30頃に前週金曜申込分をPDF形式で公表**。無料・登録不要 |
| 市場全体データ | 「信用取引現在高」(JPX公式, https://www.jpx.co.jp/markets/statistics-equities/margin/04.html)。**毎週第3営業日(水曜)15:00頃にExcel/PDF形式で公表**。市場全体の信用倍率(全国計)を直接含む |
| 実測検証 | 本タスク中に両方のファイルを実際にダウンロード・パースし、実データを抽出できることを確認した(下記) |
| フォーマットの制約 | **CSV配信はない**。銘柄別はPDF(pdfplumberでのテキスト抽出は可能だが、銘柄名部分が文字コードの都合で判読困難。証券コード列・数値列は正しく抽出できることを確認)、市場全体はExcel(pandasで問題なく読める) |
| 更新遅延 | 週末(金曜)時点データが翌週火〜水曜に公表 = 実質5〜8日遅れ。日次更新ではなく**週次更新**として設計する必要がある |

### 実測ログ(抜粋)

```
JPX「銘柄別信用取引週末残高」2026/7/3申込分PDF(85ページ)から証券コード72030(トヨタ)の行を実際に抽出:
  信用売残合計=2,171,500株  信用買残合計=22,198,100株
  制度信用売残=2,006,000株  制度信用買残=13,888,200株
  → margin_ratio_seido(制度信用倍率) = 13,888,200 / 2,006,000 ≈ 6.92倍

JPX「信用取引現在高」2026/7/3申込分Excel(mtseisan2026070300.xls)から市場全体の信用倍率を実際に抽出:
  全国計信用倍率 = 9.8029倍(東京9.8029倍、名古屋9.7965倍)
```

### 結論

信用倍率のデータ源は **未確定ではなく確定した**(P2初期リリースで代替案に頼る必要はない)。ただし以下2点をT-04/T-05への申し送り事項とする:

1. **PDF/Excelパーサの実装が必要**(CSVではないため)。銘柄別PDFは85ページに及び、証券コード・数値列の抽出ロジックが必要(会社名は文字コードの都合で使わず、`data/universe/jp.json`の銘柄マスタと証券コードで突合する設計にする)
2. **更新頻度が週次**であるため、`daily/*.json`の`margin`フィールドは日次で値が変わらない週がある(`as_of_week`で鮮度を示す設計は2.3節の通り)

## 7. 対応表: 04-site-design.md 全ページ表示要素 ⇔ スキーマフィールド

| ページ / 表示要素(04-site-design.md該当箇所) | 対応するスキーマフィールド | 判定 |
|---|---|---|
| トップ 1. ヘッダー(日付) | `daily/*.json.date` | 賄える |
| トップ 1. ヘッダー(日米市場のひとこと状況、数値ベース) | `factors/market-thermometer.json.{jp,us}.index_change_pct_1d` | 賄える |
| トップ 2. 市場体温計(日米バリュエーションの歴史的パーセンタイル帯) | `factors/market-thermometer.json.{jp,us}.index_per_percentile_5y` / `index_pbr_percentile_5y`(蓄積後に算出) | 賄える(算出はT-04、フィールドは確保済み) |
| トップ 3. ファクター天気図(各ファクターの直近リターン一覧) | `factors/{factor}.json.history[].factor_return_1m`(6ファクター共通) | 賄える |
| トップ 4. 本日の注目シグナル(該当件数の前日差) | `factors/{factor}.json.history[].screen_count`(前日分との差分) | 賄える |
| トップ 5. フッター(免責・データ出典・最終更新時刻) | `daily/*.json.generated_at` + `source`(出典)。免責文言自体は静的コンテンツ | 賄える(データ由来部分のみ) |
| /markets/{jp,us}/ 指数・バリュエーションの現在地と推移 | `factors/market-thermometer.json.{jp,us}` + `history[]` | 賄える |
| /markets/jp/ 信用残の現在地と推移 | `factors/market-thermometer.json.jp.margin_market_total` | 賄える |
| /factors/{factor}/ 解説(そもそも何か、なぜ効くか) | `factors/{factor}.json.definition` (詳細本文はfactor-evidence.mdから別途原稿化、T-09スコープ) | 賄える(データ骨格のみ。文章はT-09) |
| /factors/{factor}/ 寄与度エビデンス | `factors/{factor}.json.evidence[]` | 賄える |
| /factors/{factor}/ 過去推移(直近1年/5年ファクターリターン) | `factors/{factor}.json.history[].factor_return_1y`(日次蓄積の系列) | 賄える |
| /factors/{factor}/ 本日の該当銘柄リスト(日米タブ切替) | `factors/{factor}.json.today_screen.{jp,us}` | 賄える |
| /factors/margin-trading/ (需給参考ラベル) | `factors/margin-trading.json`(専用スキーマ、3.2節) | 賄える |
| /screener/ 本日の全スクリーニング結果一覧(ファクター横断) | `factors/{factor}.json.today_screen`を6ファクター分ビルド時にticker軸でjoinし、`daily/*.json`の指標値と結合 | 賄える(結合ロジックはT-08〜T-10スコープ) |
| 指標カード共通3点セット: 現在値 | `daily/*.json.stocks[].{per_trailing, pbr, ...}` | 賄える |
| 指標カード共通3点セット: 歴史的位置(パーセンタイル) | `daily/*.json.stocks[].percentile_in_universe`(当日クロスセクション。個別銘柄カード用)。ファクター単位の歴史的位置は`factors/{factor}.json.history[]`蓄積から算出(ファクター天気図・市場体温計用) | 賄える(前提: 「歴史的位置」は個別銘柄カードではクロスセクション百分位、ファクター/市場レベルでは自己時系列パーセンタイルという設計判断。04-site-design.mdに明記がないため本タスクの判断で決定) |
| 指標カード共通3点セット: 寄与度エビデンス(出典リンク) | `factors/{factor}.json.evidence[]` | 賄える |
| /learn/ 用語集記事 | 対象外(静的コンテンツ、指標データ不要) | N/A |
| /about/ 検証方法の透明性 | 対象外(静的コンテンツ) | N/A |
| /disclaimer/ 免責 | 対象外(静的コンテンツ) | N/A |

**検証結果**: 上記表の「判定」列に賄えない項目(✗)はゼロ。全ページ表示要素がLayer1/Layer2いずれかのフィールドから計算可能、または静的コンテンツ(N/A)として明示的に対象外と判定できた。

### 完了条件チェック(Tier1の5指標+信用倍率+市場体温計)

| 項目 | スキーマ上の場所 |
|---|---|
| バリュー(PBR/PER) | `daily/*.json.stocks[].{per_trailing, pbr}` + `factors/value.json` |
| モメンタム(12-1ヶ月) | `daily/*.json.stocks[].momentum_12_1` + `factors/momentum.json` |
| 配当利回り | `daily/*.json.stocks[].dividend_yield_pct` + `factors/dividend.json` |
| クオリティ(ROE/PBROE) | `daily/*.json.stocks[].roe` + `factors/quality.json` |
| サイズ(時価総額) | `daily/*.json.stocks[].market_cap` + `factors/size.json` |
| 信用倍率 | `daily/*.json.stocks[].margin`(JP、週次) + `factors/margin-trading.json` |
| 市場体温計 | `factors/market-thermometer.json` |

以上7項目すべてがスキーマのどのフィールドから計算されるか特定済み。

## 8. サンプルデータ

`data/samples/`配下に実データから生成したサンプルを格納した(生成スクリプト: `pipeline/spikes/t03_build_samples.py`、元データ: `pipeline/spikes/out/t03_sample_raw.json` = yfinanceから実取得したJP5銘柄・US5銘柄)。

```
data/samples/
├── daily/2026-07-10/
│   ├── jp.json   … トヨタ・SBG・ソニーG・三菱UFJ・KDDIの実データ5銘柄(トヨタのみmargin実測値付き)
│   └── us.json   … AAPL・MSFT・JPM・KO・XOMの実データ5銘柄
├── factors/
│   ├── value.json / momentum.json / dividend.json / quality.json / size.json
│   ├── margin-trading.json  … トヨタの実測信用倍率(制度信用ベース6.92倍)
│   └── market-thermometer.json … ^N225/^GSPC実測値 + JPX信用倍率全国計(9.8029倍)実測値
└── universe/
    ├── jp.json (NIKKEI225, サンプル5銘柄抜粋、実際は225銘柄)
    └── us.json (SP500, サンプル5銘柄抜粋、実際は503銘柄)
```

`percentile_in_universe`・`today_screen`のパーセンタイル/ランキングはサンプル10銘柄(JP5+US5)内で計算した参考値であり、本番の225/503銘柄内での計算はT-04のスコープ。`factor_return_*`・`index_per`等の「蓄積が必要な系列」は本サンプルでは`null`(1日分のスナップショットのみのため算出不可)としており、架空の数値を埋めていない。

## 9. 検証コマンドと実行ログ

```
python pipeline/spikes/t03_marketcap_check.py   # 時価総額突合(5節)
python pipeline/spikes/t03_sample_gen.py        # 実データ取得(8節)
python pipeline/spikes/t03_build_samples.py     # サンプルJSON生成(8節)
```

ログ格納先: `pipeline/spikes/out/t03_marketcap_check_log.txt`, `pipeline/spikes/out/t03_sample_raw.json`
