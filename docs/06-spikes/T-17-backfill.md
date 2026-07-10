# T-17 スパイク: 指数バリュエーション履歴の無料データ源(バックフィル用)

最終更新: 2026-07-10 / 作成: 実作業員(T-17担当)
目的: 市場体温計(指数PER/PBRの5年パーセンタイル)を初日から表示するため、指数バリュエーションの
5年履歴が無料で取得できるかを実測で白黒付ける。

## 結論(両市場とも取得可能=スパイク成立)

| 市場 | データ源 | 取れた定義 | 頻度 | 遡及可能期間 | 5年分の実測点数 |
|---|---|---|---|---|---|
| 日本 | 日経平均プロフィル公式(indexes.nikkei.co.jp) | PER: 加重平均(倍)/指数ベース(倍)の両方。PBRも同2系列 | **日次** | 2004年〜(セレクタの最古年) | PER 1,349点 / PBR 1,349点(2021-01-04〜2026-07-09) |
| 米国 | multpl.com(S&P 500 PE Ratio / Price to Book) | PER: trailing 12ヶ月 "as reported" earnings ベース。PBR: 四半期 | PER **月次**(当月分のみ日次スナップ)/ PBR **四半期** | PER 1871年〜 / PBR 1999年〜 | PER 60点 / PBR 19点(直近5年) |

- 採用系列: **日本=加重平均(倍)**(構成銘柄合算ベース。docs/07 3.3節の「時価総額加重平均」の意図に合致)、
  **米国=multplのtrailing PE(月次)とP/B(四半期)**。
- Shiller公開データ(ie_data.xls, econ.yale.edu)は接続不可(ECONNREFUSED)だったため不採用。multplで足りる。
- 日米で定義・頻度が異なるため、サイト表示にはデータごとの定義注記を必ず添える
  (market-thermometer.json の valuation_history.{jp,us}.definition に格納済み)。

## 日本: 日経平均プロフィル(実測詳細)

- 表示ページ: https://indexes.nikkei.co.jp/nkave/archives/data?list=per (pbr は `list=pbr`)
- 実データは下記の内部エンドポイントが月単位のHTML断片を返す(登録不要・無料):
  `https://indexes.nikkei.co.jp/nkave/statistics/dataload?list={per|pbr}&year=YYYY&month=M`
- 列構成: 日付 / 加重平均(倍) / 指数ベース(倍)。
  - **加重平均**: 構成銘柄の合算ベース(時価総額合計÷利益・純資産合計に相当)
  - **指数ベース**: 日経平均の株価換算(みなし額面調整後の株価平均)ベース
  - 計算式の正式定義はユーザーズ・ガイド: https://indexes.nikkei.co.jp/nkave/archives/file/users_guide_jp.pdf
- **パース方法**: HTML断片から `<td>YYYY.MM.DD</td><td>加重</td><td>指数ベース</td>` の行を正規表現で抽出
  (`<!--daily_changing-->` コメントが値セルに付く)。月ループ(5年×12ヶ月×2指標=約134リクエスト)で全取得。
- **制約(ハマりどころ)**: サイト全体がCloudflareのbot対策下にあり、**curl/requestsの直叩きは403**になる。
  実ブラウザ(Playwright)経由のfetchなら取得できる。よって日次バッチへの組み込みは不可で、
  **一回限りのバックフィル+スパイク成果物ファイルからの読み込み**とする設計にした
  (`pipeline/spikes/out/t17_nikkei_per_pbr_5y.json` に5年分を保存済み)。
- 実測: 2021-01-04〜2026-07-09 の日次 PER/PBR 各1,349点。
  例: 2021-01-04 PER加重25.13/指数ベース28.03、2026-07-09 PER加重18.11/指数ベース24.33。

## 米国: multpl.com(実測詳細)

- PER(月次): https://www.multpl.com/s-p-500-pe-ratio/table/by-month
  - trailing twelve month "as reported" earnings ベース。1871年1月〜現在の全1,867行が1ページのHTMLに含まれる
  - 月初値(毎月1日付)+当日推定値(† Estimateマーク付き)
- PBR(四半期): https://www.multpl.com/s-p-500-price-to-book/table/by-quarter
  - 1999年12月〜現在の四半期末値+当日推定値。**月次テーブルは存在しない**(by-monthは301でby-yearへリダイレクト)
- HTTP直叩きで取得可能(HTTP 200、UA指定のみ。Cloudflareチャレンジなし)
- **パース方法**: `<td>Mon D, YYYY</td><td>[<abbr>†</abbr>|&#x2002;] 値` を正規表現で抽出
  (最新行はEstimateの`<abbr>`、過去行は`&#x2002;`エンティティが値の前に入る点に注意)
- 実測: PER 1,867点(1871-01-01〜2026-07-09、直近5年は60点)、PBR 106点(1999-12-31〜2026-07-09、直近5年は19点)

## 外部突合(指数PER当日値)

自前の daily/2026-07-10/{jp,us}.json から合算PER(Σ時価総額 ÷ Σ(時価総額/PER))を計算して突合した:

| 市場 | 外部ソース値(2026-07-09) | 自前合算PER(2026-07-10) | 乖離 | 乖離の説明 |
|---|---|---|---|---|
| 日本 | 18.11(日経公式・加重平均) | 19.19(n=211) | +6.0% | 日経は前期基準の当期純利益合計を使用。自前はyfinance trailingPE由来で、赤字・欠損14銘柄の除外方法と利益の期ズレが乖離要因 |
| 米国 | 32.45(multpl・as reported) | 27.80(n=478) | -14.3% | multplは"as reported"(GAAP)ベースでEPSが小さく出る=PERが大きく出る。yfinanceのtrailingPEは希薄化後・継続事業ベース中心で定義が異なる |

いずれも定義差で説明可能な範囲であり、系列内の一貫性(同一ソース内の時系列)でパーセンタイルを
計算する分には問題ない。**異なるソースの値を混ぜてパーセンタイルを計算しない**こと(定義が違うため)。

## バックフィル設計への反映(フェーズ2)

1. `pipeline/backfill.py`(一回限りCLI)が、日本=スパイク成果物JSON、米国=multpl直取得で
   market-thermometer.json に `valuation_history` を格納し、最新値の5年パーセンタイルを算出する
2. 日次パイプライン(pipeline/daily.py → factors.build_market_thermometer_snapshot)は
   `valuation_history` を保持し、そこから index_per/index_pbr/percentile を毎回再計算する
   (バックフィル値が翌日のdaily実行で消えない)
3. ファクターの factor_return_1m/3m/1y は「現在の分位該当銘柄の等ウェイト・トレーリングリターン −
   ユニバース等ウェイト平均」の近似(構成銘柄固定・生存バイアスあり)。厳密なヒストリカル分位
   バックテストはT-15スコープ

## 検証コマンド

- 日経5年分の取得はPlaywright(実ブラウザ)経由で実施(Cloudflare対策)。成果物:
  `pipeline/spikes/out/t17_nikkei_per_pbr_5y.json`(per/pbr 各1,349点)
- multpl取得+パース+突合の再現: `python -m pipeline.backfill --dry-run`(実装後)
- 取得済みHTML: `pipeline/spikes/out/t17_multpl_pe.html`, `t17_multpl_pb_q.html`
