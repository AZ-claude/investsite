# 確認済みのハマりどころ・やり方(タスク別の実証記録)

CLAUDE.md から2026-07-12に移動(トークン削減のため)。新しいハマりどころはこのファイルに追記する。

## P1スパイクで実証
- データ源は日米とも **yfinance を採用**(日本株は `XXXX.T`)。J-Quants無料プランは12週遅延のため不採用(公式FAQで確認)
- **yfinance は 1.5.1 以上必須**: 0.2.51 は全リクエスト429で動作しない(curl_cffi 導入で解決済み)
- **起動直後の429連鎖に注意**: セッション初期化失敗で全滅するパターンあり。日次バッチは30〜60秒待機の再試行を入れる(T-02実測)
- 日経225構成銘柄リストは日経平均プロフィル公式CSV(無料・登録不要)。CP932エンコーディング+フッタ行のパースに注意
- yfinanceのPERは実績(trailing)ベース。Yahoo!ファイナンスJPの表示は会社予想ベースで定義が異なる。時価総額はトヨタで19%乖離の未解決事例あり(T-03/T-04で要検証)

## T-03スキーマ確定で実証
- トヨタ時価総額19%乖離の原因は**sharesOutstanding(発行済株式数)の値そのものの差**と切り分け済み(yfinanceのmarketCapは内部でsharesOutstanding×priceと完全一致=計算式自体は正しい)。自己株式控除差が最有力仮説だが未確定。サイトには出典・定義注記を必ず添える
- 信用倍率(信用取引残高)はyfinanceでは取得不可。**JPX公式サイトが週次・無料でPDF(銘柄別、火曜16:30頃)/Excel(市場全体、水曜15:00頃)を公表**しており、これが採用データ源。CSV配信はなくPDF/Excelパーサの実装が必要(T-04/T-05)。詳細: docs/07-data-schema.md 6節
- スキーマ設計は2層(`data/daily/YYYY-MM-DD/{jp|us}.json` + `data/factors/{factor}.json`)+銘柄マスタ`data/universe/{jp|us}.json`の3ファイル群構成。市場体温計は`data/factors/market-thermometer.json`としてfactors層に相乗り(第3層を作らない)

## T-04指標計算で実証
- **日経225の証券コードは英字入りがある**(285A=キオクシア、543A等)。「4桁数字」で弾くと225→223銘柄に減る。正規パターンは `\d[\dA-Z]{3}`
- **JPXページのPDFリンクを`links[-1]`で取ると事故る**: 週次データ以外のお知らせPDF(t13vrt….pdf)が混在。`syumatsuYYYYMMDD`/`mtseisanYYYYMMDD`の命名規則でフィルタし日付最大を選ぶこと(pipeline/metrics/margin_jpx.py で対策済み)
- **yfinance 1.5.1 の dividendYield は既にパーセント単位**(AAPL=0.34は0.34%の意味)。100倍しないこと。returnOnEquity はフラクション(0.102=10.2%)で単位が異なる点に注意
- JPX銘柄別信用残PDFの行フォーマット: 数値12個(6項目×[水準,前週比])、負の前週比は「▲」が独立トークン。順序は[合計売残,Δ,合計買残,Δ,一般売残,Δ,制度売残,Δ,一般買残,Δ,制度買残,Δ](トヨタ実測値で検算済み)
- 日経225のうち約5銘柄はJPX信用残PDFに存在しない(貸借銘柄でない等)。margin欠損は正常系として扱う
- ROE欠損率の実測(T-03で未実測だった項目): JP 4/225=1.78%、US 34/503=6.76%

## T-05日次蓄積で実証
- 日次CLIは `python -m pipeline.daily [--date YYYY-MM-DD] [--markets jp,us] [--mock-jp FILE]`。品質ゲート(price/market_cap欠損>5%、中央値PER前日比±30%超)に引っかかると**書き込みゼロで exit=1**(前日データ維持)。取得失敗は exit=2
- factors/*.json の history は日付キーで upsert(同日再実行は冪等上書き)。`--date`で過去日をbackfillしてもmarket-thermometerのtop-levelは常に最新日付を指す設計
- factor_return_1m/3m/1y は T-17バックフィルで「現在の分位該当銘柄のトレーリングリターン−ユニバース平均」の近似値を当日分のみ記入済み(注記は factor_return_note)。厳密なヒストリカル分位バックテストは T-15(P4)
- **長時間のPythonをバックグラウンド実行するときは `python -u` + `2>&1` でログファイルに書くこと**: stdoutがパイプだとブロックバッファリングされ、途中経過も失敗のtracebackも見えないまま静かに終わる事故を実測(T-05)
- data/logs/*.log は .gitignore の `*.log` の例外としてコミット対象(監査証跡)

## T-17バックフィルで実証
- **日経平均プロフィルの指数PER/PBRは2004年〜の日次データが無料**。実体は `https://indexes.nikkei.co.jp/nkave/statistics/dataload?list={per|pbr}&year=YYYY&month=M` が月単位HTML断片を返す。ただし**サイト全体がCloudflare保護でcurl/requestsは403**。実ブラウザ(Playwright)経由fetchなら取れる。日次バッチ組み込み不可のため、一回限りバックフィル+成果物ファイル(pipeline/spikes/out/t17_nikkei_per_pbr_5y.json)方式を採用
- 日経PER/PBRは「加重平均(倍)」「指数ベース(倍)」の2系列。市場体温計は**加重平均**を採用(時価総額加重の意図に合致)
- **multpl.com はHTTP直叩き可**(UA指定のみ)。S&P500 PER=月次1871年〜(trailing "as reported")、PBR=四半期1999年〜。**PBRのby-monthは存在しない**(301でby-yearへ)。値セルは最新行`<abbr>†</abbr>`・過去行`&#x2002;`が値の前に付く
- 指数PERの外部突合は定義差前提: 自前合算PER(Σmcap/Σearnings) vs 日経公式=+6.0%(前期基準利益差)、vs multpl=-14.3%(as reported GAAP差)。**異ソースの値を混ぜてパーセンタイル計算しない**
- market-thermometer.json の `valuation_history` と factors/*.json の backfill済み factor_return_* は、日次実行(factors.py)が保持・再計算する(バックフィルが翌日実行で消えない)。バックフィルCLIは `python -m pipeline.backfill`(冪等)
