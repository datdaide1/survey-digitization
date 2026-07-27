"""Tầng 6 (§7 docs/implement-plan-statistics-and-client-report.md) — Cronbach's alpha
cho Q14 (18 dòng phân công lao động) và Q32 (8 dòng ra quyết định), để quyết định có
gộp thành 1 chỉ số tổng hợp duy nhất hay không thay vì đọc từng dòng riêng lẻ.

Mỗi dòng ma trận quy về 1 item nhị phân "vợ có tham gia/quyết định không" (1 nếu chọn
'vợ' hoặc 'cả hai'/'cùng quyết định', 0 nếu không) — khớp đúng ví dụ khách đưa ra ở §7
("% số vấn đề mà 'vợ' hoặc 'cùng quyết định' được chọn").

Ô trống (null) trong Q14/Q32 coi là 0 (KHÔNG loại phiếu khỏi mẫu) — vì theo quy tắc đã
chốt với khách (schema/SCHEMA-FORMAT.md quy tắc #1, note thực tế nhiều dòng: "Ký hiệu
'ko' — coi như trống, không phải ambiguous"), ô trống trong ma trận này có nghĩa "không
ai tick/không áp dụng", tương đương "vợ không tham gia việc này" — không phải dữ liệu
thiếu cần loại bỏ theo listwise deletion. Thử listwise-complete-case ban đầu cho thấy
gần như toàn bộ 85 phiếu bị loại (mỗi ma trận 18/8 dòng, hầu như phiếu nào cũng trống
ít nhất 1 dòng) — xác nhận đây không phải "thiếu dữ liệu" theo nghĩa thông thường.

Mốc quyết định: alpha >= 0.7 (Nunnally, plan gợi ý mặc định, xem §13) -> tạo cột chỉ
số tổng hợp. Alpha < 0.7 -> giữ nguyên từng dòng riêng như Tầng 1/2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ALPHA_THRESHOLD = 0.7

Q14_ROWS = [
    "lam_dat", "trong", "cham_soc_cay", "thuoc_bvtv", "thu_hoach", "so_che",
    "lien_he_tieu_thu", "khac_san_xuat", "noi_tro", "giat_giu", "dua_don_con",
    "dam_cuoi_gio", "cham_soc_con", "gia_suc_nho", "gia_suc_lon",
    "quan_ly_chi_tieu", "day_do_con", "bao_duong_xe",
]
Q14_POSITIVE_CODES = {"vo", "ca_hai"}

Q32_ROWS = ["chon_cay_trong", "mua_vat_tu", "chon_ban", "vay_von", "gia_ban", "su_dung_thu_nhap", "su_dung_dat", "khac"]
Q32_POSITIVE_CODES = {"vo", "cung_quyet_dinh"}


def _is_positive(value, positive_codes: set[str]) -> float:
    if pd.isna(value):
        return np.nan
    if isinstance(value, str) and "+" in value:
        return float(any(part in positive_codes for part in value.split("+")))
    return float(value in positive_codes)


def binary_item_matrix(df: pd.DataFrame, qid: str, rows: list[str], positive_codes: set[str]) -> pd.DataFrame:
    cols = {row: df[f"{qid}_{row}"].apply(lambda v: _is_positive(v, positive_codes)) for row in rows}
    item_df = pd.DataFrame(cols)
    return item_df.fillna(0.0)


def cronbachs_alpha(item_df: pd.DataFrame) -> float | None:
    k = item_df.shape[1]
    n = item_df.shape[0]
    if k < 2 or n < 2:
        return None
    item_variances = item_df.var(axis=0, ddof=1)
    total_variance = item_df.sum(axis=1).var(ddof=1)
    if total_variance == 0:
        return None
    alpha = (k / (k - 1)) * (1 - item_variances.sum() / total_variance)
    return float(alpha)


def composite_index(item_df: pd.DataFrame) -> pd.Series:
    """% số dòng 'vợ có tham gia/quyết định' trên tổng số dòng, theo từng phiếu (0-100)."""
    return item_df.mean(axis=1) * 100


@dataclass
class ReliabilityResult:
    qid: str
    label: str
    n_items: int
    n_complete_cases: int
    alpha: float | None
    composite: pd.Series | None  # index = original df index (chỉ các dòng complete-case)


def analyze(df: pd.DataFrame, qid: str, label: str, rows: list[str], positive_codes: set[str]) -> ReliabilityResult:
    item_df = binary_item_matrix(df, qid, rows, positive_codes)
    alpha = cronbachs_alpha(item_df)
    composite = composite_index(item_df) if (alpha is not None and alpha >= ALPHA_THRESHOLD) else None
    return ReliabilityResult(qid, label, len(rows), len(item_df), alpha, composite)
