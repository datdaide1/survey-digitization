#!/usr/bin/env python3
"""Task 2 — Ingest & Assembly.

Đọc data/manifest.csv, với mỗi phiếu: tìm file nguồn duy nhất trong
data/raw/khao-sat/<province>/<commune>/<record_id>.<ext> (1 ảnh hoặc 1 PDF nhiều
trang đã là 1 phiếu đầy đủ — không còn quy ước folder nhiều file rời, chốt
22/07/2026 khi toàn bộ data thật, kể cả phiếu mẫu, đã về dạng 1 file/phiếu) —
render PDF thành ảnh, kiểm tra toàn vẹn (đủ/thiếu/thừa/hỏng trang), xuất assembly
record vào output/assembly/<record_id>.json.

KHÔNG dùng VLM, KHÔNG suy đoán thứ tự trang thật theo nội dung — đó là việc của Task 3.
Xem docs/implement-plan-02-ingest-assembly.md.

Chạy:
  python scripts/ingest.py
  python scripts/ingest.py --manifest data/manifest.csv --raw-root data/raw/khao-sat --out-dir output/assembly
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.assembly import ACCEPTED_EXTS, build_assembly  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Giá trị từ manifest được ghép vào đường dẫn file — chỉ cho phép slug an toàn để
# chặn path traversal (vd province = '..\\..\\Windows'). Khớp mọi mã/slug hợp lệ hiện có.
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")


def _safe_segment(value, field):
    """Kiểm một đoạn path từ manifest; ném ValueError nếu chứa ký tự lạ (/, \\, .., …)."""
    if not (value and SAFE_SEGMENT.match(value)):
        raise ValueError(f"{field} không hợp lệ (chỉ cho phép chữ/số/_/-): {value!r}")
    return value


def _safe_filename(record_id):
    """Tên file output an toàn — thay ký tự lạ để không thoát thư mục, kể cả với record_id hỏng."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", record_id) or "unknown"


def read_manifest(manifest_path):
    with open(manifest_path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _resolve_source(base, record_id):
    """Tìm file nguồn duy nhất của 1 phiếu dưới <province>/<commune>/.

    Quy ước (chốt 22/07/2026): đúng 1 file `<record_id>.<ext>` — không còn quy ước
    folder dự phòng cho nhiều file rời. Nếu không tìm thấy, trả về đường dẫn giả định
    `<record_id>.pdf` (không tồn tại) để build_assembly() tự báo `source_not_found`.
    """
    matches = sorted(
        p for p in base.glob(f"{record_id}.*")
        if p.is_file() and p.suffix.lower() in ACCEPTED_EXTS
    )
    if matches:
        return matches[0]
    return base / f"{record_id}.pdf"


def process_record(row, raw_root, render_root):
    record_id = _safe_segment(row["record_id"], "record_id")
    province = _safe_segment(row["province"], "province")
    commune = _safe_segment(row["commune"], "commune")
    base = Path(raw_root) / province / commune
    source = _resolve_source(base, record_id)
    expected = int(row["num_pages"])
    render_dir = Path(render_root) / "_render" / record_id
    return build_assembly(record_id, source, expected, render_dir)


def run(manifest_path, raw_root, out_dir):
    """Xử lý toàn bộ manifest, ghi JSON mỗi phiếu, trả về list record.

    Một dòng manifest hỏng (thiếu cột, num_pages sai kiểu…) chỉ làm HỎNG phiếu đó —
    ghi record lỗi rồi đi tiếp — không giết cả lô.
    """
    rows = read_manifest(manifest_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    for row in rows:
        record_id = row.get("record_id") or "?"
        try:
            record = process_record(row, raw_root, out_dir)
        except Exception as e:  # cách ly lỗi theo từng phiếu
            record = {
                "record_id": record_id,
                "expected_pages": None,
                "found_pages": 0,
                "pages": [],
                "flags": ["processing_error"],
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
            }
        out_path = out_dir / f"{_safe_filename(record_id)}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        records.append(record)
    return records


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default="data/manifest.csv")
    ap.add_argument("--raw-root", default="data/raw/khao-sat")
    ap.add_argument("--out-dir", default="output/assembly")
    args = ap.parse_args()

    records = run(args.manifest, args.raw_root, args.out_dir)

    ok_count = 0
    for record in records:
        mark = "OK " if record["status"] == "ok" else "!! "
        print(f"{mark}{record.get('record_id', '?')}: status={record['status']} "
              f"found={record.get('found_pages', 0)}/{record.get('expected_pages')} "
              f"flags={record.get('flags', [])}")
        if record["status"] == "ok":
            ok_count += 1

    print(f"\n{ok_count}/{len(records)} phiếu OK. Chi tiết: {args.out_dir}/")
    sys.exit(0 if ok_count == len(records) else 1)


if __name__ == "__main__":
    main()
