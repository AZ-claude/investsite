"""
T-03: data/samples/ 配下のサンプルJSONを実データから生成する。

入力:
  - pipeline/spikes/out/t03_sample_raw.json (yfinanceから取得したJP5銘柄+US5銘柄の実データ)
  - JPX「銘柄別信用取引週末残高」PDF(2026/7/3申込分, トヨタ実値を手動で書き写し。抽出ログはt03_marketcap_check系ではなく
    本タスクの偵察中にpdfplumberで実際に読み取った値)
  - JPX「信用取引現在高」xls(2026/7/3申込分, 全国合計の信用倍率9.8029倍等)
  - yfinance ^N225 / ^GSPC の直近終値

出力: data/samples/ 配下に docs/07-data-schema.md で定義したスキーマ形状のJSONを書き出す。
      個別銘柄は実データ、パーセンタイルは「サンプル10銘柄内(JP5/US5)」で計算した参考値(本番は225/503銘柄内でT-04が計算)。

実行方法: python pipeline/spikes/t03_build_samples.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLE_DIR = os.path.join(BASE, "data", "samples")

with open(os.path.join(BASE, "pipeline", "spikes", "out", "t03_sample_raw.json"), encoding="utf-8") as f:
    RAW = json.load(f)

DATE = "2026-07-10"
GENERATED_AT = RAW["generated_at"]


def percentile_rank(values_by_key):
    """{key: value} -> {key: percentile 0..1} (Noneは除外して計算、結果にはNoneのまま残す)"""
    items = [(k, v) for k, v in values_by_key.items() if v is not None]
    items.sort(key=lambda kv: kv[1])
    n = len(items)
    ranks = {}
    for i, (k, v) in enumerate(items):
        ranks[k] = round(i / (n - 1), 4) if n > 1 else 0.5
    result = {}
    for k, v in values_by_key.items():
        result[k] = ranks.get(k) if v is not None else None
    return result


def build_daily(market: str, rows: list, universe_name: str, currency: str, margin_lookup=None) -> dict:
    fields = ["per_trailing", "pbr", "dividend_yield_pct", "roe", "momentum_12_1", "market_cap"]
    by_field = {f: {} for f in fields}
    for r in rows:
        by_field["per_trailing"][r["ticker"]] = r["per_trailing"]
        by_field["pbr"][r["ticker"]] = r["pbr"]
        by_field["dividend_yield_pct"][r["ticker"]] = r["dividend_yield"]
        by_field["roe"][r["ticker"]] = r["roe"]
        by_field["momentum_12_1"][r["ticker"]] = r["momentum_12_1"]
        by_field["market_cap"][r["ticker"]] = r["market_cap"]

    percentiles = {f: percentile_rank(by_field[f]) for f in fields}

    stocks = []
    for r in rows:
        tkr = r["ticker"]
        stock = {
            "ticker": tkr,
            "name": r["name"],
            "currency": currency,
            "price": r["price"],
            "market_cap": r["market_cap"],
            "shares_outstanding": r["shares_outstanding"],
            "per_trailing": r["per_trailing"],
            "pbr": r["pbr"],
            "dividend_yield_pct": r["dividend_yield"],
            "roe": r["roe"],
            "trailing_eps": r["trailing_eps"],
            "book_value_per_share": r["book_value_per_share"],
            "momentum_12_1": r["momentum_12_1"],
            "percentile_in_universe": {
                "per_trailing": percentiles["per_trailing"][tkr],
                "pbr": percentiles["pbr"][tkr],
                "dividend_yield_pct": percentiles["dividend_yield_pct"][tkr],
                "roe": percentiles["roe"][tkr],
                "momentum_12_1": percentiles["momentum_12_1"][tkr],
                "market_cap": percentiles["market_cap"][tkr],
            },
            "data_quality": {
                "missing_fields": [f for f in ["per_trailing", "pbr", "dividend_yield_pct", "roe", "momentum_12_1"]
                                    if r.get(f if f != "dividend_yield_pct" else "dividend_yield") is None],
            },
        }
        if margin_lookup and tkr in margin_lookup:
            stock["margin"] = margin_lookup[tkr]
        stocks.append(stock)

    return {
        "date": DATE,
        "market": market,
        "universe": universe_name,
        "generated_at": GENERATED_AT,
        "source": {
            "provider": "yfinance",
            "library_version": "1.5.1",
            "note": "前営業日終値ベース(当日ザラ場価格は含まない)。PERは実績ベース(trailingPE)。"
                    "会社予想ベースのPER(Yahoo!ファイナンス等の主要表示)とは定義が異なる点に注意。",
        },
        "stocks": stocks,
    }


# --- トヨタ(7203.T)の実際の信用残高(JPX「銘柄別信用取引週末残高」2026/7/3申込分PDFより、本タスク中にpdfplumberで実測抽出) ---
MARGIN_LOOKUP_JP = {
    "7203.T": {
        "as_of_week": "2026-07-03",
        "unit": "shares",
        "outstanding_sales_shares": 2171500,
        "outstanding_purchases_shares": 22198100,
        "seido_sales_shares": 2006000,
        "seido_purchases_shares": 13888200,
        "ippan_sales_shares": 165500,
        "ippan_purchases_shares": 8309900,
        "margin_ratio_seido": round(13888200 / 2006000, 4),
        "margin_ratio_total": round(22198100 / 2171500, 4),
        "source": "JPX 銘柄別信用取引週末残高(PDF, https://www.jpx.co.jp/markets/statistics-equities/margin/05.html)",
    }
}

jp_daily = build_daily("jp", RAW["jp"], "NIKKEI225", "JPY", margin_lookup=MARGIN_LOOKUP_JP)
us_daily = build_daily("us", RAW["us"], "SP500", "USD")

os.makedirs(os.path.join(SAMPLE_DIR, "daily", DATE), exist_ok=True)
with open(os.path.join(SAMPLE_DIR, "daily", DATE, "jp.json"), "w", encoding="utf-8") as f:
    json.dump(jp_daily, f, ensure_ascii=False, indent=2)
with open(os.path.join(SAMPLE_DIR, "daily", DATE, "us.json"), "w", encoding="utf-8") as f:
    json.dump(us_daily, f, ensure_ascii=False, indent=2)

# --- data/samples/universe/{jp,us}.json ---
os.makedirs(os.path.join(SAMPLE_DIR, "universe"), exist_ok=True)
universe_jp = {
    "index": "NIKKEI225",
    "as_of": DATE,
    "source": "日経平均プロフィル ウェイトCSV(https://indexes.nikkei.co.jp/nkave/archives/file/nikkei_stock_average_weight_en.csv)",
    "count_total": 225,
    "tickers_sample": [{"ticker": r["ticker"], "name": r["name"]} for r in RAW["jp"]],
    "note": "本サンプルは225銘柄中5銘柄のみ抜粋。本番は全225銘柄を保持する。拡張時はindexキーを追加(例: TOPIX500)し、"
            "data/universe/配下に新規ファイルを追加すれば daily/*.json 側の universe フィールドで切替可能",
}
universe_us = {
    "index": "SP500",
    "as_of": DATE,
    "source": "Wikipedia List of S&P 500 companies (pandas.read_html)",
    "count_total": 503,
    "tickers_sample": [{"ticker": r["ticker"], "name": r["name"]} for r in RAW["us"]],
    "note": "本サンプルは503銘柄中5銘柄のみ抜粋。本番は全503銘柄を保持する。",
}
with open(os.path.join(SAMPLE_DIR, "universe", "jp.json"), "w", encoding="utf-8") as f:
    json.dump(universe_jp, f, ensure_ascii=False, indent=2)
with open(os.path.join(SAMPLE_DIR, "universe", "us.json"), "w", encoding="utf-8") as f:
    json.dump(universe_us, f, ensure_ascii=False, indent=2)

# --- data/samples/factors/{factor}.json ---
os.makedirs(os.path.join(SAMPLE_DIR, "factors"), exist_ok=True)

FACTOR_DEFS = {
    "value": {
        "label": "バリュー(PBR/PER)",
        "markets": ["jp", "us"],
        "definition": "PBR(実績)・PER(実績trailing)の低い銘柄群。日本ではFF2012等で頑健性が高いとされる一方、"
                       "PBR1倍割れの機械的買いは劣後するという逆説的知見も併記する(ニッセイ基礎研)。",
        "metric_field": "pbr",
        "quantile_direction": "low",
    },
    "momentum": {
        "label": "モメンタム(12-1ヶ月リターン)",
        "markets": ["jp", "us"],
        "definition": "直近1ヶ月を除く過去12ヶ月(13ヶ月前〜1ヶ月前)の株価騰落率。米国では効くが日本ではほぼ効かない"
                       "(年率0.7%, Asness 2011)という日米差を掲載する。",
        "metric_field": "momentum_12_1",
        "quantile_direction": "high",
    },
    "dividend": {
        "label": "配当利回り",
        "markets": ["jp", "us"],
        "definition": "配当利回り(%)。独立効果は弱くバリューに吸収されるという文献整理を必ず併記する(E=2)。",
        "metric_field": "dividend_yield_pct",
        "quantile_direction": "high",
    },
    "quality": {
        "label": "クオリティ(ROE、PBR×ROE)",
        "markets": ["jp", "us"],
        "definition": "ROE単体はQMJ(Quality Minus Junk)の部分近似と明示。PBR×ROE(PBROE)ビューも併載する。",
        "metric_field": "roe",
        "quantile_direction": "high",
    },
    "size": {
        "label": "サイズ(時価総額)",
        "markets": ["jp", "us"],
        "definition": "時価総額。小型×バリュー等の分位軸として他指標と組み合わせる。単独効果は消失論を明記する。",
        "metric_field": "market_cap",
        "quantile_direction": "low",
    },
}


def build_factor_history_entry(market: str, rows: list, metric_field: str, ordinal_field_map: dict) -> dict:
    key_map = {"pbr": "pbr", "momentum_12_1": "momentum_12_1", "dividend_yield_pct": "dividend_yield",
               "roe": "roe", "market_cap": "market_cap"}
    src_key = key_map[metric_field]
    values = [r[src_key] for r in rows if r.get(src_key) is not None]
    n = len(values)
    return {
        "date": DATE,
        "factor_return_1m": None,
        "factor_return_3m": None,
        "factor_return_1y": None,
        "screen_count": n,
        "note": "factor_return_* は分位ポートフォリオの超過リターン(T-04で計算、本サンプルは未算出のためnull)",
    }


for factor, meta in FACTOR_DEFS.items():
    key_map = {"pbr": "pbr", "momentum_12_1": "momentum_12_1", "dividend_yield_pct": "dividend_yield",
               "roe": "roe", "market_cap": "market_cap"}
    src_key = key_map[meta["metric_field"]]

    def today_screen(rows, reverse):
        ranked = [r for r in rows if r.get(src_key) is not None]
        ranked.sort(key=lambda r: r[src_key], reverse=reverse)
        out = []
        for i, r in enumerate(ranked):
            out.append({
                "ticker": r["ticker"],
                "rank": i + 1,
                "quantile": "top_quintile" if i < max(1, len(ranked) // 5) else "other",
                "metric_value": r[src_key],
            })
        return out

    reverse = (meta["quantile_direction"] == "high")
    factor_json = {
        "factor": factor,
        "label": meta["label"],
        "markets": meta["markets"],
        "definition": meta["definition"],
        "evidence": [
            {
                "claim": "docs/02-research/factor-evidence.md 参照(SSOT)。サイト側は出典と『未確認』注記を保持して転記する",
                "source": "docs/02-research/factor-evidence.md",
                "confirmed": True,
            }
        ],
        "history": [
            build_factor_history_entry("jp", RAW["jp"], meta["metric_field"], {}),
        ],
        "today_screen": {
            "jp": today_screen(RAW["jp"], reverse),
            "us": today_screen(RAW["us"], reverse),
        },
        "sample_note": "本サンプルはJP5銘柄・US5銘柄のみのミニ抽出。本番は225/503銘柄全体で計算する(T-04スコープ)。"
                        "history配列も本サンプルは1日分のみ(本番は日次追記で蓄積)。",
    }
    with open(os.path.join(SAMPLE_DIR, "factors", f"{factor}.json"), "w", encoding="utf-8") as f:
        json.dump(factor_json, f, ensure_ascii=False, indent=2)

# --- margin-trading.json (参考指標枠、日本のみ、週次) ---
margin_trading_json = {
    "factor": "margin-trading",
    "label": "信用倍率・信用残(日本)",
    "markets": ["jp"],
    "frequency": "weekly",
    "definition": "信用買残 ÷ 信用売残(制度信用ベース)。学術的な寄与度の実証はほぼ皆無(E=1)。"
                   "「需給参考」ラベルで隔離掲載し、エビデンス欄には『寄与の実証なし』と明記する。",
    "evidence": [
        {"claim": "寄与度の学術的実証はほぼ皆無", "source": "docs/03-metrics-ranking.md 参考指標枠", "confirmed": True}
    ],
    "data_source": {
        "provider": "JPX(日本取引所グループ)",
        "per_stock": "銘柄別信用取引週末残高(PDF, 毎週第2営業日16:30頃更新)",
        "per_stock_url": "https://www.jpx.co.jp/markets/statistics-equities/margin/05.html",
        "market_total": "信用取引現在高(Excel/PDF, 毎週第3営業日15:00頃更新)",
        "market_total_url": "https://www.jpx.co.jp/markets/statistics-equities/margin/04.html",
        "format": "PDF(銘柄別)/ Excel・PDF(市場全体)。CSV配信はない。本番実装(T-04/T-05)でPDF/Excelパーサが必要",
        "update_lag": "「N週N月N日申込分」= 前週金曜時点のスナップショットを翌週火〜水曜に公表(実質5〜8日遅れ)",
    },
    "today_screen": {
        "jp": [
            {
                "ticker": "7203.T",
                "as_of_week": "2026-07-03",
                "margin_ratio_seido": round(13888200 / 2006000, 4),
                "note": "本タスク中にJPX公式PDFをpdfplumberで実測抽出した実データ(架空値ではない)",
            }
        ]
    },
    "sample_note": "本サンプルは実測できたトヨタ(7203.T)1銘柄のみ。全225銘柄分の抽出はPDFパーサ実装が必要でT-04/T-05スコープ。",
}
with open(os.path.join(SAMPLE_DIR, "factors", "margin-trading.json"), "w", encoding="utf-8") as f:
    json.dump(margin_trading_json, f, ensure_ascii=False, indent=2)

# --- market-thermometer.json ---
market_thermometer = {
    "date": DATE,
    "jp": {
        "index": "NIKKEI225",
        "index_level": 66819.046875,
        "index_level_as_of": "2026-07-08",
        "index_change_pct_1d": round((66819.046875 - 68256.9609375) / 68256.9609375 * 100, 3),
        "index_per": None,
        "index_per_percentile_5y": None,
        "index_pbr": None,
        "index_pbr_percentile_5y": None,
        "index_per_note": "指数PER/PBRは225銘柄の時価総額加重集計が必要(T-04スコープ)。本サンプルではnull",
        "margin_market_total": {
            "as_of_week": "2026-07-03",
            "unit": "thousand_shares_and_jpy_million",
            "outstanding_sales_thousand_shares": 281113,
            "outstanding_purchases_thousand_shares": 3870000,
            "margin_ratio_national_total": 9.8029,
            "margin_ratio_tokyo": 9.8029,
            "margin_ratio_nagoya": 9.7965,
            "source": "JPX 信用取引現在高(Excel, https://www.jpx.co.jp/markets/statistics-equities/margin/04.html)",
        },
    },
    "us": {
        "index": "SP500",
        "index_level": 7540.93994140625,
        "index_level_as_of": "2026-07-09",
        "index_change_pct_1d": round((7540.93994140625 - 7482.7099609375) / 7482.7099609375 * 100, 3),
        "index_per": None,
        "index_per_percentile_5y": None,
        "index_pbr": None,
        "index_pbr_percentile_5y": None,
        "index_per_note": "指数PERは503銘柄の時価総額加重集計が必要(T-04スコープ)。本サンプルではnull",
    },
    "history": [
        {"date": DATE, "note": "本サンプルは1日分のみ。本番は日次追記で5年分蓄積し、パーセンタイル算出に用いる"}
    ],
    "source_note": "index_level/index_change_pct_1d は yfinance(^N225, ^GSPC)の実測値。"
                    "margin_market_totalはJPX公式Excel(2026/7/3申込分)をpandasで実測抽出した実データ。",
}
with open(os.path.join(SAMPLE_DIR, "factors", "market-thermometer.json"), "w", encoding="utf-8") as f:
    json.dump(market_thermometer, f, ensure_ascii=False, indent=2)

print("サンプル生成完了:")
for root, _, files in os.walk(SAMPLE_DIR):
    for fn in files:
        print(" ", os.path.relpath(os.path.join(root, fn), BASE))
