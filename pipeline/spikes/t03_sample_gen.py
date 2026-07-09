"""
T-03: docs/07-data-schema.md 用サンプルデータ生成スクリプト(実データ取得)

data/samples/ 配下のサンプルJSONは架空値ではなく実際のyfinance取得値から生成する。
このスクリプトはその場限りの生成用(T-05本実装のものではない)。

実行方法: python pipeline/spikes/t03_sample_gen.py
出力: pipeline/spikes/out/t03_sample_raw.json (中間データ、確認用)
"""
import io
import json
import sys
from datetime import datetime, timezone, timedelta

import yfinance as yf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

JST = timezone(timedelta(hours=9))

JP_TICKERS = ["7203.T", "9984.T", "6758.T", "8306.T", "9433.T"]
US_TICKERS = ["AAPL", "MSFT", "JPM", "KO", "XOM"]

FIELDS = [
    "currentPrice", "regularMarketPrice", "trailingPE", "priceToBook", "marketCap",
    "sharesOutstanding", "dividendYield", "returnOnEquity", "trailingEps", "bookValue",
    "shortName",
]


def fetch(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info
    hist = t.history(period="14mo", interval="1d")
    momentum_12_1 = None
    if len(hist) > 22:
        close = hist["Close"]
        # 12-1ヶ月モメンタム: t-1ヶ月(直近21営業日前)を終点、t-12ヶ月(約252営業日前)を起点とするリターン
        end_idx = -22  # 直近1ヶ月(約21営業日)を除外
        start_idx = -22 - 231  # そこからさらに約11ヶ月(231営業日)遡る
        if abs(start_idx) <= len(close):
            p_end = close.iloc[end_idx]
            p_start = close.iloc[start_idx]
            momentum_12_1 = float(p_end / p_start - 1)

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    row = {
        "ticker": ticker,
        "name": info.get("shortName"),
        "price": price,
        "per_trailing": info.get("trailingPE"),
        "pbr": info.get("priceToBook"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "dividend_yield": info.get("dividendYield"),
        "roe": info.get("returnOnEquity"),
        "trailing_eps": info.get("trailingEps"),
        "book_value_per_share": info.get("bookValue"),
        "momentum_12_1": momentum_12_1,
        "history_rows": len(hist),
    }
    return row


if __name__ == "__main__":
    print(f"実行日時(JST): {datetime.now(JST).isoformat()}")
    out = {"generated_at": datetime.now(JST).isoformat(), "jp": [], "us": []}
    for tkr in JP_TICKERS:
        try:
            r = fetch(tkr)
            out["jp"].append(r)
            print("JP", r)
        except Exception as e:
            print(f"[ERROR] {tkr}: {e}")
    for tkr in US_TICKERS:
        try:
            r = fetch(tkr)
            out["us"].append(r)
            print("US", r)
        except Exception as e:
            print(f"[ERROR] {tkr}: {e}")

    with open("pipeline/spikes/out/t03_sample_raw.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n書き出し完了: pipeline/spikes/out/t03_sample_raw.json")
