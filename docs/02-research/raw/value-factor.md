# 調査素材: バリューファクター(PBR/PER/EV-EBITDA)

状態: 子エージェント調査結果の原文保存(統合前の素材)。統合先: ../factor-evidence.md

## 1. エビデンス(学術・実務)

**米国:**
- Fama & French (1992) "The Cross-Section of Expected Stock Returns", Journal of Finance — 簿価時価比率(B/M)が将来リターンを説明する主要変数であることを実証。1963-1990年で、高B/M上位10分位と低B/M下位10分位の月次リターン差は平均0.99%(年率換算で約12%、ただし極端分位ポートフォリオの差であり実務上のHMLファクターとは定義が異なる点に注意)。
- Fama & French (1993) で3ファクターモデル(HML含む)を提示。HMLの長期平均年率プレミアムは一般に**年率3〜5%程度**とされる(出典: MetricGate/StableBread等の解説記事。学術原典での正確な年率値は本調査では未確認、数値は目安)。

**日本:**
- 学術論文「日本株式市場におけるバリュー株効果要因分析」(西岡, 証券アナリストジャーナル懸賞論文, 2007)ではバリュー効果の多くが「一時的バリュー」要因によるという分析結果。
- ニッセイ基礎研究所のレポートでは、過去25年の分析でPBR1倍割れ銘柄群がその後5年間でTOPIXを**年率約2〜3%下回った**という逆説的な結果も報告されており、単純なPBRスクリーニングだけでは一様にプラスの効果が出るわけではないことを示唆。
- 野村證券(2025年)のレポートでは、1970〜2024年の55年間でバリュー効果はおおむね安定的に観測され、情報レシオ(IR)の目安として「1.0程度」を効果の基準としているが、具体的な年率超過リターンの数値は記事内で確認できず(未確認)。

## 2. 効果の大きさ

- 米国: HML年率プレミアムはおおよそ**3〜5%**が目安(出典未特定、要検証)。
- 日本: 具体的な年率超過リターンの一貫した数値は確認できず。PBR単体戦略は時期依存性が強く、2000年代前半は好調、2017年前後は不調、直近は回復傾向という定性的トレンドのみ確認。**数値は未確認**。

## 3. 日米差

米国は学術文献(Fama-French系列)でデータが体系化され数値の再現性が高いのに対し、日本株は運用会社・証券会社のレポートが中心で、統一された年率数値の学術コンセンサスが手薄。日本では「PBR1倍割れ=割安」という単純な解釈がむしろ逆効果になり得るとの指摘(ニッセイ基礎研)がある点が米国の教科書的HML研究と異なる。

## 4. 近年の減衰(factor decay)議論

- AQR (Israel, Laursen, Richardson, 2020) "Is (Systematic) Value Investing Dead?" — 2017-2019年はほぼ全てのバリュー指標でマイナスリターンとなったが、統計的・経済的裏付けは大きく変化していないと結論。
- McLean & Pontiff (2016) — アノマリーは学術公表後にアルファの約半分が消失するという一般的なファクター減衰の実証結果あり(バリュー限定ではない一般論)。
- 2021年以降のリバイバル: 2022年にはFama-French米国HMLが年初来+18.8%(8月時点)と20年ぶりの好成績を記録(出典: 検索結果記事、一次データ未確認)。金利上昇・グロース株のバリュエーション調整が主因とされる。
- 日本でも野村證券のレポートで2017-2020年の不調後、直近(2024-2025年)は日銀利上げ期待を追い風にバリュー株が年初来高値圏に接近との記述あり。

## 5. 再現容易性の評価: ★★★☆☆(5段階中3)

**理由:**
- データ入手: 米国はYahoo Finance / yfinance(無料Pythonライブラリ)でPER・PBR(priceToBook)を含む主要指標が取得可能で容易。日本株もYahoo!ファイナンスやEDINET(XBRL財務データ、無料)で財務諸表自体は入手できるが、PBR/PERの時系列・ヒストリカルな指標データを個人が無料で大量取得するのは米国よりやや手間がかかる(EDINETは生の財務諸表であり指標化に加工が必要)。
- 計算自体(PBR = 時価総額/純資産、PER = 時価総額/純利益)は単純だが、ポートフォリオ構築(分位分け、リバランス、生存バイアス除去、配当込みリターン計算)を正確に行うにはある程度のプログラミング・データクレンジング能力が必要。
- Yahoo Financeのスクリーナー自体はバックテスト機能を持たないため、厳密な学術論文レベルの検証(五分位ポートフォリオの年率リターン算出等)を個人が再現するには、無料データ+自作コード(yfinance等)での構築が必要で、中級者向けの難易度。

## 出典一覧
- [Fama-French Three-Factor Asset Pricing Calculator (MetricGate)](https://metricgate.com/docs/fama-french-three-factor-model/)
- [How to Calculate and Interpret the Fama and French and Carhart Multifactor Models (StableBread)](https://stablebread.com/fama-french-carhart-multifactor-models/)
- [BOOK-TO-MARKET EFFECT AND FAMA FRENCH](http://arc.hhs.se/download.aspx?MediumId=574)
- [The Value Premium and the CAPM (Fama & French, Dartmouth)](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/acrobat/Size%20Value%20and%20the%20CAPM_2005_05.pdf)
- [日本株式市場におけるバリュー株効果要因分析(西岡, 証券アナリストジャーナル)](https://www.saa.or.jp/journal/prize/pdf/2007nishioka.pdf)
- [日本のバリュー株に「本当の値打ちがある」のか(ニッセイ基礎研究所)](https://www.nli-research.co.jp/report/detail/id=71292?site=nli)
- [国内株式のバリュー効果について(野村ホールディングス 財界観測)](https://www.nomuraholdings.com/jp/services/global_research/zaikai/news20250301102962.html)
- [バリュー株、2025年来高値水準に接近(NOMURA ウェルスタイル)](https://www.nomura.co.jp/wealthstyle/article/0680/)
- [Is (Systematic) Value Investing Dead? (AQR, 2020)](https://www.aqr.com/Insights/Perspectives/Is-Systematic-Value-Investing-Dead)
- [The Reports of Factor Investing's Death Are Greatly Exaggerated (Larry Swedroe)](https://larryswedroe.substack.com/p/the-reports-of-factor-investings)
- [The Great Value Rotation (Forbes, 2021)](https://www.forbes.com/sites/jeffhenriksen/2021/03/04/the-great-value-rotation-a-revival-in-the-performance-of-value-stocks-masks-an-evolution-in-the-storied-investment-strategy/)
- [Rotation from growth to value stocks and its implications (BIS)](https://www.bis.org/publ/qtrpdf/r_qt2203x.htm)
- [GitHub - ranaroussi/yfinance](https://github.com/ranaroussi/yfinance)
- [Free Stock Screener - Yahoo Finance](https://finance.yahoo.com/research-hub/screener/equity/)

※数値のうち出典元一次論文まで遡って確認できなかったもの(米国HMLの年率3〜5%、2022年+18.8%など)は「方向性のみ確認、数値は二次情報由来で未確認」として扱う。
