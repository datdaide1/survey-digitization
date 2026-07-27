"""Tầng 2 (§3 docs/implement-plan-statistics-and-client-report.md) — cross-tab theo
tỉnh (mức "theo vùng" chính, §3.1). Hàm thuần pandas, dùng để validate công thức Excel
sống (COUNTIFS 2 điều kiện) ở scripts/lib/report/xlsx_writer.py.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .frequency import category_rows
from .codebook import build_codebook

CODEBOOK = build_codebook()

PROVINCE_LABELS = [("__all__", "Toàn thể (85)"), ("lao-cai", "Lào Cai"), ("lai-chau", "Lai Châu")]


def province_crosstab(column: str, df: pd.DataFrame) -> dict[str, Any]:
    """Bảng tần suất của 1 biến, bẻ theo tỉnh (Toàn thể / Lào Cai / Lai Châu)."""
    meta = CODEBOOK[column]
    series_all = df[column]

    if meta["kind"] == "boolean":
        rows_def = [(True, "Có"), (False, "Không")]
    else:
        rows_def = category_rows(column, series_all)

    # 26/07: mẫu số % = TỔNG SỐ PHIẾU của nhóm (tỉnh)/toàn thể — total_n = len(sub), cố
    # định theo cỡ nhóm (85/58/27) — không phải chỉ số phiếu trả lời câu này trong nhóm
    # đó (trước dùng valid_n = dropna() riêng từng nhóm). Cùng nguyên tắc frequency.py.
    groups = {}
    for code, _label in PROVINCE_LABELS:
        sub = df if code == "__all__" else df[df["province"] == code]
        valid = sub[column].dropna()
        groups[code] = {"valid_n": int(len(valid)), "total_n": int(len(sub)), "counts": valid.value_counts()}

    table = []
    for code, label in rows_def:
        row = {"code": code, "label": label}
        for prov_code, _prov_label in PROVINCE_LABELS:
            g = groups[prov_code]
            n = int(g["counts"].get(code, 0))
            pct = (n / g["total_n"] * 100) if g["total_n"] else 0.0
            row[prov_code] = {"n": n, "pct": pct}
        table.append(row)

    return {
        "column": column,
        "label": meta["label"],
        "kind": meta["kind"],
        "valid_n_by_group": {code: groups[code]["valid_n"] for code, _ in PROVINCE_LABELS},
        "total_n_by_group": {code: groups[code]["total_n"] for code, _ in PROVINCE_LABELS},
        "rows": table,
    }
