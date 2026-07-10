/**
 * data.ts — data/daily/ と data/factors/ のJSONを読むための共有データアクセス層。
 *
 * 設計方針(docs/07-data-schema.md 準拠):
 * - `data/daily/YYYY-MM-DD/{jp|us}.json`(Layer 1: 銘柄別スナップショット)
 * - `data/factors/{factor}.json`(Layer 2: ファクター単位の時系列集計。market-thermometer.json も
 *   「ファクターに準じる特殊ファイル」としてこの層に含まれる)
 * を読み込み、型付きで返す。
 *
 * ビルド耐性(T-08完了条件): 指定日のデータが無い場合は、存在する最新の日付に
 * 自動フォールバックする。データが1件も無い場合は null を返し、呼び出し側で
 * 「データなし」を正直に表示する(捏造しない・ビルドを落とさない)。
 *
 * このモジュールは T-08(トップページ)専用ではなく、T-09(ファクター個別ページ)・
 * T-10(市場サマリ等)からも再利用される共有基盤として設計している。
 * ページ固有の文言生成(日本語フォーマット等)はここに置かず、呼び出し側(.astroページ)で行う。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * リポジトリルートの data/ ディレクトリへの絶対パスを解決する。
 *
 * 注意(ハマりどころ): `import.meta.url` ベースの相対パス(`__dirname` 相当)は
 * `astro dev` では動くが、`astro build` の静的プリレンダーではソースファイルが
 * Viteにバンドルされ出力先が変わるため、ビルド後は本来の `site/src/lib/data.ts` の
 * 位置と食い違い、パス解決が壊れる(実測: 本タスクでこれが原因で daily/factors が
 * 常にnull扱いになり、ページ全体が「データなし」状態でビルドされる不具合が発生した)。
 * そのため `process.cwd()` を主軸にした複数候補からの解決に切り替えている
 * (`npm run dev`/`npm run build` は共に `site/` を cwd として実行される運用のため)。
 *
 * `INVESTSITE_DATA_ROOT` 環境変数が設定されている場合は最優先で使う
 * (欠損データケースの検証用。本物の data/ を書き換えずにコピー先を指してビルド検証できるようにする)。
 */
function resolveDataRoot(): string {
  if (process.env.INVESTSITE_DATA_ROOT) {
    return path.resolve(process.env.INVESTSITE_DATA_ROOT);
  }

  const candidates = [
    path.resolve(process.cwd(), "../data"), // cwd = site/ (通常のnpm run dev/build)
    path.resolve(process.cwd(), "data"), // cwd = リポジトリルート
    path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../data"), // devサーバー等のフォールバック
  ];

  const found = candidates.find((c) => fs.existsSync(c));
  return found ?? candidates[0];
}

const DATA_ROOT = resolveDataRoot();

export type Market = "jp" | "us";

/** 初期リリース6ファクターのスラッグ。docs/04-site-design.md 2節のURLパスと一致。 */
export const FACTOR_SLUGS = [
  "value",
  "momentum",
  "dividend",
  "quality",
  "size",
  "margin-trading",
] as const;

export type FactorSlug = (typeof FACTOR_SLUGS)[number];

// ---------------------------------------------------------------------------
// Layer 1: data/daily/YYYY-MM-DD/{jp|us}.json
// ---------------------------------------------------------------------------

/** docs/07-data-schema.md 2.3節。日本株のみ・週次更新の信用倍率情報。 */
export interface StockMargin {
  as_of_week: string;
  outstanding_sales_shares: number;
  outstanding_purchases_shares: number;
  seido_sales_shares: number;
  seido_purchases_shares: number;
  ippan_sales_shares: number;
  ippan_purchases_shares: number;
  margin_ratio_seido: number;
  margin_ratio_total: number;
  source: string;
}

/** docs/07-data-schema.md 2.2節。銘柄別レコード。 */
export interface DailyStock {
  ticker: string;
  name: string;
  currency: string;
  price: number;
  market_cap: number;
  shares_outstanding: number;
  per_trailing: number | null;
  pbr: number | null;
  dividend_yield_pct: number | null;
  roe: number | null;
  trailing_eps: number | null;
  book_value_per_share: number | null;
  momentum_12_1: number | null;
  percentile_in_universe: Record<string, number | null>;
  data_quality: { missing_fields: string[] };
  margin?: StockMargin;
}

export interface DailySnapshot {
  date: string;
  market: Market;
  universe: string;
  generated_at: string;
  source: { provider: string; library_version?: string; note?: string };
  stocks: DailyStock[];
}

/** loadDailySnapshot() の戻り値。実際に読めた日付とフォールバックの有無を併せて返す。 */
export interface DailySnapshotResult {
  data: DailySnapshot;
  resolvedDate: string;
  /** true の場合、preferredDate(または最新扱いの日付)と異なる日付にフォールバックした。 */
  isFallback: boolean;
}

/**
 * data/daily/ 配下に実在する日付ディレクトリ一覧を新しい順(降順)で返す。
 * ディレクトリが無ければ空配列(呼び出し側でビルドを落とさない前提)。
 */
export function listAvailableDailyDates(): string[] {
  const dailyDir = path.join(DATA_ROOT, "daily");
  if (!fs.existsSync(dailyDir)) return [];
  return fs
    .readdirSync(dailyDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
    .map((entry) => entry.name)
    .sort()
    .reverse();
}

/**
 * 指定市場の日次スナップショットを読む。
 *
 * 解決ルール:
 * 1. preferredDate 省略時 → 存在する最新日付を使う
 * 2. preferredDate 指定時、その日付の {market}.json が無い → 「preferredDate以前で最新」の日付に
 *    フォールバックする(前日データフォールバック要件)
 * 3. 1件もデータが無い → null を返す(ビルドを落とさず、呼び出し側で「データなし」表示)
 */
export function loadDailySnapshot(
  market: Market,
  preferredDate?: string,
): DailySnapshotResult | null {
  const dates = listAvailableDailyDates();
  if (dates.length === 0) return null;

  const candidateDates = preferredDate
    ? dates.filter((d) => d <= preferredDate)
    : dates;
  const searchOrder = candidateDates.length > 0 ? candidateDates : dates;

  for (const date of searchOrder) {
    const filePath = path.join(DATA_ROOT, "daily", date, `${market}.json`);
    if (fs.existsSync(filePath)) {
      const data = JSON.parse(fs.readFileSync(filePath, "utf-8")) as DailySnapshot;
      const targetDate = preferredDate ?? dates[0];
      return { data, resolvedDate: date, isFallback: date !== targetDate };
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Layer 2: data/factors/{factor}.json
// ---------------------------------------------------------------------------

export interface FactorEvidence {
  claim: string;
  source: string;
  confirmed: boolean;
}

/** docs/07-data-schema.md 3.1節。日次追記される時系列の1要素。 */
export interface FactorHistoryEntry {
  date: string;
  factor_return_1m?: number | null;
  factor_return_3m?: number | null;
  factor_return_1y?: number | null;
  screen_count?: number;
}

export interface FactorScreenItem {
  ticker: string;
  rank: number;
  quantile: string;
  metric_value: number;
}

export interface FactorFile {
  factor: FactorSlug;
  label: string;
  markets: Market[];
  definition: string;
  evidence: FactorEvidence[];
  history: FactorHistoryEntry[];
  /**
   * T-17で追加: factor_return_1m/3m/1y の算出方法の注記(トレーリング近似・生存/先読みバイアスの明示)。
   * 表示側はこの注記を必ず値と併記すること(誠実なエビデンス表示の方針)。
   */
  factor_return_note?: string;
  today_screen?: Partial<Record<Market, FactorScreenItem[]>>;
  /** margin-trading のみ: "weekly" */
  frequency?: string;
  data_source?: Record<string, unknown>;
}

/** data/factors/{slug}.json を読む。ファイルが無ければ null(ビルドを落とさない)。 */
export function loadFactor(slug: FactorSlug): FactorFile | null {
  const filePath = path.join(DATA_ROOT, "factors", `${slug}.json`);
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as FactorFile;
}

/** FACTOR_SLUGS 全件を一括で読む。個々のファクターが欠損していても他は返す。 */
export function loadAllFactors(): Partial<Record<FactorSlug, FactorFile>> {
  const result: Partial<Record<FactorSlug, FactorFile>> = {};
  for (const slug of FACTOR_SLUGS) {
    const f = loadFactor(slug);
    if (f) result[slug] = f;
  }
  return result;
}

/**
 * ファクターの history[] から最新1件を返す(date昇順を仮定せず、date文字列で比較して最新を選ぶ)。
 * 1件も無ければ null。
 */
export function latestFactorHistory(factor: FactorFile): FactorHistoryEntry | null {
  if (!factor.history || factor.history.length === 0) return null;
  return [...factor.history].sort((a, b) => (a.date < b.date ? 1 : -1))[0];
}

/**
 * 最新の1つ前の history エントリを返す(前日比算出用)。
 * 蓄積が1日分しかない場合は null(「前日比は明日から」を呼び出し側で表示する判断材料)。
 */
export function previousFactorHistory(factor: FactorFile): FactorHistoryEntry | null {
  if (!factor.history || factor.history.length < 2) return null;
  return [...factor.history].sort((a, b) => (a.date < b.date ? 1 : -1))[1];
}

/** ファクターの蓄積日数(history[]の件数)。「データ蓄積中(N日目)」表示に使う。 */
export function accumulatedDays(factor: FactorFile): number {
  return factor.history?.length ?? 0;
}

// ---------------------------------------------------------------------------
// market-thermometer.json (Layer 2 の特殊ファイル。docs/07-data-schema.md 3.3節)
// ---------------------------------------------------------------------------

export interface MarketThermometerSide {
  index: string;
  index_level: number;
  index_level_as_of: string;
  index_change_pct_1d: number;
  index_per: number | null;
  index_pbr: number | null;
  index_per_percentile_5y: number | null;
  index_pbr_percentile_5y: number | null;
  margin_market_total?: {
    outstanding_sales_thousand_shares: number;
    outstanding_purchases_thousand_shares: number;
    margin_ratio_national_total: number;
    source: string;
    as_of_week: string;
  };
}

export interface MarketThermometerHistoryEntry {
  date: string;
  jp: MarketThermometerSide;
  us: MarketThermometerSide;
}

export interface MarketThermometer {
  date: string;
  jp: MarketThermometerSide;
  us: MarketThermometerSide;
  history: MarketThermometerHistoryEntry[];
  source_note?: string;
}

/** data/factors/market-thermometer.json を読む。無ければ null(ビルドを落とさない)。 */
export function loadMarketThermometer(): MarketThermometer | null {
  const filePath = path.join(DATA_ROOT, "factors", "market-thermometer.json");
  if (!fs.existsSync(filePath)) return null;
  return JSON.parse(fs.readFileSync(filePath, "utf-8")) as MarketThermometer;
}

/** 市場体温計の蓄積日数(history[]の件数)。パーセンタイル欄が null の間の「N日目」表示に使う。 */
export function thermometerAccumulatedDays(thermometer: MarketThermometer): number {
  return thermometer.history?.length ?? 0;
}
