"""Tầng 7 (§8 docs/implement-plan-statistics-and-client-report.md) — Factor analysis
cho Q14/Q32, tự tính bằng numpy (eigen-decomposition trên ma trận tương quan + xoay
varimax) thay vì dùng thư viện `factor_analyzer`.

`factor_analyzer==0.5.1` (ghim trong requirements.txt) gọi `check_array(force_all_finite=...)`
nội bộ — tham số này đã bị đổi tên trong `scikit-learn==1.9.0` đang cài trong env
`survey-digitizer` -> `TypeError` khi `.fit()`. Đã test trực tiếp để xác nhận (25/07).
Cách tự tính dưới đây theo đúng tinh thần các module Tầng 3/4 khác (association.py,
effect_size.py) — công thức thống kê chuẩn viết tay bằng numpy/scipy, không phụ thuộc
thư viện ML nặng, và né được xung đột dependency nói trên.

Số factor giữ lại theo Kaiser criterion (eigenvalue > 1, tối thiểu 1) — mặc định đã chốt
với khách ở §13 khi chưa có yêu cầu khác. Item nhị phân được coi như biến liên tục khi
tính ma trận tương quan (Pearson) — chấp nhận được cho mục đích thăm dò/minh hoạ ở đây,
không phải phân tích khẳng định.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .reliability import binary_item_matrix

MIN_ITEMS_PER_OBS_RATIO = 5.0


def _varimax(loadings: np.ndarray, gamma: float = 1.0, max_iter: int = 50, tol: float = 1e-6) -> np.ndarray:
    """Xoay varimax chuẩn (Kaiser 1958) bằng SVD lặp — thuật toán kinh điển, tự viết
    bằng numpy để không phụ thuộc thư viện `factor_analyzer` (xem lý do ở docstring module)."""
    n_items, n_factors = loadings.shape
    if n_factors < 2:
        return loadings
    rotation = np.eye(n_factors)
    d_sum = 0.0
    for _ in range(max_iter):
        rotated = loadings @ rotation
        u, s, vt = np.linalg.svd(
            loadings.T @ (rotated**3 - (gamma / n_items) * rotated @ np.diag(np.diag(rotated.T @ rotated)))
        )
        rotation = u @ vt
        d_new = float(np.sum(s))
        if d_sum != 0 and d_new < d_sum * (1 + tol):
            break
        d_sum = d_new
    return loadings @ rotation


@dataclass
class FactorAnalysisResult:
    qid: str
    label: str
    n_items: int
    n_obs: int
    eigenvalues: np.ndarray
    n_factors: int
    loadings: pd.DataFrame | None  # index=item code, columns="Nhân tố 1".."Nhân tố k"
    low_ratio_warning: bool  # True nếu n_obs/n_items < MIN_ITEMS_PER_OBS_RATIO (mẫu mỏng, §8)


def run_factor_analysis(
    df: pd.DataFrame, qid: str, label: str, rows: list[str], positive_codes: set[str],
) -> FactorAnalysisResult:
    item_df = binary_item_matrix(df, qid, rows, positive_codes)
    n_obs, n_items = item_df.shape
    ratio = (n_obs / n_items) if n_items else 0.0
    low_ratio_warning = ratio < MIN_ITEMS_PER_OBS_RATIO

    corr = item_df.corr().to_numpy()
    corr = np.nan_to_num(corr, nan=0.0)  # item hằng số (variance=0) -> corr NaN với mọi item khác
    np.fill_diagonal(corr, 1.0)

    eigvals, eigvecs = np.linalg.eigh(corr)  # tăng dần theo mặc định numpy
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    n_factors = max(1, min(int(np.sum(eigvals > 1.0)), n_items))
    selected_vals = np.clip(eigvals[:n_factors], a_min=0.0, a_max=None)
    raw_loadings = eigvecs[:, :n_factors] * np.sqrt(selected_vals)
    rotated = _varimax(raw_loadings) if n_factors > 1 else raw_loadings

    loadings_df = pd.DataFrame(
        rotated, index=rows, columns=[f"Nhân tố {i + 1}" for i in range(n_factors)],
    )
    return FactorAnalysisResult(qid, label, n_items, n_obs, eigvals, n_factors, loadings_df, low_ratio_warning)
