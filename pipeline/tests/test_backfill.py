"""T-17: pipeline/backfill.py と factors.py のバックフィル関連ロジックの単体テスト。"""
from __future__ import annotations

import json
import os

import pytest

from pipeline import backfill
from pipeline.metrics import calculations as calc
from pipeline.metrics import factors as factors_mod


# ---------------------------------------------------------------------------
# calculations: historical_percentile / trailing_return
# ---------------------------------------------------------------------------

class TestHistoricalPercentile:
    def test_empty_window_returns_none(self):
        assert calc.historical_percentile([], 10.0) is None

    def test_none_x_returns_none(self):
        assert calc.historical_percentile([1.0, 2.0], None) is None

    def test_all_none_window_returns_none(self):
        assert calc.historical_percentile([None, None], 1.0) is None

    def test_max_value(self):
        # 10要素中、最大値(自分含む)= (9 + 0.5)/10 = 0.95
        window = list(range(1, 11))
        assert calc.historical_percentile(window, 10) == pytest.approx(0.95)

    def test_min_value(self):
        window = list(range(1, 11))
        assert calc.historical_percentile(window, 1) == pytest.approx(0.05)

    def test_ties_use_average_rank(self):
        # [1,2,2,3] で x=2 → (1 + 2/2)/4 = 0.5
        assert calc.historical_percentile([1, 2, 2, 3], 2) == pytest.approx(0.5)


class TestTrailingReturn:
    def test_basic(self):
        closes = [100.0] * 21 + [110.0]  # 22点 → 21営業日リターン
        assert calc.trailing_return(closes, 21) == pytest.approx(0.10)

    def test_insufficient_history_returns_none(self):
        assert calc.trailing_return([100.0] * 21, 21) is None  # 22点必要

    def test_none_input(self):
        assert calc.trailing_return(None, 21) is None

    def test_zero_start_price(self):
        closes = [0.0] + [100.0] * 21
        assert calc.trailing_return(closes, 21) is None

    def test_empty(self):
        assert calc.trailing_return([], 21) is None


# ---------------------------------------------------------------------------
# backfill: multplパース
# ---------------------------------------------------------------------------

MULTPL_SAMPLE = """
<tr><td>Jul 9, 2026</td>
<td>
<abbr title="Estimate">†</abbr>
32.45
</td></tr>
<tr class="odd"><td>Sep 1, 2025</td>
<td>
&#x2002;
28.13
</td></tr>
<tr><td>Jan 1, 1871</td>
<td>
&#x2002;
11.10
</td></tr>
"""


class TestParseMultplTable:
    def test_parses_estimate_and_regular_rows(self):
        rows = backfill.parse_multpl_table(MULTPL_SAMPLE)
        assert rows == [
            {"date": "1871-01-01", "value": 11.10},
            {"date": "2025-09-01", "value": 28.13},
            {"date": "2026-07-09", "value": 32.45},
        ]

    def test_empty_html(self):
        assert backfill.parse_multpl_table("<html></html>") == []


# ---------------------------------------------------------------------------
# backfill: 日経スパイク成果物の読み込み
# ---------------------------------------------------------------------------

class TestLoadJpValuation:
    def test_converts_dates_and_uses_weighted(self, tmp_path):
        src = {
            "per": [
                {"date": "2021.01.04", "weighted": 25.13, "index_based": 28.03},
                {"date": "2021.01.05", "weighted": 25.02, "index_based": 27.93},
            ],
            "pbr": [{"date": "2021.01.04", "weighted": 1.2, "index_based": 2.05}],
        }
        p = tmp_path / "jp.json"
        p.write_text(json.dumps(src), encoding="utf-8")
        out = backfill.load_jp_valuation(str(p))
        assert out["per"][0] == {"date": "2021-01-04", "value": 25.13}
        assert out["per"][1]["value"] == 25.02
        assert out["pbr"] == [{"date": "2021-01-04", "value": 1.2}]

    def test_skips_error_rows(self, tmp_path):
        src = {"per": [{"error": "boom", "year": 2021, "month": 1},
                        {"date": "2021.01.04", "weighted": 25.13, "index_based": 28.03}],
               "pbr": []}
        p = tmp_path / "jp.json"
        p.write_text(json.dumps(src), encoding="utf-8")
        out = backfill.load_jp_valuation(str(p))
        assert len(out["per"]) == 1
        assert out["pbr"] == []


# ---------------------------------------------------------------------------
# backfill: 品質ゲート
# ---------------------------------------------------------------------------

class TestValidateSeries:
    def test_pass(self):
        series = [{"date": f"2025-01-{d:02d}", "value": 20.0} for d in range(1, 31)]
        assert backfill.validate_series(series, 30, "x") == []

    def test_too_few_points(self):
        assert backfill.validate_series([], 1, "x")

    def test_out_of_range_value(self):
        series = [{"date": "2025-01-01", "value": 9999.0}]
        problems = backfill.validate_series(series, 1, "x")
        assert any("レンジ外" in p for p in problems)

    def test_malformed_date(self):
        series = [{"date": "2025.01.01", "value": 20.0}]
        problems = backfill.validate_series(series, 1, "x")
        assert any("日付形式" in p for p in problems)


# ---------------------------------------------------------------------------
# backfill: 超過リターン計算
# ---------------------------------------------------------------------------

def _flat_series(final_return: float, days: int = 260) -> list[float]:
    """days+1点で最終値のみ動く単純系列(全ホライズンで同一リターンになる)。"""
    return [100.0] * days + [100.0 * (1 + final_return)]


class TestComputeExcessReturns:
    def test_positive_excess(self):
        prices = {"A": _flat_series(0.10), "B": _flat_series(0.02), "C": _flat_series(0.04)}
        out = backfill.compute_excess_returns(["A"], ["A", "B", "C"], prices)
        # 分位=10%、ユニバース平均=(10+2+4)/3=5.333% → 超過 +4.67pt
        for field in backfill.RETURN_HORIZONS:
            assert out[field] == pytest.approx(4.67, abs=0.01)

    def test_empty_quintile_returns_none(self):
        prices = {"B": _flat_series(0.02)}
        out = backfill.compute_excess_returns([], ["B"], prices)
        assert all(v is None for v in out.values())

    def test_low_coverage_returns_none(self):
        # 分位2銘柄のうち履歴が取れたのは0銘柄 → カバレッジ0% < 50% → None
        prices = {"B": _flat_series(0.02)}
        out = backfill.compute_excess_returns(["X", "Y"], ["B"], prices)
        assert all(v is None for v in out.values())

    def test_short_history_excluded_per_horizon(self):
        # Aは1ヶ月分しか履歴が無い → 1mのみ算出、3m/1yはカバレッジ不足でNone
        prices = {"A": [100.0] * 21 + [110.0], "B": _flat_series(0.02)}
        out = backfill.compute_excess_returns(["A"], ["A", "B"], prices)
        assert out["factor_return_1m"] is not None
        assert out["factor_return_3m"] is None
        assert out["factor_return_1y"] is None


# ---------------------------------------------------------------------------
# backfill: ファクターへの記入と冪等性
# ---------------------------------------------------------------------------

def _factor_fixture() -> dict:
    return {
        "factor": "value",
        "markets": ["jp", "us"],
        "history": [
            {"date": "2026-07-09", "factor_return_1m": None, "factor_return_3m": None,
             "factor_return_1y": None, "screen_count": 10},
            {"date": "2026-07-10", "factor_return_1m": None, "factor_return_3m": None,
             "factor_return_1y": None, "screen_count": 12},
        ],
        "today_screen": {
            "jp": [{"ticker": "7203.T", "rank": 1, "quantile": "top_quintile", "metric_value": 0.9}],
            "us": [{"ticker": "F", "rank": 1, "quantile": "top_quintile", "metric_value": 1.4},
                    {"ticker": "AAPL", "rank": 2, "quantile": "other", "metric_value": 30.0}],
        },
    }


class TestApplyFactorReturns:
    def test_writes_to_latest_entry_only(self):
        returns = {"factor_return_1m": 1.5, "factor_return_3m": -0.3, "factor_return_1y": 4.0}
        out = backfill.apply_factor_returns(_factor_fixture(), returns)
        assert out["history"][-1]["factor_return_1m"] == 1.5
        assert out["history"][-1]["date"] == "2026-07-10"
        assert out["history"][0]["factor_return_1m"] is None  # 過去分は触らない
        assert "近似" in out["factor_return_note"]

    def test_idempotent(self):
        returns = {"factor_return_1m": 1.5, "factor_return_3m": -0.3, "factor_return_1y": 4.0}
        once = backfill.apply_factor_returns(_factor_fixture(), returns)
        twice = backfill.apply_factor_returns(once, returns)
        assert once == twice
        assert len(twice["history"]) == 2  # 重複追加しない

    def test_empty_history_no_crash(self):
        f = _factor_fixture()
        f["history"] = []
        out = backfill.apply_factor_returns(f, {"factor_return_1m": 1.0})
        assert out["history"] == []


class TestQuintileTickers:
    def test_top_quintile_from_both_markets(self):
        assert backfill.quintile_tickers_for_factor(_factor_fixture()) == ["7203.T", "F"]

    def test_margin_trading_top20pct(self):
        f = {"factor": "margin-trading",
             "today_screen": {"jp": [{"ticker": f"{i}.T"} for i in range(10)]}}
        assert backfill.quintile_tickers_for_factor(f) == ["0.T", "1.T"]

    def test_margin_trading_empty(self):
        f = {"factor": "margin-trading", "today_screen": {"jp": []}}
        assert backfill.quintile_tickers_for_factor(f) == []


# ---------------------------------------------------------------------------
# factors: valuation_history の適用と日次実行での保持
# ---------------------------------------------------------------------------

def _valuation(n_days: int = 1300, latest: float = 18.0) -> dict:
    """約5年分のダミー日次系列(値は10..30の繰り返し、最新のみlatest)。"""
    from datetime import date, timedelta
    start = date(2021, 1, 4)
    series = []
    for i in range(n_days):
        d = start + timedelta(days=i)
        series.append({"date": d.isoformat(), "value": 10 + (i % 21)})
    series.append({"date": "2026-07-09", "value": latest})
    return {"per": series, "pbr": series}


class TestApplyValuationHistory:
    def test_fills_per_pbr_and_percentile(self):
        block = {"index": "NIKKEI225", "index_per": None, "index_pbr": None,
                 "index_per_percentile_5y": None, "index_pbr_percentile_5y": None}
        factors_mod.apply_valuation_history(block, _valuation(latest=18.0))
        assert block["index_per"] == 18.0
        assert block["index_per_as_of"] == "2026-07-09"
        assert 0.0 <= block["index_per_percentile_5y"] <= 1.0
        assert block["index_pbr"] == 18.0

    def test_extreme_low_value_is_low_percentile(self):
        block = {"index_per": None, "index_per_percentile_5y": None}
        factors_mod.apply_valuation_history(block, {"per": _valuation(latest=1.0)["per"], "pbr": []})
        assert block["index_per_percentile_5y"] < 0.01

    def test_none_block_or_valuation_no_crash(self):
        factors_mod.apply_valuation_history(None, _valuation())
        block = {"index_per": None}
        factors_mod.apply_valuation_history(block, None)
        assert block["index_per"] is None

    def test_empty_series_keeps_null(self):
        block = {"index_per": None, "index_per_percentile_5y": None}
        factors_mod.apply_valuation_history(block, {"per": [], "pbr": []})
        assert block["index_per"] is None
        assert block["index_per_percentile_5y"] is None


class TestThermometerPreservesValuation:
    def test_daily_rerun_keeps_valuation_and_percentiles(self):
        existing = {
            "date": "2026-07-10",
            "jp": {}, "us": {},
            "history": [],
            "valuation_history": {"jp": _valuation(), "us": _valuation()},
        }
        out = factors_mod.build_market_thermometer_snapshot(
            existing, "2026-07-11",
            jp_index={"level": 69000.0, "level_as_of": "2026-07-11", "change_pct_1d": 0.1},
            us_index={"level": 7500.0, "level_as_of": "2026-07-10", "change_pct_1d": 0.2},
            margin_market_total=None,
        )
        assert "valuation_history" in out
        assert out["jp"]["index_per"] is not None
        assert out["jp"]["index_per_percentile_5y"] is not None
        assert out["us"]["index_pbr_percentile_5y"] is not None

    def test_without_valuation_stays_null(self):
        out = factors_mod.build_market_thermometer_snapshot(
            None, "2026-07-11",
            jp_index={"level": 69000.0, "level_as_of": "2026-07-11", "change_pct_1d": 0.1},
            us_index=None, margin_market_total=None,
        )
        assert out["jp"]["index_per"] is None
        assert "valuation_history" not in out


class TestFactorSnapshotPreservesBackfill:
    def test_same_date_rerun_keeps_backfilled_returns(self):
        stocks_jp = [{"ticker": f"{1000+i}.T", "pbr": 1.0 + i * 0.1} for i in range(10)]
        first = factors_mod.build_factor_snapshot(None, "value", "2026-07-10", stocks_jp, [])
        # バックフィルでリターンを記入
        first["history"][-1]["factor_return_1m"] = 2.5
        first["factor_return_note"] = "note"
        # 同日再実行(冪等な上書き)でも保持される
        second = factors_mod.build_factor_snapshot(first, "value", "2026-07-10", stocks_jp, [])
        assert second["history"][-1]["factor_return_1m"] == 2.5
        assert second["factor_return_note"] == "note"
        assert len(second["history"]) == 1

    def test_new_date_entry_is_null(self):
        stocks_jp = [{"ticker": f"{1000+i}.T", "pbr": 1.0 + i * 0.1} for i in range(10)]
        first = factors_mod.build_factor_snapshot(None, "value", "2026-07-10", stocks_jp, [])
        first["history"][-1]["factor_return_1m"] = 2.5
        second = factors_mod.build_factor_snapshot(first, "value", "2026-07-11", stocks_jp, [])
        assert second["history"][-1]["factor_return_1m"] is None  # 翌日分は捏造しない
        assert second["history"][0]["factor_return_1m"] == 2.5


# ---------------------------------------------------------------------------
# run(): 品質ゲートで書き込みしない(統合・ファイルI/O)
# ---------------------------------------------------------------------------

class TestRunQualityGate:
    def test_broken_jp_file_exits_2_without_write(self, tmp_path):
        data_dir = tmp_path / "data"
        (data_dir / "factors").mkdir(parents=True)
        thermo_path = data_dir / "factors" / "market-thermometer.json"
        thermo_path.write_text('{"date": "2026-07-10", "jp": {}, "us": {}, "history": []}', encoding="utf-8")
        rc = backfill.run(
            data_dir=str(data_dir),
            jp_valuation_file=str(tmp_path / "missing.json"),
            skip_factor_returns=True,
        )
        assert rc == 2
        assert "valuation_history" not in json.loads(thermo_path.read_text(encoding="utf-8"))

    def test_too_short_series_exits_1_without_write(self, tmp_path):
        data_dir = tmp_path / "data"
        (data_dir / "factors").mkdir(parents=True)
        thermo_path = data_dir / "factors" / "market-thermometer.json"
        thermo_path.write_text('{"date": "2026-07-10", "jp": {}, "us": {}, "history": []}', encoding="utf-8")
        jp_file = tmp_path / "jp.json"
        jp_file.write_text(json.dumps({
            "per": [{"date": "2026.07.09", "weighted": 18.0, "index_based": 24.0}],
            "pbr": [{"date": "2026.07.09", "weighted": 1.9, "index_based": 2.8}],
        }), encoding="utf-8")
        rc = backfill.run(
            data_dir=str(data_dir),
            jp_valuation_file=str(jp_file),
            fetch_us=lambda: {"per": [], "pbr": []},
            skip_factor_returns=True,
        )
        assert rc == 1
        assert "valuation_history" not in json.loads(thermo_path.read_text(encoding="utf-8"))
