"""pipeline/metrics/margin_jpx.py の単体テスト。

実PDF/Excelファイルへの依存を避けるため、実測で確認した本物のテキスト/DataFrame構造を
そのままフィクスチャとして再現する(pipeline/spikes/out/ で実データ検証済みの値と一致させている)。
"""
import pandas as pd

from pipeline.metrics import margin_jpx


# 実測: JPX「銘柄別信用取引週末残高」2026/7/3申込分PDF 18ページ目、トヨタ(7203.T)の実際の抽出行
TOYOTA_LINE = (
    "B トヨタ自動車 普通株式 72030 JP3633400001 2,171,500 ▲ 162,000 22,198,100 ▲ 1,555,400 "
    "165,500 ▲ 11,800 2,006,000 ▲ 150,200 8,309,900 ▲ 189,900 13,888,200 ▲ 1,365,500"
)

# 前週比がすべて正(▲なし)の合成行(パーサがΔの符号有無両方を扱えることの確認用)
POSITIVE_DELTA_LINE = (
    "B テスト銘柄 普通株式 99990 JP0000000000 1,000 100 2,000 200 500 50 500 50 1,000 100 1,000 100"
)

# データ行ではない見出し行(コード列がないため無視されるべき)
HEADER_LINE = "銘柄 コード ISIN Code 信用売り 信用買い"


class TestParseMarginPdfText:
    def test_extracts_toyota_row_matching_documented_values(self):
        """docs/07-data-schema.md 6節に記載の実測値(トヨタ制度信用倍率≈6.92倍)と一致すること。"""
        result = margin_jpx.parse_margin_pdf_text(TOYOTA_LINE, as_of_week="2026-07-03")
        assert "7203.T" in result
        rec = result["7203.T"]
        assert rec["outstanding_sales_shares"] == 2171500
        assert rec["outstanding_purchases_shares"] == 22198100
        assert rec["seido_sales_shares"] == 2006000
        assert rec["seido_purchases_shares"] == 13888200
        assert rec["ippan_sales_shares"] == 165500
        assert rec["ippan_purchases_shares"] == 8309900
        assert abs(rec["margin_ratio_seido"] - 6.9233) < 0.001
        assert rec["as_of_week"] == "2026-07-03"

    def test_positive_delta_row_parses_correctly(self):
        """前週比がすべて正(▲トークンなし)でもトークン数のズレなく正しくパースできること。"""
        result = margin_jpx.parse_margin_pdf_text(POSITIVE_DELTA_LINE, as_of_week="2026-07-03")
        assert "9999.T" in result
        rec = result["9999.T"]
        assert rec["outstanding_sales_shares"] == 1000
        assert rec["outstanding_purchases_shares"] == 2000

    def test_header_line_ignored(self):
        result = margin_jpx.parse_margin_pdf_text(HEADER_LINE, as_of_week="2026-07-03")
        assert result == {}

    def test_empty_text_returns_empty_dict(self):
        """境界値: 空テキスト(PDFページ抽出失敗等)でエラーにならず空辞書を返す。"""
        assert margin_jpx.parse_margin_pdf_text("", as_of_week="2026-07-03") == {}

    def test_zero_sales_does_not_crash_ratio(self):
        """境界値: 信用売残ゼロの銘柄でゼロ除算せずmargin_ratio_seidoがNoneになること。"""
        line = "B ゼロ売残銘柄 普通株式 88880 JP1111111111 0 0 5,000 500 0 0 0 0 5,000 500 0 0"
        result = margin_jpx.parse_margin_pdf_text(line, as_of_week="2026-07-03")
        rec = result["8888.T"]
        assert rec["seido_sales_shares"] == 0
        assert rec["margin_ratio_seido"] is None


class TestSelectLatestWeeklyLink:
    """URL選択の回帰テスト: 実運用で「links[-1]が無関係なお知らせPDFを掴む」事故が発生したため、
    命名規則フィルタ+日付最大選択の挙動を固定する。"""

    HTML = (
        '<a href="/margin/att/syumatsu2026062600.pdf">6/26</a>'
        '<a href="/margin/att/syumatsu2026070300.pdf">7/3</a>'
        '<a href="/margin/att/t13vrt000000ci1v.pdf">お知らせ</a>'  # 実際に誤取得した無関係PDF
    )

    def test_picks_latest_weekly_pdf_not_notice(self):
        link = margin_jpx.select_latest_weekly_link(self.HTML, "syumatsu", "pdf")
        assert link == "/margin/att/syumatsu2026070300.pdf"

    def test_no_match_returns_none(self):
        assert margin_jpx.select_latest_weekly_link('<a href="/x/notice.pdf">n</a>', "syumatsu", "pdf") is None

    def test_excel_pattern(self):
        html = '<a href="/att/mtseisan2026062600.xls">a</a><a href="/att/mtseisan2026070300.xls">b</a>'
        link = margin_jpx.select_latest_weekly_link(html, "mtseisan", "(?:xls|xlsx)")
        assert link == "/att/mtseisan2026070300.xls"


class TestParseMarketTotalExcel:
    def _build_real_layout_df(self):
        """実測(mtseisan2026070300.xls)の行6を再現したDataFrame。"""
        rows = []
        # ダミーのヘッダ行(0〜5)
        for _ in range(6):
            rows.append([None] * 15)
        # 実測した「全国計」行(2026/7/3申込分、docs/07-data-schema.md 6節の9.8029倍と一致)
        rows.append(
            [None, "二市場計\nTotal", "株数Shs.", 281113, -89458, 3870000, -69461,
             113792, -14209, 1201, 90, 394905, -103667, 3871201, -69371]
        )
        return pd.DataFrame(rows)

    def test_extracts_national_total_ratio(self):
        df = self._build_real_layout_df()
        result = margin_jpx.parse_market_total_excel(df)
        assert result is not None
        assert result["outstanding_sales_thousand_shares"] == 394905
        assert result["outstanding_purchases_thousand_shares"] == 3871201
        assert abs(result["margin_ratio_national_total"] - 9.8029) < 0.001

    def test_missing_label_returns_none(self):
        """境界値: レイアウト変更等でラベル行が見つからない場合はNoneを返す(例外を出さない)。"""
        df = pd.DataFrame([[None, "無関係な行", None]] * 5)
        assert margin_jpx.parse_market_total_excel(df) is None

    def test_empty_dataframe_returns_none(self):
        """境界値: 空のDataFrame。"""
        assert margin_jpx.parse_market_total_excel(pd.DataFrame()) is None
