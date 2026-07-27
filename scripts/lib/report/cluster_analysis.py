"""Tầng 7 (§8 docs/implement-plan-statistics-and-client-report.md) — Cluster analysis:
phân khúc 85 phụ nữ khảo sát thành vài nhóm "tự chủ" dựa trên nhiều chỉ số cùng lúc
(thiết bị, đi lại, tham gia quyết định, nguồn lực...), hữu ích để thiết kế can thiệp
theo nhóm đối tượng.

n=85 khá mỏng để cụm ổn định/lặp lại được — kết quả CHỈ mang tính gợi ý, không phải
phân loại chính thức (nhắc rõ ở narrative DOCX, xem docx_writer._add_advanced_section).

Số cụm k thử k=2..4 (mặc định §13), chọn theo silhouette score cao nhất — ghi lại toàn
bộ điểm đã thử cho từng k, không chỉ báo cáo mỗi k tốt nhất.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .reliability import (
    Q14_POSITIVE_CODES,
    Q14_ROWS,
    Q32_POSITIVE_CODES,
    Q32_ROWS,
    binary_item_matrix,
    composite_index,
)

K_RANGE = (2, 3, 4)
RANDOM_STATE = 42


def _co_to_float(series: pd.Series) -> pd.Series:
    return series.map({"co": 1.0, "khong": 0.0})


def build_feature_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng "tự chủ" ghép từ các cột đã có sẵn trong combined.csv — tính trong bộ
    nhớ, KHÔNG ghi cột mới vào output/combined.csv (cùng cách
    curated_pairs.derive_helper_columns đang làm cho Tầng 4/5)."""
    q14 = binary_item_matrix(df, "Q14", Q14_ROWS, Q14_POSITIVE_CODES)
    q32 = binary_item_matrix(df, "Q32", Q32_ROWS, Q32_POSITIVE_CODES)

    return pd.DataFrame(
        {
            "Sở hữu thiết bị (vợ)": df[["Q17_dien_thoai_vo", "Q17_may_tinh_vo", "Q17_may_tinh_bang_vo"]].mean(axis=1),
            "Biết đi xe máy": _co_to_float(df["Q24"]),
            "Có xe máy riêng": _co_to_float(df["Q25"]),
            "Là hội viên đoàn thể": df["Q11_khong_hoi_vien"].map({1: 0.0, 0: 1.0}),
            "Đã tham gia tập huấn": df["Q21a"].isin(["1_3_lan", "tren_3_lan"]).astype(float),
            "Đã vay vốn": df["Q22a_chua"].map({1: 0.0, 0: 1.0}),
            "Đứng tên đất": df["Q27a"].isin(["vo", "ca_hai"]).astype(float),
            "Chỉ số phân công lao động (%)": composite_index(q14),
            "Chỉ số ra quyết định (%)": composite_index(q32),
        },
        index=df.index,
    )


def _fill_missing(features: pd.DataFrame) -> pd.DataFrame:
    """Cột chỉ số (%) -> điền median; cột nhị phân còn lại -> điền mode (giá trị phổ
    biến nhất). Không loại phiếu khỏi mẫu vì thiếu 1-2 đặc trưng — n=85 đã mỏng sẵn,
    loại thêm sẽ méo kết quả hơn là điền giá trị trung tâm."""
    filled = features.copy()
    for col in filled.columns:
        if not filled[col].isna().any():
            continue
        if col.endswith("(%)"):
            filled[col] = filled[col].fillna(filled[col].median())
        else:
            mode = filled[col].mode(dropna=True)
            filled[col] = filled[col].fillna(mode.iloc[0] if len(mode) else 0.0)
    return filled


@dataclass
class ClusterResult:
    record_ids: pd.Series
    feature_labels: list[str]
    feature_matrix_raw: pd.DataFrame  # đơn vị gốc, đã điền thiếu — dùng để mô tả đặc điểm cụm
    k_tried: list[int]
    silhouette_scores: dict[int, float]
    best_k: int
    labels: np.ndarray
    cluster_sizes: dict[int, int]
    cluster_means_raw: pd.DataFrame  # index=cluster, columns=feature_labels
    pca_2d: np.ndarray  # (n, 2)


def run_cluster_analysis(df: pd.DataFrame) -> ClusterResult:
    features_raw = _fill_missing(build_feature_matrix(df))
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(features_raw.to_numpy())

    silhouette_scores: dict[int, float] = {}
    fitted_labels: dict[int, np.ndarray] = {}
    for k in K_RANGE:
        labels = KMeans(n_clusters=k, n_init=10, random_state=RANDOM_STATE).fit_predict(x_scaled)
        silhouette_scores[k] = float(silhouette_score(x_scaled, labels))
        fitted_labels[k] = labels

    best_k = max(silhouette_scores, key=silhouette_scores.get)
    labels = fitted_labels[best_k]

    cluster_sizes = {int(c): int((labels == c).sum()) for c in sorted(set(labels))}
    means_df = features_raw.copy()
    means_df["_cluster"] = labels
    cluster_means_raw = means_df.groupby("_cluster").mean()

    pca_2d = PCA(n_components=2, random_state=RANDOM_STATE).fit_transform(x_scaled)

    return ClusterResult(
        record_ids=df["record_id"],
        feature_labels=list(features_raw.columns),
        feature_matrix_raw=features_raw,
        k_tried=list(K_RANGE),
        silhouette_scores=silhouette_scores,
        best_k=int(best_k),
        labels=labels,
        cluster_sizes=cluster_sizes,
        cluster_means_raw=cluster_means_raw,
        pca_2d=pca_2d,
    )
