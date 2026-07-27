"""Danh sách cặp cụ thể đã thảo luận với khách (§3.2) cho Tầng 4 (effect size) + ví dụ
áp dụng Tầng 5 (so sánh nhóm phi tham số, §6) — KHÔNG giới hạn, mở rộng thêm khi làm
thật theo đúng tinh thần §3.2. Vài biến gốc trong §3.2 là categorical/multi-select
(Q21a 3 mức, Q19/Q33 multi-select, Q8 thứ bậc) — cần quy đổi sang dạng phù hợp với 3
loại effect size đã chọn (odds ratio: nhị phân-nhị phân; eta-squared: phân loại-số;
hệ số hồi quy: số-số). ``derive_helper_columns`` tạo các cột phụ trợ trong bộ nhớ
(KHÔNG ghi vào output/combined.csv) — nhị phân hoá multi-select thành "có/không", và
đổi Q8 (4 bậc) thành thang số thứ tự 1-4 để dùng được trong hồi quy/so sánh nhóm.
"""

from __future__ import annotations

import pandas as pd

Q8_ORDINAL = {"duoi_25": 1, "25_50": 2, "51_75": 3, "tren_75": 4}


def _co_khong_bool(series: pd.Series) -> pd.Series:
    """'co'/'khong' -> True/False/NaN, ép rõ chiều True='co' (tránh sort alphabet đưa
    'co' thành mức tham chiếu 0 một cách ngẫu nhiên trong odds_ratio — 'c' < 'k')."""
    return series.map({"co": True, "khong": False})


def derive_helper_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Q8_ordinal"] = out["Q8"].map(Q8_ORDINAL)  # tổ hợp multi-mark (vd '25_50+51_75') -> NaN, không suy đoán
    out["Q21a_da_tham_gia"] = (out["Q21a"] == "1_3_lan") | (out["Q21a"] == "tren_3_lan")
    out["Q11_la_hoi_vien"] = out["Q11_khong_hoi_vien"].map({1: False, 0: True})
    out["Q33_co_vai_tro_lanh_dao"] = out["Q33_khong"].map({1: False, 0: True})
    out["Q19_co_ung_dung_cong_nghe"] = out["Q19_khong"].map({1: False, 0: True})
    out["Q22a_da_vay_von"] = out["Q22a_chua"].map({1: False, 0: True})
    out["Q27a_dung_ten_dat"] = out["Q27a"].isin(["vo", "ca_hai"])
    out["Q25_co_xe_may_rieng"] = _co_khong_bool(out["Q25"])
    out["Q26_phai_xin_phep"] = _co_khong_bool(out["Q26"])
    out["Q16a_co_thay_doi"] = _co_khong_bool(out["Q16a"])
    return out


# 26/07 (phản hồi khách — biểu đồ Tầng 4 hiện thẳng tên biến thô như "Q11_la_hoi_vien"
# thay vì tiếng Việt, đọc không hiểu): các cột phụ trợ ở trên KHÔNG có trong CODEBOOK
# (build_codebook() chỉ đọc schema gốc, không biết derive_helper_columns tạo thêm gì) —
# nơi nào tra nhãn cho cột effect size (docx_writer._effect_sentence, biểu đồ Tầng 4,
# effect_size_sheet._label) phải tra qua HELPER_COLUMN_LABELS trước, xem resolve_label().
HELPER_COLUMN_LABELS: dict[str, str] = {
    "Q8_ordinal": "Q8 – Tỷ lệ thu nhập dược liệu (thang bậc 1-4)",
    "Q21a_da_tham_gia": "Đã tham gia tập huấn (2 năm qua)",
    "Q11_la_hoi_vien": "Là hội viên đoàn thể",
    "Q33_co_vai_tro_lanh_dao": "Có vai trò lãnh đạo",
    "Q19_co_ung_dung_cong_nghe": "Có ứng dụng công nghệ trong sản xuất/kinh doanh",
    "Q22a_da_vay_von": "Đã từng vay vốn",
    "Q27a_dung_ten_dat": "Đứng tên quyền sử dụng đất (vợ hoặc cả hai)",
    "Q25_co_xe_may_rieng": "Có xe máy riêng",
    "Q26_phai_xin_phep": "Phải xin phép khi tham gia hoạt động xã hội",
    "Q16a_co_thay_doi": "Có thay đổi vai trò giới",
}


def resolve_label(col: str, codebook: dict) -> str:
    """Nhãn tiếng Việt cho 1 cột dùng ở Tầng 4/5 — tra CODEBOOK (cột gốc) trước, sau đó
    HELPER_COLUMN_LABELS (cột phụ trợ tạo trong hàm trên), cuối cùng mới rơi về tên cột
    thô (không nên xảy ra với các cặp đã khai báo trong EFFECT_SIZE_PAIRS/
    GROUP_COMPARISON_PAIRS — nếu vẫn thấy tên thô kiểu 'Q11_la_hoi_vien' lên báo cáo,
    nghĩa là thiếu 1 dòng trong HELPER_COLUMN_LABELS)."""
    if col in codebook:
        return codebook[col]["label"]
    if col in HELPER_COLUMN_LABELS:
        return HELPER_COLUMN_LABELS[col]
    return col


# (chủ đề, biến 1, biến 2, loại effect size, mô tả ví dụ gốc khách đưa ra)
EFFECT_SIZE_PAIRS: list[tuple[str, str, str, str, str]] = [
    ("Kinh nghiệm ↔ thu nhập", "Q9_derived_years_exp", "Q8_ordinal", "slope",
     "Mỗi năm kinh nghiệm tăng thêm, tỷ lệ thu nhập dược liệu (thang 1-4) tăng thêm khoảng bao nhiêu bậc"),
    ("Kinh nghiệm ↔ thu nhập", "Q9_derived_years_exp", "Q30", "eta_squared",
     "Số năm kinh nghiệm khác nhau bao nhiêu giữa các khâu tham gia chính trong chuỗi giá trị"),
    ("Kinh nghiệm ↔ thu nhập", "Q9_derived_years_exp", "Q13", "eta_squared",
     "Số năm kinh nghiệm khác nhau bao nhiêu giữa các nhóm 'ai tham gia chính trồng/bán'"),
    ("Học vấn ↔ kiến thức (proxy)", "education_grade_bracket", "Q28_thieu_kien_thuc", "eta_squared",
     "Trình độ học vấn giải thích được bao nhiêu % khác biệt trong việc tick 'thiếu kiến thức kỹ thuật/thị trường'"),
    ("Học vấn ↔ kiến thức (proxy)", "education_grade_bracket", "Q29b_nang_cao_kien_thuc", "eta_squared",
     "Trình độ học vấn ↔ tick 'được nâng cao kiến thức'"),
    ("Học vấn ↔ kiến thức (proxy)", "education_grade_bracket", "Q18_tim_kiem_thong_tin", "eta_squared",
     "Trình độ học vấn ↔ tick 'tìm kiếm thông tin, nâng cao kiến thức'"),
    ("Dân tộc, tuổi, hôn nhân", "Q4", "Q9_derived_years_exp", "eta_squared",
     "Dân tộc giải thích được bao nhiêu % khác biệt số năm kinh nghiệm"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q11_la_hoi_vien", "Q21a_da_tham_gia", "odds_ratio",
     "Là hội viên đoàn thể → khả năng đã tham gia tập huấn cao/thấp gấp bao nhiêu lần"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q11_la_hoi_vien", "Q33_co_vai_tro_lanh_dao", "odds_ratio",
     "Là hội viên đoàn thể → khả năng có vai trò lãnh đạo cao/thấp gấp bao nhiêu lần"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q25_co_xe_may_rieng", "Q21a_da_tham_gia", "odds_ratio",
     "Có xe máy riêng → khả năng tham gia tập huấn cao gấp bao nhiêu lần (ví dụ gốc khách đưa ra)"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q26_phai_xin_phep", "Q21a_da_tham_gia", "odds_ratio",
     "Phải xin phép khi tham gia hoạt động xã hội → khả năng đã tham gia tập huấn"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q22a_da_vay_von", "Q8_ordinal", "eta_squared",
     "Đã từng vay vốn ↔ tỷ lệ thu nhập dược liệu"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q23", "Q8_ordinal", "eta_squared",
     "Nhận hỗ trợ vật chất ↔ tỷ lệ thu nhập dược liệu"),
    ("Nguồn lực/tự chủ ↔ tham gia", "Q19_co_ung_dung_cong_nghe", "Q21a_da_tham_gia", "odds_ratio",
     "Có ứng dụng công nghệ trong sản xuất/kinh doanh → khả năng đã tham gia tập huấn"),
    ("Rào cản ↔ kết quả", "Q28_thieu_kien_thuc", "Q8_ordinal", "eta_squared",
     "Tick 'thiếu kiến thức kỹ thuật/thị trường' ↔ tỷ lệ thu nhập dược liệu"),
    ("Rào cản ↔ kết quả", "Q16a_co_thay_doi", "Q33_co_vai_tro_lanh_dao", "odds_ratio",
     "Có thay đổi vai trò giới → khả năng có vai trò lãnh đạo"),
    ("Rào cản ↔ kết quả", "Q29a", "Q9_derived_years_exp", "eta_squared",
     "Tự thấy có lợi ích khi tham gia trồng/bán dược liệu ↔ số năm kinh nghiệm"),
]

# (mô tả, biến số/ordinal, biến nhóm, loại test)
# 26/07: bỏ so sánh "theo tỉnh" (từng có ở đây: Q9_derived_years_exp giữa Lào Cai/Lai
# Châu) — quyết định của user, không cần so sánh giữa các vùng nữa. Xem
# [[project-survey-no-region-comparison]].
GROUP_COMPARISON_PAIRS: list[tuple[str, str, str, str]] = [
    ("Tuổi kết hôn giữa nhóm có/không đứng tên đất", "Q6_tuoi_ket_hon", "Q27a_dung_ten_dat", "mann_whitney"),
    ("Tỷ lệ thu nhập dược liệu (thang thứ bậc) giữa các nhóm dân tộc", "Q8_ordinal", "Q4", "kruskal_wallis"),
]
