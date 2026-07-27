"""Tầng 5 (§6 docs/implement-plan-statistics-and-client-report.md) — so sánh nhóm bằng
kiểm định phi tham số (không giả định phân phối chuẩn, phù hợp dữ liệu categorical/cỡ
mẫu nhỏ/lệch của khảo sát này): Mann-Whitney U (đúng 2 nhóm), Kruskal-Wallis (3+ nhóm).

Nhắc lại đúng tinh thần §5/§6: với subgroup nhỏ (nhiều xã <10 phiếu, một số nhóm dân
tộc n rất nhỏ), kết quả các test này chỉ mang tính tham khảo, không diễn giải theo
nghĩa hàn lâm "khác biệt có ý nghĩa thống kê".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
from scipy import stats


@dataclass
class GroupTestResult:
    test: str  # "mann_whitney" | "kruskal_wallis"
    statistic: float | None
    p_value: float | None
    groups: list[dict[str, Any]]  # [{"group": ..., "n": ..., "median": ...}, ...]
    low_n: bool


LOW_N_GROUP_THRESHOLD = 10  # nhóm <10 phiếu -> kết quả chỉ tham khảo (§6)


def mann_whitney(numeric: pd.Series, group: pd.Series) -> GroupTestResult:
    df = pd.DataFrame({"x": numeric, "g": group}).dropna()
    levels = sorted(df["g"].unique(), key=str)
    if len(levels) != 2:
        return GroupTestResult("mann_whitney", None, None, [], True)

    samples = []
    groups_info = []
    for lvl in levels:
        vals = df.loc[df["g"] == lvl, "x"].astype(float)
        samples.append(vals)
        groups_info.append({"group": lvl, "n": int(len(vals)), "median": float(vals.median()) if len(vals) else None, "values": vals.tolist()})

    if any(len(s) < 2 for s in samples):
        return GroupTestResult("mann_whitney", None, None, groups_info, True)

    stat, p = stats.mannwhitneyu(samples[0], samples[1], alternative="two-sided")
    low_n = any(g["n"] < LOW_N_GROUP_THRESHOLD for g in groups_info)
    return GroupTestResult("mann_whitney", float(stat), float(p), groups_info, low_n)


def kruskal_wallis(numeric: pd.Series, group: pd.Series) -> GroupTestResult:
    df = pd.DataFrame({"x": numeric, "g": group}).dropna()
    levels = sorted(df["g"].unique(), key=str)
    samples = []
    groups_info = []
    for lvl in levels:
        vals = df.loc[df["g"] == lvl, "x"].astype(float)
        samples.append(vals)
        groups_info.append({"group": lvl, "n": int(len(vals)), "median": float(vals.median()) if len(vals) else None, "values": vals.tolist()})

    valid_samples = [s for s in samples if len(s) >= 2]
    if len(valid_samples) < 2:
        return GroupTestResult("kruskal_wallis", None, None, groups_info, True)

    stat, p = stats.kruskal(*valid_samples)
    low_n = any(g["n"] < LOW_N_GROUP_THRESHOLD for g in groups_info)
    return GroupTestResult("kruskal_wallis", float(stat), float(p), groups_info, low_n)
