"""T-04: 実データ1日分のスナップショット生成(検証用の一時実行スクリプト。T-05の本CLIではない)。

実行方法: python pipeline/spikes/t04_run_snapshot.py
出力: pipeline/spikes/out/t04_jp_snapshot.json, pipeline/spikes/out/t04_us_snapshot.json
      標準出力にROE欠損率・所要時間ログ
"""
import io
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pipeline.metrics import snapshot  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")


def main():
    t0 = time.time()
    print("=== JP(日経225)スナップショット生成開始 ===")
    jp = snapshot.build_jp_snapshot(fetch_margin=True)
    jp_elapsed = time.time() - t0
    print(f"JP完了: {jp_elapsed:.1f}秒, 銘柄数={len(jp['stocks'])}")
    jp_roe = snapshot.roe_missing_rate(jp["stocks"])
    print(f"JP ROE欠損率: {jp_roe}")
    margin_count = sum(1 for s in jp["stocks"] if "margin" in s)
    print(f"JP margin付与銘柄数: {margin_count}/{len(jp['stocks'])}")

    t1 = time.time()
    print("\n=== US(S&P500)スナップショット生成開始 ===")
    us = snapshot.build_us_snapshot()
    us_elapsed = time.time() - t1
    print(f"US完了: {us_elapsed:.1f}秒, 銘柄数={len(us['stocks'])}")
    us_roe = snapshot.roe_missing_rate(us["stocks"])
    print(f"US ROE欠損率: {us_roe}")

    with open(os.path.join(OUT_DIR, "t04_jp_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(jp, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUT_DIR, "t04_us_snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(us, f, ensure_ascii=False, indent=2)

    print(f"\n総所要時間: {time.time() - t0:.1f}秒")
    print("書き出し完了: pipeline/spikes/out/t04_{jp,us}_snapshot.json")


if __name__ == "__main__":
    main()
