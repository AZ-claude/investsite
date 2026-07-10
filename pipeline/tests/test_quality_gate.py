"""pipeline/metrics/quality_gate.py の単体テスト(T-05)。

品質ゲートの2条件(欠損率閾値、前日比異常値検知)と、境界値(空リスト、前日データなし)を確認する。
"""
from pipeline.metrics import quality_gate as qg


def make_stock(ticker, price=100.0, market_cap=1000.0, per_trailing=15.0):
    return {"ticker": ticker, "price": price, "market_cap": market_cap, "per_trailing": per_trailing}


class TestMissingRate:
    def test_no_missing(self):
        stocks = [make_stock("A"), make_stock("B")]
        assert qg.missing_rate(stocks, "price") == 0.0

    def test_all_missing(self):
        stocks = [make_stock("A", price=None), make_stock("B", price=None)]
        assert qg.missing_rate(stocks, "price") == 1.0

    def test_partial_missing(self):
        stocks = [make_stock("A", price=None), make_stock("B"), make_stock("C"), make_stock("D")]
        assert qg.missing_rate(stocks, "price") == 0.25

    def test_empty_list_returns_zero(self):
        """境界値: 銘柄0件は「異常なし」として扱う(0.0を返す)。"""
        assert qg.missing_rate([], "price") == 0.0


class TestMedianOf:
    def test_normal(self):
        stocks = [make_stock("A", per_trailing=10), make_stock("B", per_trailing=20), make_stock("C", per_trailing=30)]
        assert qg.median_of(stocks, "per_trailing") == 20

    def test_all_none_returns_none(self):
        stocks = [make_stock("A", per_trailing=None)]
        assert qg.median_of(stocks, "per_trailing") is None

    def test_empty_returns_none(self):
        assert qg.median_of([], "per_trailing") is None


class TestCheckMarket:
    def test_pass_normal(self):
        stocks = [make_stock(f"T{i}") for i in range(20)]
        result = qg.check_market("jp", stocks)
        assert result.passed is True
        assert result.reasons == []

    def test_fail_missing_rate_over_threshold(self):
        """欠損だらけのモック: price欠損率が閾値5%を超えたら異常。"""
        stocks = [make_stock(f"T{i}", price=None) for i in range(10)] + [make_stock("T10")]
        result = qg.check_market("jp", stocks, missing_threshold=0.05)
        assert result.passed is False
        assert any("price" in r for r in result.reasons)

    def test_missing_rate_at_threshold_boundary_passes(self):
        """境界値: 欠損率がちょうど閾値と同じ場合は「超過」ではないためPASS。"""
        stocks = [make_stock("T0", price=None)] + [make_stock(f"T{i}") for i in range(1, 20)]
        # 1/20 = 5% ちょうど
        result = qg.check_market("jp", stocks, missing_threshold=0.05)
        assert result.passed is True

    def test_pass_when_no_previous_day_data(self):
        """境界値: 前日データがない(初回実行)場合、前日比チェックはスキップされPASSする。"""
        stocks = [make_stock(f"T{i}", per_trailing=1000) for i in range(20)]  # 異常値でも前日比較対象がない
        result = qg.check_market("jp", stocks, prev_stocks=None)
        assert result.passed is True

    def test_fail_median_change_over_threshold(self):
        """前日比異常値検知: 中央値PERが前日比+30%超で異常。"""
        today = [make_stock(f"T{i}", per_trailing=20) for i in range(20)]
        prev = [make_stock(f"T{i}", per_trailing=10) for i in range(20)]  # 中央値10→20 = +100%
        result = qg.check_market("jp", today, prev_stocks=prev, median_change_threshold=0.30)
        assert result.passed is False
        assert any("中央値" in r for r in result.reasons)

    def test_pass_median_change_within_threshold(self):
        today = [make_stock(f"T{i}", per_trailing=12) for i in range(20)]
        prev = [make_stock(f"T{i}", per_trailing=10) for i in range(20)]  # +20%
        result = qg.check_market("jp", today, prev_stocks=prev, median_change_threshold=0.30)
        assert result.passed is True

    def test_prev_median_zero_does_not_crash(self):
        """境界値: 前日中央値が0(ゼロ除算対策)でも例外を出さない。"""
        today = [make_stock(f"T{i}", per_trailing=5) for i in range(5)]
        prev = [make_stock(f"T{i}", per_trailing=0) for i in range(5)]
        result = qg.check_market("jp", today, prev_stocks=prev)
        assert result.passed is True  # 前日比チェックはNoneガードでスキップされる
