"""JPX週次信用取引データのパーサ(docs/07-data-schema.md 6節)。

データ源(T-03調査で確定済み):
  - 銘柄別: 「銘柄別信用取引週末残高」PDF(火曜16:30頃公表) https://www.jpx.co.jp/markets/statistics-equities/margin/05.html
  - 市場全体: 「信用取引現在高」Excel(水曜15:00頃公表) https://www.jpx.co.jp/markets/statistics-equities/margin/04.html

設計方針: パース関数(pure、テキスト/DataFrameを受け取る)とネットワーク取得関数を分離し、
パース関数を実PDF/Excelなしで単体テスト可能にする。

実測で確認したPDF行フォーマット(2026/7/3申込分、トヨタ7203.T=証券コード72030の実際の抽出行):
  "B トヨタ自動車 普通株式 72030 JP3633400001 2,171,500 ▲ 162,000 22,198,100 ▲ 1,555,400 " \
  "165,500 ▲ 11,800 2,006,000 ▲ 150,200 8,309,900 ▲ 189,900 13,888,200 ▲ 1,365,500"
数値は12個(6項目×[水準, 前週比]の組)で、順序は以下の通り(実データで検算済み):
  [合計信用売残, Δ, 合計信用買残, Δ, 一般信用売残, Δ, 制度信用売残, Δ, 一般信用買残, Δ, 制度信用買残, Δ]
前週比が負の場合は "▲" が独立トークンとして数値の直前に入る(正の場合は入らない)ため、
トークン数は行ごとに変動する。パース時に▲トークンを吸収してから偶数インデックス(水準)のみを使う。
"""
from __future__ import annotations

import re
import time
from typing import Optional

import requests

JPX_STOCK_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/margin/05.html"
JPX_MARKET_PAGE = "https://www.jpx.co.jp/markets/statistics-equities/margin/04.html"
JPX_BASE = "https://www.jpx.co.jp"

_UA = {"User-Agent": "Mozilla/5.0 (investsite-pipeline/1.0)"}

# 行内の証券コード(5桁)+ISIN(JP+10桁英数字)を検出する正規表現
_ROW_RE = re.compile(r"(?P<code>\d{5})\s+(?P<isin>[A-Z]{2}[A-Z0-9]{10})\s+(?P<rest>.+)$")


def _parse_number(token: str) -> int:
    return int(token.replace(",", ""))


def _split_signed_values(rest: str) -> list[int]:
    """"2,171,500 ▲ 162,000 22,198,100 ..." 形式のトークン列を、符号を吸収した数値リストに変換する。"""
    tokens = rest.split()
    values: list[int] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "▲":
            if i + 1 >= len(tokens):
                break
            values.append(-_parse_number(tokens[i + 1]))
            i += 2
        else:
            try:
                values.append(_parse_number(tok))
            except ValueError:
                # 数値化できないトークン(想定外フォーマット)は行全体を打ち切る
                break
            i += 1
    return values


def parse_margin_pdf_text(text: str, as_of_week: str) -> dict[str, dict]:
    """PDFの1ページ分(または複数ページ結合)のテキストから銘柄別信用残高を抽出する。

    戻り値: {"7203.T": {...docs/07-data-schema.md 2.3節のフィールド...}, ...}
    フォーマットに合致しない行は黙ってスキップする(85ページに及び見出し・空行等が混在するため)。
    """
    result: dict[str, dict] = {}
    for line in text.splitlines():
        m = _ROW_RE.search(line)
        if not m:
            continue
        code5 = m.group("code")
        rest = m.group("rest")
        values = _split_signed_values(rest)
        if len(values) < 11:
            # 6項目×2(水準+前週比)=12個に満たない場合はデータ行ではないとみなす
            continue
        total_sales, _d1, total_purchases, _d2, ippan_sales, _d3, seido_sales, _d4, \
            ippan_purchases, _d5, seido_purchases = values[:11]

        # 証券コードは5桁(末尾は市場区分等のチェック用桁)。yfinanceティッカーは先頭4桁+".T"
        ticker = f"{code5[:4]}.T"
        margin_ratio_seido = None
        if seido_sales:
            margin_ratio_seido = round(seido_purchases / seido_sales, 4)
        margin_ratio_total = None
        if total_sales:
            margin_ratio_total = round(total_purchases / total_sales, 4)

        result[ticker] = {
            "as_of_week": as_of_week,
            "outstanding_sales_shares": total_sales,
            "outstanding_purchases_shares": total_purchases,
            "seido_sales_shares": seido_sales,
            "seido_purchases_shares": seido_purchases,
            "ippan_sales_shares": ippan_sales,
            "ippan_purchases_shares": ippan_purchases,
            "margin_ratio_seido": margin_ratio_seido,
            "margin_ratio_total": margin_ratio_total,
            "source": JPX_STOCK_PAGE,
        }
    return result


def parse_market_total_excel(df) -> Optional[dict]:
    """「信用取引現在高」Excelから全国計の信用倍率を抽出する(pandas DataFrame, header=None想定)。

    実測フォーマット(2026/7/3申込分 mtseisan xls, シート1枚目):
      行(ラベル列に "全国計" を含む行)の "合計 Total" ブロックに [Sales, Δ, Purchases, Δ] があり、
      その2つの水準値(Sales, Purchases)から信用倍率を算出する。
    レイアウト変更に備え、ラベル文字列の部分一致で行を検索する(列インデックス固定に頼らない)。
    """
    import pandas as pd  # ローカルインポート(依存を軽量化)

    label_col_candidates = [1, 2]
    total_row_idx = None
    for ridx in range(len(df)):
        row = df.iloc[ridx]
        for c in label_col_candidates:
            if c >= len(row):
                continue
            cell = row[c]
            if isinstance(cell, str) and ("全国" in cell or "Total" in cell):
                total_row_idx = ridx
                break
        if total_row_idx is not None:
            break
    if total_row_idx is None:
        return None

    row = df.iloc[total_row_idx]
    numeric_vals = []
    for v in row:
        if isinstance(v, (int, float)) and not pd.isna(v):
            numeric_vals.append(v)
    # 実測レイアウト(mtseisan xls, 2026/7/3申込分で実測検証済み):
    # [顧客Sales, Δ顧客Sales, 顧客Purchases, Δ顧客Purchases,
    #  自己Sales, Δ自己Sales, 自己Purchases, Δ自己Purchases,
    #  合計Sales, Δ合計Sales, 合計Purchases, Δ合計Purchases]  (計12個)
    # 合計(全国計)のSales/Purchasesは「水準値」であり、各ブロックの末尾2組(Δを含む4個)の
    # 先頭2つ(Δではない方)に相当する = 末尾から4番目(Sales)・末尾から2番目(Purchases)
    if len(numeric_vals) < 4:
        return None
    total_purchases = numeric_vals[-2]
    total_sales = numeric_vals[-4]
    if not total_sales:
        return None
    ratio = round(total_purchases / total_sales, 4)
    return {
        "outstanding_sales_thousand_shares": total_sales,
        "outstanding_purchases_thousand_shares": total_purchases,
        "margin_ratio_national_total": ratio,
        "source": JPX_MARKET_PAGE,
    }


# --- ネットワークI/O(実PDF/Excel取得) ---


def select_latest_weekly_link(html: str, stem: str, ext_pattern: str) -> Optional[str]:
    """HTML中のhrefから、週次ファイル命名規則 {stem}YYYYMMDD….{ext} に合致するリンクのうち日付最大のものを返す。

    ページには週次データ以外のファイル(お知らせPDF等、例: t13vrt….pdf)も混在するため、
    命名規則でフィルタする(単純に「最後のリンク」を使うと無関係なPDFを掴む事故を実測で確認済み)。
    合致するリンクがなければNone。
    """
    links = re.findall(rf'href="([^"]*{stem}\d{{8}}[^"]*\.{ext_pattern})"', html)
    if not links:
        return None
    return max(links, key=lambda u: re.search(rf"{stem}(\d{{8}})", u).group(1))


def find_latest_pdf_url() -> Optional[str]:
    """JPX「銘柄別信用取引週末残高」ページから最新の週次PDF(syumatsuYYYYMMDD….pdf)URLを取得する。"""
    resp = requests.get(JPX_STOCK_PAGE, headers=_UA, timeout=30)
    resp.raise_for_status()
    link = select_latest_weekly_link(resp.text, "syumatsu", "pdf")
    return JPX_BASE + link if link else None


def find_latest_excel_url() -> Optional[str]:
    """JPX「信用取引現在高」ページから最新の週次Excel(mtseisanYYYYMMDD….xls)URLを取得する。"""
    resp = requests.get(JPX_MARKET_PAGE, headers=_UA, timeout=30)
    resp.raise_for_status()
    link = select_latest_weekly_link(resp.text, "mtseisan", "(?:xls|xlsx)")
    return JPX_BASE + link if link else None


def _extract_as_of_week(url: str) -> str:
    """ファイル名末尾のYYYYMMDD(申込基準日=前週金曜)からas_of_week文字列を組み立てる。"""
    m = re.search(r"(\d{4})(\d{2})(\d{2})\d*\.(?:pdf|xls)", url)
    if not m:
        return ""
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"


def fetch_stock_margin(max_retries: int = 3, backoff_base: float = 3.0) -> dict[str, dict]:
    """最新の銘柄別信用取引週末残高PDFを取得・パースして返す。

    85ページに及ぶPDF全体をpdfplumberでテキスト抽出するため数十秒かかる。429対策として
    リトライ(指数バックオフ)を入れる(CLAUDE.mdの「起動直後の429連鎖に注意」を踏襲)。
    """
    import pdfplumber
    import io

    url = find_latest_pdf_url()
    if not url:
        return {}
    as_of_week = _extract_as_of_week(url)

    content = None
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=_UA, timeout=60)
            resp.raise_for_status()
            content = resp.content
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_base ** attempt)
    if content is None:
        raise RuntimeError(f"銘柄別信用残高PDFの取得に失敗: {last_err}")

    result: dict[str, dict] = {}
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            result.update(parse_margin_pdf_text(text, as_of_week))
    return result


def fetch_market_total_margin(max_retries: int = 3, backoff_base: float = 3.0) -> Optional[dict]:
    """最新の市場全体信用取引現在高Excelを取得・パースして返す。"""
    import pandas as pd
    import io

    url = find_latest_excel_url()
    if not url:
        return None
    as_of_week = _extract_as_of_week(url)

    content = None
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=_UA, timeout=60)
            resp.raise_for_status()
            content = resp.content
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < max_retries:
                time.sleep(backoff_base ** attempt)
    if content is None:
        raise RuntimeError(f"市場全体信用取引現在高Excelの取得に失敗: {last_err}")

    df = pd.read_excel(io.BytesIO(content), header=None)
    parsed = parse_market_total_excel(df)
    if parsed is None:
        return None
    parsed["as_of_week"] = as_of_week
    return parsed
