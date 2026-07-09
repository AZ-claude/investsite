"""
T-03 事前検証: 時価総額(marketCap)乖離の原因調査

背景: T-01スパイクで「トヨタ(7203.T)の時価総額がYahoo!ファイナンスJP表示と19%乖離」が
未解決事例として報告された(docs/06-spikes/T-01-jp-data.md 5節)。
本スクリプトは yfinance の marketCap と、sharesOutstanding(発行済株式数) × 株価 を
複数銘柄で突合し、乖離の原因を切り分ける。

仮説:
  H1: 自己株式控除の有無(sharesOutstandingが自己株式を含む/含まない)
  H2: 発行済株式数データの鮮度(古いスナップショット)
  H3: marketCap自体が別の計算式(例: floatShares基準)を使っている
  H4: 優先株等の資本構成の特殊性

実行方法: python pipeline/spikes/t03_marketcap_check.py
"""

import io
import sys
from datetime import datetime, timezone, timedelta

import yfinance as yf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

JST = timezone(timedelta(hours=9))

# T-01で乖離が観測された3銘柄(トヨタ=19%乖離、SBG・ソニー=1~2%差の対照群)
# + 検証範囲を広げるため日経225主要4銘柄を追加
TARGETS = [
    ("7203.T", "トヨタ自動車", 41.22e12),   # Yahoo!ファイナンスJP表示の時価総額(2026-07-10 T-01調査時点)
    ("9984.T", "ソフトバンクグループ", 32.88e12),
    ("6758.T", "ソニーグループ", 20.34e12),
    ("8306.T", "三菱UFJフィナンシャル・グループ", None),
    ("9432.T", "NTT", None),
    ("8035.T", "東京エレクトロン", None),
]


def check(ticker: str, name: str, yahoo_mcap_ref):
    print("-" * 70)
    print(f"{ticker} ({name})")
    t = yf.Ticker(ticker)
    info = t.info

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    market_cap = info.get("marketCap")
    shares_out = info.get("sharesOutstanding")
    float_shares = info.get("floatShares")
    impl_shares_from_mcap = info.get("impliedSharesOutstanding")

    computed_mcap_from_shares_out = (price * shares_out) if (price and shares_out) else None
    computed_mcap_from_float = (price * float_shares) if (price and float_shares) else None

    print(f"  price                         = {price}")
    print(f"  marketCap (yfinance)          = {market_cap}")
    print(f"  sharesOutstanding (yfinance)  = {shares_out}")
    print(f"  floatShares (yfinance)        = {float_shares}")
    print(f"  impliedSharesOutstanding      = {impl_shares_from_mcap}")
    print(f"  sharesOutstanding × price     = {computed_mcap_from_shares_out}")
    print(f"  floatShares × price           = {computed_mcap_from_float}")

    if market_cap and computed_mcap_from_shares_out:
        diff_pct = (market_cap - computed_mcap_from_shares_out) / computed_mcap_from_shares_out * 100
        print(f"  → marketCap vs (sharesOutstanding×price) の差: {diff_pct:+.2f}%")

    if market_cap and shares_out and price:
        # marketCap を price で逆算した「実効株式数」
        implied_shares_from_mcap_calc = market_cap / price
        print(f"  marketCap ÷ price (逆算株式数) = {implied_shares_from_mcap_calc:,.0f}")
        print(f"  sharesOutstanding              = {shares_out:,.0f}")
        share_diff_pct = (implied_shares_from_mcap_calc - shares_out) / shares_out * 100
        print(f"  → 株式数の差: {share_diff_pct:+.2f}%")

    if yahoo_mcap_ref:
        print(f"  [参考] Yahoo!ファイナンスJP表示(T-01調査時点) = {yahoo_mcap_ref:,.0f}")
        if market_cap:
            diff_vs_yahoo = (market_cap - yahoo_mcap_ref) / yahoo_mcap_ref * 100
            print(f"  → yfinance marketCap vs Yahoo!表示 の差: {diff_vs_yahoo:+.2f}%")
        if computed_mcap_from_shares_out:
            diff_vs_yahoo2 = (computed_mcap_from_shares_out - yahoo_mcap_ref) / yahoo_mcap_ref * 100
            print(f"  → (sharesOutstanding×price) vs Yahoo!表示 の差: {diff_vs_yahoo2:+.2f}%")

    return {
        "ticker": ticker,
        "price": price,
        "marketCap": market_cap,
        "sharesOutstanding": shares_out,
        "floatShares": float_shares,
        "computed_from_shares_out": computed_mcap_from_shares_out,
    }


if __name__ == "__main__":
    print(f"実行日時(JST): {datetime.now(JST).isoformat()}")
    print(f"yfinance version: {yf.__version__}\n")
    print("T-03 事前検証: marketCap と sharesOutstanding×price の突合\n")

    results = []
    for tkr, name, yref in TARGETS:
        try:
            r = check(tkr, name, yref)
            results.append(r)
        except Exception as e:
            print(f"  [ERROR] {tkr}: 取得失敗 {e}")

    print("\n" + "=" * 70)
    print("サマリ")
    print("=" * 70)
    for r in results:
        if r.get("marketCap") and r.get("computed_from_shares_out"):
            diff = (r["marketCap"] - r["computed_from_shares_out"]) / r["computed_from_shares_out"] * 100
            print(f"  {r['ticker']}: marketCap={r['marketCap']:.3e}  "
                  f"sharesOutstanding×price={r['computed_from_shares_out']:.3e}  差={diff:+.2f}%")
