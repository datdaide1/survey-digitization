#!/usr/bin/env python3
"""Task 6 — Tầng dữ liệu an toàn cho thống kê.

Đọc data/manifest.csv + output/full/*.json (85 phiếu), với mỗi phiếu:
- Bỏ Q1 (PII) -> ghi output/stats/<record_id>.json (85 file, README §4 lớp `stats`).
- Nổ multi-select/matrix + áp công thức stats_bucketing (Q2/Q5/Q6/Q9) -> 1 dòng
  output/combined.csv (bảng phẳng dùng cho mọi tầng thống kê, xem
  docs/implement-plan-statistics-and-client-report.md §1).

LƯU Ý: script này chạy được ngay cả khi dữ liệu CHƯA sạch 100% needs_review — in cảnh
báo số field còn needs_review theo từng phiếu, không chặn build (đúng quyết định đã
thống nhất: khách muốn xem bản trực quan trước, review dữ liệu xong sau sẽ chạy lại
script này để cập nhật — pipeline reproducible, không cần làm lại từ đầu).

Chạy:
  python scripts/build_stats_layer.py
  python scripts/build_stats_layer.py `
    --manifest data/manifest.csv --full-dir output/full `
    --stats-out-dir output/stats --combined-out output/combined.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.flatten import flatten_stats  # noqa: E402
from lib.pii import to_stats_record  # noqa: E402
from lib.records import (  # noqa: E402
    count_needs_review,
    has_been_reviewed,
    iter_full_records,
    load_manifest,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def run(manifest_path: str, full_dir: str, stats_out_dir: str, combined_out: str):
    """Trả về (rows, review_counts) — rows dùng cho combined.csv, review_counts để in cảnh báo."""
    manifest = load_manifest(manifest_path)
    stats_out = Path(stats_out_dir)
    stats_out.mkdir(parents=True, exist_ok=True)

    rows = []
    # Chỉ đếm needs_review "còn treo thật sự" ở phiếu CHƯA qua Review UI (không .bak).
    # Phiếu đã review vẫn có thể còn cờ needs_review trong `flags` nhưng đó là dấu vết
    # audit đã có quyết định (docs/review-summary-report.md §1), không tính vào đây.
    pending_review_counts: dict[str, int] = {}
    for record in iter_full_records(full_dir):
        record_id = record["record_id"]
        if record_id not in manifest:
            raise ValueError(f"{record_id}: không có trong {manifest_path}")

        if not has_been_reviewed(full_dir, record_id):
            pending_review_counts[record_id] = count_needs_review(record)

        stats_record = to_stats_record(record)
        with open(stats_out / f"{record_id}.json", "w", encoding="utf-8") as f:
            json.dump(stats_record, f, ensure_ascii=False, indent=2)

        rows.append(flatten_stats(record, manifest[record_id]))

    rows.sort(key=lambda r: r["record_id"])

    import pandas as pd

    df = pd.DataFrame(rows)
    Path(combined_out).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(combined_out, index=False, encoding="utf-8-sig")

    return df, pending_review_counts


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="data/manifest.csv")
    ap.add_argument("--full-dir", default="output/full")
    ap.add_argument("--stats-out-dir", default="output/stats")
    ap.add_argument("--combined-out", default="output/combined.csv")
    args = ap.parse_args()

    df, pending_review_counts = run(args.manifest, args.full_dir, args.stats_out_dir, args.combined_out)

    not_reviewed_records = len(pending_review_counts)
    total_pending_fields = sum(pending_review_counts.values())

    print(f"OK: {len(df)} phiếu -> {args.combined_out} ({len(df.columns)} cột)")
    print(f"OK: {len(df)} file ẩn danh -> {args.stats_out_dir}/")
    if not_reviewed_records:
        print(
            f"\n!! CẢNH BÁO: {not_reviewed_records}/{len(df)} phiếu CHƯA qua Review UI "
            f"(không có .bak), còn {total_pending_fields} field needs_review thật sự "
            "chưa xử lý (xem docs/review-summary-report.md). Build vẫn chạy theo yêu "
            "cầu khách — chạy lại script này sau khi review xong để cập nhật số liệu."
        )
    else:
        print("\nOK: 85/85 phiếu đã qua Review UI.")

    sys.exit(0)


if __name__ == "__main__":
    main()
