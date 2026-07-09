"""
T-02 スパイク: S&P500全銘柄の無料データ取得(yfinance)の実測スクリプト。

目的:
  - S&P500構成銘柄リストの無料取得方法を確定する(Wikipediaパース)
  - yfinanceで全銘柄の 株価/PER/PBR/時価総額 を一括取得し、所要時間・失敗率を計測
  - リトライ戦略(待機+再試行)の効果を計測
  - モメンタム計算用の13ヶ月分日次終値の一括取得(yf.download バルク)を計測

再実行方法:
  python pipeline/spikes/t02_us_data.py --full          # 全銘柄(約503銘柄)で実測
  python pipeline/spikes/t02_us_data.py --limit 50       # 先頭50銘柄でパイロット実測

出力:
  - pipeline/spikes/out/sp500_tickers.csv        取得した構成銘柄リスト(キャッシュ)
  - pipeline/spikes/out/fundamentals_result.csv  銘柄別の取得結果(成功/失敗、値、試行回数)
  - pipeline/spikes/out/run_log.txt              実行ログ(タイムスタンプ付き)
  - 標準出力に集計サマリを表示(docs/06-spikes/T-02-us-data.md に転記する)

非スコープ: 指標計算ロジック、蓄積設計、日本株(T-01が担当)
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)
LOG_PATH = OUT_DIR / "run_log.txt"

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_sp500_tickers(use_cache: bool = True) -> list[str]:
    """WikipediaのS&P500構成銘柄一覧をパースしてティッカーリストを返す。

    再現可能性のため:
      1. requests + 明示的UAヘッダでHTML取得(pandas.read_htmlの直接URL読みはUA拒否されることがある)
      2. pandas.read_html でテーブルパース
      3. 結果をCSVにキャッシュ(次回以降はネットワーク不要)
    """
    cache_path = OUT_DIR / "sp500_tickers.csv"
    if use_cache and cache_path.exists():
        log(f"S&P500銘柄リストはキャッシュから読込: {cache_path}")
        df = pd.read_csv(cache_path)
        return df["Symbol"].tolist()

    log(f"Wikipediaから S&P500構成銘柄リストを取得: {WIKI_URL}")
    headers = {"User-Agent": "Mozilla/5.0 (investsite-spike/1.0)"}
    resp = requests.get(WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]  # 1つ目のテーブルが構成銘柄一覧
    # yfinanceのティッカー表記に合わせる(BRK.B -> BRK-B など、ピリオドをハイフンに置換)
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    df.to_csv(cache_path, index=False)
    log(f"取得完了: {len(df)}銘柄。キャッシュ保存: {cache_path}")
    return df["Symbol"].tolist()


@dataclass
class FetchStats:
    total: int = 0
    success: int = 0
    failed: int = 0
    retried_success: int = 0  # 1回目失敗し、リトライで成功した件数
    total_attempts: int = 0
    elapsed_sec: float = 0.0
    rows: list[dict] = field(default_factory=list)


def fetch_fundamentals(tickers: list[str], max_retries: int = 3, backoff_base: float = 2.0) -> FetchStats:
    """各銘柄の株価・PER・PBR・時価総額を Ticker.info で取得。

    リトライ戦略: 失敗時に backoff_base ** attempt 秒待機して再試行(最大 max_retries 回)。
    """
    stats = FetchStats(total=len(tickers))
    t0 = time.time()

    for i, ticker in enumerate(tickers, start=1):
        attempt = 0
        ok = False
        last_err = ""
        while attempt < max_retries and not ok:
            attempt += 1
            stats.total_attempts += 1
            try:
                info = yf.Ticker(ticker).info
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                per = info.get("trailingPE")
                pbr = info.get("priceToBook")
                mcap = info.get("marketCap")
                if price is None and mcap is None:
                    # 空データ(銘柄自体は存在するがフィールドが取れない)も失敗扱い
                    raise ValueError("empty info payload")
                stats.rows.append({
                    "ticker": ticker, "attempt": attempt, "price": price,
                    "per": per, "pbr": pbr, "market_cap": mcap, "status": "success",
                })
                ok = True
                stats.success += 1
                if attempt > 1:
                    stats.retried_success += 1
            except Exception as e:  # yfinanceは多様な例外(HTTPError, JSONDecodeError等)を投げるため広く捕捉
                last_err = f"{type(e).__name__}: {e}"
                if attempt < max_retries:
                    wait = backoff_base ** attempt
                    log(f"[{i}/{len(tickers)}] {ticker} 試行{attempt}失敗({last_err})。{wait:.1f}秒待機してリトライ")
                    time.sleep(wait)
        if not ok:
            stats.failed += 1
            stats.rows.append({
                "ticker": ticker, "attempt": attempt, "price": None,
                "per": None, "pbr": None, "market_cap": None,
                "status": "failed", "error": last_err,
            })
            log(f"[{i}/{len(tickers)}] {ticker} 最終失敗(試行{attempt}回): {last_err}")
        elif i % 25 == 0 or i == len(tickers):
            log(f"[{i}/{len(tickers)}] 進捗: 成功{stats.success} 失敗{stats.failed}")

    stats.elapsed_sec = time.time() - t0
    return stats


def fetch_price_history_bulk(tickers: list[str], period: str = "13mo") -> dict:
    """モメンタム計算用の日次終値履歴をyf.downloadで一括取得。"""
    t0 = time.time()
    log(f"yf.download で {len(tickers)}銘柄の{period}分の日次終値を一括取得開始")
    data = yf.download(
        tickers, period=period, interval="1d", group_by="ticker",
        auto_adjust=True, threads=True, progress=False,
    )
    elapsed = time.time() - t0

    # 銘柄ごとにClose列が全NaNでないかで成否判定
    got_tickers = set()
    if isinstance(data.columns, pd.MultiIndex):
        top_level = set(data.columns.get_level_values(0))
        for t in tickers:
            if t in top_level:
                try:
                    col = data[t]["Close"]
                    if col.notna().sum() > 0:
                        got_tickers.add(t)
                except Exception:
                    pass
    else:
        # 単一銘柄の場合はMultiIndexにならない
        if len(tickers) == 1 and data.get("Close") is not None and data["Close"].notna().sum() > 0:
            got_tickers.add(tickers[0])

    result = {
        "requested": len(tickers),
        "got": len(got_tickers),
        "missing": sorted(set(tickers) - got_tickers),
        "elapsed_sec": elapsed,
        "rows_per_ticker_sample": int(data.shape[0]) if not data.empty else 0,
    }
    log(f"yf.download 完了: {elapsed:.1f}秒, 成功{len(got_tickers)}/{len(tickers)}銘柄")
    return result


def main():
    parser = argparse.ArgumentParser(description="T-02: S&P500 yfinance一括取得スパイク")
    parser.add_argument("--limit", type=int, default=None, help="先頭N銘柄のみ実行(パイロット用)")
    parser.add_argument("--full", action="store_true", help="全銘柄で実行(--limitと排他)")
    parser.add_argument("--no-cache", action="store_true", help="Wikipediaのティッカーリストキャッシュを無視して再取得")
    parser.add_argument("--skip-history", action="store_true", help="株価履歴の一括取得をスキップ(高速確認用)")
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    # 実行のたびにログファイルを新規化
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    log("=== T-02 米国株データ取得スパイク 開始 ===")
    tickers = get_sp500_tickers(use_cache=not args.no_cache)
    log(f"S&P500構成銘柄数: {len(tickers)}")

    if args.limit:
        tickers = tickers[: args.limit]
        log(f"--limit指定によりパイロット実行: {len(tickers)}銘柄")
    elif not args.full:
        # デフォルトは安全のため小規模パイロット
        tickers = tickers[:20]
        log(f"デフォルト(--full/--limit未指定)によりパイロット実行: {len(tickers)}銘柄")

    # --- ファンダメンタルズ(株価/PER/PBR/時価総額) ---
    log(f"--- ファンダメンタルズ一括取得({len(tickers)}銘柄, max_retries={args.max_retries}) ---")
    fstats = fetch_fundamentals(tickers, max_retries=args.max_retries)

    result_csv = OUT_DIR / "fundamentals_result.csv"
    with open(result_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "attempt", "price", "per", "pbr", "market_cap", "status", "error"])
        writer.writeheader()
        for row in fstats.rows:
            row.setdefault("error", "")
            writer.writerow(row)

    log("=== ファンダメンタルズ取得 結果サマリ ===")
    log(f"対象銘柄数: {fstats.total}")
    log(f"成功: {fstats.success} ({fstats.success/fstats.total*100:.1f}%)")
    log(f"失敗(最終): {fstats.failed} ({fstats.failed/fstats.total*100:.1f}%)")
    log(f"リトライで救済された件数: {fstats.retried_success}")
    log(f"総リクエスト試行回数: {fstats.total_attempts}(平均 {fstats.total_attempts/fstats.total:.2f}回/銘柄)")
    log(f"所要時間: {fstats.elapsed_sec:.1f}秒({fstats.elapsed_sec/fstats.total:.2f}秒/銘柄)")
    log(f"結果CSV: {result_csv}")

    # --- 株価履歴一括取得(モメンタム用) ---
    if not args.skip_history:
        log(f"--- 株価履歴一括取得({len(tickers)}銘柄, 13ヶ月分) ---")
        hstats = fetch_price_history_bulk(tickers, period="13mo")
        log("=== 株価履歴一括取得 結果サマリ ===")
        log(f"リクエスト銘柄数: {hstats['requested']}")
        log(f"取得成功銘柄数: {hstats['got']} ({hstats['got']/hstats['requested']*100:.1f}%)")
        log(f"取得失敗銘柄: {hstats['missing'][:20]}{'...' if len(hstats['missing']) > 20 else ''}")
        log(f"所要時間: {hstats['elapsed_sec']:.1f}秒")
        log(f"1回のyf.download呼び出しあたり行数(最新側の日数x銘柄MultiIndex分): {hstats['rows_per_ticker_sample']}")

    log("=== T-02 スパイク 終了 ===")


if __name__ == "__main__":
    main()
