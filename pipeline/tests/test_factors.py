"""pipeline/metrics/factors.py の単体テスト(T-05)。history upsertの冪等性、分位抽出、境界値を確認する。"""
from pipeline.metrics import factors as fx


def stock(ticker, **kw):
    return {"ticker": ticker, **kw}


class TestUpsertHistory:
    def test_appends_new_date(self):
        history = [{"date": "2026-07-08", "v": 1}]
        out = fx.upsert_history(history, {"date": "2026-07-09", "v": 2})
        assert [h["date"] for h in out] == ["2026-07-08", "2026-07-09"]

    def test_replaces_same_date_idempotent(self):
        """同一日付の再実行は上書き(冪等)であり、件数が増えないこと。"""
        history = [{"date": "2026-07-09", "v": 1}]
        out = fx.upsert_history(history, {"date": "2026-07-09", "v": 2})
        assert len(out) == 1
        assert out[0]["v"] == 2

    def test_sorts_by_date(self):
        history = [{"date": "2026-07-10", "v": 1}]
        out = fx.upsert_history(history, {"date": "2026-07-05", "v": 2})
        assert [h["date"] for h in out] == ["2026-07-05", "2026-07-10"]

    def test_empty_history(self):
        out = fx.upsert_history([], {"date": "2026-07-10", "v": 1})
        assert len(out) == 1


class TestBuildTodayScreen:
    def test_low_direction_picks_lowest_values(self):
        rows = [stock(f"T{i}", pbr=float(i)) for i in range(1, 11)]  # 1..10
        out = fx.build_today_screen(rows, "pbr", "low")
        top = [r for r in out if r["quantile"] == "top_quintile"]
        assert {r["ticker"] for r in top} == {"T1", "T2"}  # 上位20% = 最小2件

    def test_high_direction_picks_highest_values(self):
        rows = [stock(f"T{i}", momentum_12_1=float(i)) for i in range(1, 11)]
        out = fx.build_today_screen(rows, "momentum_12_1", "high")
        top = [r for r in out if r["quantile"] == "top_quintile"]
        assert {r["ticker"] for r in top} == {"T9", "T10"}

    def test_excludes_none_values(self):
        rows = [stock("A", pbr=None), stock("B", pbr=1.0)]
        out = fx.build_today_screen(rows, "pbr", "low")
        assert len(out) == 1
        assert out[0]["ticker"] == "B"

    def test_empty_rows_returns_empty(self):
        """境界値: 銘柄0件の場合は空リスト。"""
        assert fx.build_today_screen([], "pbr", "low") == []

    def test_single_row_gets_top_quintile(self):
        """境界値: 1銘柄しかない場合でも top_quintile が最低1件付与される。"""
        out = fx.build_today_screen([stock("A", pbr=1.0)], "pbr", "low")
        assert out[0]["quantile"] == "top_quintile"


class TestBuildFactorSnapshot:
    def test_first_run_creates_default_evidence(self):
        jp = [stock(f"T{i}", pbr=float(i)) for i in range(1, 6)]
        result = fx.build_factor_snapshot(None, "value", "2026-07-10", jp, [])
        assert result["factor"] == "value"
        assert result["evidence"] == fx.FACTOR_DEFS["value"]["default_evidence"]
        assert len(result["history"]) == 1
        assert result["history"][0]["date"] == "2026-07-10"
        assert result["history"][0]["screen_count"] == 5

    def test_rerun_same_date_is_idempotent(self):
        jp = [stock(f"T{i}", pbr=float(i)) for i in range(1, 6)]
        first = fx.build_factor_snapshot(None, "value", "2026-07-10", jp, [])
        second = fx.build_factor_snapshot(first, "value", "2026-07-10", jp, [])
        assert len(second["history"]) == 1

    def test_accumulates_over_two_dates(self):
        jp = [stock(f"T{i}", pbr=float(i)) for i in range(1, 6)]
        first = fx.build_factor_snapshot(None, "value", "2026-07-09", jp, [])
        second = fx.build_factor_snapshot(first, "value", "2026-07-10", jp, [])
        assert [h["date"] for h in second["history"]] == ["2026-07-09", "2026-07-10"]

    def test_preserves_custom_evidence_across_runs(self):
        jp = [stock("T1", pbr=1.0)]
        first = fx.build_factor_snapshot(None, "value", "2026-07-09", jp, [])
        first["evidence"] = [{"claim": "custom", "source": "x", "confirmed": True}]
        second = fx.build_factor_snapshot(first, "value", "2026-07-10", jp, [])
        assert second["evidence"] == [{"claim": "custom", "source": "x", "confirmed": True}]


class TestBuildMarginTradingSnapshot:
    def test_ranks_by_margin_ratio_seido_desc(self):
        jp = [
            stock("A", margin={"margin_ratio_seido": 2.0, "as_of_week": "2026-07-03"}),
            stock("B", margin={"margin_ratio_seido": 5.0, "as_of_week": "2026-07-03"}),
            stock("C"),  # marginキーなし(週次データ未取得銘柄)
        ]
        result = fx.build_margin_trading_snapshot(None, "2026-07-10", jp)
        tickers = [r["ticker"] for r in result["today_screen"]["jp"]]
        assert tickers == ["B", "A"]
        assert result["history"][0]["screen_count"] == 2


class TestBuildMarketThermometerSnapshot:
    def test_first_run(self):
        jp_index = {"level": 66819.0, "level_as_of": "2026-07-08", "change_pct_1d": -2.1}
        us_index = {"level": 7540.9, "level_as_of": "2026-07-09", "change_pct_1d": 0.8}
        result = fx.build_market_thermometer_snapshot(None, "2026-07-10", jp_index, us_index, None)
        assert result["date"] == "2026-07-10"
        assert result["jp"]["index_level"] == 66819.0
        assert result["us"]["index_level"] == 7540.9
        assert len(result["history"]) == 1

    def test_top_level_reflects_latest_date_after_backfill(self):
        """境界値: --dateで過去日を後追い実行しても、top-levelは常にhistory中の最新日付を指す。"""
        idx1 = {"level": 100.0, "level_as_of": "2026-07-10", "change_pct_1d": 1.0}
        latest = fx.build_market_thermometer_snapshot(None, "2026-07-10", idx1, idx1, None)

        idx0 = {"level": 90.0, "level_as_of": "2026-07-08", "change_pct_1d": -1.0}
        backfilled = fx.build_market_thermometer_snapshot(latest, "2026-07-08", idx0, idx0, None)

        assert backfilled["date"] == "2026-07-10"
        assert backfilled["jp"]["index_level"] == 100.0
        assert len(backfilled["history"]) == 2
