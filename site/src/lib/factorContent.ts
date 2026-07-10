/**
 * factorContent.ts — /factors/{slug}/ の解説文・寄与度エビデンス原稿(T-09)。
 *
 * SSOT: docs/02-research/factor-evidence.md。転記時は同ファイルの方針どおり
 * 出典と「未確認」注記を保持する(confirmed: false の項目には未確認バッジを出す)。
 * docs/03-metrics-ranking.md の掲載仕様(E軸による枠分け)にも整合させている。
 *
 * このファイルは data.ts とは独立(data.ts への破壊的変更は禁止のため、
 * ページ固有の文言はここに置く)。ページ側(factors/[slug].astro, factors/index.astro)から読む。
 *
 * 表現規制: 助言表現(推奨・買うべき・売るべき等)は一切含めないこと。
 */
import type { FactorSlug } from "./data";

export interface EvidenceItem {
  /** 効果の内容(数値があれば数値、無ければ方向性のみと明記) */
  claim: string;
  sourceLabel: string;
  sourceUrl?: string;
  /** factor-evidence.md で「未確認」と明記されている場合は false */
  confirmed: boolean;
}

export interface FactorContent {
  slug: FactorSlug;
  /** そもそも何か */
  whatIsIt: string;
  /** なぜ効くとされるか */
  whyItWorks: string;
  /** 日米差(あれば) */
  japanUsGap?: string;
  /** 減衰の議論(あれば) */
  decayNote?: string;
  /** 再現容易性(factor-evidence.md の★表記をそのまま転記) */
  reproducibility: string;
  evidence: EvidenceItem[];
  /** margin-trading 用: 「需給参考」枠に隔離する */
  isReference?: boolean;
  referenceNote?: string;
}

export const FACTOR_CONTENT: Record<FactorSlug, FactorContent> = {
  value: {
    slug: "value",
    whatIsIt:
      "PBR(株価純資産倍率)やPER(株価収益率)など、企業の純資産・利益といったファンダメンタルズに対して株価が割安な銘柄群を指します。学術的には「高B/M(簿価/時価、PBRの逆数)− 低B/M」の差(HML)が代表的な測り方です。",
    whyItWorks:
      "割安に放置された銘柄は、将来的に本来の価値へ株価が収れんする、あるいは追加的なリスクを負っている分だけ長期的な期待リターンが高いと説明されます(Fama & French の3ファクターモデル)。",
    japanUsGap:
      "米国はFama-French系列でデータが体系的に整備され再現性が高い一方、日本はバリュー効果自体は頑健とされつつも、「PBR1倍割れ銘柄を機械的に買う」という単純な解釈はむしろ劣後するという逆説的な報告があります(ニッセイ基礎研究所)。",
    decayNote:
      "2017〜2020年にHML(バリュー指標)は過去最大級のドローダウン(推計▲55%)を記録し、2021年以降に回復したとされています。日本でも同時期に不調→直近(2024〜2025年)は回復傾向との整理があります(野村ホールディングス)。",
    reproducibility: "★★★★☆(4/5) — 現在値の追跡は最容易。ヒストリカルな分位ポートフォリオの厳密な再現は中級者向け。",
    evidence: [
      {
        claim:
          "米国 1963〜1990年、高B/M上位10分位と低B/M下位10分位の月次リターン差は平均0.99%(年率換算約12%。ただし極端分位間の差であり実務的なHMLの定義とは異なる点に注意)。",
        sourceLabel: "Fama & French (1992) \"The Cross-Section of Expected Stock Returns\", JF",
        confirmed: true,
      },
      {
        claim:
          "Fama & French (2012) は日米欧豪の4地域全てでバリュープレミアムを確認。日本のみ大型株でもバリュー効果が縮小しないという特異性を報告。",
        sourceLabel: "Fama & French (2012) \"Size, Value, and Momentum in International Stock Returns\", JFE",
        sourceUrl: "https://www.sciencedirect.com/science/article/abs/pii/S0304405X12000931",
        confirmed: true,
      },
      {
        claim:
          "PBR1倍割れ銘柄群を機械的に買うだけでは、その後5年間でTOPIXを年率約2〜3%下回ったという逆説的な結果。単純スクリーニングの限界を示す。",
        sourceLabel: "ニッセイ基礎研究所「日本のバリュー株に『本当の値打ちがある』のか」",
        sourceUrl: "https://www.nli-research.co.jp/report/detail/id=71292?site=nli",
        confirmed: true,
      },
      {
        claim:
          "米国HMLの長期平均は年率3〜5%程度が通説とされるが、これは二次解説記事由来であり学術原典での正確な年率値は未確認。日本は一貫した年率数値の学術コンセンサスが手薄(方向性のみ確認)。",
        sourceLabel: "docs/02-research/factor-evidence.md 1節(調査上の注記)",
        confirmed: false,
      },
    ],
  },

  momentum: {
    slug: "momentum",
    whatIsIt:
      "過去12ヶ月(直近1ヶ月を除く)のリターンが高い銘柄群を指します。「12-1ヶ月モメンタム」と呼ばれる定義が学術上の標準です。",
    whyItWorks:
      "投資家の反応不足(アンダーリアクション)や情報の徐々の織り込みにより、株価トレンドが一定期間持続するためと説明されます(Jegadeesh & Titman 1993)。",
    japanUsGap:
      "日本はモメンタムがほぼ効かない世界的な例外として知られています。Asness (2011) は日本のモメンタムを年率0.7%・シャープレシオ0.03(1981〜2010年)と報告し、Fama & French (2012) も日本のモメンタムスプレッドを月次−0.08%(他地域は全て正)と報告しています。一方で、バリューとの逆相関を利用した50/50合成ではシャープレシオ0.65まで改善するとの報告や、市場・ファクター調整後の「残差モメンタム」は日本でも有効とする研究もあります。",
    decayNote:
      "公表後の減衰は他のアノマリーと比べて小さいとされますが、急落後の反発局面で崩壊するモメンタムクラッシュのテールリスクと、頻繁な売買によるコスト増が実装上の課題として指摘されています。",
    reproducibility: "★★★☆☆(3/5) — 計算自体は株価時系列のみで可能。日本では「そもそも効きにくい」という前提での注記が必須。",
    evidence: [
      {
        claim: "米国 1965〜1989年、形成・保有期間の全組合せで正のリターンを実証。年率約12%(取引コスト控除前)。",
        sourceLabel: "Jegadeesh & Titman (1993) \"Returns to Buying Winners and Selling Losers\", JF",
        confirmed: true,
      },
      {
        claim: "日本のJTモメンタムは年率0.7%・シャープレシオ0.03(1981〜2010年)。ほぼ効かない。",
        sourceLabel: "Asness (2011) \"Momentum in Japan: The Exception That Proves the Rule\"",
        sourceUrl: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1776123",
        confirmed: true,
      },
      {
        claim: "市場急落後の反発局面でモメンタム戦略が崩壊する現象(2009年に大幅損失)を体系化。",
        sourceLabel: "Daniel & Moskowitz (2016) \"Momentum Crashes\"",
        sourceUrl: "https://www.stern.nyu.edu/sites/default/files/assets/documents/con_038332.pdf",
        confirmed: true,
      },
      {
        claim: "市場・ファクター調整後の「残差モメンタム」は日本でも有効との報告(通常のモメンタムとは定義が異なる)。",
        sourceLabel: "\"Residual momentum in Japan\", Journal of Empirical Finance",
        sourceUrl: "https://www.sciencedirect.com/science/article/abs/pii/S0927539817301093",
        confirmed: true,
      },
    ],
  },

  dividend: {
    slug: "dividend",
    whatIsIt: "予想または実績の配当利回りが高い銘柄群を指します。",
    whyItWorks:
      "配当利回りの高さは割安さ(バリュー)の一側面と解釈されることが多く、独立した効果というよりバリューファクターに吸収されるとの見方が学術的には有力です。",
    japanUsGap:
      "日本では2024年以降の新NISA拡大に伴う高配当株ブームが需給を押し上げ、配当ファクターのロング・ショートが直近1年で+11%超と主要ファクター中最高だったとの報道があります。ただしこれが構造的なプレミアムなのか、一時的な需給要因なのかは未確認です。",
    decayNote: "米国では公表後に効果が弱まったとの指摘があり、独立効果自体が脆弱でバリューの代理変数と考えるのが安全とされています。",
    reproducibility: "★★★★★(5/5) — 全無料スクリーナーでランキング取得可。ただし減配前の見かけ高利回り銘柄の排除には追加の財務確認が必要。",
    evidence: [
      {
        claim:
          "サイズ・バリューをコントロールすると超過リターンは年率2%台以下に縮小、あるいは消失するとの報告(数値は目安)。独立ファクターというよりバリューに吸収されるとの見方が有力。",
        sourceLabel: "FPA \"Dividend Investing: A Value Tilt in Disguise?\"",
        sourceUrl: "https://www.financialplanningassociation.org/article/journal/APR13-dividend-investing-value-tilt-disguise",
        confirmed: false,
      },
      {
        claim: "日本株市場で配当ファクターのロング・ショートが直近1年で+11%超と主要ファクター中最高だったとの報道。構造的プレミアムか需給の一時要因かは未確認。",
        sourceLabel: "Bloomberg (2025-02)「配当ファクターが日本株市場で存在感」",
        sourceUrl: "https://www.bloomberg.co.jp/news/articles/2025-02-12/SRJJVBT0G1KW00",
        confirmed: false,
      },
    ],
  },

  quality: {
    slug: "quality",
    whatIsIt:
      "収益性・成長性・安全性(低レバレッジ・低利益変動)などの複合スコアが高い銘柄群を指します。代表的な指標はROE(自己資本利益率)で、実務ではPBRと組み合わせた「PBROE」ビューも使われます。",
    whyItWorks:
      "収益性が高く財務健全性の高い企業は、将来の業績が安定しやすく、市場がそのクオリティを過小評価している場合に超過リターンが生まれると説明されます(Asness, Frazzini & Pedersen の QMJ = Quality Minus Junk)。",
    japanUsGap:
      "QMJは検証した24カ国全て(日本含む)で正のリスク調整後リターンが確認されています。国内実務では「高ROE銘柄は割高化しがち」として、PBRと組み合わせる併用アプローチ(PBROE)が提案されています。",
    reproducibility:
      "★★☆☆☆(2/5) — ROE単体なら無料スクリーナーで容易だが、QMJ本来の複合スコア(粗利益率・アクルーアル・レバレッジ等の合成)は財務データの継続取得・加工が必要。本サイトのROE表示は「QMJの部分近似」であることに留意。",
    evidence: [
      {
        claim: "米国1957年〜および24カ国で検証し、24カ国すべて(日本含む)で正のリスク調整後リターンを確認。米国で年率約4.7%(1958〜2018年)。",
        sourceLabel: "Asness, Frazzini & Pedersen (2019) \"Quality Minus Junk\", Review of Accounting Studies",
        sourceUrl: "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2312432",
        confirmed: true,
      },
      {
        claim: "日本単独の年率効果量は本調査では特定できず(方向性のみ確認)。",
        sourceLabel: "docs/02-research/factor-evidence.md 3節",
        confirmed: false,
      },
    ],
  },

  size: {
    slug: "size",
    whatIsIt: "時価総額の小さい銘柄群を指します(いわゆる小型株効果)。Fama-FrenchのSMBファクターが代表的な測り方です。",
    whyItWorks:
      "小型株は情報の非対称性や流動性リスクが大きく、その分だけ追加的なリスクプレミアムが乗るためと説明されます(Banz 1981)。ただし近年は「単独では効果がほぼ消失した」という整理が優勢です。",
    japanUsGap:
      "小型>大型という方向性は日米で概ね一致しますが、単一の年率数値を語りにくいという特徴があります。日本の推計は研究により1.4%〜10.6%と期間・手法でばらつきが非常に大きいことが知られています。",
    decayNote:
      "米国では「公表後に効果がほぼ消失した」との議論が有力です。一方、低クオリティ小型株(いわゆる「ジャンク株」)を除けばプレミアムは健在とする反論もあり、サイズ単独ではなくクオリティとの併用が現在の主流的な整理です。",
    reproducibility: "★★★★★(5/5) — 時価総額は最も入手容易。計算も分位分けのみ。",
    evidence: [
      {
        claim: "米国1936〜1975年で小型株効果を発見。効果は極小型株に集中する非線形性が知られる。",
        sourceLabel: "Banz (1981) \"The Relationship Between Return and Market Value of Common Stocks\", JFE",
        confirmed: true,
      },
      {
        claim:
          "日本の推計は岡田(2006)10.6%、山口(2007)2.0%、太田他(2012)1.4%、砂川・加藤(2015)3.7%と、期間・手法によるばらつきが非常に大きい。",
        sourceLabel: "日本の小型株効果推計サーベイ(証券アナリストジャーナル)",
        sourceUrl: "https://www.saa.or.jp/dc/sale/apps/journal/JournalShowDetail.do?goDownload=&itmNo=35526",
        confirmed: true,
      },
      {
        claim: "低クオリティ小型株を除けばサイズプレミアムは健在という反論(「Size Matters, If You Control Your Junk」)。",
        sourceLabel: "Asness et al. (2018)",
        confirmed: true,
      },
    ],
  },

  "margin-trading": {
    slug: "margin-trading",
    isReference: true,
    referenceNote:
      "文献による寄与度エビデンスはありません。この指標は「需給の参考情報」として掲載しており、寄与度あり枠の指標(バリュー・モメンタム等)とは明確に区別しています。",
    whatIsIt:
      "信用買残 ÷ 信用売残(制度信用ベース)で計算する需給指標です。買い残過多は将来の売り圧力(将来売られる可能性)、売り残過多は踏み上げ期待(将来の買い戻し圧力)、と解釈されることがあります。",
    whyItWorks:
      "「なぜ効くか」を語れるだけの学術的な定量エビデンスは本調査では確認できていません。証券会社の解説でも「単独では判断材料として不十分」との留保が付いています。学術的に最も近いのは米国のショートインタレスト研究(空売り比率が高いほど将来リターンが低い傾向)ですが、日本の信用倍率への直接の適用は限定的です。",
    reproducibility:
      "★★★★★(5/5) — JPXが週次で無料公表しており取得は最容易。ただし「データは最も取りやすいがエビデンスは最も弱い」という非対称性に注意が必要です。",
    evidence: [
      {
        claim: "信用倍率が将来リターンに寄与するという学術的な定量エビデンスは本調査では確認できず(方向性のみ、数値は未確認)。",
        sourceLabel: "docs/02-research/factor-evidence.md 8節",
        confirmed: false,
      },
    ],
  },
};
