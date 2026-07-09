"""
T-01: 日本株の無料データ取得スパイク検証スクリプト

目的: 「日本株の"本日の"PBR/PER/時価総額/株価が無料で取れるか」を実測する。
実行方法: python pipeline/spikes/t01_jp_data.py
出力: 標準出力にログ。docs/06-spikes/T-01-jp-data.md に要約結果を転記している(このスクリプトは生成しない)。

非スコープ: 指標計算ロジック、蓄積設計。ここではあくまで取得可否・欠損率・所要時間の実測のみ。
"""

import time
import urllib.request
import sys
import io
from datetime import datetime, timezone, timedelta

import yfinance as yf

# Windows環境でのコンソール/リダイレクト時の文字化け対策(常にUTF-8で出力する)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

JST = timezone(timedelta(hours=9))

# --- 検証1: yfinance で10銘柄の Tier1 指標取得 ---
SAMPLE_TICKERS = [
    "7203.T",  # トヨタ自動車
    "9984.T",  # ソフトバンクグループ
    "6758.T",  # ソニーグループ
    "8306.T",  # 三菱UFJフィナンシャル・グループ
    "9432.T",  # NTT
    "6501.T",  # 日立製作所
    "8035.T",  # 東京エレクトロン
    "4063.T",  # 信越化学工業
    "9433.T",  # KDDI
    "6098.T",  # リクルートホールディングス
]

# Yahoo!ファイナンス(finance.yahoo.co.jp)の画面表示値と突合する3銘柄(手動確認用の参照値)
# 突合は別途ブラウザで finance.yahoo.co.jp の当該銘柄ページを開き、
# 本スクリプトの出力値(株価・PER・PBR・時価総額)と目視比較する。
CROSS_CHECK_TICKERS = ["7203.T", "9984.T", "6758.T"]

TIER1_FIELDS = ["price", "trailingPE", "priceToBook", "marketCap"]


def fetch_tier1(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.fast_info  # 高速版(価格・時価総額系)
    slow_info = {}
    try:
        slow_info = t.info  # PER/PBR等はslow info(scraped)側
    except Exception as e:
        print(f"  [WARN] {ticker}: .info 取得失敗: {e}")

    result = {
        "ticker": ticker,
        "price": None,
        "trailingPE": None,
        "priceToBook": None,
        "marketCap": None,
        "lastPriceTime": None,
    }
    try:
        result["price"] = info.last_price
    except Exception:
        pass
    try:
        result["marketCap"] = info.market_cap
    except Exception:
        pass
    result["trailingPE"] = slow_info.get("trailingPE")
    result["priceToBook"] = slow_info.get("priceToBook")
    # marketCap を info.info からも二重チェック(fast_infoが欠損する場合のフォールバック)
    if result["marketCap"] is None:
        result["marketCap"] = slow_info.get("marketCap")
    return result


def verify_price_history(ticker: str) -> dict:
    """12-1ヶ月モメンタム計算に使う株価履歴(13ヶ月分)が取れるかを検証する"""
    t = yf.Ticker(ticker)
    hist = t.history(period="14mo", interval="1d")
    return {
        "ticker": ticker,
        "rows": len(hist),
        "first_date": str(hist.index.min()) if len(hist) else None,
        "last_date": str(hist.index.max()) if len(hist) else None,
    }


def section1_sample_tickers():
    print("=" * 70)
    print("検証1: yfinance で東証10銘柄の Tier1 指標取得")
    print("=" * 70)
    results = []
    missing_count = {f: 0 for f in TIER1_FIELDS}
    t0 = time.time()
    for tkr in SAMPLE_TICKERS:
        try:
            r = fetch_tier1(tkr)
        except Exception as e:
            print(f"  [ERROR] {tkr}: 取得失敗 {e}")
            r = {"ticker": tkr, "price": None, "trailingPE": None, "priceToBook": None, "marketCap": None}
        results.append(r)
        for f in TIER1_FIELDS:
            if r.get(f) is None:
                missing_count[f] += 1
        print(f"  {tkr}: price={r.get('price')} trailingPE={r.get('trailingPE')} "
              f"priceToBook={r.get('priceToBook')} marketCap={r.get('marketCap')}")
    elapsed = time.time() - t0
    n = len(SAMPLE_TICKERS)
    print(f"\n所要時間: {elapsed:.1f}秒 ({n}銘柄)")
    print("欠損率:")
    for f in TIER1_FIELDS:
        print(f"  {f}: {missing_count[f]}/{n} ({missing_count[f]/n*100:.0f}%)")

    print(f"\n--- モメンタム用株価履歴(14ヶ月) 突合対象3銘柄含む全10銘柄で検証 ---")
    for tkr in SAMPLE_TICKERS:
        try:
            h = verify_price_history(tkr)
            print(f"  {tkr}: rows={h['rows']} range=[{h['first_date']} .. {h['last_date']}]")
        except Exception as e:
            print(f"  [ERROR] {tkr}: 履歴取得失敗 {e}")

    print(f"\n--- Yahoo!ファイナンス(finance.yahoo.co.jp)突合用の参照値(手動確認) ---")
    for tkr in CROSS_CHECK_TICKERS:
        r = next(x for x in results if x["ticker"] == tkr)
        print(f"  {tkr}: yfinance price={r.get('price')} PER={r.get('trailingPE')} "
              f"PBR={r.get('priceToBook')} 時価総額={r.get('marketCap')}")
    return results, missing_count, elapsed


def section2_jquants_note():
    print("\n" + "=" * 70)
    print("検証2: J-Quants API 無料プラン仕様(公式ドキュメント確認、実測未)")
    print("=" * 70)
    print("""
出典: https://jpx-jquants.com/ja (J-Quants公式サイト, 2026-07-10時点確認)
      https://www.jpx.co.jp/corporate/news/news-releases/6020/20250505-01.html (JPX公式ニュースリリース)

Freeplan の内容(公式表記そのまま):
  - 取得可能過去データ: 直近12週間を除く2年間
  - APIコール制限: 5件/分
  - CSVダウンロード: 不可
  - データ種別: 上場銘柄一覧 / 株価四本値(日通し) / 財務情報(サマリーのみ) / 決算発表予定日 / 取引カレンダー
  - TOPIX四本値・指数四本値・信用取引データ等は Free プラン対象外(Light以上)

FAQ抜粋(公式):
  Q. 無料プランでは当日の株価を取得できないのでしょうか？
  A. できません。無料プランではデータは12週間遅延して配信されます。

結論: 「本日の」指標という完了条件に対し、J-Quants Freeプランは12週間遅延のため
      構造的に不成立。登録・APIキー発行が必要なため本スクリプトでの実測(API呼び出し)は
      行っていない(ドキュメント確認のみ、実測未)。
      また財務情報はサマリーのみでPER/PBRの元となるEPS/BPSが直接提供されるかは
      未確認(実測できないため)。株価が12週遅延する時点で「本日の」指標としては使えない。
""")


def section3_nikkei225_bulk():
    print("=" * 70)
    print("検証3: 日経225構成銘柄リストの無料取得 + 全銘柄一括取得")
    print("=" * 70)

    # 3-1. 日経225構成銘柄リストの無料取得元
    # 出典: 日経平均プロフィル(公式) の Weight CSV (無料・登録不要でダウンロード可能)
    csv_url = "https://indexes.nikkei.co.jp/nkave/archives/file/nikkei_stock_average_weight_en.csv"
    print(f"\n3-1. 日経225構成銘柄リスト取得元: {csv_url}")
    try:
        req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
        raw_bytes = urllib.request.urlopen(req, timeout=15).read()
        try:
            raw = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw = raw_bytes.decode("cp932")  # 日経公式CSVはShift-JIS系エンコーディング
    except Exception as e:
        print(f"  [ERROR] CSV取得失敗: {e}")
        return

    lines = raw.strip().splitlines()
    header = lines[0]
    print(f"  ヘッダ: {header}")
    codes = []
    for line in lines[1:]:
        # "2026/06/30","1332","NISSUI CORP.",... の形式
        parts = [p.strip('"') for p in line.split(",")]
        if len(parts) >= 2:
            codes.append(parts[1])
    print(f"  取得銘柄数: {len(codes)}")
    if len(codes) != 225:
        print(f"  [注意] 225銘柄ちょうどではない(想定外のフォーマット変更の可能性)")

    tickers = [f"{c}.T" for c in codes]

    # 3-2. 全銘柄一括取得(Tier1指標)の所要時間・失敗率・レート制限挙動
    print(f"\n3-2. 日経225全{len(tickers)}銘柄の一括取得(yfinance)")
    t0 = time.time()
    success = 0
    fail = 0
    fail_tickers = []
    missing_field_count = {f: 0 for f in TIER1_FIELDS}
    rate_limited = False

    # yfinance の Tickers 一括ダウンロード API を使用(内部でスレッド並列)
    try:
        data = yf.Tickers(" ".join(tickers))
    except Exception as e:
        print(f"  [ERROR] Tickers初期化失敗: {e}")
        data = None

    for i, tkr in enumerate(tickers):
        try:
            sub = data.tickers[tkr] if data else yf.Ticker(tkr)
            fi = sub.fast_info
            price = None
            mcap = None
            try:
                price = fi.last_price
            except Exception:
                pass
            try:
                mcap = fi.market_cap
            except Exception:
                pass
            pe = None
            pb = None
            try:
                info = sub.info
                pe = info.get("trailingPE")
                pb = info.get("priceToBook")
                if mcap is None:
                    mcap = info.get("marketCap")
            except Exception as e:
                msg = str(e).lower()
                if "rate" in msg or "429" in msg or "too many" in msg:
                    rate_limited = True

            if price is None and mcap is None:
                fail += 1
                fail_tickers.append(tkr)
            else:
                success += 1
            for fname, val in [("price", price), ("trailingPE", pe), ("priceToBook", pb), ("marketCap", mcap)]:
                if val is None:
                    missing_field_count[fname] += 1
        except Exception as e:
            fail += 1
            fail_tickers.append(tkr)
            msg = str(e).lower()
            if "rate" in msg or "429" in msg or "too many" in msg:
                rate_limited = True

        if (i + 1) % 50 == 0:
            elapsed_so_far = time.time() - t0
            print(f"    {i+1}/{len(tickers)} 処理済み ({elapsed_so_far:.1f}秒経過, "
                  f"成功{success} 失敗{fail})")

    elapsed = time.time() - t0
    n = len(tickers)
    print(f"\n  所要時間: {elapsed:.1f}秒 ({n}銘柄, 平均{elapsed/n:.2f}秒/銘柄)")
    print(f"  成功: {success}/{n} ({success/n*100:.1f}%)")
    print(f"  失敗: {fail}/{n} ({fail/n*100:.1f}%)")
    print(f"  レート制限の兆候(429等): {'あり' if rate_limited else '観測されず'}")
    print("  欠損率(取得成功分含む全体に対して):")
    for f in TIER1_FIELDS:
        print(f"    {f}: {missing_field_count[f]}/{n} ({missing_field_count[f]/n*100:.1f}%)")
    if fail_tickers:
        print(f"  失敗銘柄(先頭10件): {fail_tickers[:10]}")


if __name__ == "__main__":
    print(f"実行日時(JST): {datetime.now(JST).isoformat()}")
    print(f"yfinance version: {yf.__version__}\n")

    section2_jquants_note()
    section1_sample_tickers()
    section3_nikkei225_bulk()

    print("\n" + "=" * 70)
    print("検証完了")
    print("=" * 70)
