"""Công thức stats_bucketing khai báo trong schema/questionnaire_v1.json — chỉ Task 6
(tầng thống kê) mới được bucket, Task 3b/5 chỉ trích xuất giá trị thô (đúng nguyên tắc
"raw first, derived later" ở README). 4 field có stats_bucketing chính thức: Q2, Q5,
Q6, Q9 — công thức lấy nguyên văn từ schema + docs/client-feedback-2026-07-22-extraction-rules.md.

Giá trị dẫn xuất của Q9 (Q9_derived_start_year/years_exp) đã được tính sẵn trong từng
record ở output/full (Task 5, chuẩn hoá 24/07) — module này CHỈ bucket từ giá trị đã
có, không tính lại năm 2026 - start_year/years_exp từ đầu.

REFERENCE_YEAR chỉ dùng cho age_bracket (Q2), vì Task 6 chưa ai tính tuổi từ năm sinh.
"""

from __future__ import annotations

import re
from typing import Any

REFERENCE_YEAR = 2026

_INT_RE = re.compile(r"-?\d+")


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        m = _INT_RE.fullmatch(value.strip())
        if m:
            return int(m.group())
        return None
    return None


def age_from_birth_year(birth_year_value: Any) -> int | None:
    """Q2 (năm sinh) -> tuổi tính đến REFERENCE_YEAR. None nếu không đọc được số nguyên."""
    year = _safe_int(birth_year_value)
    if year is None:
        return None
    return REFERENCE_YEAR - year


def age_bracket(age: int | None) -> str | None:
    """schema Q2.stats_bucketing: '<35' / '35-45' / '>45'."""
    if age is None:
        return None
    if age < 35:
        return "<35"
    if age <= 45:
        return "35-45"
    return ">45"


_GRADE_KEYWORDS = [
    (re.compile(r"thpt|trung\s*học\s*phổ\s*thông", re.IGNORECASE), 12),
    (re.compile(r"thcs|trung\s*học\s*cơ\s*sở", re.IGNORECASE), 9),
    (re.compile(r"tiểu\s*học", re.IGNORECASE), 5),
]


def _grade_number(lop_cao_nhat: Any) -> int | None:
    """Đọc số lớp từ chuỗi tự do kiểu 'Hết lớp 9' -> 9, '9/12' -> 9 (số đầu tiên luôn là
    lớp đã học/hoàn thành theo cách ghi trên phiếu, số sau '/' là tổng số lớp hệ 10 hoặc
    12 — không phải lớp thứ 2 cần đọc). Nếu không có số (vd chỉ ghi chữ 'Tiểu học' —
    case LCH-MSP-013), suy ra số lớp tương ứng từ từ khoá cấp học. None nếu không đọc
    được gì (không suy đoán)."""
    if not isinstance(lop_cao_nhat, str):
        return None
    m = re.search(r"\d+", lop_cao_nhat)
    if m:
        return int(m.group())
    for pattern, grade in _GRADE_KEYWORDS:
        if pattern.search(lop_cao_nhat):
            return grade
    return None


def education_grade_bracket(lop_cao_nhat: Any, khong_di_hoc: Any = None, trung_cap_dh: Any = None) -> str | None:
    """schema Q5.stats_bucketing — CẬP NHẬT 26/07 (phản hồi khách trực tiếp qua chat):
    quay lại gộp 2 tick `Q5_khong_di_hoc`/`Q5_trung_cap_dh` vào bucket này (khác quyết
    định 25/07 — xem docs/client-feedback-2026-07-25-q5-grade-split.md — đã tách riêng
    hoàn toàn, để lại 46/85 phiếu "thiếu/không rõ" chỉ vì phần điền Q5_lop_cao_nhat bỏ
    trống, dù thực ra có trả lời qua tick). Ưu tiên theo thứ tự:
      1. `Q5_trung_cap_dh` = True -> "thpt" (khách xác nhận: tốt nghiệp lớp 12 mới được
         học trung cấp/cao đẳng/đại học, nên tick này chắc chắn đã hoàn thành THPT).
      2. `Q5_khong_di_hoc` = True -> "khong_di_hoc" (bucket riêng, KHÔNG gộp vào
         "tieu_hoc" — chưa từng đi học khác với đã học xong tiểu học).
      3. Còn lại: bucket phần điền tự do (Q5_lop_cao_nhat) theo lớp ĐÃ HỌC XONG — hết
         lớp 9 mới tính THCS, hết lớp 12 mới tính THPT (không phải "đang học lớp mấy"):
         lớp 6/7/8 (chưa hết lớp 9) vẫn tính tiểu học; lớp 10/11 (đã hết lớp 9, chưa hết
         lớp 12) tính THCS chứ không phải THPT.
      `Q5_khong_tieng_pho_thong` vẫn KHÔNG gộp vào đây — không nói được tiếng phổ thông
      không suy ra được cấp học, tiếp tục thống kê % riêng như cột boolean độc lập.
    """
    if trung_cap_dh is True:
        return "thpt"
    if khong_di_hoc is True:
        return "khong_di_hoc"
    grade = _grade_number(lop_cao_nhat)
    if grade is None:
        return None
    if grade >= 12:
        return "thpt"
    if grade >= 9:
        return "thcs"
    return "tieu_hoc"


def marriage_age_bracket(marriage_age: Any) -> str | None:
    """schema Q6.stats_bucketing: '<18' (tảo hôn) / '>=18'."""
    age = _safe_int(marriage_age)
    if age is None:
        return None
    return "<18" if age < 18 else ">=18"


def experience_years_bracket(years_exp: Any) -> str | None:
    """schema Q9.stats_bucketing: '<1' / '>=1'.

    years_exp có thể là chuỗi khoảng ('7-8', case LCA-HR-016 trước 26/07) — theo quy tắc
    đã chốt, giữ nguyên không ép kiểu ở record gốc; ở đây bucket trả None cho trường hợp
    đó vì không thể xác định chắc chắn <1 hay >=1 (đúng tinh thần "không suy đoán").

    26/07 (phản hồi khách): với 2 phiếu không đọc được số năm cụ thể nhưng CHẮC CHẮN đã
    trồng lâu hơn 1 năm theo nội dung Q9 gốc (LCA-HR-010: "nhà chồng đã trồng từ trước";
    LCH-MSP-023: bắt đầu năm "202_" — thập niên 2020 nên chắc chắn hơn 1 năm tính đến
    2026) — review quyết định gắn bucket ">=1" dù không có số cụ thể, ghi nhận bằng
    chuỗi định tính ">1" ở Q9_derived_years_exp (thay vì số) để KHÔNG lẫn vào giá trị số
    trung bình/median (safe_float(">1") = None, không lọt vào biến liên tục).
    """
    if isinstance(years_exp, str) and years_exp.strip().startswith(">"):
        threshold = _safe_float(years_exp.strip()[1:])
        if threshold is not None and threshold >= 1:
            return ">=1"
        return None
    value = _safe_float(years_exp)
    if value is None:
        return None
    return "<1" if value < 1 else ">=1"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        try:
            return float(s)
        except ValueError:
            return None
    return None


# Public aliases — scripts/lib/flatten.py cần parse cùng kiểu số cho cột continuous
# (Q9_derived_years_exp...) như bucketing dùng nội bộ, tránh viết lại logic 2 lần.
safe_int = _safe_int
safe_float = _safe_float


# Q4 (dân tộc) — plan thống kê (§3) giả định "đã chuẩn hoá chính tả" nhưng bước này
# chưa ai làm (Task 3b/5 chỉ phiên âm nguyên văn other_text viết tay, đúng thiết kế).
# Corpus thật có các biến thể chính tả CÙNG 1 dân tộc do viết tay/phiên âm khác nhau
# (kiểm tra thực tế trên combined.csv 24/07): "H'mong"/"H'Mông"/"H'mông" đều là "Mông".
# "Dao đỏ" gộp vào "Dao" (26/07, quyết định của user — đảo lại quyết định cũ 24/07 vốn
# giữ riêng vì coi là tên nhánh Dao cụ thể). Tính chung là "Dao" cho tầng thống kê.
_ETHNICITY_SPELLING_VARIANTS: dict[str, str] = {
    "h'mong": "Mông",
    "h'mông": "Mông",
    "hmong": "Mông",
    "hmông": "Mông",
    "mong": "Mông",
    "mông": "Mông",
    "dao đỏ": "Dao",
    "dao do": "Dao",
}


def normalize_ethnicity(value: str | None) -> str | None:
    """Chuẩn hoá chính tả tên dân tộc Q4 cho tầng thống kê (Task 6). 'kinh' (code
    schema) -> 'Kinh' (nhãn) để đồng nhất với các giá trị other_text đã viết hoa tên
    riêng; các biến thể chính tả của cùng 1 dân tộc gộp về 1 chính tả chuẩn."""
    if value is None:
        return None
    if value == "kinh":
        return "Kinh"
    key = value.strip().casefold()
    return _ETHNICITY_SPELLING_VARIANTS.get(key, value.strip())
