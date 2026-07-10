"""pipeline/daily.py の統合テスト(T-05)。実ネットワークは使わず fetch_* を差し替えて検証する。

正常系(2日分の冪等な蓄積)と異常系(壊しテスト: 欠損だらけ/前日比異常データを注入して
品質ゲートが実際に弾く=非ゼロ終了+書き込みなしを実証)の両方をカバーする。
"""
import json
import os

import pytest

from pipeline import daily


def make_snapshot(date, n=20, price=100.0, market_cap=1000.0, per_trailing=15.0, missing_price_count=0):
    stocks = []
    for i in range(n):
        p = None if i < missing_price_count else price
        stocks.append({
            "ticker": f"T{i}",
            "name": f"Stock {i}",
            "currency": "JPY",
            "price": p,
            "market_cap": None if i < missing_price_count else market_cap,
            "per_trailing": per_trailing,
            "pbr": 1.5,
            "dividend_yield_pct": 2.0,
            "roe": 0.1,
            "momentum_12_1": 0.05,
        })
    return {
        "date": date,
        "market": "jp",
        "universe": "NIKKEI225",
        "generated_at": f"{date}T18:00:00+09:00",
        "source": {"provider": "yfinance", "library_version": "1.5.1", "note": "test"},
        "stocks": stocks,
    }


@pytest.fixture
def data_dir(tmp_path):
    return str(tmp_path / "data")


class TestNormalRun:
    def test_first_run_writes_files_and_exits_zero(self, data_dir):
        snap = make_snapshot("2026-07-09")
        code = daily.run(
            date="2026-07-09", markets=("jp",), data_dir=data_dir,
            fetch_jp=lambda: snap, skip_thermometer=True,
        )
        assert code == 0
        daily_path = os.path.join(data_dir, "daily", "2026-07-09", "jp.json")
        assert os.path.exists(daily_path)
        with open(daily_path, encoding="utf-8") as f:
            written = json.load(f)
        assert written["date"] == "2026-07-09"
        assert len(written["stocks"]) == 20

        value_path = os.path.join(data_dir, "factors", "value.json")
        assert os.path.exists(value_path)
        log_path = os.path.join(data_dir, "logs", "2026-07-09.log")
        assert os.path.exists(log_path)

    def test_rerun_same_date_is_idempotent(self, data_dir):
        """同一日付の再実行は上書き(冪等)であること。"""
        snap = make_snapshot("2026-07-09")
        daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: snap, skip_thermometer=True)
        code2 = daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: snap, skip_thermometer=True)
        assert code2 == 0

        value_path = os.path.join(data_dir, "factors", "value.json")
        with open(value_path, encoding="utf-8") as f:
            value_json = json.load(f)
        # 同日を2回実行してもhistoryは1件のまま(重複追記されない)
        assert len(value_json["history"]) == 1

    def test_two_dates_accumulate(self, data_dir):
        """2日分の擬似実行で daily/ が2ディレクトリ、factors/history が2件に蓄積されること。"""
        snap1 = make_snapshot("2026-07-09")
        snap2 = make_snapshot("2026-07-10")
        code1 = daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: snap1, skip_thermometer=True)
        code2 = daily.run(date="2026-07-10", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: snap2, skip_thermometer=True)
        assert code1 == 0
        assert code2 == 0
        assert os.path.exists(os.path.join(data_dir, "daily", "2026-07-09", "jp.json"))
        assert os.path.exists(os.path.join(data_dir, "daily", "2026-07-10", "jp.json"))

        value_path = os.path.join(data_dir, "factors", "value.json")
        with open(value_path, encoding="utf-8") as f:
            value_json = json.load(f)
        assert [h["date"] for h in value_json["history"]] == ["2026-07-09", "2026-07-10"]


class TestBreakingTests:
    """壊しテスト: 意図的な異常データ注入で品質ゲートが実際に弾くことを検証する。"""

    def test_missing_data_blocks_write_and_exits_nonzero(self, data_dir):
        broken = make_snapshot("2026-07-09", n=20, missing_price_count=10)  # 50%欠損
        code = daily.run(
            date="2026-07-09", markets=("jp",), data_dir=data_dir,
            fetch_jp=lambda: broken, skip_thermometer=True,
        )
        assert code == 1
        assert not os.path.exists(os.path.join(data_dir, "daily", "2026-07-09", "jp.json"))
        assert not os.path.exists(os.path.join(data_dir, "factors", "value.json"))

    def test_previous_day_data_preserved_after_gate_failure(self, data_dir):
        """異常検知時に前日データが維持される(安全側)ことを確認する。"""
        good = make_snapshot("2026-07-09")
        code1 = daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: good, skip_thermometer=True)
        assert code1 == 0

        broken = make_snapshot("2026-07-10", n=20, missing_price_count=10)
        code2 = daily.run(date="2026-07-10", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: broken, skip_thermometer=True)
        assert code2 == 1

        # 前日(07-09)分は消えておらず、07-10分は書き込まれていない
        assert os.path.exists(os.path.join(data_dir, "daily", "2026-07-09", "jp.json"))
        assert not os.path.exists(os.path.join(data_dir, "daily", "2026-07-10", "jp.json"))

    def test_median_change_anomaly_blocks_write(self, data_dir):
        """前日比異常値検知: 中央値PERが前日比+30%超で異常終了すること。"""
        prev = make_snapshot("2026-07-09", per_trailing=10.0)
        code1 = daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: prev, skip_thermometer=True)
        assert code1 == 0

        anomaly = make_snapshot("2026-07-10", per_trailing=25.0)  # 10 -> 25 = +150%
        code2 = daily.run(date="2026-07-10", markets=("jp",), data_dir=data_dir, fetch_jp=lambda: anomaly, skip_thermometer=True)
        assert code2 == 1
        assert not os.path.exists(os.path.join(data_dir, "daily", "2026-07-10", "jp.json"))

    def test_fetch_failure_exits_with_code_2(self, data_dir):
        def failing_fetch():
            raise RuntimeError("network down")

        code = daily.run(date="2026-07-09", markets=("jp",), data_dir=data_dir, fetch_jp=failing_fetch, skip_thermometer=True)
        assert code == 2
        assert not os.path.exists(os.path.join(data_dir, "daily", "2026-07-09"))


class TestCliArgParsing:
    def test_main_with_mock_files(self, data_dir, tmp_path):
        snap = make_snapshot("2026-07-09")
        mock_path = tmp_path / "mock_jp.json"
        mock_path.write_text(json.dumps(snap), encoding="utf-8")

        code = daily.main([
            "--date", "2026-07-09",
            "--markets", "jp",
            "--data-dir", data_dir,
            "--mock-jp", str(mock_path),
        ])
        assert code == 0
        assert os.path.exists(os.path.join(data_dir, "daily", "2026-07-09", "jp.json"))
