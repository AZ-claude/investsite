"""yfinanceからの生データ取得(ネットワークI/O)。T-01/T-02スパイクのコードを流用。

429対策: CLAUDE.md「確認済みのハマりどころ」に基づき、
  - 個別銘柄の取得失敗は指数バックオフ(2秒→4秒→8秒、最大3回)でリトライ
  - セッション初期化直後の全滅パターン対策として、初回バッチ取得が閾値以上の失敗率を示した場合は
    30〜60秒待機してから全体を1回だけ再試行する(T-02実測の「起動直後429連鎖」対策)
"""
from __future__ import annotations

import io
import re
import time
import urllib.request
from dataclasses import dataclass, field

import pandas as pd
import requests
import yfinance as yf

NIKKEI225_CSV_URL = "https://indexes.nikkei.co.jp/nkave/archives/file/nikkei_stock_average_weight_en.csv"
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

FUNDAMENTAL_KEYS = [
    "shortName", "currentPrice", "regularMarketPrice", "trailingPE", "priceToBook",
    "marketCap", "sharesOutstanding", "dividendYield", "returnOnEquity",
    "trailingEps", "bookValue",
]

# 起動直後429連鎖の検知閾値: 初回バッチの失敗率がこれ以上なら「セッション初期化失敗」とみなす
STARTUP_FAILURE_RATE_THRESHOLD = 0.5
STARTUP_RETRY_WAIT_SEC = 45


def get_nikkei225_tickers() -> list[dict]:
    """日経平均プロフィル公式CSV(無料・登録不要)から日経225構成銘柄を取得する。

    CP932フォールバック(CLAUDE.mdのハマりどころ)。フッタ行(著作権注記等)は証券コードの
    パターン(4文字、先頭は数字、以降は数字または英大文字。例: 7203, 285A)に合致しないため除外される。
    """
    req = urllib.request.Request(NIKKEI225_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
    raw_bytes = urllib.request.urlopen(req, timeout=15).read()
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw = raw_bytes.decode("cp932")

    lines = raw.strip().splitlines()
    out = []
    for line in lines[1:]:
        parts = [p.strip('"') for p in line.split(",")]
        if len(parts) < 3:
            continue
        code = parts[1].strip()
        name = parts[2].strip()
        if not re.fullmatch(r"\d[\dA-Z]{3}", code):
            continue  # フッタ行(注記等)を除外。英字入りコード(285A等)は正規の構成銘柄なので通す
        out.append({"ticker": f"{code}.T", "name": name})
    return out


def get_sp500_tickers() -> list[dict]:
    """WikipediaのS&P500構成銘柄一覧をパースする。BRK.B等のピリオドはハイフンに置換。"""
    headers = {"User-Agent": "Mozilla/5.0 (investsite-pipeline/1.0)"}
    resp = requests.get(SP500_WIKI_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    out = []
    for _, r in df.iterrows():
        out.append({"ticker": r["Symbol"], "name": r.get("Security", r["Symbol"])})
    return out


@dataclass
class FetchResult:
    raw_by_ticker: dict = field(default_factory=dict)
    failed_tickers: list = field(default_factory=list)
    elapsed_sec: float = 0.0


def _fetch_one(ticker: str, max_retries: int, backoff_base: float) -> dict | None:
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price is None and info.get("marketCap") is None:
                raise ValueError("empty info payload")
            row = {k: info.get(k) for k in FUNDAMENTAL_KEYS}
            row["ticker"] = ticker
            return row
        except Exception as e:  # noqa: BLE001 - yfinanceは多様な例外を投げる
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_base ** attempt)
    return None


def fetch_fundamentals_bulk(
    tickers: list[str],
    max_retries: int = 3,
    backoff_base: float = 2.0,
    startup_retry: bool = True,
) -> FetchResult:
    """複数銘柄のファンダメンタルズ(価格・PER・PBR・時価総額等)を取得する。

    起動直後429連鎖対策: 全体の失敗率が STARTUP_FAILURE_RATE_THRESHOLD 以上だった場合、
    startup_retry=True なら STARTUP_RETRY_WAIT_SEC 秒待機して失敗銘柄のみ1回だけ再試行する。
    """
    t0 = time.time()
    result = FetchResult()
    for tkr in tickers:
        row = _fetch_one(tkr, max_retries, backoff_base)
        if row is None:
            result.failed_tickers.append(tkr)
        else:
            result.raw_by_ticker[tkr] = row

    if tickers and startup_retry:
        failure_rate = len(result.failed_tickers) / len(tickers)
        if failure_rate >= STARTUP_FAILURE_RATE_THRESHOLD:
            time.sleep(STARTUP_RETRY_WAIT_SEC)
            retry_targets = list(result.failed_tickers)
            result.failed_tickers = []
            for tkr in retry_targets:
                row = _fetch_one(tkr, max_retries, backoff_base)
                if row is None:
                    result.failed_tickers.append(tkr)
                else:
                    result.raw_by_ticker[tkr] = row

    result.elapsed_sec = time.time() - t0
    return result


def fetch_price_history_bulk(tickers: list[str], period: str = "14mo") -> dict[str, list[float]]:
    """モメンタム計算用の日次終値履歴をyf.downloadで一括取得する。

    戻り値: {ticker: [close, close, ...]}(日付昇順)。取得失敗銘柄はキー自体を含めない。
    """
    if not tickers:
        return {}
    data = yf.download(
        tickers, period=period, interval="1d", group_by="ticker",
        auto_adjust=True, threads=True, progress=False,
    )
    result: dict[str, list[float]] = {}
    if isinstance(data.columns, pd.MultiIndex):
        top_level = set(data.columns.get_level_values(0))
        for t in tickers:
            if t in top_level:
                try:
                    col = data[t]["Close"].dropna()
                    if len(col) > 0:
                        result[t] = col.tolist()
                except Exception:
                    pass
    else:
        if len(tickers) == 1:
            col = data.get("Close")
            if col is not None:
                col = col.dropna()
                if len(col) > 0:
                    result[tickers[0]] = col.tolist()
    return result
