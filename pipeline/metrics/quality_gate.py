"""T-05: 日次スナップショットの品質ゲート(純粋関数、ネットワーク・ファイルI/Oなし)。

docs/05-work-breakdown.md T-05の作業定義:
  (a) 欠損率閾値: price/market_cap の欠損率が閾値(既定5%)を超えたら異常
  (b) 前日比異常値検知: 銘柄群の中央値PER(per_trailing)が前日比で閾値(既定±30%)を超えて変動したら異常
  (c) 異常時は呼び出し側(daily.py)が書き込みを行わず非ゼロ終了する(本モジュールは判定のみ行う)

T-01/T-02実測(docs/07-data-schema.md 2.2節)では price/market_cap の欠損率は日米とも0%だったため、
通常運転でこのゲートに誤検知で引っかかることはない想定(閾値5%は実測値に対して十分な余裕を持たせた設計)。
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Optional, Sequence

DEFAULT_MISSING_FIELDS = ("price", "market_cap")
DEFAULT_MISSING_THRESHOLD = 0.05
DEFAULT_MEDIAN_CHANGE_FIELD = "per_trailing"
DEFAULT_MEDIAN_CHANGE_THRESHOLD = 0.30


def missing_rate(stocks: Sequence[dict], field_name: str) -> float:
    """指定フィールドの欠損率(0.0〜1.0)を返す。銘柄0件の場合は0.0を返す(境界値: 空リスト)。"""
    n = len(stocks)
    if n == 0:
        return 0.0
    missing = sum(1 for s in stocks if s.get(field_name) is None)
    return missing / n


def median_of(stocks: Sequence[dict], field_name: str) -> Optional[float]:
    """指定フィールドの中央値(Noneは除外)を返す。全件Noneまたは空リストならNone。"""
    values = [s.get(field_name) for s in stocks if s.get(field_name) is not None]
    if not values:
        return None
    return statistics.median(values)


@dataclass
class GateResult:
    passed: bool
    reasons: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def check_market(
    market: str,
    today_stocks: Sequence[dict],
    prev_stocks: Optional[Sequence[dict]] = None,
    missing_fields: Sequence[str] = DEFAULT_MISSING_FIELDS,
    missing_threshold: float = DEFAULT_MISSING_THRESHOLD,
    median_change_field: str = DEFAULT_MEDIAN_CHANGE_FIELD,
    median_change_threshold: float = DEFAULT_MEDIAN_CHANGE_THRESHOLD,
) -> GateResult:
    """1市場分の品質ゲート判定。

    prev_stocksがNone(前日データなし=初回実行等)の場合、前日比チェックはスキップする
    (安全側=判定不能を異常扱いにはしない。ただし欠損率チェックは常に実施する)。
    """
    reasons: list[str] = []
    metrics: dict = {}

    for f in missing_fields:
        rate = missing_rate(today_stocks, f)
        metrics[f"missing_rate.{f}"] = rate
        if rate > missing_threshold:
            reasons.append(
                f"{market}: {f} の欠損率 {rate:.2%} が閾値 {missing_threshold:.0%} を超過"
            )

    if prev_stocks is not None:
        today_med = median_of(today_stocks, median_change_field)
        prev_med = median_of(prev_stocks, median_change_field)
        metrics[f"median.{median_change_field}.today"] = today_med
        metrics[f"median.{median_change_field}.prev"] = prev_med
        if today_med is not None and prev_med:
            change = abs(today_med - prev_med) / abs(prev_med)
            metrics[f"median.{median_change_field}.change_pct"] = change
            if change > median_change_threshold:
                reasons.append(
                    f"{market}: 中央値{median_change_field}の前日比変動 {change:.2%} が"
                    f"閾値 {median_change_threshold:.0%} を超過(前日={prev_med:.4g} 本日={today_med:.4g})"
                )

    return GateResult(passed=not reasons, reasons=reasons, metrics=metrics)
