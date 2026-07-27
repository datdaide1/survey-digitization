"""Tách PII khỏi 1 record output/full/*.json -> bản ghi ẩn danh cho output/stats/*.json.

Theo README §4 (lớp `full` có PII / lớp `stats` không PII) và §10 của
docs/implement-plan-statistics-and-client-report.md: field PII duy nhất trong schema
là Q1 (`pii: true`, họ tên + có thể kèm SĐT cùng dòng — xem schema/questionnaire_v1.json).
Không field nào khác trong schema mang `pii: true`.
"""

from __future__ import annotations

import copy
from typing import Any


def to_stats_record(record: dict[str, Any]) -> dict[str, Any]:
    """Trả về bản sao của record, bỏ hẳn key Q1 khỏi answers (không che, xoá hẳn)."""
    stats_record = copy.deepcopy(record)
    stats_record.get("answers", {}).pop("Q1", None)
    return stats_record
