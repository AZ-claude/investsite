# pipeline/

investsite のデータパイプライン(Python)。yfinance / J-Quants API 無料枠から取得した
株価・指標データを整形し、`data/` 配下に JSON として出力する。

- `pipeline/spikes/` — データ取得スパイク検証スクリプト(T-01, T-02)
- `pipeline/metrics/` — 指標計算モジュール(T-04)
- `pipeline/tests/` — 単体テスト(T-04)
- `pipeline/daily.py` — 日次実行エントリポイント(T-05)

サイト本体(Astro)は `site/` を参照。
