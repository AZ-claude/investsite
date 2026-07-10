"""T-04: 既知5銘柄(日3・米2)の外部サイト突合表を生成する(検証用の一時スクリプト)。

前提: t04_run_snapshot.py 実行済み(t04_{jp,us}_snapshot.json が存在)、
      t04_yahoo_jp_reference.json / t04_us_reference*.json が取得済み。
実行方法: python pipeline/spikes/t04_crosscheck.py
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUT = os.path.join(os.path.dirname(__file__), "out")


def load(name):
    with open(os.path.join(OUT, name), encoding="utf-8") as f:
        return json.load(f)


jp = load("t04_jp_snapshot.json")
us = load("t04_us_snapshot.json")
yjp = {r["code"]: r for r in load("t04_yahoo_jp_reference.json")}
usr = {r["symbol"]: r for r in load("t04_us_reference_stats.json")}
usr_sum = {r["symbol"]: r for r in load("t04_us_reference.json")}

jp_stocks = {s["ticker"]: s for s in jp["stocks"]}
us_stocks = {s["ticker"]: s for s in us["stocks"]}


def num(s):
    if s in (None, "---", ""):
        return None
    return float(str(s).replace(",", "").replace("%", ""))


print("=== 日本株3銘柄(Yahoo!ファイナンスJP突合) ===")
for code, name in [("7203", "トヨタ自動車"), ("9984", "ソフトバンクG"), ("6758", "ソニーG")]:
    s = jp_stocks[f"{code}.T"]
    y = yjp[code]
    print(f"\n--- {code} {name} ---")
    print(f"  price(yf前営業日終値)     = {s['price']}")
    print(f"  per_trailing(yf実績)      = {s['per_trailing']}  | Yahoo PER(会社予想) = {y.get('PER(会社予想)')}")
    print(f"  pbr(yf)                   = {s['pbr']}  | Yahoo PBR(実績) = {y.get('PBR(実績)')}")
    mc_yf = s["market_cap"]
    mc_y = num(y.get("時価総額(百万円)"))
    mc_y_yen = mc_y * 1e6 if mc_y else None
    diff = (mc_yf / mc_y_yen - 1) * 100 if (mc_yf and mc_y_yen) else None
    print(f"  market_cap(yf)            = {mc_yf:.4g}  | Yahoo = {mc_y_yen:.4g} 円  | 差 = {diff:+.1f}%")
    print(f"  shares_outstanding(yf)    = {s['shares_outstanding']}  | Yahoo発行済株式数 = {y.get('発行済株式数')}")
    print(f"  dividend_yield_pct(yf)    = {s['dividend_yield_pct']}  | Yahoo配当利回り(会社予想) = {y.get('配当利回り(会社予想)%')}")
    roe_y = num(y.get("ROE(実績)%"))
    roe_yf_pct = s["roe"] * 100 if s["roe"] is not None else None
    print(f"  roe(yf, %換算)            = {roe_yf_pct}  | Yahoo ROE(実績) = {roe_y}")
    print(f"  momentum_12_1(yf)         = {s['momentum_12_1']}(外部サイトに対応表示なし、定義独自)")
    if "margin" in s:
        print(f"  margin_ratio_seido        = {s['margin']['margin_ratio_seido']} (as_of {s['margin']['as_of_week']})")

print("\n=== 米国株2銘柄(stockanalysis.com突合) ===")
for sym in ["AAPL", "MSFT"]:
    s = us_stocks[sym]
    r = usr[sym]
    rs = usr_sum[sym]
    print(f"\n--- {sym} ---")
    print(f"  per_trailing(yf) = {s['per_trailing']}  | SA PE Ratio = {r.get('pe_ratio')}")
    print(f"  pbr(yf)          = {s['pbr']}  | SA PB Ratio = {r.get('pb_ratio')}")
    print(f"  market_cap(yf)   = {s['market_cap']:.4g}  | SA Market Cap = {rs.get('market_cap')}")
    roe_yf_pct = s["roe"] * 100 if s["roe"] is not None else None
    print(f"  roe(yf, %換算)   = {roe_yf_pct}  | SA ROE = {r.get('roe')}")
    print(f"  dividend_yield_pct(yf) = {s['dividend_yield_pct']}  | SA Dividend Yield = {r.get('dividend_yield')}")
    print(f"  percentile(pbr)  = {s['percentile_in_universe']['pbr']}")
