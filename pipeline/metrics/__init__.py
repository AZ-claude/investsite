"""T-04: 指標計算モジュール。

docs/07-data-schema.md をスキーマ契約として、生データ(yfinance/JPX)から
daily/{jp|us}.json 相当のオブジェクトを組み立てる。

サブモジュール:
  - calculations.py  … 個別指標の計算ロジック(純粋関数、ネットワーク不要)
  - margin_jpx.py     … JPX信用残高PDF/Excelパーサ(純粋パース関数 + 取得関数)
  - fetch_yfinance.py … yfinanceからの生データ取得(ネットワークI/O、429対策リトライ)
  - snapshot.py        … 上記を組み合わせてスキーマ準拠のdailyスナップショットを構築
"""
