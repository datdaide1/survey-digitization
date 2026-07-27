"""Tầng 1 (§2 docs/implement-plan-statistics-and-client-report.md) — bảng tần suất +
% + n hợp lệ/missing cho mọi biến, và bảng mô tả (mean/median/mode/std/min/max/quartile)
cho 4 biến số liên tục. Hàm thuần Python/pandas — dùng để: (1) hiển thị số trong DOCX,
(2) so khớp (spot-check) với công thức Excel sống ở scripts/lib/report/xlsx_writer.py.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd

from .codebook import build_codebook

CODEBOOK = build_codebook()


def _combo_parts(code: Any, label_by_code: dict[str, str]) -> list[str] | None:
    """Nếu `code` là tổ hợp multi-mark thật (vd 'buon_ban+nong_dan' — 1 phiếu tick ≥2 ô
    trên câu chỉ cho chọn 1, xem scripts/lib/records.as_single_category), trả về danh
    sách các code thành phần để CỘNG DỒN vào từng lựa chọn gốc (giống cách 1 câu multi-
    select thật được kiểm — mỗi lựa chọn được tick tính riêng, %  các lựa chọn có thể
    cộng vượt 100%). Trả None nếu không phải tổ hợp (giá trị bình thường, hoặc chuỗi lạ
    không tách được về option đã biết — vd tên dân tộc tự do ở Q4)."""
    if not isinstance(code, str) or "+" not in code:
        return None
    parts = code.split("+")
    if len(parts) < 2 or any(p not in label_by_code for p in parts):
        return None
    return parts


def category_rows(column: str, series: pd.Series) -> list[tuple[str, str]]:
    """Danh sách (code, label) sẽ xuất hiện trong bảng tần suất của 1 cột, theo đúng
    thứ tự: option đã biết trước từ schema (nếu có) trước, sau đó là giá trị lạ/phát
    sinh thật sự có trong dữ liệu (vd tên dân tộc cụ thể ở Q4) được nối thêm, sort theo
    alpha để ổn định giữa các lần chạy. Tổ hợp multi-mark ('+') KHÔNG tạo hàng riêng ở
    đây — xem frequency_table(): mỗi phần của tổ hợp được cộng thẳng vào hàng lựa chọn
    gốc của nó, giống cách 1 câu multi-select thật được tính.
    """
    meta = CODEBOOK[column]
    known = meta.get("options") or []
    known_codes = [code for code, _label in known]
    label_by_code = dict(known)

    observed = sorted(v for v in series.dropna().unique())
    extra = [
        v for v in observed
        if v not in known_codes and _combo_parts(v, label_by_code) is None
    ]

    rows = list(known)
    for code in extra:
        rows.append((code, str(code)))
    return rows


def frequency_table(column: str, series: pd.Series) -> dict[str, Any]:
    """Bảng tần suất cho 1 biến categorical/binary/boolean.

    - 26/07 (quyết định user, đảo lại §2 cũ): mẫu số của % là TỔNG SỐ PHIẾU
      (``total_n = len(series)``, cố định = 85 cho mọi biến), KHÔNG loại missing/null
      khỏi mẫu số nữa — 1 phiếu bỏ trống câu X vẫn tính là 1/85, không phải bị loại khỏi
      mẫu rồi tính trên phần còn lại (cách đó làm % bị "phồng" lên so với toàn mẫu ở
      những câu có nhiều phiếu bỏ trống). ``valid_n``/``missing_n`` vẫn giữ nguyên để
      hiển thị riêng (biết được bao nhiêu phiếu thực sự trả lời câu này), chỉ có mẫu số
      của cột "%" là đổi.
    - Với tổ hợp multi-mark (vd 1 phiếu tick cả 'Nông dân' và 'Buôn bán' trên câu chỉ
      cho chọn 1 nghề): CỘNG DỒN phiếu đó vào CẢ HAI hàng 'Nông dân' và 'Buôn bán' thay
      vì tạo hàng riêng 'Nông dân + Buôn bán' — nên tổng n/tổng % của bảng có thể vượt
      valid_n/100% (has_overlap) HOẶC thấp hơn total_n/100% nếu có phiếu bỏ trống — cả 2
      điều đều bình thường, không phải lỗi tính toán.
    """
    meta = CODEBOOK[column]
    valid = series.dropna()
    valid_n = int(len(valid))
    missing_n = int(series.isna().sum())
    total_n = valid_n + missing_n  # = len(series), luôn = 85 (cỡ mẫu cố định)

    if meta["kind"] == "boolean":
        rows = [(True, "Có"), (False, "Không")]
        label_by_code: dict[str, str] = {}
    else:
        rows = category_rows(column, series)
        known = meta.get("options") or []
        label_by_code = dict(known)

    counts: Counter = Counter()
    for value in valid:
        parts = _combo_parts(value, label_by_code) if meta["kind"] != "boolean" else None
        if parts:
            counts.update(parts)
        else:
            counts[value] += 1

    table = []
    for code, label in rows:
        n = int(counts.get(code, 0))
        pct = (n / total_n * 100) if total_n else 0.0
        table.append({"code": code, "label": label, "n": n, "pct": pct})

    total_tallied = sum(row["n"] for row in table)

    return {
        "column": column,
        "label": meta["label"],
        "kind": meta["kind"],
        "valid_n": valid_n,
        "missing_n": missing_n,
        "total_n": total_n,
        "rows": table,
        "has_overlap": total_tallied > valid_n,
    }


def descriptive_stats(column: str, series: pd.Series) -> dict[str, Any]:
    """Bảng mô tả cho 4 biến liên tục (§2 bổ sung 24/07): n, mean, median, mode, std,
    min, max, Q1/Q3 (QUARTILE.INC tương đương numpy interpolation='linear')."""
    meta = CODEBOOK[column]
    valid = series.dropna().astype(float)
    n = int(len(valid))
    if n == 0:
        return {
            "column": column, "label": meta["label"], "n": 0, "mean": None, "median": None,
            "mode": None, "std": None, "min": None, "max": None, "q1": None, "q3": None,
        }

    mode_result = valid.mode()
    return {
        "column": column,
        "label": meta["label"],
        "n": n,
        "mean": float(valid.mean()),
        "median": float(valid.median()),
        "mode": float(mode_result.iloc[0]) if not mode_result.empty else None,
        "std": float(valid.std(ddof=1)) if n > 1 else None,
        "min": float(valid.min()),
        "max": float(valid.max()),
        "q1": float(np.percentile(valid, 25)),
        "q3": float(np.percentile(valid, 75)),
    }


CONTINUOUS_COLUMNS = ["Q2_tuoi", "Q6_tuoi_ket_hon", "Q9_derived_years_exp"]


def all_frequency_tables(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {
        col: frequency_table(col, df[col])
        for col in df.columns
        if col in CODEBOOK and col not in CONTINUOUS_COLUMNS
    }


def all_descriptive_stats(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {col: descriptive_stats(col, df[col]) for col in CONTINUOUS_COLUMNS}
