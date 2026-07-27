"""Tầng 4 (§5 docs/implement-plan-statistics-and-client-report.md) — độ ảnh hưởng có
CHIỀU (khác Tầng 3 — association.py — vốn đối xứng, không nói chiều). 3 loại phù hợp
dữ liệu này: odds ratio (2 biến nhị phân), eta-squared (phân loại -> số), hệ số hồi quy/
slope (số -> số).

CẢNH BÁO BẮT BUỘC (§5): đây KHÔNG PHẢI bằng chứng nhân quả — khảo sát cắt ngang, không
nhóm đối chứng. Luôn diễn giải bằng "liên hệ quan sát được", không dùng "tác động"/
"ảnh hưởng" (áp dụng ở tầng viết văn DOCX, xem narrative.py/docx_writer.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .association import correlation_ratio


@dataclass
class EffectSizeResult:
    kind: str  # "odds_ratio" | "eta_squared" | "slope"
    value: float | None
    n: int
    detail: dict[str, Any]


def odds_ratio(a: pd.Series, b: pd.Series) -> EffectSizeResult:
    """(a*d)/(b*c) từ bảng 2x2 — a,b phải là 2 biến đúng 2 mức (0/1 hoặc bool)."""
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    n = len(df)
    levels_a = sorted(df["a"].unique(), key=str)
    levels_b = sorted(df["b"].unique(), key=str)
    if n < 4 or len(levels_a) != 2 or len(levels_b) != 2:
        return EffectSizeResult("odds_ratio", None, n, {})

    a1, a0 = levels_a[1], levels_a[0]
    b1, b0 = levels_b[1], levels_b[0]
    n11 = int(((df["a"] == a1) & (df["b"] == b1)).sum())
    n10 = int(((df["a"] == a1) & (df["b"] == b0)).sum())
    n01 = int(((df["a"] == a0) & (df["b"] == b1)).sum())
    n00 = int(((df["a"] == a0) & (df["b"] == b0)).sum())

    # Haldane-Anscombe correction khi có ô = 0, tránh chia 0 / OR vô cực
    if 0 in (n11, n10, n01, n00):
        n11, n10, n01, n00 = n11 + 0.5, n10 + 0.5, n01 + 0.5, n00 + 0.5
        corrected = True
    else:
        corrected = False

    value = (n11 * n00) / (n10 * n01)
    return EffectSizeResult(
        "odds_ratio", float(value), n,
        {"table": {"a1_b1": n11, "a1_b0": n10, "a0_b1": n01, "a0_b0": n00}, "corrected": corrected},
    )


def eta_squared(categorical: pd.Series, numeric: pd.Series) -> EffectSizeResult:
    eta, n, _p, _min_group_n = correlation_ratio(categorical, numeric)
    value = None if eta is None else float(eta ** 2)
    return EffectSizeResult("eta_squared", value, n, {})


def _is_numeric(series: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def compute_effect_size(kind: str, col_a: str, col_b: str, df: pd.DataFrame) -> EffectSizeResult:
    """Dispatch đúng thứ tự tham số theo kind — tránh gọi nhầm eta_squared(numeric,
    categorical) thay vì eta_squared(categorical, numeric) tại nơi gọi (lỗi thực tế đã
    gặp khi test thủ công: cột nào numeric/categorical phụ thuộc dtype thật trong df,
    không phải thứ tự khai báo trong curated_pairs.EFFECT_SIZE_PAIRS)."""
    a, b = df[col_a], df[col_b]
    if kind == "odds_ratio":
        return odds_ratio(a, b)
    if kind == "slope":
        return regression_slope(a, b)
    if kind == "eta_squared":
        if _is_numeric(a) and not _is_numeric(b):
            return eta_squared(b, a)
        return eta_squared(a, b)
    raise ValueError(f"Loại effect size không hỗ trợ: {kind!r}")


def regression_slope(x: pd.Series, y: pd.Series) -> EffectSizeResult:
    """SLOPE/LINEST tương đương — y theo x (x là biến giải thích, theo đúng chiều cặp đã liệt kê ở §3.2)."""
    df = pd.DataFrame({"x": x, "y": y}).dropna().astype(float)
    n = len(df)
    if n < 3 or df["x"].nunique() < 2:
        return EffectSizeResult("slope", None, n, {})
    result = stats.linregress(df["x"], df["y"])
    return EffectSizeResult(
        "slope", float(result.slope), n,
        {"intercept": float(result.intercept), "r": float(result.rvalue), "p": float(result.pvalue)},
    )
