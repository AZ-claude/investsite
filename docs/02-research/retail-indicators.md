# 個人投資家が見る指標の実態、および既存投資情報サイトの機能調査

## サマリ

- 日本の個人投資家がどの指標を「どれだけ」重視しているかを定量化した公的統計は見つからなかった（日証協「個人投資家の証券投資に関する意識調査」はNISA利用・資産配分が主眼で、PER/PBR等の指標選好は調査対象外）。
- 定量データが取れたのはマネックス証券の投資家アンケート（テクニカル指標人気ランキング）のみ。1位移動平均線、2位ボリンジャーバンド、3位一目均衡表、4位MACD、5位RSI（調査母数・時期は非公開）。
- ファンダメンタル指標（PER/PBR/配当利回り/ROE）は証券会社の初心者向け教育コンテンツで一貫して「代表的な指標セット」として扱われているが、利用率調査は見当たらなかった（一般的に言われている、出典未確認）。
- 信用倍率・信用残は日本特有の需給指標として個人投資家向けに広く解説されているが、これも利用率の定量データはない。
- 米国では学術研究（アナリストEPS予想改定と個人投資家売買の関係）やSchwab/eToro/FINRAの意識調査はあるが、「何%がP/Eを見るか」のような指標別利用率を直接示す一次資料は見つからなかった。SchwabはP/E, PEG, ROE, P/B, D/Eを「5大指標」として教育コンテンツで提示。
- 既存サイトの機能マップでは、PER/PBR/配当利回り等の基礎指標は無料開放が業界標準で完全にコモディティ化。差別化軸は「決算の速報性」（株探）、「財務データの網羅性」（バフェットコード）、「AI予想・集合知」（みんかぶ）、「板情報・機関投資家データ」（moomoo/TradingView/Seeking Alpha）に移っている。
- 空白領域の考察: (1) 指標の「解釈・文脈化」レイヤー、(2) 需給データ（信用残等）の可視化、(3) 「どの指標がどれだけ効くか」の定量提示はどのサイトも行っておらず、本プロジェクトの寄与度軸と重複しない。

---

## 1. 日本の個人投資家が参照する指標

### 1-1. 公的・業界統計の状況（事実）

日本証券業協会（JSDA）は毎年「個人投資家の証券投資に関する意識調査」を実施しているが、2025年調査報告書（[jsda.or.jp 全文PDF](https://www.jsda.or.jp/shiryoshitsu/toukei/2025ishikichousasyousai.pdf)、[概要版](https://www.jsda.or.jp/shiryoshitsu/toukei/2025kozintoushika.pdf)）を全文検索したところ、調査項目は年齢・年収・金融資産保有額、NISA利用状況、投資信託購入時の重視点（「安定性やリスクの低さ」50.7%が最多）などが中心で、**個別株の銘柄選定でPER/PBR/ROE等の指標をどの程度参照するかを問う設問は含まれていない**（事実: 報告書全文で「PER」「PBR」「ROE」「配当利回り」「移動平均」「信用倍率」「テクニカル」「出来高」の出現数はいずれも0件であることを機械検索で確認）。投資信託協会のアンケート調査（[toushin.or.jp](https://www.toushin.or.jp/statistics/statistics/index.html)、[imaj調査](https://www.imaj.or.jp/statistics/report/survey/general/research2025/index.html)）も投資信託が対象で、個別株の指標選好調査は同様に見当たらなかった。

→ **日本の個人投資家の「指標別重視度」を定量化した公的一次資料は本調査では確認できなかった**（不明）。以下は証券会社の教育コンテンツ・メディア記事から再構成した間接的な実態像である。

### 1-2. ファンダメンタル指標

| 指標 | 位置づけ（証券会社解説・メディアより） | 出典 |
|---|---|---|
| PER（株価収益率） | 割安・割高判断の代表指標。「多くの投資家が投資判断に利用している」との記載あり（利用率の定量データなし） | [マネックス証券](https://info.monex.co.jp/stock/beginner/choice.html), [auカブコム証券](https://kabu.com/beginner/stock/per.html) |
| PBR（株価純資産倍率） | PBR=PER×ROEに分解可能。東証のPBR1倍割れ改善要請以降メディア露出が増加 | [バフェット・コード ガイド](https://www.buffett-code.com/guide), [経産省資料](https://www.meti.go.jp/shingikai/economy/improving_corporate_value/pdf/001_04_00.pdf) |
| 配当利回り | 高配当株スクリーニングの軸として個人投資家メディアで頻出（ランキング記事多数） | [ダイヤモンドZAi](https://diamond.jp/zai/articles/-/1021745), [松井証券](https://www.matsui.co.jp/study/dividend/) |
| ROE（自己資本利益率） | 収益性指標としてPER/PBRとセットで解説されることが多い | [マネックス証券](https://info.monex.co.jp/stock/beginner/choice.html) |
| 決算・業績修正 | 株探が「決算発表・業績修正」を専用カテゴリでリアルタイム自動配信するなど、個人投資家の関心が高いイベントとして商業的に成立している。一方、楽天証券コラムには「プロ投資家は会社発表の業績予想やそれに基づくPER・配当利回りをそのまま使わない」という指摘があり、個人とプロで参照姿勢が異なる可能性が示唆される（コラムの主張であり実証データではない） | [株探ニュース](https://kabutan.jp/news/), [楽天証券コラム](https://media.rakuten-sec.net/articles/-/8868?page=2) |

### 1-3. 需給指標（信用倍率・信用残）— 日本特有

| 指標 | 内容 | 出典 |
|---|---|---|
| 信用倍率（取組倍率） | 信用買残÷信用売残。1超＝買い長（強気過熱の警戒）、1未満＝売り長（踏み上げ期待）。株価の先行きを需給から予測する指標として広く解説されている | [野村證券 用語解説](https://www.nomura.co.jp/terms/japan/si/sinyobairitu.html), [SMBC日興証券](https://www.smbcnikko.co.jp/products/stock/margin/knowledge/017.html), [マネックス証券](https://info.monex.co.jp/news/2024/20241218_02.html) |
| 信用残高（買い残・売り残） | 週次で公表。信用買い残の急増は将来の売り圧力を示唆するとされる | [SBIネオトレード](https://www.sbineotrade.jp/margin/column/magnification/) |

利用率の定量データはないが、主要ネット証券5社以上（野村、SMBC日興、マネックス、SBIネオトレード、auカブコム）が専用解説ページを持つことから、日本市場で一定の実務的重要性を持つ指標と推定される（複数社がコンテンツを持つことは事実、利用率は不明）。

### 1-4. テクニカル指標（唯一取得できた定量データ）

マネックス証券の投資家アンケートによる「テクニカル指標人気ランキングTOP8」（[出典](https://info.monex.co.jp/technical-analysis/column/005.html)。調査時期・母数は非公開のため精度に留保が必要）。

| 順位 | 指標 | 分類 |
|---|---|---|
| 1 | 移動平均線 | トレンド系 |
| 2 | ボリンジャーバンド | トレンド系 |
| 3 | 一目均衡表 | トレンド系（日本発） |
| 4 | MACD | トレンド系 |
| 5 | RSI | オシレーター系 |
| 6 | ストキャスティクス | オシレーター系 |
| 7 | 酒田五法 | ローソク足分析 |
| 8 | RCI | オシレーター系 |

出来高単独の利用率調査は見つからなかったが、ローソク足・移動平均とともにテクニカル分析の基本要素として証券会社教材に一貫して登場する（[大和証券](https://www.daiwa.jp/seminar/technical/09/), [松井証券](https://www.matsui.co.jp/fx/study/article/analysis/technical/)）。

---

## 2. 米国個人投資家（retail investors）が参照する指標

### 2-1. 教育コンテンツ上の「標準セット」

Charles Schwabは個人投資家向けに「5 Key Financial Ratios」として **P/E、PEG、ROE、P/B、Debt-to-Equity** を提示し、EPS・P/Eを長期投資（ファンダメンタル）の基礎、移動平均・モメンタム等を短期トレード（テクニカル）の基礎と位置づけている（[Schwab: Five Key Financial Ratios](https://www.schwab.com/learn/story/five-key-financial-ratios-stock-analysis), [Schwab: Fundamentals vs Technicals](https://www.schwab.com/learn/story/how-to-pick-stocks-using-fundamental-and-technical-analysis)）。

### 2-2. アナリスト予想への反応（学術的証拠）

- McLean et al.（2021）は、アナリストのレーティング・目標株価・EPS予想の改定に対する個人投資家の売買反応を分析。個人投資家はアナリストの改定に反応しており、**ネガティブなEPS予想修正の後により強く買い増しする**（逆張り的）という結果を報告（[Retail Investors and Analysts](https://haslam.utk.edu/wp-content/uploads/2022/09/Retail-Investors-and-Analysts-McLean-1.pdf)）。
- 別のSSRN論文も、EPS予想改定の正負どちらでも個人投資家の純買いが増え、特に下方修正後に強いことを報告（[Do Retail Investors Pay Attention to Sell-Side Analysts?](https://papers.ssrn.com/sol3/Delivery.cfm/4737062.pdf?abstractid=4737062&mirid=1)）。

これらは「個人投資家がアナリスト情報（レーティング、目標株価、EPS予想）に実際に反応している」ことを取引データで示す証拠だが、アンケート形式の利用率調査ではない点に注意。

### 2-3. センチメント・意識調査

| 調査 | 内容 | 指標利用率の有無 | 出典 |
|---|---|---|---|
| Schwab Retail Client / Trader Sentiment Survey（四半期） | 相場観、地政学・原油・インフレ等の懸念要因を調査 | なし | [Schwab Q2 2026](https://www.aboutschwab.com/schwab-retail-client-sentiment-survey-q2-2026) |
| Schwab Trading Activity Index (STAX) | 顧客の実売買行動から算出する独自センチメント指数 | なし（行動ベース） | [STAX](https://www.schwab.com/investment-research/stax/view-schwab-trading-activity-index) |
| eToro Retail Investor Beat | 世界10,000人の個人投資家センチメント調査。資産配分・マクロ観が中心 | なし | [eToro](https://www.etoro.com/investing/retail-investor-beat/) |
| FINRA Foundation NFCS Investor Survey (2024) | 全米の投資家の知識・行動・態度の大規模調査 | 指標別ランキングはなし | [FINRA PDF](https://finrafoundation.org/sites/finrafoundation/files/2025-11/NFCS_Investor_Survey_Report_White_Paper.pdf) |

→ 米国でも「銘柄選びで何の指標を見るか」を直接ランキング化した大規模一次調査は本調査では発見できなかった（不明）。

### 2-4. モメンタム・Options flow・取引シェア

- Options flow（オプション大口フロー可視化）やLevel2板情報は、moomoo等のプラットフォームが個人投資家向け機能として提供している（3節参照）。利用率の統計は見つからなかった。
- MEMXの推計では、個人投資家は米国株式の日次出来高の30〜37%を占める（[MEMX Retail Trading Insights](https://memx.com/insights/retail-trading-insights)）。これは指標利用ではなく取引シェアの推計。
- WallStreetBets等のSNS発モメンタム売買の存在は学術研究の対象になっている（参加度指標+センチメントが個人投資家の協調行動の代理変数になるとするNLP研究: [ProQuest](https://search.proquest.com/openview/eb9bca4f565f3fcd2daaf0fcdd6ee6c3/1)）。

### 2-5. 参考: 指標選好の実験研究（インド）

日米の直接データではないが参考として、Gopal et al.（2025）の被験者実験（n=75、インド）では、投資判断に影響した因子として **ROE（52件言及）、P/E（48件）、3年CAGR純利益（36件）** が上位で、ESG要因（計74件言及）より最終判断はファンダメンタル指標が支配的だったと報告している（[出典](https://businessperspectives.org/journals/investment-management-and-financial-innovations/issue-474/esg-or-financial-metrics-what-retail-investors-really-look-for-in-decision-making)）。日米への一般化には留意が必要。

---

## 3. 既存サイトの機能マップ

| サイト | 主な指標・機能 | 無料 | 有料 | 出典 |
|---|---|---|---|---|
| **Yahoo!ファイナンス**（日本） | 株価・チャート・掲示板・ニュース・スクリーニング（優待、最低購入代金、指標） | 基本機能ほぼ全部 | VIP倶楽部: 注目銘柄ランキング、業績グラフ拡充、リアルタイム板気配、時系列データDL | [VIP倶楽部](https://finance.yahoo.co.jp/feature/promotion/vip/information/), [Lycorp発表](https://www.lycorp.co.jp/ja/news/release/020087/) |
| **株探（かぶたん）** | 決算・業績修正の即時分析記事（独自エンジンで自動生成・配信）、「銘柄探検」（編集部プリセットのスクリーニング相当）、テーマ・ニュース | ニュース・銘柄情報・銘柄探検 | 株探プレミアム: 過去データ拡張ほか | [株探ニュース](https://kabutan.jp/news/), [スクリーニングヘルプ](https://support.kabutan.jp/hc/ja/articles/53644738258841) |
| **バフェットコード** | 日米上場企業の財務・株価指標（30以上）のワンストップ表示、企業間比較 | 基本指標・企業比較 | スクリーニング・API等は有料プラン中心 | [トップ](https://www.buffett-code.com/), [企業比較](https://www.buffett-code.com/comps), [第三者比較記事](https://edinetdb.jp/blog/buffett-code-alternative) |
| **みんかぶ** | AI株価診断、会員の売買予想（集合知）、アナリスト予想、掲示板、資産管理連携 | 株価予想・売買シミュレーションは無料 | 有料会員で追加機能 | [トップ](https://minkabu.jp/), [銘柄分析ページ例](https://minkabu.jp/stock/3562/analysis) |
| **TradingView** | 高機能チャート、多数のテクニカル指標、ファンダ+テクニカル両対応スクリーナー、アラート | 広告あり・チャート数/指標数/アラート数に制限 | Premium等: 指標50/チャート、アラート1,000件、複数レイアウト等 | [Pricing](https://www.tradingview.com/pricing/), [Screener解説](https://www.tradingview.com/support/solutions/43000718885-tradingview-screeners-walkthrough/) |
| **Finviz** | スクリーナー（P/E, P/FCF等ファンダ+テクニカル多数）、ヒートマップ、ニュース | スクリーナーはほぼ全機能無料（遅延データ・広告あり） | Elite: リアルタイム、広告非表示、アラート、エクスポート/API、保存プリセット50→200 | [Finviz Elite](https://finviz.com/elite), [Screener Help](https://finviz.com/help/screener), [レビュー](https://www.wallstreetzen.com/blog/finviz-stock-screener-elite-review/) |
| **moomoo** | 取引アプリ+Level 2板情報、アナリストレーティング・目標株価、インサイダー取引、オプション情報、AIツール | NASDAQ Level2等の一部データ、基本チャート | プレミアム: NYSE Arcabook Level2、OPRAオプションLevel2、アナリストレーティング、インサイダー動向 | [Premium features](https://www.moomoo.com/us/support/topic4_512), [Analyst Ratings解説](https://www.moomoo.com/us/learn/detail-use-analyst-ratings-to-help-make-timely-investment-decisions-116863-230998138) |
| **Seeking Alpha** | 個人・プロ著者の銘柄分析記事、Quant Ratings（独自クオンツ格付け）、100+フィルタのスクリーナー、配当ツール | BASIC: 記事アクセスに制限 | Premium（年約269ドル）: 全記事、Quant Ratings、スクリーナー。Pro: さらに上位 | [Subscriptions](https://seekingalpha.com/subscriptions), [比較記事](https://www.matchmybroker.com/articles/seeking-alpha-subscriptions-compared) |

### 3-1. 機能マップから読み取れる共通パターン（観測）

- **基礎バリュエーション指標（PER/PBR/配当利回り/ROE/EPS）の数値表示は全サイトで無料**。数値提供そのものは差別化要因になっていない。
- 有料化の対象は主に4系統: (a) リアルタイム性・板情報（Level2）、(b) 独自アルゴリズムによる予想・格付け（Seeking Alpha Quant Ratings、みんかぶAI診断）、(c) スクリーニングの網羅性・保存数・API/エクスポート、(d) 広告非表示等のUX。
- 日本勢は「決算速報の速さ」「集合知」「財務データ網羅」で、米国勢は「チャート/スクリーナー高機能化」「機関投資家級データの開放」で差別化する傾向。

---

## 4. 考察: コモディティ化 vs 空白（付加価値の余地)

以下は本調査の事実・観測に基づく考察（指標の有効性検証は別担当のため行わない）。

### コモディティ化している領域（観測に基づく)

| 領域 | 状況 |
|---|---|
| PER/PBR/配当利回り/ROE等の数値表示 | 全調査対象サイトで無料。数値の羅列に付加価値なし |
| 主要テクニカル指標の描画 | TradingView・Finviz・各証券アプリで無料〜低コスト提供 |
| 決算速報 | 株探がほぼ制圧（独自エンジンで即時記事化）。速度勝負は分が悪い |
| スクリーナー | Finviz（米）・Yahoo!ファイナンス（日）等が無料で相当数の条件を提供 |

### 空白＝付加価値の余地（考察、要検証）

1. **「どの指標がどれだけ効くか（寄与度）」の定量提示はどのサイトも行っていない**。既存サイトは「指標の現在値」を見せることに終始しており、「PERが低いことが過去どれだけリターンに効いたか」を個人投資家向けに分かりやすく示すサービスは調査した8サイトの中に存在しなかった（観測）。本プロジェクトの中核コンセプトと既存サービスは競合しない。
2. **指標の「解釈・文脈化」レイヤー**。楽天証券コラムの「プロは会社予想ベースのPERをそのまま使わない」という指摘が示すように、数値と使い方の間にギャップがある。「同業比較・過去水準比でどうか」「なぜその水準か」の解説には余地がある（考察）。
3. **需給指標（信用残・信用倍率）の可視化の手薄さ**。日本特有の指標で解説記事は豊富な一方、銘柄横断のトレンド可視化・スクリーニングとして提供する無料サービスは限定的（バフェットコード等は財務中心で需給は手薄な様子。網羅的確認はしていないため「限定的」は推測を含む）。
4. **アナリスト予想と個人投資家行動のギャップの解説**。米国ではEPS予想改定への個人投資家の逆張り反応が学術的に確認されており、「アナリスト情報をどう読むべきか」自体がコンテンツになりうる（考察）。
5. **日本の指標選好一次データの不在**。日証協・投信協会・証券会社いずれも個別株のファンダ指標選好を定量調査しておらず、このギャップを埋める調査・コンテンツ自体に希少価値がある（観測に基づく考察）。

---

## 出典一覧

### 日本の個人投資家・指標
1. 日本証券業協会「個人投資家の証券投資に関する意識調査」 https://www.jsda.or.jp/shiryoshitsu/toukei/kojn_isiki.html
2. 同 2025年 調査結果概要（PDF） https://www.jsda.or.jp/shiryoshitsu/toukei/2025kozintoushika.pdf
3. 同 2025年 意識調査報告書 全文（PDF） https://www.jsda.or.jp/shiryoshitsu/toukei/2025ishikichousasyousai.pdf
4. 投資信託協会 統計データ https://www.toushin.or.jp/statistics/statistics/index.html
5. 投資信託協会 投資信託に関するアンケート調査報告書2025 https://www.imaj.or.jp/statistics/report/survey/general/research2025/index.html
6. マネックス証券「人気のテクニカル指標はコレだ！」 https://info.monex.co.jp/technical-analysis/column/005.html
7. マネックス証券 PER/PBR/ROE解説 https://info.monex.co.jp/stock/beginner/choice.html
8. auカブコム証券 PER/PBR/ROE解説 https://kabu.com/beginner/stock/per.html
9. バフェット・コード 財務数値ガイド https://www.buffett-code.com/guide
10. 経済産業省 企業価値向上に関する参考資料（PBR/PER/ROE） https://www.meti.go.jp/shingikai/economy/improving_corporate_value/pdf/001_04_00.pdf
11. ダイヤモンドZAi PBR1倍割れ配当利回りランキング https://diamond.jp/zai/articles/-/1021745
12. 松井証券 高配当銘柄ランキング https://www.matsui.co.jp/study/dividend/
13. 野村證券 証券用語解説集「信用倍率」 https://www.nomura.co.jp/terms/japan/si/sinyobairitu.html
14. SMBC日興証券 信用売り残高解説 https://www.smbcnikko.co.jp/products/stock/margin/knowledge/017.html
15. マネックス証券 信用建玉残高情報の活用方法 https://info.monex.co.jp/news/2024/20241218_02.html
16. SBIネオトレード証券 信用倍率とは https://www.sbineotrade.jp/margin/column/magnification/
17. 大和証券 テクニカル指標編（オシレーター系） https://www.daiwa.jp/seminar/technical/09/
18. 松井証券 テクニカル分析とは https://www.matsui.co.jp/fx/study/article/analysis/technical/
19. 楽天証券コラム「プロ投資家は企業発表の業績予想を見ていない？」 https://media.rakuten-sec.net/articles/-/8868?page=2
20. 株探 決算発表・業績修正ニュース https://kabutan.jp/news/

### 米国個人投資家・指標
21. Charles Schwab: Five Key Financial Ratios for Stock Analysis https://www.schwab.com/learn/story/five-key-financial-ratios-stock-analysis
22. Charles Schwab: How to Pick Stocks (Fundamentals vs Technicals) https://www.schwab.com/learn/story/how-to-pick-stocks-using-fundamental-and-technical-analysis
23. Schwab Q2 2026 Retail Client Sentiment Report https://www.aboutschwab.com/schwab-retail-client-sentiment-survey-q2-2026
24. Schwab Trading Activity Index (STAX) https://www.schwab.com/investment-research/stax/view-schwab-trading-activity-index
25. McLean et al. (2021) Retail Investors and Analysts https://haslam.utk.edu/wp-content/uploads/2022/09/Retail-Investors-and-Analysts-McLean-1.pdf
26. Do Retail Investors Pay Attention to Sell-Side Analysts? (SSRN) https://papers.ssrn.com/sol3/Delivery.cfm/4737062.pdf?abstractid=4737062&mirid=1
27. eToro Retail Investor Beat https://www.etoro.com/investing/retail-investor-beat/
28. FINRA Foundation NFCS Investor Survey Report (2024) https://finrafoundation.org/sites/finrafoundation/files/2025-11/NFCS_Investor_Survey_Report_White_Paper.pdf
29. MEMX Retail Trading Insights https://memx.com/insights/retail-trading-insights
30. Gopal et al. (2025) ESG or financial metrics? What retail investors really look for https://businessperspectives.org/journals/investment-management-and-financial-innovations/issue-474/esg-or-financial-metrics-what-retail-investors-really-look-for-in-decision-making
31. r/WallStreetBets NLP研究（ProQuest） https://search.proquest.com/openview/eb9bca4f565f3fcd2daaf0fcdd6ee6c3/1

### 既存サイトの機能
32. Yahoo!ファイナンス VIP倶楽部 https://finance.yahoo.co.jp/feature/promotion/vip/information/
33. LYcorp「VIP倶楽部リニューアル」発表 https://www.lycorp.co.jp/ja/news/release/020087/
34. 株探ヘルプ スクリーニング機能について https://support.kabutan.jp/hc/ja/articles/53644738258841
35. バフェット・コード トップ https://www.buffett-code.com/
36. バフェット・コード 企業比較 https://www.buffett-code.com/comps
37. EDINET DB バフェットコード代替比較記事 https://edinetdb.jp/blog/buffett-code-alternative
38. みんかぶ トップ https://minkabu.jp/
39. みんかぶ 銘柄分析ページ例 https://minkabu.jp/stock/3562/analysis
40. TradingView Pricing https://www.tradingview.com/pricing/
41. TradingView Screeners Walkthrough https://www.tradingview.com/support/solutions/43000718885-tradingview-screeners-walkthrough/
42. Finviz Elite https://finviz.com/elite
43. Finviz Help: Screener https://finviz.com/help/screener
44. WallStreetZen Finviz Elite Review https://www.wallstreetzen.com/blog/finviz-stock-screener-elite-review/
45. moomoo Premium Features https://www.moomoo.com/us/support/topic4_512
46. moomoo Analyst Ratings解説 https://www.moomoo.com/us/learn/detail-use-analyst-ratings-to-help-make-timely-investment-decisions-116863-230998138
47. Seeking Alpha Subscriptions https://seekingalpha.com/subscriptions
48. matchmybroker Seeking Alphaプラン比較 https://www.matchmybroker.com/articles/seeking-alpha-subscriptions-compared
