"""daily/{jp|us}.json 相当のオブジェクトを構築するオーケストレーション層。

docs/07-data-schema.md 2節のスキーマに厳密に従う。ファイル書き出しは行わない(T-05スコープ)。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from . import calculations as calc
from . import fetch_yfinance as fy
from . import margin_jpx

JST = timezone(timedelta(hours=9))

PERCENTILE_FIELDS = ["per_trailing", "pbr", "dividend_yield_pct", "roe", "momentum_12_1", "market_cap"]

SOURCE_NOTE = (
    "前営業日終値ベース(当日ザラ場価格は含まない)。PERは実績ベース(trailingPE)。"
    "会社予想ベースのPER(Yahoo!ファイナンス等の主要表示)とは定義が異なる点に注意。"
    "時価総額はsharesOutstanding×priceで算出しており、Yahoo!ファイナンス等の表示と"
    "発行済株式数の算出方法が異なる場合がある(T-03で最大19%の乖離を確認、原因は自己株式控除差が最有力仮説だが未確定)。"
)


def build_stock_record(
    ticker: str,
    name: Optional[str],
    currency: str,
    raw: dict,
    close_prices: Optional[list[float]],
    margin: Optional[dict] = None,
) -> dict:
    """1銘柄分のraw情報からスキーマ準拠のstocksレコードを組み立てる(percentile_in_universeは未設定=呼び出し側で後付け)。"""
    price = raw.get("currentPrice") or raw.get("regularMarketPrice")
    shares_outstanding = raw.get("sharesOutstanding")
    trailing_eps = raw.get("trailingEps")
    book_value_per_share = raw.get("bookValue")

    market_cap = raw.get("marketCap")
    if market_cap is None:
        market_cap = calc.compute_market_cap(shares_outstanding, price)

    per_trailing = calc.compute_per_trailing(raw.get("trailingPE"), price=price, eps=trailing_eps)
    pbr = calc.compute_pbr(raw.get("priceToBook"), price=price, book_value_per_share=book_value_per_share)
    dividend_yield_pct = calc.compute_dividend_yield_pct(raw.get("dividendYield"))
    roe = calc.compute_roe(raw.get("returnOnEquity"))
    momentum_12_1 = calc.compute_momentum_12_1(close_prices) if close_prices else None

    stock = {
        "ticker": ticker,
        "name": name or raw.get("shortName"),
        "currency": currency,
        "price": price,
        "market_cap": market_cap,
        "shares_outstanding": shares_outstanding,
        "per_trailing": per_trailing,
        "pbr": pbr,
        "dividend_yield_pct": dividend_yield_pct,
        "roe": roe,
        "trailing_eps": trailing_eps,
        "book_value_per_share": book_value_per_share,
        "momentum_12_1": momentum_12_1,
    }
    stock["data_quality"] = {"missing_fields": calc.detect_missing_fields(stock)}
    if margin is not None:
        stock["margin"] = margin
    return stock


def attach_percentiles(stocks: list[dict], fields: list[str] = PERCENTILE_FIELDS) -> None:
    """stocks(リスト、in-place変更)に percentile_in_universe を付与する。空リストなら何もしない。"""
    percentiles = calc.compute_all_percentiles(stocks, fields)
    for s in stocks:
        s["percentile_in_universe"] = percentiles.get(s["ticker"], {f: None for f in fields})


def build_daily_snapshot(
    market: str,
    universe_name: str,
    tickers: list[dict],
    fundamentals_by_ticker: dict,
    price_history_by_ticker: dict,
    currency: str,
    margin_by_ticker: Optional[dict] = None,
    library_version: Optional[str] = None,
    generated_at: Optional[str] = None,
    date: Optional[str] = None,
) -> dict:
    """docs/07-data-schema.md 2.1/2.2/2.3節に準拠した daily/{jp|us}.json 相当の辞書を構築する。

    tickers: [{"ticker": ..., "name": ...}, ...] (ユニバース全体。fundamentalsが取れなかった銘柄も
             stocksに含め、当該フィールドはNoneのまま出力する=「欠損はnull、フィールド自体は残す」方針)
    fundamentals_by_ticker: fetch_yfinance.fetch_fundamentals_bulk() の raw_by_ticker
    price_history_by_ticker: fetch_yfinance.fetch_price_history_bulk() の戻り値
    margin_by_ticker: margin_jpx.fetch_stock_margin() の戻り値(JPのみ、Noneなら付与しない)
    """
    now = datetime.now(JST)
    stocks = []
    for entry in tickers:
        tkr = entry["ticker"]
        raw = fundamentals_by_ticker.get(tkr, {})
        close_prices = price_history_by_ticker.get(tkr)
        margin = (margin_by_ticker or {}).get(tkr)
        stocks.append(build_stock_record(tkr, entry.get("name"), currency, raw, close_prices, margin))

    attach_percentiles(stocks)

    return {
        "date": date or now.strftime("%Y-%m-%d"),
        "market": market,
        "universe": universe_name,
        "generated_at": generated_at or now.isoformat(),
        "source": {
            "provider": "yfinance",
            "library_version": library_version or fy.yf.__version__,
            "note": SOURCE_NOTE,
        },
        "stocks": stocks,
    }


def build_jp_snapshot(fetch_margin: bool = True) -> dict:
    """日本株(日経225)の実データ1日分スナップショットをフル取得・構築する(ネットワークI/O)。"""
    tickers = fy.get_nikkei225_tickers()
    ticker_list = [t["ticker"] for t in tickers]
    fresult = fy.fetch_fundamentals_bulk(ticker_list)
    history = fy.fetch_price_history_bulk(ticker_list)
    margin_by_ticker = margin_jpx.fetch_stock_margin() if fetch_margin else None
    return build_daily_snapshot(
        market="jp",
        universe_name="NIKKEI225",
        tickers=tickers,
        fundamentals_by_ticker=fresult.raw_by_ticker,
        price_history_by_ticker=history,
        currency="JPY",
        margin_by_ticker=margin_by_ticker,
    )


def build_us_snapshot() -> dict:
    """米国株(S&P500)の実データ1日分スナップショットをフル取得・構築する(ネットワークI/O)。"""
    tickers = fy.get_sp500_tickers()
    ticker_list = [t["ticker"] for t in tickers]
    fresult = fy.fetch_fundamentals_bulk(ticker_list)
    history = fy.fetch_price_history_bulk(ticker_list)
    return build_daily_snapshot(
        market="us",
        universe_name="SP500",
        tickers=tickers,
        fundamentals_by_ticker=fresult.raw_by_ticker,
        price_history_by_ticker=history,
        currency="USD",
    )


def roe_missing_rate(stocks: list[dict]) -> dict:
    """ROEの欠損率を実測する(schemaで「未実測」となっていたT-04申し送り事項)。"""
    n = len(stocks)
    if n == 0:
        return {"total": 0, "missing": 0, "missing_rate_pct": None}
    missing = sum(1 for s in stocks if s.get("roe") is None)
    return {"total": n, "missing": missing, "missing_rate_pct": round(missing / n * 100, 2)}
