"""Tầng 3 (§4 docs/implement-plan-statistics-and-client-report.md) — ma trận liên quan
cho MỌI cặp biến (~99×99). Không dùng Pearson vì phần lớn biến là categorical — dùng
đúng fallback đã ghi trong plan gốc (bỏ qua `phik` để tránh phụ thuộc kém ổn định):

- categorical ↔ categorical (kể cả binary/boolean, coi là categorical 2 mức) -> Cramér's V
- liên tục ↔ liên tục -> Spearman
- liên tục ↔ categorical đúng 2 mức (binary/boolean) -> rank-biserial
- liên tục ↔ categorical >2 mức -> hệ số tương quan (correlation ratio, eta) — mở rộng
  ngoài 3 loại plan liệt kê, cần thiết vì ma trận đầy đủ có nhiều cặp kiểu này (vd
  Q9_derived_years_exp ↔ Q4 dân tộc) mà không loại nào trong 3 loại trên áp dụng được.

QUYẾT ĐỊNH KỸ THUẬT (khác với brainstorm gốc §4.1): thay vì dựng công thức Excel "sống"
cho heatmap từng khối, mọi giá trị trong "Ma trận liên quan" đều tính TĨNH bằng Python
(scipy, đã kiểm thử) rồi dán vào Excel kèm conditional formatting (color scale) — vẫn
tô màu theo đúng heatmap thật của Excel, chỉ số không tự đổi khi sửa dữ liệu. Lý do:
Cramér's V cần dựng bảng contingency + chi-square bằng SUMPRODUCT lồng nhau cho từng
cặp — hàng chục nghìn công thức ẩn, rủi ro sai sót cao hơn hẳn so với dùng scipy đã có
sẵn, đổi lại phải chạy lại script khi có bản review dữ liệu mới (giống Tầng 7/ma trận
99×99 đã chấp nhận trong plan gốc — mở rộng cùng nguyên tắc cho toàn bộ Tầng 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from .codebook import build_codebook

CODEBOOK = build_codebook()

LOW_N_THRESHOLD = 20  # §13 đã chốt trong plan build: n<20 -> đánh dấu "độ tin cậy thấp"

# Cặp biến định danh địa lý/dân tộc — tương quan giữa các cột này chỉ phản ánh CÁCH CHỌN
# MẪU (mỗi xã/tỉnh vốn tập trung sẵn 1-2 dân tộc), không phải phát hiện hành vi/sinh kế
# đáng chú ý cho khảo sát này -> loại khỏi bảng "Top liên quan mạnh nhất" (không loại khỏi
# ma trận đầy đủ 99x99, khách vẫn xem được nếu cần, chỉ không đưa vào danh sách nổi bật).
# Q4 (dân tộc) vẫn được giữ khi ghép với biến hành vi khác (vd Q4 <-> Q27a ở §3.2).
STRUCTURAL_DEMOGRAPHIC_COLUMNS = {"province", "commune", "Q4"}

_BASE_QUESTION_RE = re.compile(r"^([A-Za-z]+\d+[a-c]?)")
_BASE_QUESTION_OVERRIDE = {
    "age_bracket": "Q2",
    "education_grade_bracket": "Q5",
    "marriage_age_bracket": "Q6",
    "experience_years_bracket": "Q9",
    "province": "META",
    "commune": "META",
}


def base_question(col: str) -> str:
    """Câu hỏi gốc của 1 cột combined.csv — dùng để loại các cặp cùng 1 câu hỏi (vd
    bucket với biến thô sinh ra nó, hay 2 lựa chọn cùng 1 multi_select) khỏi bảng "Top
    liên quan mạnh nhất" — các cặp đó liên quan mạnh do THIẾT KẾ câu hỏi/công thức bucket,
    không phải phát hiện đáng chú ý về hành vi/nhân khẩu học."""
    if col in _BASE_QUESTION_OVERRIDE:
        return _BASE_QUESTION_OVERRIDE[col]
    m = _BASE_QUESTION_RE.match(col)
    return m.group(1) if m else col


def _is_continuous(col: str) -> bool:
    return CODEBOOK[col]["kind"] == "continuous"


SIGNIFICANCE_ALPHA = 0.05  # mốc p thông thường, dùng để đánh dấu "ý nghĩa thống kê" trong bảng/DOCX

# 26/07 (phản hồi khách: "p toàn 0,000 mà top liên quan chả liên quan gì" — Cramér's V/
# rank-biserial có thể "phóng đại" lên gần 1 và p gần 0 một cách GIẢ TẠO khi 1 trong 2
# biến có 1 nhóm cực nhỏ (vd "Không ai trong nhà có thiết bị" chỉ 2/85 phiếu) — chỉ cần
# 2 phiếu đó tình cờ trùng nhóm nào đó ở biến kia là ra V=1, p=0.000, dù không nói lên
# điều gì đáng tin. Đây là hạn chế thống kê chuẩn khi cỡ nhóm nhỏ (quy tắc kinh điển:
# kiểm định chi-square/Cramér's V không đáng tin nếu có ô/nhóm kỳ vọng <5) — KHÔNG phải
# chỉ n tổng của cặp (đã lọc n<20 từ trước) mà là cỡ của NHÓM NHỎ NHẤT trong từng biến.
MIN_CATEGORY_N = 5


def cramers_v(a: pd.Series, b: pd.Series) -> tuple[float | None, int, float | None, int | None]:
    """Cramér's V cho 2 biến categorical (kể cả binary/boolean coi là 2 mức)."""
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    n = len(df)
    if n < 2:
        return None, n, None, None
    table = pd.crosstab(df["a"], df["b"])
    if table.shape[0] < 2 or table.shape[1] < 2:
        return None, n, None, None  # 1 biến chỉ có 1 giá trị -> không tính được liên quan
    chi2, p_value, _dof, _expected = stats.chi2_contingency(table, correction=False)
    k = min(table.shape) - 1
    if k <= 0 or n == 0:
        return None, n, None, None
    v = float(np.sqrt((chi2 / n) / k))
    min_group_n = int(min(table.sum(axis=1).min(), table.sum(axis=0).min()))
    return min(v, 1.0), n, float(p_value), min_group_n


def spearman_rho(a: pd.Series, b: pd.Series) -> tuple[float | None, int, float | None, int | None]:
    """Spearman cho 2 biến liên tục."""
    df = pd.DataFrame({"a": a, "b": b}).dropna().astype(float)
    n = len(df)
    if n < 3 or df["a"].nunique() < 2 or df["b"].nunique() < 2:
        return None, n, None, None
    rho, p_value = stats.spearmanr(df["a"], df["b"])
    return (None if np.isnan(rho) else float(rho)), n, float(p_value), None


def rank_biserial(numeric: pd.Series, binary: pd.Series) -> tuple[float | None, int, float | None, int | None]:
    """Rank-biserial: liên tục <-> nhị phân/2 mức (dấu cho biết chiều — nhóm nào cao hơn)."""
    df = pd.DataFrame({"x": numeric, "g": binary}).dropna()
    n = len(df)
    levels = sorted(df["g"].unique(), key=str)
    if n < 3 or len(levels) != 2:
        return None, n, None, None
    g0, g1 = levels
    x0 = df.loc[df["g"] == g0, "x"].astype(float)
    x1 = df.loc[df["g"] == g1, "x"].astype(float)
    if len(x0) == 0 or len(x1) == 0:
        return None, n, None, None
    u_stat, p_value = stats.mannwhitneyu(x1, x0, alternative="two-sided")
    r = float(1 - (2 * u_stat) / (len(x0) * len(x1)))
    return r, n, float(p_value), min(len(x0), len(x1))


def correlation_ratio(categorical: pd.Series, numeric: pd.Series) -> tuple[float | None, int, float | None, int | None]:
    """Eta (correlation ratio) — liên tục <-> categorical >2 mức (dùng ANOVA giữa nhóm)."""
    df = pd.DataFrame({"g": categorical, "x": numeric}).dropna()
    n = len(df)
    groups = [g["x"].astype(float).values for _k, g in df.groupby("g") if len(g) > 0]
    if n < 3 or len(groups) < 2:
        return None, n, None, None
    grand_mean = df["x"].astype(float).mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups)
    ss_total = sum((df["x"].astype(float) - grand_mean) ** 2)
    if ss_total == 0:
        return None, n, None, None
    eta = float(np.sqrt(ss_between / ss_total))
    # p-value từ ANOVA 1 chiều giữa các nhóm — cùng dữ liệu, cùng giả định với eta ở trên
    # (khác Cramér's V/Spearman/rank-biserial vốn có test đi kèm sẵn, correlation_ratio
    # trước đây là loại duy nhất "thiếu" p-value vì tự tính SS thay vì gọi thẳng scipy).
    p_value = None
    if len(groups) >= 2 and all(len(g) >= 1 for g in groups):
        try:
            _f_stat, p_value = stats.f_oneway(*groups)
            p_value = None if np.isnan(p_value) else float(p_value)
        except ValueError:
            p_value = None
    min_group_n = min(len(g) for g in groups)
    return min(eta, 1.0), n, p_value, min_group_n


@dataclass
class AssociationResult:
    value: float | None
    method: str
    n: int
    low_n: bool
    p_value: float | None = None
    min_group_n: int | None = None

    @property
    def significant(self) -> bool | None:
        """True/False nếu có p-value và n đủ lớn để tin (không low_n); None nếu không
        tính được p (vd n quá nhỏ) — KHÔNG được hiểu None là "không có ý nghĩa", chỉ là
        "chưa đủ căn cứ để nói", tránh nhầm giữa 'not significant' và 'unknown'."""
        if self.p_value is None or self.low_n:
            return None
        return self.p_value < SIGNIFICANCE_ALPHA


def association(col_a: str, col_b: str, df: pd.DataFrame) -> AssociationResult:
    a_continuous = _is_continuous(col_a)
    b_continuous = _is_continuous(col_b)
    a, b = df[col_a], df[col_b]

    if a_continuous and b_continuous:
        value, n, p_value, min_group_n = spearman_rho(a, b)
        method = "spearman"
    elif a_continuous or b_continuous:
        numeric, categorical, method_side = (a, b, "b") if a_continuous else (b, a, "a")
        n_levels = categorical.dropna().nunique()
        if n_levels == 2:
            value, n, p_value, min_group_n = rank_biserial(numeric, categorical)
            method = "rank_biserial"
        else:
            value, n, p_value, min_group_n = correlation_ratio(categorical, numeric)
            method = "eta"
    else:
        value, n, p_value, min_group_n = cramers_v(a, b)
        method = "cramers_v"

    # low_n giờ gồm cả 2 điều kiện: mẫu chung quá nhỏ (<20) HOẶC 1 trong 2 biến có nhóm
    # nhỏ nhất <5 phiếu — trường hợp sau mới là nguyên nhân chính gây V=1/p=0.000 giả tạo
    # (xem MIN_CATEGORY_N ở trên).
    low_n = (n < LOW_N_THRESHOLD) or (min_group_n is not None and min_group_n < MIN_CATEGORY_N)
    return AssociationResult(value=value, method=method, n=n, low_n=low_n, p_value=p_value, min_group_n=min_group_n)


def compute_association_matrix(df: pd.DataFrame, columns: list[str]) -> dict[tuple[str, str], AssociationResult]:
    """Tính đủ 1 lần cho mọi cặp KHÔNG lặp (i<j) — matrix đối xứng, đường chéo không tính."""
    results: dict[tuple[str, str], AssociationResult] = {}
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1:]:
            results[(col_a, col_b)] = association(col_a, col_b, df)
    return results


def _is_structural_demographic_pair(col_a: str, col_b: str) -> bool:
    """True nếu cả 2 cột đều là định danh địa lý/dân tộc (province/commune/Q4) — tương
    quan giữa chúng phản ánh cách chọn mẫu, không phải phát hiện đáng đưa vào Top list
    (xem STRUCTURAL_DEMOGRAPHIC_COLUMNS). Kiểm tra bằng TÊN CỘT GỐC, không qua
    base_question() — vì base_question("province")/("commune") trả về "META" (dùng để
    loại cặp bucket-vs-biến-thô ở chỗ khác), sẽ không khớp trực tiếp với
    STRUCTURAL_DEMOGRAPHIC_COLUMNS nếu đi qua đó."""
    return col_a in STRUCTURAL_DEMOGRAPHIC_COLUMNS and col_b in STRUCTURAL_DEMOGRAPHIC_COLUMNS


def top_associations(
    matrix: dict[tuple[str, str], AssociationResult], k: int = 20
) -> list[tuple[str, str, AssociationResult]]:
    """Top k cặp |value| lớn nhất, loại cặp cùng 1 câu hỏi gốc (xem base_question), cặp
    n quá nhỏ (<LOW_N_THRESHOLD, không đủ tin cậy để đưa vào danh sách nổi bật), và cặp
    thuần địa lý/dân tộc (xem _is_structural_demographic_pair — vẫn còn trong ma trận
    đầy đủ, chỉ không lọt vào danh sách "nổi bật" vì không phải phát hiện hành vi/sinh kế)."""
    candidates = [
        (a, b, r) for (a, b), r in matrix.items()
        if r.value is not None
        and not r.low_n
        and base_question(a) != base_question(b)
        and not _is_structural_demographic_pair(a, b)
    ]
    candidates.sort(key=lambda item: abs(item[2].value), reverse=True)
    return candidates[:k]
