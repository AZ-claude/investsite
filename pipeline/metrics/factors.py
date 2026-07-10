"""T-05: factors/{factor}.json および market-thermometer.json / margin-trading.json の

日次追記(upsert)ロジック。ネットワーク・ファイルI/Oなし(純粋関数、単体テストしやすい形に分離)。
docs/07-data-schema.md 3節のスキーマに従う。

設計判断(T-05時点):
  - `factor_return_1m/3m/1y`(分位ポートフォリオの超過リターン)は簡易バックテスト実装が前提で
    T-15(P4)スコープ。T-05では算出せず null のまま保持する(架空値を埋めない、docs/07 8節の方針を踏襲)。
  - today_screen の分位判定は上位/下位20%(квинタイル)を `quantile_direction` に従って抽出する。
  - history は日付で upsert(同一日付の再実行は置換)し、常に日付昇順を維持する = 冪等。
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from pipeline.metrics.calculations import metric_value_for_ranking

FACTOR_DEFS: dict[str, dict] = {
    "value": {
        "label": "バリュー(PBR/PER)",
        "markets": ["jp", "us"],
        "definition": "PBR(実績)・PER(実績trailing)の低い銘柄群。日本ではFF2012等で頑健性が高いとされる一方、"
                       "PBR1倍割れの機械的買いは劣後するという逆説的知見も併記する(ニッセイ基礎研)。",
        "metric_field": "pbr",
        "quantile_direction": "low",
        "default_evidence": [
            {"claim": "docs/02-research/factor-evidence.md 参照(SSOT)。出典と『未確認』注記を保持して転記する",
             "source": "docs/02-research/factor-evidence.md", "confirmed": True}
        ],
    },
    "momentum": {
        "label": "モメンタム(12-1ヶ月リターン)",
        "markets": ["jp", "us"],
        "definition": "直近1ヶ月を除く過去12ヶ月(13ヶ月前〜1ヶ月前)の株価騰落率。米国では効くが日本ではほぼ効かない"
                       "(年率0.7%, Asness 2011)という日米差を掲載する。",
        "metric_field": "momentum_12_1",
        "quantile_direction": "high",
        "default_evidence": [
            {"claim": "docs/02-research/factor-evidence.md 参照(SSOT)。出典と『未確認』注記を保持して転記する",
             "source": "docs/02-research/factor-evidence.md", "confirmed": True}
        ],
    },
    "dividend": {
        "label": "配当利回り",
        "markets": ["jp", "us"],
        "definition": "配当利回り(%)。独立効果は弱くバリューに吸収されるという文献整理を必ず併記する。",
        "metric_field": "dividend_yield_pct",
        "quantile_direction": "high",
        "default_evidence": [
            {"claim": "docs/02-research/factor-evidence.md 参照(SSOT)。出典と『未確認』注記を保持して転記する",
             "source": "docs/02-research/factor-evidence.md", "confirmed": True}
        ],
    },
    "quality": {
        "label": "クオリティ(ROE、PBR×ROE)",
        "markets": ["jp", "us"],
        "definition": "ROE単体はQMJ(Quality Minus Junk)の部分近似と明示。PBR×ROE(PBROE)ビューも併載する。",
        "metric_field": "roe",
        "quantile_direction": "high",
        "default_evidence": [
            {"claim": "docs/02-research/factor-evidence.md 参照(SSOT)。出典と『未確認』注記を保持して転記する",
             "source": "docs/02-research/factor-evidence.md", "confirmed": True}
        ],
    },
    "size": {
        "label": "サイズ(時価総額)",
        "markets": ["jp", "us"],
        "definition": "時価総額。小型×バリュー等の分位軸として他指標と組み合わせる。単独効果は消失論を明記する。",
        "metric_field": "market_cap",
        "quantile_direction": "low",
        "default_evidence": [
            {"claim": "docs/02-research/factor-evidence.md 参照(SSOT)。出典と『未確認』注記を保持して転記する",
             "source": "docs/02-research/factor-evidence.md", "confirmed": True}
        ],
    },
}

QUANTILE_FRACTION = 0.2  # 上位/下位20%(五分位)を today_screen の対象とする


def upsert_history(history: Sequence[dict], entry: dict) -> list[dict]:
    """historyをdateキーでupsertし、日付昇順にソートして返す(同一日付の再実行=冪等な置換)。"""
    date = entry["date"]
    out = [h for h in history if h.get("date") != date]
    out.append(entry)
    out.sort(key=lambda h: h["date"])
    return out


def build_today_screen(rows: Sequence[dict], field: str, direction: str,
                        quantile_frac: float = QUANTILE_FRACTION) -> list[dict]:
    """指定フィールドでランキングし、上位/下位quantile_frac(既定20%、五分位)に quantile='top_quintile' を付与する。

    direction: "low"(値が低いほど上位、例: PBR) | "high"(値が高いほど上位、例: モメンタム)
    値がNoneの銘柄はランキング対象から除外する(欠損はスクリーニング対象外)。
    定義不能な値(pbr<=0・per_trailing<=0: 簿価・利益が非正でB/M等が定義できない銘柄)も
    欠損と同様にランキング対象外とする(T-04fix。calculations.metric_value_for_ranking参照)。
    空リストの場合は空リストを返す(境界値: 銘柄0件)。
    """
    ranked = [
        (r, v) for r in rows
        if (v := metric_value_for_ranking(field, r.get(field))) is not None
    ]
    reverse = direction == "high"
    ranked.sort(key=lambda rv: rv[1], reverse=reverse)
    n = len(ranked)
    top_n = max(1, math.ceil(n * quantile_frac)) if n else 0
    out = []
    for i, (r, v) in enumerate(ranked):
        out.append({
            "ticker": r["ticker"],
            "rank": i + 1,
            "quantile": "top_quintile" if i < top_n else "other",
            "metric_value": v,
        })
    return out


def build_factor_history_entry(date: str, screen_count: int) -> dict:
    return {
        "date": date,
        "factor_return_1m": None,
        "factor_return_3m": None,
        "factor_return_1y": None,
        "screen_count": screen_count,
    }


def build_factor_snapshot(existing: Optional[dict], factor: str, date: str,
                           jp_stocks: Sequence[dict], us_stocks: Sequence[dict]) -> dict:
    """factors/{factor}.json 相当の辞書を構築する(既存があればhistoryを引き継いでupsert)。"""
    meta = FACTOR_DEFS[factor]
    field = meta["metric_field"]
    direction = meta["quantile_direction"]
    markets = meta["markets"]

    today_screen = {
        "jp": build_today_screen(jp_stocks, field, direction) if "jp" in markets else [],
        "us": build_today_screen(us_stocks, field, direction) if "us" in markets else [],
    }
    # screen_count = スクリーニング該当数(分位該当=top_quintileの銘柄数、jp+us合計)。
    # docs/04-site-design.md「注目シグナル(該当件数の前日差)」の定義に対応する
    # (データが揃った銘柄の総数ではない点に注意。T-05fixで修正)。
    screen_count = sum(
        1 for m in ("jp", "us") for r in today_screen.get(m, []) if r["quantile"] == "top_quintile"
    )
    entry = build_factor_history_entry(date, screen_count)

    history = list((existing or {}).get("history") or [])
    history = upsert_history(history, entry)

    return {
        "factor": factor,
        "label": meta["label"],
        "markets": markets,
        "definition": meta["definition"],
        "evidence": (existing or {}).get("evidence") or meta["default_evidence"],
        "history": history,
        "today_screen": today_screen,
    }


MARGIN_TRADING_DEFAULT_EVIDENCE = [
    {"claim": "寄与度の学術的実証はほぼ皆無", "source": "docs/03-metrics-ranking.md 参考指標枠", "confirmed": True}
]


def build_margin_trading_snapshot(existing: Optional[dict], date: str, jp_stocks: Sequence[dict]) -> dict:
    """factors/margin-trading.json 相当の辞書を構築する(週次データ、JPのみ)。"""
    rows = [dict(ticker=s["ticker"], **s["margin"]) for s in jp_stocks if s.get("margin")]
    rows.sort(key=lambda r: (r.get("margin_ratio_seido") or 0), reverse=True)
    today_screen_jp = [
        {
            "ticker": r["ticker"],
            "as_of_week": r.get("as_of_week"),
            "margin_ratio_seido": r.get("margin_ratio_seido"),
        }
        for r in rows
    ]
    entry = {"date": date, "screen_count": len(today_screen_jp)}
    history = list((existing or {}).get("history") or [])
    history = upsert_history(history, entry)

    return {
        "factor": "margin-trading",
        "label": "信用倍率・信用残(日本)",
        "markets": ["jp"],
        "frequency": "weekly",
        "definition": "信用買残 ÷ 信用売残(制度信用ベース)。学術的な寄与度の実証はほぼ皆無。"
                       "「需給参考」ラベルで隔離掲載し、エビデンス欄には『寄与の実証なし』と明記する。",
        "evidence": (existing or {}).get("evidence") or MARGIN_TRADING_DEFAULT_EVIDENCE,
        "data_source": {
            "provider": "JPX(日本取引所グループ)",
            "per_stock": "銘柄別信用取引週末残高(PDF, 毎週第2営業日16:30頃更新)",
            "per_stock_url": "https://www.jpx.co.jp/markets/statistics-equities/margin/05.html",
            "format": "PDF。CSV配信はない。",
            "update_lag": "「N週N月N日申込分」= 前週金曜時点のスナップショットを翌週火〜水曜に公表(実質5〜8日遅れ)",
        },
        "history": history,
        "today_screen": {"jp": today_screen_jp},
    }


def build_market_thermometer_snapshot(
    existing: Optional[dict],
    date: str,
    jp_index: Optional[dict],
    us_index: Optional[dict],
    margin_market_total: Optional[dict],
) -> dict:
    """factors/market-thermometer.json 相当の辞書を構築する(市場体温計、指数レベル)。

    jp_index/us_index: fetch_yfinance.fetch_index_quote() の戻り値相当
        {"level": ..., "level_as_of": ..., "change_pct_1d": ...} または None(未取得市場)
    index_per/index_pbr(時価総額加重の指数PER/PBR)はT-04/T-05スコープ外(全銘柄集計要)のためnull固定。
    5年パーセンタイルはhistory蓄積が進んでから算出可能なため、蓄積が浅い間はnullのまま運用する
    (docs/07-data-schema.md 3.3節の設計方針通り)。
    """
    history = list((existing or {}).get("history") or [])

    def block(index_name, idx, extra=None):
        if idx is None:
            return None
        b = {
            "index": index_name,
            "index_level": idx.get("level"),
            "index_level_as_of": idx.get("level_as_of"),
            "index_change_pct_1d": idx.get("change_pct_1d"),
            "index_per": None,
            "index_pbr": None,
            "index_per_percentile_5y": None,
            "index_pbr_percentile_5y": None,
        }
        if extra:
            b.update(extra)
        return b

    jp_block = block("NIKKEI225", jp_index, {"margin_market_total": margin_market_total} if margin_market_total else None)
    us_block = block("SP500", us_index)

    entry = {"date": date, "jp": jp_block, "us": us_block}
    history = upsert_history(history, entry)

    # 常に「history中の最新日付」を top-level jp/us に反映する(--dateによる過去日backfill実行時に
    # 新しい日付のtop-levelが古い日付の書き込みで上書き退行しないようにするため)。
    latest = history[-1]
    result_jp = latest.get("jp") or (existing or {}).get("jp")
    result_us = latest.get("us") or (existing or {}).get("us")

    return {
        "date": latest["date"],
        "jp": result_jp,
        "us": result_us,
        "history": history,
        "source_note": "index_level/index_change_pct_1d は yfinance(^N225, ^GSPC)の実測値。"
                        "margin_market_totalはJPX公式Excel(週次)の実測値。"
                        "index_per/index_pbrは全銘柄時価総額加重集計が必要なためT-05時点ではnull固定"
                        "(将来の指標拡充スコープ)。",
    }
