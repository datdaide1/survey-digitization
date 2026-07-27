"""Đọc và chuẩn hoá bản ghi output/full/*.json + data/manifest.csv cho tầng thống kê.

Corpus thật KHÔNG đồng nhất về cách biểu diễn `needs_review`/`flags` (phiếu cũ chỉ
dùng mảng `flags`, phiếu mới thêm cả boolean sibling key `needs_review`) và về kiểu
`value` của single_select/matrix row (scalar khi 1 dấu, list khi multi-mark chưa
được reviewer chốt lại) — mọi hàm ở đây xử lý cả hai dạng thay vì giả định 1 dạng.

Xem docs/implement-plan-statistics-and-client-report.md và báo cáo khảo sát cấu trúc
JSON thật (output/full/*.json) đã làm trước khi viết module này.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Iterator

RECORD_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_COMMUNE_SUFFIX_RE = re.compile(r"-\d+phieu$")


def load_json(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root JSON phải là object, nhận {type(data).__name__}")
    return data


def iter_full_record_paths(full_dir: str | Path) -> Iterator[Path]:
    """Duyệt output/full/*.json theo thứ tự record_id, bỏ qua *.json.bak."""
    for path in sorted(Path(full_dir).glob("*.json")):
        yield path


def iter_full_records(full_dir: str | Path) -> Iterator[dict[str, Any]]:
    for path in iter_full_record_paths(full_dir):
        record = load_json(path)
        if not RECORD_ID_RE.fullmatch(record.get("record_id", "")):
            raise ValueError(f"{path}: record_id không hợp lệ hoặc thiếu: {record.get('record_id')!r}")
        yield record


def clean_commune(raw_commune: str) -> str:
    """Bỏ hậu tố '-Nphieu' khỏi tên xã trong manifest (vd 'lung-phinh-16phieu' -> 'lung-phinh')."""
    return _COMMUNE_SUFFIX_RE.sub("", raw_commune)


def load_manifest(manifest_path: str | Path) -> dict[str, dict[str, str]]:
    """record_id -> {"province": ..., "commune": ..., "commune_raw": ...}."""
    out: dict[str, dict[str, str]] = {}
    with open(manifest_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            record_id = row["record_id"]
            out[record_id] = {
                "province": row["province"],
                "commune": clean_commune(row["commune"]),
                "commune_raw": row["commune"],
            }
    return out


def get_value(answer: dict[str, Any] | None) -> Any:
    """Lấy answer['value'] an toàn; None nếu answer thiếu hẳn (câu không tồn tại trong record)."""
    if answer is None:
        return None
    return answer.get("value")


def is_flagged_review(answer: dict[str, Any] | None) -> bool:
    """True nếu field còn cần review, bất kể biểu diễn cũ (flags) hay mới (needs_review bool)."""
    if not answer:
        return False
    if answer.get("needs_review") is True:
        return True
    flags = answer.get("flags") or []
    return "needs_review" in flags


def count_needs_review(record: dict[str, Any]) -> int:
    """Đếm số field còn cờ needs_review trong 1 record — dạng thô, KHÔNG phân biệt
    "còn treo" (phiếu chưa qua Review UI) với "đã xử lý, giữ cờ làm dấu vết audit"
    (phiếu đã qua Review UI, xem docs/review-summary-report.md). Muốn biết số field
    THẬT SỰ còn chờ xử lý, kết hợp với ``has_been_reviewed`` bên dưới."""
    answers = record.get("answers", {})
    total = 0
    for answer in answers.values():
        if isinstance(answer, dict) and is_flagged_review(answer):
            total += 1
    return total


def has_been_reviewed(full_dir: str | Path, record_id: str) -> bool:
    """True nếu record đã qua Review UI ít nhất 1 lần (có file .bak — quy ước của
    scripts/review_ui, xem docs/review-summary-report.md). Với các phiếu đã review,
    cờ needs_review còn sót trong `flags` là dấu vết audit đã có quyết định trong
    `note`, KHÔNG phải việc chưa xử lý — xem docs/review-summary-report.md §1."""
    return (Path(full_dir) / f"{record_id}.json.bak").exists()


def as_code_list(value: Any) -> list[str]:
    """Chuẩn hoá value của multi_select/device_grid row về list[str] (rỗng nếu None)."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def as_single_category(value: Any) -> str | None:
    """Chuẩn hoá value của single_select/matrix row về 1 chuỗi category cho bảng tần suất.

    Khi value là list (multi-mark chưa được reviewer chốt lại thành 1 giá trị cuối —
    xem docs/review-summary-report.md), nối các code đã sắp xếp bằng '+' để giữ
    nguyên bằng chứng multi-mark thay vì tự ý chọn 1 giá trị (không đoán liều).
    """
    if value is None:
        return None
    if isinstance(value, list):
        codes = [str(v) for v in value if v is not None]
        if not codes:
            return None
        return "+".join(sorted(codes))
    return str(value)
