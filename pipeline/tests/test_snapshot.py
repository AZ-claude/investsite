"""pipeline/metrics/snapshot.py の単体テスト。ネットワークI/Oなし(raw辞書を直接注入してテスト)。"""
from pipeline.metrics import snapshot


def _make_raw(**overrides):
    base = {
        "shortName": "テスト銘柄",
        "currentPrice": 100.0,
        "regularMarketPrice": 100.0,
        "trailingPE": 15.0,
        "priceToBook": 1.5,
        "marketCap": 1_000_000,
        "sharesOutstanding": 10_000,
        "dividendYield": 2.0,
        "returnOnEquity": 0.1,
        "trailingEps": 6.6,
        "bookValue": 66.6,
    }
    base.update(overrides)
    return base


class TestBuildStockRecord:
    def test_normal_stock_all_fields_present(self):
        full_history = [100.0 + i * 0.1 for i in range(300)]
        stock = snapshot.build_stock_record("TEST.T", "テスト銘柄", "JPY", _make_raw(), close_prices=full_history)
        assert stock["ticker"] == "TEST.T"
        assert stock["per_trailing"] == 15.0
        assert stock["pbr"] == 1.5
        assert stock["data_quality"]["missing_fields"] == []

    def test_zero_eps_boundary_no_crash(self):
        """境界値: EPS=0の銘柄(直近赤字化直後等)でtrailingPEも欠損の場合、ゼロ除算せずNoneになること。"""
        raw = _make_raw(trailingPE=None, trailingEps=0.0)
        stock = snapshot.build_stock_record("ZERO.T", "ゼロEPS銘柄", "JPY", raw, close_prices=None)
        assert stock["per_trailing"] is None
        assert "per_trailing" in stock["data_quality"]["missing_fields"]

    def test_missing_fields_propagate_as_null(self):
        """境界値: 欠損値(null)。フィールド自体は残しNoneのまま保持する。"""
        raw = _make_raw(trailingPE=None, priceToBook=None, dividendYield=None, returnOnEquity=None,
                         trailingEps=None, bookValue=None)
        stock = snapshot.build_stock_record("MISS.T", "欠損銘柄", "JPY", raw, close_prices=None)
        for f in ["per_trailing", "pbr", "dividend_yield_pct", "roe"]:
            assert stock[f] is None
        assert set(stock["data_quality"]["missing_fields"]) >= {
            "per_trailing", "pbr", "dividend_yield_pct", "roe", "trailing_eps", "book_value_per_share",
        }

    def test_recently_listed_stock_momentum_none(self):
        """境界値: 上場直後で株価履歴が12ヶ月未満の銘柄はmomentum_12_1がNoneになること。"""
        short_history = [100.0 + i * 0.1 for i in range(50)]  # 約2.5ヶ月分
        stock = snapshot.build_stock_record("NEW.T", "新規上場銘柄", "JPY", _make_raw(), close_prices=short_history)
        assert stock["momentum_12_1"] is None

    def test_market_cap_fallback_when_missing(self):
        raw = _make_raw(marketCap=None, sharesOutstanding=1000, currentPrice=50)
        stock = snapshot.build_stock_record("MC.T", "時価総額フォールバック銘柄", "JPY", raw, close_prices=None)
        assert stock["market_cap"] == 50000

    def test_margin_attached_only_when_provided(self):
        stock_with = snapshot.build_stock_record(
            "7203.T", "トヨタ自動車", "JPY", _make_raw(), close_prices=None,
            margin={"margin_ratio_seido": 6.9233},
        )
        assert "margin" in stock_with
        stock_without = snapshot.build_stock_record("6758.T", "ソニーG", "JPY", _make_raw(), close_prices=None)
        assert "margin" not in stock_without


class TestAttachPercentiles:
    def test_empty_universe_boundary(self):
        """境界値: 空のユニバース(銘柄0件)でも例外を出さない。"""
        stocks = []
        snapshot.attach_percentiles(stocks)
        assert stocks == []

    def test_single_stock_universe(self):
        stocks = [snapshot.build_stock_record("A.T", "A", "JPY", _make_raw(), close_prices=None)]
        snapshot.attach_percentiles(stocks)
        assert stocks[0]["percentile_in_universe"]["pbr"] == 0.5

    def test_percentile_direction_low_to_high(self):
        stocks = [
            snapshot.build_stock_record("LOW.T", "低PBR", "JPY", _make_raw(priceToBook=0.5), close_prices=None),
            snapshot.build_stock_record("HIGH.T", "高PBR", "JPY", _make_raw(priceToBook=3.0), close_prices=None),
        ]
        snapshot.attach_percentiles(stocks)
        low = next(s for s in stocks if s["ticker"] == "LOW.T")
        high = next(s for s in stocks if s["ticker"] == "HIGH.T")
        assert low["percentile_in_universe"]["pbr"] < high["percentile_in_universe"]["pbr"]


class TestBuildDailySnapshot:
    def test_empty_universe_returns_valid_shape(self):
        """境界値: 空のユニバース(該当市場の銘柄が1件も取得できなかった異常系)でもスキーマ形状は保つ。"""
        result = snapshot.build_daily_snapshot(
            market="jp", universe_name="NIKKEI225", tickers=[],
            fundamentals_by_ticker={}, price_history_by_ticker={}, currency="JPY",
        )
        assert result["stocks"] == []
        assert result["market"] == "jp"
        assert result["source"]["provider"] == "yfinance"
        assert "date" in result and "generated_at" in result

    def test_ticker_without_fundamentals_still_included_with_nulls(self):
        """欠損銘柄(fundamentals取得失敗)もstocksに含め、値はNoneのまま出力する方針の確認。"""
        result = snapshot.build_daily_snapshot(
            market="jp", universe_name="NIKKEI225",
            tickers=[{"ticker": "9999.T", "name": "取得失敗銘柄"}],
            fundamentals_by_ticker={}, price_history_by_ticker={}, currency="JPY",
        )
        assert len(result["stocks"]) == 1
        stock = result["stocks"][0]
        assert stock["ticker"] == "9999.T"
        assert stock["price"] is None
        assert stock["per_trailing"] is None

    def test_full_snapshot_schema_fields_present(self):
        tickers = [{"ticker": "7203.T", "name": "トヨタ自動車"}, {"ticker": "9984.T", "name": "SBG"}]
        fundamentals = {
            "7203.T": _make_raw(shortName="トヨタ自動車"),
            "9984.T": _make_raw(shortName="SBG", priceToBook=2.5),
        }
        result = snapshot.build_daily_snapshot(
            market="jp", universe_name="NIKKEI225", tickers=tickers,
            fundamentals_by_ticker=fundamentals, price_history_by_ticker={}, currency="JPY",
        )
        for top_key in ["date", "market", "universe", "generated_at", "source", "stocks"]:
            assert top_key in result
        for stock in result["stocks"]:
            for field in ["ticker", "name", "currency", "price", "market_cap", "shares_outstanding",
                          "per_trailing", "pbr", "dividend_yield_pct", "roe", "trailing_eps",
                          "book_value_per_share", "momentum_12_1", "percentile_in_universe", "data_quality"]:
                assert field in stock


class TestRoeMissingRate:
    def test_empty_universe_boundary(self):
        """境界値: 空のユニバース。"""
        result = snapshot.roe_missing_rate([])
        assert result == {"total": 0, "missing": 0, "missing_rate_pct": None}

    def test_computes_rate(self):
        stocks = [{"roe": 0.1}, {"roe": None}, {"roe": None}, {"roe": 0.05}]
        result = snapshot.roe_missing_rate(stocks)
        assert result["total"] == 4
        assert result["missing"] == 2
        assert result["missing_rate_pct"] == 50.0
