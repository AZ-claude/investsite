"""T-17: 過去データのバックフィルCLI(一回限り実行)。

実行方法: python -m pipeline.backfill [--data-dir DIR] [--jp-valuation FILE]
          [--skip-valuation] [--skip-factor-returns] [--price-history FILE]

やること:
  (a) market-thermometer.json に指数PER/PBRの5年履歴(valuation_history)を格納し、
      最新値の5年パーセンタイル(index_per_percentile_5y等)を算出して反映する。
      - 日本: 日経平均プロフィル公式アーカイブ(日次、加重平均ベース)。サイトがCloudflare保護で
        HTTP直叩き不可のため、スパイクで実ブラウザ取得した成果物JSONをファイル入力とする
        (既定: pipeline/spikes/out/t17_nikkei_per_pbr_5y.json)。
      - 米国: multpl.com(PER=月次trailing "as reported"、PBR=四半期)をHTTPで直接取得。
  (b) factors/*.json の factor_return_1m/3m/1y を「現在の分位該当銘柄(等ウェイト)の
      トレーリングリターン − ユニバース等ウェイト平均」として株価履歴(yfinance、
      T-02のバルク取得方式)から算出し、最新history エントリに記入する。
      ※ 現在の構成銘柄で固定した近似(生存バイアス・先読みバイアスあり)。
        厳密なヒストリカル分位バックテストはT-15スコープ。

冪等性: valuation_history は全置換、factor_return_* は同一フィールドの上書きのため、
再実行しても重複・増殖しない。品質ゲートに引っかかった場合は該当ファイルを書き込まない。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from statistics import mean
from typing import Callable, Optional, Sequence

import requests

from pipeline.metrics import calculations as calc
from pipeline.metrics import factors as factors_mod
from pipeline.metrics import fetch_yfinance as fy

REPO_ROOT = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep, 1)[0]
DEFAULT_JP_VALUATION_FILE = os.path.join(
    REPO_ROOT, "pipeline", "spikes", "out", "t17_nikkei_per_pbr_5y.json"
)

MULTPL_PE_URL = "https://www.multpl.com/s-p-500-pe-ratio/table/by-month"
MULTPL_PB_URL = "https://www.multpl.com/s-p-500-price-to-book/table/by-quarter"
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (investsite-pipeline/1.0)"}

# トレーリングリターンの営業日ホライズン(1ヶ月=21営業日、3ヶ月=63、1年=252)
RETURN_HORIZONS = {
    "factor_return_1m": 21,
    "factor_return_3m": 63,
    "factor_return_1y": 252,
}

# 品質ゲート閾値
JP_MIN_POINTS = 500          # 日次5年分なら1200点前後あるはず。500未満は取得不良とみなす
US_PE_MIN_POINTS = 30        # 月次5年分=60点前後
US_PB_MIN_POINTS = 10        # 四半期5年分=20点前後
VALUE_RANGE = (0.1, 500.0)   # PER/PBRの許容レンジ(異常値検知)
MIN_QUANTILE_COVERAGE = 0.5  # 分位銘柄のうち株価履歴が取れた割合がこれ未満ならnullのまま

FACTOR_RETURN_NOTE = (
    "factor_return_1m/3m/1y は『現在の分位該当銘柄(等ウェイト)のトレーリングリターン − "
    "ユニバース全体の等ウェイト平均』(%ポイント)。現在の構成銘柄で固定して過去リターンを"
    "遡って測る近似のため、生存バイアス・構成入れ替えの先読みバイアスを含む。"
    "厳密なヒストリカル分位バックテスト(T-15)による値ではない。"
)

JP_VALUATION_DEFINITION = (
    "日経平均採用銘柄の加重平均ベース(構成銘柄の合算。日経公式『加重平均(倍)』列)。"
    "PERは前期基準利益ベース。日次系列。"
)
US_PE_DEFINITION = (
    "S&P500のPER(trailing 12ヶ月 'as reported' earningsベース、multpl.com)。"
    "月次系列(月初値)+最新日推定値。yfinanceのtrailingPE(希薄化後中心)とは定義が異なる。"
)
US_PB_DEFINITION = "S&P500のPBR(multpl.com)。四半期系列+最新日推定値。"


# ---------------------------------------------------------------------------
# 取得・パース(純粋関数はテスト可能な形に分離)
# ---------------------------------------------------------------------------

def parse_multpl_table(html: str) -> list[dict]:
    """multpl.comのテーブルHTMLから [{date: 'YYYY-MM-DD', value: float}] を抽出する(日付昇順)。

    行フォーマット: <td>Mon D, YYYY</td><td>[<abbr>†</abbr>|&#x2002;] 値</td>
    (最新行はEstimateの<abbr>、過去行は&#x2002;エンティティが値の前に付く。T-17スパイク実測)
    """
    rows = re.findall(
        r"<td>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td[^>]*>\s*(?:<abbr[^>]*>[^<]*</abbr>|&#x2002;)?\s*([\d.]+)",
        html,
    )
    out = []
    for date_str, val in rows:
        iso = datetime.strptime(date_str, "%b %d, %Y").strftime("%Y-%m-%d")
        out.append({"date": iso, "value": float(val)})
    out.sort(key=lambda p: p["date"])
    return out


def load_jp_valuation(path: str) -> dict:
    """スパイク成果物JSON(日経公式アーカイブの5年分)を valuation_history 形式に変換する。

    入力: {"per": [{"date": "YYYY.MM.DD", "weighted": f, "index_based": f}], "pbr": [...]}
    出力: {"per": [{"date": "YYYY-MM-DD", "value": f}], "pbr": [...]}(加重平均ベースを採用)
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    out = {}
    for metric in ("per", "pbr"):
        series = []
        for row in raw.get(metric, []):
            if "error" in row or row.get("weighted") is None:
                continue
            series.append({"date": row["date"].replace(".", "-"), "value": float(row["weighted"])})
        series.sort(key=lambda p: p["date"])
        out[metric] = series
    return out


def fetch_us_valuation(fetch: Optional[Callable[[str], str]] = None) -> dict:
    """multpl.comからS&P500のPER(月次)・PBR(四半期)を取得しvaluation_history形式で返す。"""
    fetch = fetch or (lambda url: requests.get(url, headers=HTTP_HEADERS, timeout=30).text)
    return {
        "per": parse_multpl_table(fetch(MULTPL_PE_URL)),
        "pbr": parse_multpl_table(fetch(MULTPL_PB_URL)),
    }


# ---------------------------------------------------------------------------
# 品質ゲート
# ---------------------------------------------------------------------------

def validate_series(series: Sequence[dict], min_points: int, label: str) -> list[str]:
    """点数・値レンジ・日付形式を検査し、問題のリストを返す(空リスト=PASS)。"""
    problems = []
    if len(series) < min_points:
        problems.append(f"{label}: 点数不足 {len(series)} < {min_points}")
    lo, hi = VALUE_RANGE
    bad = [p for p in series if not (lo <= p["value"] <= hi)]
    if bad:
        problems.append(f"{label}: レンジ外の値 {len(bad)}件 (例: {bad[0]})")
    malformed = [p for p in series if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date"])]
    if malformed:
        problems.append(f"{label}: 日付形式不正 {len(malformed)}件 (例: {malformed[0]})")
    return problems


# ---------------------------------------------------------------------------
# ファクター・トレーリングリターン
# ---------------------------------------------------------------------------

def quintile_tickers_for_factor(factor_file: dict) -> list[str]:
    """today_screen から分位該当(top_quintile)銘柄を返す。

    margin-trading は today_screen にquantileフィールドが無いため、
    margin_ratio_seido 降順ランキングの上位20%(五分位、最低1銘柄)を分位相当として扱う。
    """
    screen = factor_file.get("today_screen") or {}
    if factor_file.get("factor") == "margin-trading":
        jp = screen.get("jp") or []
        top_n = max(1, math.ceil(len(jp) * factors_mod.QUANTILE_FRACTION)) if jp else 0
        return [r["ticker"] for r in jp[:top_n]]
    out = []
    for m in ("jp", "us"):
        out.extend(r["ticker"] for r in (screen.get(m) or []) if r.get("quantile") == "top_quintile")
    return out


def universe_tickers_for_factor(factor_file: dict, jp_tickers: Sequence[str], us_tickers: Sequence[str]) -> list[str]:
    """ファクターの対象市場に応じたユニバース銘柄リスト(等ウェイト平均の母集団)。"""
    markets = factor_file.get("markets") or ["jp", "us"]
    out = []
    if "jp" in markets:
        out.extend(jp_tickers)
    if "us" in markets:
        out.extend(us_tickers)
    return out


def compute_excess_returns(
    quintile: Sequence[str],
    universe: Sequence[str],
    price_history: dict[str, Sequence[float]],
) -> dict[str, Optional[float]]:
    """分位該当銘柄の等ウェイト・トレーリングリターン − ユニバース等ウェイト平均(%ポイント)。

    ホライズンごとに、株価履歴が足りる銘柄のみで平均する。
    分位側のカバレッジ(履歴が取れた銘柄割合)が MIN_QUANTILE_COVERAGE 未満、
    またはユニバース側が空の場合はそのホライズンを None にする(架空値を埋めない)。
    """
    result: dict[str, Optional[float]] = {}
    for field, days in RETURN_HORIZONS.items():
        q_returns = [r for t in quintile if (r := calc.trailing_return(price_history.get(t), days)) is not None]
        u_returns = [r for t in universe if (r := calc.trailing_return(price_history.get(t), days)) is not None]
        if not quintile or not u_returns or len(q_returns) / len(quintile) < MIN_QUANTILE_COVERAGE:
            result[field] = None
            continue
        result[field] = round((mean(q_returns) - mean(u_returns)) * 100, 2)
    return result


def apply_factor_returns(factor_file: dict, returns: dict[str, Optional[float]]) -> dict:
    """最新のhistoryエントリに factor_return_* を記入し、注記フィールドを付与して返す(冪等)。"""
    history = list(factor_file.get("history") or [])
    if history:
        history.sort(key=lambda h: h["date"])
        latest = dict(history[-1])
        latest.update(returns)
        history[-1] = latest
    out = dict(factor_file)
    out["history"] = history
    out["factor_return_note"] = FACTOR_RETURN_NOTE
    return out


# ---------------------------------------------------------------------------
# CLI本体
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def backfill_thermometer(data_dir: str, jp_valuation: Optional[dict], us_valuation: Optional[dict],
                          log: Callable[[str], None]) -> bool:
    """market-thermometer.json に valuation_history を格納しパーセンタイルを反映する。"""
    path = os.path.join(data_dir, "factors", "market-thermometer.json")
    thermo = _load_json(path)
    if thermo is None:
        log(f"[thermometer] {path} が存在しないためスキップ(先に pipeline.daily を実行すること)")
        return False

    valuation_history = dict(thermo.get("valuation_history") or {})
    if jp_valuation:
        valuation_history["jp"] = {
            "per": jp_valuation["per"],
            "pbr": jp_valuation["pbr"],
            "definition": JP_VALUATION_DEFINITION,
            "source": "https://indexes.nikkei.co.jp/nkave/archives/data?list=per (list=pbr)",
            "frequency": "daily",
        }
    if us_valuation:
        valuation_history["us"] = {
            "per": us_valuation["per"],
            "pbr": us_valuation["pbr"],
            "definition_per": US_PE_DEFINITION,
            "definition_pbr": US_PB_DEFINITION,
            "source": f"{MULTPL_PE_URL} / {MULTPL_PB_URL}",
            "frequency": "monthly(per) / quarterly(pbr)",
        }
    thermo["valuation_history"] = valuation_history

    # top-level と最新history エントリの両方に反映する
    for block_holder in (thermo, (thermo.get("history") or [{}])[-1]):
        factors_mod.apply_valuation_history(block_holder.get("jp"), valuation_history.get("jp"))
        factors_mod.apply_valuation_history(block_holder.get("us"), valuation_history.get("us"))

    thermo["source_note"] = (
        "index_level/index_change_pct_1d は yfinance(^N225, ^GSPC)の実測値。"
        "margin_market_totalはJPX公式Excel(週次)の実測値。"
        "index_per/index_pbr と 5年パーセンタイルは valuation_history 由来: "
        "日本=日経平均プロフィル公式アーカイブ(加重平均ベース・日次)、"
        "米国=multpl.com(PER=月次trailing as-reported、PBR=四半期)。"
        "日米で定義・頻度が異なるため水準の直接比較は不可(各市場の自己時系列内の位置のみ有効)。"
    )
    _write_json(path, thermo)
    for m in ("jp", "us"):
        b = thermo.get(m) or {}
        log(f"[thermometer] {m}: index_per={b.get('index_per')} (pctile={b.get('index_per_percentile_5y')}) "
            f"index_pbr={b.get('index_pbr')} (pctile={b.get('index_pbr_percentile_5y')})")
    return True


def backfill_factor_returns(data_dir: str, price_history: dict[str, Sequence[float]],
                             jp_tickers: Sequence[str], us_tickers: Sequence[str],
                             log: Callable[[str], None]) -> None:
    """factors/*.json(margin-trading含む6本)の最新エントリに factor_return_* を記入する。"""
    slugs = list(factors_mod.FACTOR_DEFS) + ["margin-trading"]
    for slug in slugs:
        path = os.path.join(data_dir, "factors", f"{slug}.json")
        factor_file = _load_json(path)
        if factor_file is None:
            log(f"[factors/{slug}] ファイルなし、スキップ")
            continue
        quintile = quintile_tickers_for_factor(factor_file)
        universe = universe_tickers_for_factor(factor_file, jp_tickers, us_tickers)
        returns = compute_excess_returns(quintile, universe, price_history)
        updated = apply_factor_returns(factor_file, returns)
        _write_json(path, updated)
        log(f"[factors/{slug}] quintile={len(quintile)}銘柄 returns={returns}")


def run(
    data_dir: Optional[str] = None,
    jp_valuation_file: Optional[str] = None,
    skip_valuation: bool = False,
    skip_factor_returns: bool = False,
    fetch_us: Optional[Callable[[], dict]] = None,
    fetch_prices: Optional[Callable[[list[str]], dict]] = None,
) -> int:
    """バックフィルを実行する。戻り値: 0=正常, 1=品質ゲート異常, 2=取得失敗。"""
    data_dir = data_dir or os.path.join(REPO_ROOT, "data")
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    def finish(code: int) -> int:
        log_path = os.path.join(data_dir, "logs", "backfill-t17.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")
        return code

    log(f"=== pipeline.backfill 開始 (T-17) data_dir={data_dir} ===")

    if not skip_valuation:
        # 日本(スパイク成果物ファイル)
        jp_path = jp_valuation_file or DEFAULT_JP_VALUATION_FILE
        try:
            jp_val = load_jp_valuation(jp_path)
        except (OSError, json.JSONDecodeError, KeyError) as e:
            log(f"[jp] 読み込み失敗 ({jp_path}): {e}")
            return finish(2)
        # 米国(multpl直取得)
        try:
            us_val = (fetch_us or fetch_us_valuation)()
        except Exception as e:  # noqa: BLE001
            log(f"[us] multpl取得失敗: {e}")
            return finish(2)

        problems = []
        problems += validate_series(jp_val["per"], JP_MIN_POINTS, "jp.per")
        problems += validate_series(jp_val["pbr"], JP_MIN_POINTS, "jp.pbr")
        problems += validate_series(us_val["per"], US_PE_MIN_POINTS, "us.per")
        problems += validate_series(us_val["pbr"], US_PB_MIN_POINTS, "us.pbr")
        if problems:
            log("品質ゲート異常のため書き込みを行わず終了します:")
            for p in problems:
                log(f"  - {p}")
            return finish(1)
        log(f"[品質ゲート] PASS jp.per={len(jp_val['per'])}点 jp.pbr={len(jp_val['pbr'])}点 "
            f"us.per={len(us_val['per'])}点 us.pbr={len(us_val['pbr'])}点")
        backfill_thermometer(data_dir, jp_val, us_val, log)
    else:
        log("[valuation] --skip-valuation指定によりスキップ")

    if not skip_factor_returns:
        # 最新のdailyスナップショットからユニバース銘柄を取得
        daily_dir = os.path.join(data_dir, "daily")
        dates = sorted(d for d in os.listdir(daily_dir)) if os.path.isdir(daily_dir) else []
        if not dates:
            log("[factors] dailyスナップショットが無いためスキップ")
            return finish(2)
        latest_date = dates[-1]
        jp_snap = _load_json(os.path.join(daily_dir, latest_date, "jp.json")) or {}
        us_snap = _load_json(os.path.join(daily_dir, latest_date, "us.json")) or {}
        jp_tickers = [s["ticker"] for s in jp_snap.get("stocks", [])]
        us_tickers = [s["ticker"] for s in us_snap.get("stocks", [])]
        all_tickers = jp_tickers + us_tickers
        log(f"[factors] 対象ユニバース: jp={len(jp_tickers)} us={len(us_tickers)} (daily {latest_date})")

        try:
            fetcher = fetch_prices or (lambda ts: fy.fetch_price_history_bulk(ts, period="14mo"))
            price_history = fetcher(all_tickers)
        except Exception as e:  # noqa: BLE001
            log(f"[factors] 株価履歴の取得失敗: {e}")
            return finish(2)
        coverage = len(price_history) / len(all_tickers) if all_tickers else 0
        log(f"[factors] 株価履歴カバレッジ: {len(price_history)}/{len(all_tickers)} = {coverage:.1%}")
        if coverage < 0.5:
            log("[factors] カバレッジ50%未満のため書き込みを行わず終了します(取得不良の疑い)")
            return finish(1)
        backfill_factor_returns(data_dir, price_history, jp_tickers, us_tickers, log)
    else:
        log("[factors] --skip-factor-returns指定によりスキップ")

    log("=== pipeline.backfill 正常終了 ===")
    return finish(0)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="T-17: 過去データバックフィル(一回限り)")
    parser.add_argument("--data-dir", help="出力先dataディレクトリ(省略時はリポジトリ直下のdata/)")
    parser.add_argument("--jp-valuation", help="日経PER/PBRスパイク成果物JSON(省略時は既定パス)")
    parser.add_argument("--skip-valuation", action="store_true", help="市場体温計バックフィルをスキップ")
    parser.add_argument("--skip-factor-returns", action="store_true", help="ファクターリターン算出をスキップ")
    args = parser.parse_args(argv)
    return run(
        data_dir=args.data_dir,
        jp_valuation_file=args.jp_valuation,
        skip_valuation=args.skip_valuation,
        skip_factor_returns=args.skip_factor_returns,
    )


if __name__ == "__main__":
    sys.exit(main())
