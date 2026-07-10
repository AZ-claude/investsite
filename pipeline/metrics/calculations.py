"""指標計算の純粋関数群(ネットワーク・ファイルI/Oなし。単体テストしやすい形に分離)。

docs/07-data-schema.md 2.2節のフィールド定義に厳密に従う:
  - per_trailing: 実績PER(trailingPE)。yfinance値を優先し、欠損時のみ price/eps でフォールバック計算
  - pbr: PBR(priceToBook)。同様にフォールバックあり
  - dividend_yield_pct: 配当利回り(%)。yfinance 1.5.1の dividendYield は既にパーセント単位の数値
    (例: AAPL=0.34 は 0.34% を意味する。フラクション(0.0034)ではない。実測で確認済み)なのでそのまま採用する
  - roe: yfinance の returnOnEquity をそのまま採用(フラクション表記、例 0.102 = 10.2%)。
    パーセント変換はしない(サイト表示側の責務。データ層は生の比率を保持する)
  - momentum_12_1: 12-1ヶ月モメンタム。直近1ヶ月(約21営業日)を除く過去12ヶ月(約231営業日前〜21営業日前)の騰落率。
    T-01/T-02/T-03のスパイクで使われた定義(end_idx=-22, start_idx=-22-231)をそのまま踏襲する
  - market_cap: shares_outstanding × price のyfinance内部式をそのまま踏襲(T-03 5節で検証済み、乖離はsharesOutstanding由来)
"""
from __future__ import annotations

from typing import Iterable, Sequence


def safe_div(numerator, denominator):
    """ゼロ除算・None入力に対して安全な除算。None or 0除算の場合は None を返す。"""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    try:
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def compute_per_trailing(trailing_pe, price=None, eps=None):
    """実績PER。yfinanceの trailingPE を優先採用。

    欠損時のみ price/eps からのフォールバック計算を試みる(EPS<=0 の場合は意味を持たない
    ため None を返す。将来の連続赤字銘柄の混入等に対する境界値対策)。
    """
    if trailing_pe is not None:
        return trailing_pe
    if eps is None or eps <= 0:
        return None
    return safe_div(price, eps)


def compute_pbr(price_to_book, price=None, book_value_per_share=None):
    """PBR。yfinanceの priceToBook を優先採用。欠損時のみ price/BPS からフォールバック計算。"""
    if price_to_book is not None:
        return price_to_book
    if book_value_per_share is None or book_value_per_share <= 0:
        return None
    return safe_div(price, book_value_per_share)


def compute_dividend_yield_pct(dividend_yield_raw):
    """配当利回り(%)。yfinance 1.5.1 の dividendYield は既にパーセント単位のためそのまま返す。

    None(無配・非開示)はそのままNoneとして保持する(欠損は`null`、フィールド自体は残す方針)。
    """
    return dividend_yield_raw


def compute_roe(return_on_equity_raw):
    """ROE。yfinanceの returnOnEquity(フラクション表記)をそのまま返す。"""
    return return_on_equity_raw


def compute_market_cap(shares_outstanding, price):
    """時価総額 = 発行済株式数 × 株価。"""
    if shares_outstanding is None or price is None:
        return None
    return shares_outstanding * price


# --- モメンタム ---

# 12-1ヶ月モメンタムの定義: 直近1ヶ月(約21営業日)を除いた過去12ヶ月(約231営業日)の騰落率。
# T-01/T-02/T-03スパイクの実装をそのまま定数化して踏襲する。
MOMENTUM_EXCLUDE_DAYS = 22  # 直近1ヶ月(約21営業日)を除外するオフセット
MOMENTUM_LOOKBACK_DAYS = 231  # そこからさらに遡る約11ヶ月分(合計約12ヶ月)


def compute_momentum_12_1(close_prices: Sequence[float]) -> float | None:
    """12-1ヶ月モメンタムを計算する。

    close_prices: 日付昇順の終値シーケンス(古い→新しい)。
    上場直後等でヒストリーが不足する銘柄(13ヶ月=約253営業日に満たない)は None を返す
    (境界値: 上場直後で株価履歴が12ヶ月未満の銘柄)。
    """
    if close_prices is None:
        return None
    n = len(close_prices)
    end_idx = -MOMENTUM_EXCLUDE_DAYS
    start_idx = -MOMENTUM_EXCLUDE_DAYS - MOMENTUM_LOOKBACK_DAYS
    required = abs(start_idx)
    if n < required:
        return None
    p_end = close_prices[end_idx]
    p_start = close_prices[start_idx]
    if p_start is None or p_end is None or p_start == 0:
        return None
    return float(p_end / p_start - 1)


# --- ランキング/パーセンタイルにおける値の有効性(T-04fix) ---

# バリュー系指標は分母(簿価・利益)が非正だと定義不能になる。ファクター投資の定石に従い、
# pbr<=0(自己資本マイナス=債務超過等)・per_trailing<=0 はランキング/分位/パーセンタイルの
# 対象外(欠損扱い)とする。daily/*.json の生値としてのpbr自体はそのまま保持する(表示用の事実)。
POSITIVE_ONLY_FIELDS = frozenset({"pbr", "per_trailing"})


def metric_value_for_ranking(field: str, value):
    """ランキング/分位/パーセンタイル算出に使う値を返す。定義不能な値は None(欠損扱い)を返す。

    - None はそのまま None(欠損)
    - POSITIVE_ONLY_FIELDS(pbr, per_trailing)は 0以下を定義不能として None 扱い
    - その他のフィールドは値をそのまま返す(momentum/roe等の負値は正当な値)
    """
    if value is None:
        return None
    if field in POSITIVE_ONLY_FIELDS and value <= 0:
        return None
    return value


# --- パーセンタイル ---


def percentile_rank(values_by_key: dict) -> dict:
    """{key: value} -> {key: percentile(0..1)} を返す(平均順位ベース、タイは同順位平均)。

    Noneの値は算出対象から除外するが、結果の辞書にはNoneのまま残す(欠損はnullのまま保持)。
    空のユニバース・全値Noneの場合は空辞書 {} を返す(境界値: 空のユニバース)。
    値が1件のみの場合は 0.5(中央)を返す。
    """
    items = [(k, v) for k, v in values_by_key.items() if v is not None]
    if not items:
        return {k: None for k in values_by_key}

    items_sorted = sorted(items, key=lambda kv: kv[1])
    n = len(items_sorted)

    # タイ(同値)は平均順位で扱う
    ranks: dict = {}
    i = 0
    while i < n:
        j = i
        while j < n and items_sorted[j][1] == items_sorted[i][1]:
            j += 1
        avg_rank = (i + j - 1) / 2  # 0-indexed平均順位
        for k in range(i, j):
            key = items_sorted[k][0]
            ranks[key] = avg_rank / (n - 1) if n > 1 else 0.5
        i = j

    result = {}
    for k, v in values_by_key.items():
        result[k] = ranks.get(k) if v is not None else None
    return result


def compute_all_percentiles(stocks: Iterable[dict], fields: Sequence[str]) -> dict:
    """複数銘柄・複数フィールドについて一括でユニバース内パーセンタイルを計算する。

    stocks: 各要素が {"ticker": ..., field1: value1, ...} の辞書のシーケンス
    戻り値: {ticker: {field: percentile}}
    空のユニバース(stocksが空)の場合は空辞書を返す。
    定義不能な値(pbr<=0等、metric_value_for_ranking参照)は欠損(None)扱いで算出から除外する。
    """
    stocks = list(stocks)
    result = {s["ticker"]: {} for s in stocks}
    if not stocks:
        return {}
    for field in fields:
        values_by_key = {s["ticker"]: metric_value_for_ranking(field, s.get(field)) for s in stocks}
        percentiles = percentile_rank(values_by_key)
        for ticker, pct in percentiles.items():
            result[ticker][field] = pct
    return result


# --- 信用倍率(週次、日本株のみ) ---


def compute_margin_ratio(purchases_shares, sales_shares):
    """信用倍率 = 買残 ÷ 売残。売残ゼロ(踏み上げ状態の極端値)は None を返す(ゼロ除算対策)。"""
    return safe_div(purchases_shares, sales_shares)


# --- 欠損フィールド検出 ---

DAILY_NULLABLE_FIELDS = [
    "per_trailing",
    "pbr",
    "dividend_yield_pct",
    "roe",
    "trailing_eps",
    "book_value_per_share",
    "momentum_12_1",
]


def detect_missing_fields(stock: dict, fields: Sequence[str] = DAILY_NULLABLE_FIELDS) -> list[str]:
    """当該銘柄でNoneになっているフィールド名一覧を返す(data_quality.missing_fields用)。"""
    return [f for f in fields if stock.get(f) is None]
