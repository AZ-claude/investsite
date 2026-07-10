"""T-05: 日次スナップショット蓄積CLI。

実行方法: python -m pipeline.daily [--date YYYY-MM-DD] [--markets jp,us] [--data-dir DIR]
          [--mock-jp FILE] [--mock-us FILE] [--skip-thermometer]

処理フロー: 取得(pipeline/metrics/snapshot.py, T-04実装) → 計算(取得内で実施済み)
          → 品質ゲート(pipeline/metrics/quality_gate.py) → data/daily/YYYY-MM-DD/{jp|us}.json 書き出し
          → data/factors/*.json ・ data/factors/market-thermometer.json の時系列追記(upsert=冪等)

品質ゲートで異常判定した場合は書き込みを一切行わず、非ゼロ終了する(前日データ維持=安全側)。
実行結果は標準出力 + data/logs/YYYY-MM-DD.log に記録する。

--mock-jp/--mock-us: 実ネットワーク取得の代わりにJSONファイルをそのまま当日データとして使う開発・テスト用フック。
  壊しテスト(意図的に異常データを注入して品質ゲートを弾かせる検証)や、実ネットワーク再取得なしでの
  2日分蓄積の動作確認に使う。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from pipeline.metrics import factors as factors_mod
from pipeline.metrics import fetch_yfinance as fy
from pipeline.metrics import margin_jpx
from pipeline.metrics import quality_gate
from pipeline.metrics import snapshot

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.abspath(__file__)).rsplit(os.sep, 1)[0]


def _load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def find_previous_snapshot(data_dir: str, market: str, before_date: str) -> Optional[dict]:
    """指定日より前の日付で最も新しい daily/{market}.json を探して返す(前日比ゲート用)。

    データが飛び飛びの場合(週末・休場日等)に備え、直前1日ではなく「before_dateより前で最新」を探す。
    見つからなければNone(前日比チェックはスキップされる)。
    """
    daily_dir = os.path.join(data_dir, "daily")
    if not os.path.isdir(daily_dir):
        return None
    candidates = sorted(d for d in os.listdir(daily_dir) if d < before_date)
    for d in reversed(candidates):
        path = os.path.join(daily_dir, d, f"{market}.json")
        if os.path.exists(path):
            return _load_json(path)
    return None


def run(
    date: Optional[str] = None,
    markets: tuple = ("jp", "us"),
    data_dir: Optional[str] = None,
    fetch_jp: Optional[Callable[[], dict]] = None,
    fetch_us: Optional[Callable[[], dict]] = None,
    fetch_jp_index: Optional[Callable[[], dict]] = None,
    fetch_us_index: Optional[Callable[[], dict]] = None,
    fetch_margin_total: Optional[Callable[[], Optional[dict]]] = None,
    skip_thermometer: bool = False,
    missing_threshold: float = quality_gate.DEFAULT_MISSING_THRESHOLD,
    median_change_threshold: float = quality_gate.DEFAULT_MEDIAN_CHANGE_THRESHOLD,
) -> int:
    """1回分の日次パイプラインを実行する。戻り値は終了コード(0=正常, 1=品質ゲート異常, 2=取得失敗)。

    fetch_jp/fetch_us/fetch_jp_index/fetch_us_index/fetch_margin_total を差し替えることで、
    実ネットワークなしに動作確認・壊しテストができる(依存性注入)。
    """
    data_dir = data_dir or os.path.join(REPO_ROOT, "data")
    date = date or datetime.now(JST).strftime("%Y-%m-%d")
    fetch_jp = fetch_jp or (lambda: snapshot.build_jp_snapshot(fetch_margin=True))
    fetch_us = fetch_us or snapshot.build_us_snapshot
    fetch_jp_index = fetch_jp_index or (lambda: fy.fetch_index_quote("^N225"))
    fetch_us_index = fetch_us_index or (lambda: fy.fetch_index_quote("^GSPC"))
    fetch_margin_total = fetch_margin_total or margin_jpx.fetch_market_total_margin

    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    def finish(code: int) -> int:
        log_path = os.path.join(data_dir, "logs", f"{date}.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines) + "\n")
        return code

    log(f"=== pipeline.daily 開始 date={date} markets={markets} ===")

    fetchers = {"jp": fetch_jp, "us": fetch_us}
    snapshots: dict[str, dict] = {}
    for m in markets:
        log(f"[{m}] 取得開始")
        try:
            snap = fetchers[m]()
        except Exception as e:  # noqa: BLE001
            log(f"[{m}] 取得失敗: {e}")
            return finish(2)
        snap = dict(snap)
        snap["date"] = date  # --date指定 / mock注入時も日付を統一する
        snapshots[m] = snap
        log(f"[{m}] 取得完了 銘柄数={len(snap.get('stocks', []))}")

    gate_failed = False
    for m, snap in snapshots.items():
        prev = find_previous_snapshot(data_dir, m, date)
        result = quality_gate.check_market(
            m,
            snap.get("stocks", []),
            prev.get("stocks") if prev else None,
            missing_threshold=missing_threshold,
            median_change_threshold=median_change_threshold,
        )
        for f in quality_gate.DEFAULT_MISSING_FIELDS:
            log(f"[{m}] {f} 欠損率 = {result.metrics.get(f'missing_rate.{f}', 0.0):.2%}")
        if prev is None:
            log(f"[{m}] 前日データなし(前日比ゲートはスキップ)")
        if result.passed:
            log(f"[{m}] 品質ゲート: PASS")
        else:
            log(f"[{m}] 品質ゲート: FAIL")
            for r in result.reasons:
                log(f"  - {r}")
            gate_failed = True

    if gate_failed:
        log("品質ゲート異常のため書き込みを行わず終了します(前日データを維持=安全側)")
        return finish(1)

    for m, snap in snapshots.items():
        path = os.path.join(data_dir, "daily", date, f"{m}.json")
        _write_json(path, snap)
        log(f"[{m}] 書き出し完了: {path}")

    jp_stocks = snapshots.get("jp", {}).get("stocks", [])
    us_stocks = snapshots.get("us", {}).get("stocks", [])

    for factor in factors_mod.FACTOR_DEFS:
        path = os.path.join(data_dir, "factors", f"{factor}.json")
        existing = _load_json(path)
        updated = factors_mod.build_factor_snapshot(existing, factor, date, jp_stocks, us_stocks)
        _write_json(path, updated)
        log(f"[factors/{factor}.json] 更新完了 history件数={len(updated['history'])}")

    if "jp" in snapshots:
        path = os.path.join(data_dir, "factors", "margin-trading.json")
        existing = _load_json(path)
        updated = factors_mod.build_margin_trading_snapshot(existing, date, jp_stocks)
        _write_json(path, updated)
        log(f"[factors/margin-trading.json] 更新完了 history件数={len(updated['history'])}")

    if not skip_thermometer:
        path = os.path.join(data_dir, "factors", "market-thermometer.json")
        existing = _load_json(path)
        jp_index = fetch_jp_index() if "jp" in snapshots else None
        us_index = fetch_us_index() if "us" in snapshots else None
        margin_total = fetch_margin_total() if "jp" in snapshots else None
        updated = factors_mod.build_market_thermometer_snapshot(existing, date, jp_index, us_index, margin_total)
        _write_json(path, updated)
        log(f"[factors/market-thermometer.json] 更新完了 history件数={len(updated['history'])}")
    else:
        log("[factors/market-thermometer.json] --skip-thermometer指定によりスキップ")

    log(f"=== pipeline.daily 正常終了 date={date} ===")
    return finish(0)


def _load_mock(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="T-05: 日次スナップショット蓄積CLI")
    parser.add_argument("--date", help="対象日(YYYY-MM-DD)。省略時はJST当日")
    parser.add_argument("--markets", default="jp,us", help="カンマ区切り(例: jp,us / jp)")
    parser.add_argument("--data-dir", help="出力先dataディレクトリ(省略時はリポジトリ直下のdata/)")
    parser.add_argument("--mock-jp", help="実取得の代わりに使うJSONファイル(開発・壊しテスト用)")
    parser.add_argument("--mock-us", help="実取得の代わりに使うJSONファイル(開発・壊しテスト用)")
    parser.add_argument("--skip-thermometer", action="store_true", help="market-thermometer更新をスキップ")
    parser.add_argument("--missing-threshold", type=float, default=quality_gate.DEFAULT_MISSING_THRESHOLD)
    parser.add_argument("--median-change-threshold", type=float, default=quality_gate.DEFAULT_MEDIAN_CHANGE_THRESHOLD)
    args = parser.parse_args(argv)

    markets = tuple(m.strip() for m in args.markets.split(",") if m.strip())

    fetch_jp = (lambda p=args.mock_jp: _load_mock(p)) if args.mock_jp else None
    fetch_us = (lambda p=args.mock_us: _load_mock(p)) if args.mock_us else None
    skip_thermometer = args.skip_thermometer or bool(args.mock_jp or args.mock_us)

    return run(
        date=args.date,
        markets=markets,
        data_dir=args.data_dir,
        fetch_jp=fetch_jp,
        fetch_us=fetch_us,
        skip_thermometer=skip_thermometer,
        missing_threshold=args.missing_threshold,
        median_change_threshold=args.median_change_threshold,
    )


if __name__ == "__main__":
    sys.exit(main())
