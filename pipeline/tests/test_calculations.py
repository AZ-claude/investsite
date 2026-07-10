"""pipeline/metrics/calculations.py の単体テスト。境界値(欠損・ゼロ除算・空ユニバース)を重点的に確認する。"""
from pipeline.metrics import calculations as calc


class TestSafeDiv:
    def test_normal(self):
        assert calc.safe_div(10, 2) == 5

    def test_zero_denominator(self):
        assert calc.safe_div(10, 0) is None

    def test_none_numerator(self):
        assert calc.safe_div(None, 5) is None

    def test_none_denominator(self):
        assert calc.safe_div(5, None) is None


class TestComputePerTrailing:
    def test_prefers_yfinance_value(self):
        assert calc.compute_per_trailing(15.0, price=100, eps=5) == 15.0

    def test_fallback_when_missing(self):
        assert calc.compute_per_trailing(None, price=100, eps=10) == 10

    def test_zero_eps_returns_none(self):
        """境界値: EPS=0(赤字転換直後等)でゼロ除算にならずNoneを返すこと。"""
        assert calc.compute_per_trailing(None, price=100, eps=0) is None

    def test_negative_eps_returns_none(self):
        """境界値: 赤字銘柄(EPSが負)はPERとして無意味なためNone。"""
        assert calc.compute_per_trailing(None, price=100, eps=-5) is None

    def test_missing_price_and_eps_returns_none(self):
        assert calc.compute_per_trailing(None, price=None, eps=None) is None


class TestComputePbr:
    def test_prefers_yfinance_value(self):
        assert calc.compute_pbr(1.5, price=100, book_value_per_share=50) == 1.5

    def test_fallback_when_missing(self):
        assert calc.compute_pbr(None, price=100, book_value_per_share=50) == 2.0

    def test_zero_book_value_returns_none(self):
        """境界値: 1株当たり純資産ゼロ(債務超過寸前等)でゼロ除算にならずNoneを返すこと。"""
        assert calc.compute_pbr(None, price=100, book_value_per_share=0) is None

    def test_negative_book_value_returns_none(self):
        """境界値: 債務超過(BPSが負)はPBRとして無意味なためNone。"""
        assert calc.compute_pbr(None, price=100, book_value_per_share=-10) is None


class TestComputeDividendYieldPct:
    def test_passthrough(self):
        assert calc.compute_dividend_yield_pct(2.53) == 2.53

    def test_none_stays_none(self):
        """境界値: 無配・非開示銘柄はNoneのまま保持する(0%と混同しない)。"""
        assert calc.compute_dividend_yield_pct(None) is None


class TestComputeRoe:
    def test_passthrough(self):
        assert calc.compute_roe(0.102) == 0.102

    def test_none_stays_none(self):
        assert calc.compute_roe(None) is None


class TestComputeMarketCap:
    def test_normal(self):
        assert calc.compute_market_cap(1000, 50) == 50000

    def test_missing_shares_returns_none(self):
        assert calc.compute_market_cap(None, 50) is None

    def test_missing_price_returns_none(self):
        assert calc.compute_market_cap(1000, None) is None


class TestComputeMomentum121:
    def _make_series(self, n, start=100.0, step=0.1):
        return [start + i * step for i in range(n)]

    def test_full_history_computes_value(self):
        closes = self._make_series(300)
        result = calc.compute_momentum_12_1(closes)
        assert result is not None
        end_idx = -calc.MOMENTUM_EXCLUDE_DAYS
        start_idx = -calc.MOMENTUM_EXCLUDE_DAYS - calc.MOMENTUM_LOOKBACK_DAYS
        expected = closes[end_idx] / closes[start_idx] - 1
        assert abs(result - expected) < 1e-9

    def test_listed_recently_insufficient_history_returns_none(self):
        """境界値: 上場直後で株価履歴が12ヶ月未満(253営業日未満)の銘柄はNoneを返す。"""
        closes = self._make_series(100)  # 約5ヶ月分しかない
        assert calc.compute_momentum_12_1(closes) is None

    def test_exactly_at_boundary(self):
        required = calc.MOMENTUM_EXCLUDE_DAYS + calc.MOMENTUM_LOOKBACK_DAYS
        closes = self._make_series(required)
        assert calc.compute_momentum_12_1(closes) is not None

    def test_one_short_of_boundary_returns_none(self):
        required = calc.MOMENTUM_EXCLUDE_DAYS + calc.MOMENTUM_LOOKBACK_DAYS
        closes = self._make_series(required - 1)
        assert calc.compute_momentum_12_1(closes) is None

    def test_empty_history_returns_none(self):
        assert calc.compute_momentum_12_1([]) is None

    def test_none_input_returns_none(self):
        assert calc.compute_momentum_12_1(None) is None

    def test_zero_start_price_returns_none(self):
        """境界値: 起点株価が0(データ異常)の場合ゼロ除算せずNoneを返す。"""
        required = calc.MOMENTUM_EXCLUDE_DAYS + calc.MOMENTUM_LOOKBACK_DAYS
        closes = [0.0] + [100.0] * (required - 1)
        assert calc.compute_momentum_12_1(closes) is None


class TestPercentileRank:
    def test_basic_ordering(self):
        values = {"a": 10, "b": 20, "c": 30}
        result = calc.percentile_rank(values)
        assert result["a"] < result["b"] < result["c"]
        assert result["a"] == 0.0
        assert result["c"] == 1.0

    def test_empty_universe_returns_all_none(self):
        """境界値: 空のユニバース(全銘柄None、または辞書自体が空)。"""
        assert calc.percentile_rank({}) == {}

    def test_all_none_values(self):
        result = calc.percentile_rank({"a": None, "b": None})
        assert result == {"a": None, "b": None}

    def test_none_values_excluded_but_present_in_result(self):
        result = calc.percentile_rank({"a": 10, "b": None, "c": 30})
        assert result["b"] is None
        assert result["a"] is not None
        assert result["c"] is not None

    def test_single_value_is_median(self):
        result = calc.percentile_rank({"a": 42})
        assert result["a"] == 0.5

    def test_ties_get_average_rank(self):
        result = calc.percentile_rank({"a": 10, "b": 10, "c": 20})
        assert result["a"] == result["b"]
        assert result["a"] < result["c"]


class TestComputeAllPercentiles:
    def test_empty_stocks_returns_empty_dict(self):
        """境界値: 空のユニバース(銘柄リストが空)ではエラーにならず空辞書を返す。"""
        assert calc.compute_all_percentiles([], ["pbr"]) == {}

    def test_multiple_fields(self):
        stocks = [
            {"ticker": "A", "pbr": 1.0, "roe": 0.1},
            {"ticker": "B", "pbr": 2.0, "roe": None},
        ]
        result = calc.compute_all_percentiles(stocks, ["pbr", "roe"])
        assert set(result.keys()) == {"A", "B"}
        assert result["A"]["pbr"] < result["B"]["pbr"]
        assert result["B"]["roe"] is None


class TestMetricValueForRanking:
    """T-04fix: pbr<=0・per_trailing<=0 は定義不能としてランキング/パーセンタイルから除外する。"""

    def test_negative_pbr_is_invalid(self):
        assert calc.metric_value_for_ranking("pbr", -621.3) is None

    def test_zero_pbr_is_invalid(self):
        assert calc.metric_value_for_ranking("pbr", 0.0) is None

    def test_positive_pbr_is_valid(self):
        assert calc.metric_value_for_ranking("pbr", 1.5) == 1.5

    def test_negative_per_is_invalid(self):
        assert calc.metric_value_for_ranking("per_trailing", -5.0) is None

    def test_negative_momentum_is_valid(self):
        """momentum/roe等の負値は正当な値としてそのまま通す。"""
        assert calc.metric_value_for_ranking("momentum_12_1", -0.3) == -0.3
        assert calc.metric_value_for_ranking("roe", -0.1) == -0.1

    def test_none_stays_none(self):
        assert calc.metric_value_for_ranking("pbr", None) is None


class TestComputeAllPercentilesExcludesInvalid:
    def test_negative_pbr_gets_null_percentile_and_excluded_from_calc(self):
        """T-04fix回帰: 負PBR銘柄はパーセンタイルがnullになり、他銘柄の百分位計算からも除外される。"""
        stocks = [
            {"ticker": "NEG", "pbr": -100.0},
            {"ticker": "A", "pbr": 1.0},
            {"ticker": "B", "pbr": 2.0},
        ]
        result = calc.compute_all_percentiles(stocks, ["pbr"])
        assert result["NEG"]["pbr"] is None
        # NEGが除外された2銘柄内での百分位(0.0 / 1.0)になる
        assert result["A"]["pbr"] == 0.0
        assert result["B"]["pbr"] == 1.0


class TestComputeMarginRatio:
    def test_normal(self):
        assert calc.compute_margin_ratio(13888200, 2006000) == 13888200 / 2006000

    def test_zero_sales_returns_none(self):
        """境界値: 信用売残ゼロ(踏み上げ相場等)でゼロ除算せずNoneを返す。"""
        assert calc.compute_margin_ratio(1000, 0) is None


class TestDetectMissingFields:
    def test_detects_none_fields(self):
        stock = {"per_trailing": None, "pbr": 1.5, "dividend_yield_pct": None, "roe": 0.1,
                  "trailing_eps": 10, "book_value_per_share": None, "momentum_12_1": 0.05}
        missing = calc.detect_missing_fields(stock)
        assert set(missing) == {"per_trailing", "dividend_yield_pct", "book_value_per_share"}

    def test_no_missing_fields(self):
        stock = {f: 1.0 for f in calc.DAILY_NULLABLE_FIELDS}
        assert calc.detect_missing_fields(stock) == []
