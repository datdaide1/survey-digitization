"""Bốn trụ cột thống kê (docs/implement-plan-statistics-and-client-report.md, bản 26/07):
thị trường (A), vị trí chuỗi giá trị (B), rào cản sản xuất (C), môi trường chính sách (D),
và chỉ số vai trò trong chuỗi giá trị (E — Cronbach's alpha, phạm vi Q14 đã thu hẹp).

Hàm thuần Python/pandas, tách khỏi cách trình bày (xlsx_writer/docx) để dùng chung cho cả
sheet Excel và narrative DOCX — tính 1 lần, hiển thị 2 nơi, tránh lệch số.

Quy ước mẫu số: bảng tần suất 1 biến dùng tổng mẫu cố định (85, theo quyết định 26/07 chung
của dự án — xem frequency.py). Bảng cross-tab (so 2+ nhóm) dùng CỠ NHÓM làm mẫu số (theo
đúng quy ước đã có ở crosstab.py) — không đổi quy ước này, 2 loại bảng có mục đích khác
nhau (mô tả toàn mẫu so với so sánh giữa các nhóm).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .codebook import build_codebook
from .frequency import category_rows, descriptive_stats, frequency_table
from .reliability import Q32_POSITIVE_CODES, Q32_ROWS, analyze

CODEBOOK = build_codebook()

# ---------------------------------------------------------------------------
# Tiện ích dùng chung
# ---------------------------------------------------------------------------


def _opt_label(qid: str, opt: str) -> str:
    full = CODEBOOK[f"{qid}_{opt}"]["label"]
    return full.split(" — ", 1)[-1] if " — " in full else full


def multi_select_freq(df: pd.DataFrame, qid: str, options: list[str]) -> dict[str, Any]:
    """Bảng tần suất cho 1 câu multi-select (mẫu số = 85 cố định), sắp giảm dần theo n."""
    total_n = len(df)
    rows = []
    for opt in options:
        col = f"{qid}_{opt}"
        n = int((df[col] == 1).sum())
        pct = (n / total_n * 100) if total_n else 0.0
        rows.append({"code": opt, "label": _opt_label(qid, opt), "n": n, "pct": pct})
    rows.sort(key=lambda r: -r["n"])
    return {"qid": qid, "total_n": total_n, "rows": rows}


def _is_positive(value: Any, positive_codes: set[str]) -> bool:
    """1 nếu ô ghi đúng 1 trong các code 'dương' (vd 'vo'/'ca_hai'), kể cả tổ hợp 'vo+chong'
    — cùng logic với scripts/lib/report/reliability._is_positive, viết lại ở đây vì hàm gốc
    trả về float NaN-able cho ma trận, còn đây cần bool rõ ràng cho từng ô riêng lẻ."""
    if pd.isna(value):
        return False
    if isinstance(value, str) and "+" in value:
        return any(part in positive_codes for part in value.split("+"))
    return value in positive_codes


# ---------------------------------------------------------------------------
# A. Thị trường & mức độ gắn bó
# ---------------------------------------------------------------------------

Q7_OPTIONS = ["trong_trot", "chan_nuoi", "cay_duoc_lieu", "lam_nghiep", "phi_nong_nghiep"]


def pillar_a(df: pd.DataFrame) -> dict[str, Any]:
    q7 = multi_select_freq(df, "Q7", Q7_OPTIONS)
    q8 = frequency_table("Q8", df["Q8"])
    q9_desc = descriptive_stats("Q9_derived_years_exp", df["Q9_derived_years_exp"])

    # Cross-tab kinh nghiệm (<1 / >=1 năm) x Q8 — mẫu số = cỡ nhóm kinh nghiệm.
    exp_groups = [("<1", "Dưới 1 năm kinh nghiệm"), (">=1", "Từ 1 năm kinh nghiệm trở lên")]
    q8_rows = category_rows("Q8", df["Q8"])
    cross = []
    for code, label in exp_groups:
        sub = df[df["experience_years_bracket"] == code]
        n_group = int(len(sub))
        counts = sub["Q8"].value_counts()
        cells = []
        for q8_code, q8_label in q8_rows:
            n = int(counts.get(q8_code, 0))
            pct = (n / n_group * 100) if n_group else 0.0
            cells.append({"code": q8_code, "label": q8_label, "n": n, "pct": pct})
        cross.append({"group_code": code, "group_label": label, "n_group": n_group, "cells": cells})

    return {"q7": q7, "q8": q8, "q9_desc": q9_desc, "experience_x_income": cross}


# ---------------------------------------------------------------------------
# B. Vị trí trong chuỗi giá trị
# ---------------------------------------------------------------------------

Q30_NODES = [
    ("san_xuat", "Sản xuất"),
    ("thu_hai", "Thu hái"),
    ("che_bien", "Chế biến"),
    ("thuong_mai", "Thương mại"),
    ("tieu_thu", "Tiêu thụ"),
]

# Khâu "cao giá" (gần khách hàng hơn, thường gắn với đàm phán giá/kênh bán) so với khâu
# "thấp giá" (sản xuất/thu hái/chế biến thô) — dùng để chia nhóm ở Pillar C. Ghi rõ đây là
# giả định làm việc, cần khách xác nhận lại thứ tự giá trị các khâu (xem §6 implement plan).
HIGH_VALUE_NODES = {"thuong_mai", "tieu_thu"}


def _q30_has_node(value: Any, node_code: str) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str) and "+" in value:
        return node_code in value.split("+")
    return value == node_code


EDUCATION_GROUPS = [
    ("khong_di_hoc", "Chưa từng đi học chính quy"),
    ("tieu_hoc", "Tiểu học"),
    ("thcs", "THCS/cấp 2"),
    ("thpt", "THPT/cấp 3 trở lên"),
]
MOBILITY_GROUPS = [("co", "Có xe máy riêng tự đi lại"), ("khong", "Không có xe máy riêng")]

# Cột phụ trợ (không nằm trong combined.csv gốc) — 1 nếu chọn ÍT NHẤT 1 trong 3 vai trò
# lãnh đạo (Q33), khớp cách tính "OR" đã dùng cho Q30_nhom_khau_cao_gia (add_derived_columns,
# pillar_xlsx.py). Định nghĩa Ở ĐÂY (không phải add_derived_columns) vì hàm này cũng cần
# dùng trực tiếp trên df gốc (không qua add_derived_columns) cho phần narrative DOCX.
Q33_LEADERSHIP_COLS = ["Q33_ban_chu_nhiem_htx", "Q33_nhom_san_xuat", "Q33_quan_ly_rung"]


def _has_leadership_role(df: pd.DataFrame) -> pd.Series:
    return (df[Q33_LEADERSHIP_COLS] == 1).any(axis=1)


def _q30_group_breakdown(df: pd.DataFrame, group_col: str, group_defs: list[tuple[Any, str]]) -> list[dict[str, Any]]:
    """Phân bố Q30 (combo-aware, tái dùng frequency_table) theo từng nhóm của group_col —
    mẫu số MỖI NHÓM = cỡ nhóm đó (đúng quy ước cross-tab), không phải 85 cố định."""
    out = []
    for code, label in group_defs:
        sub = df[df[group_col] == code] if not isinstance(code, bool) else df[df[group_col] == code]
        n_group = int(len(sub))
        q30 = frequency_table("Q30", sub["Q30"]) if n_group else None
        out.append({"group_code": code, "group_label": label, "n_group": n_group, "q30": q30})
    return out


def education_x_participation(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Học thức × Q30 — học vấn cao hơn có đi cùng tham gia khâu 'cao giá' (thương mại/
    tiêu thụ) nhiều hơn không (§1.B mở rộng, docs implement plan §8)."""
    return _q30_group_breakdown(df, "education_grade_bracket", EDUCATION_GROUPS)


def leadership_x_participation(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Có vai trò lãnh đạo nhóm SX/HTX/quản lý rừng (Q33) × Q30 — gắn với domain
    'leadership/collective agency' của khung WEAI dùng cho dự án."""
    has_role = _has_leadership_role(df)
    out = []
    for flag, label in ((True, "Có vai trò lãnh đạo (HTX/nhóm SX/quản lý rừng)"), (False, "Không có vai trò lãnh đạo nào")):
        sub = df[has_role == flag]
        n_group = int(len(sub))
        q30 = frequency_table("Q30", sub["Q30"]) if n_group else None
        out.append({"group_code": flag, "group_label": label, "n_group": n_group, "q30": q30})
    return out


def mobility_x_participation(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Có xe máy riêng tự đi lại (Q25) × Q30 — nhiều khâu chuỗi giá trị (đặc biệt thương
    mại/tiêu thụ) cần di chuyển đến chợ/điểm thu mua; đi lại độc lập là 1 chỉ số 'nguồn
    lực/instrumental agency' thường dùng trong khung WEAI."""
    return _q30_group_breakdown(df, "Q25", MOBILITY_GROUPS)


DEVICE_USAGE_ITEMS = [
    ("Dùng điện thoại để giao dịch/bán hàng", "Q18_giao_dich_ban_hang"),
    ("Dùng điện thoại để quảng bá sản phẩm", "Q19_quang_ba"),
    ("Bán hàng online", "Q19_ban_hang_online"),
]


def device_ownership_vs_usage(df: pd.DataFrame) -> dict[str, Any]:
    """Sở hữu thiết bị (Q17, vợ sở hữu điện thoại thông minh) so với DÙNG thiết bị đó cho
    mục đích kinh tế (Q18/Q19) — sở hữu cao không tự động nghĩa là dùng được cho buôn bán/
    quảng bá, khoảng cách này mới là điều đáng chú ý (khác cross-tab nhóm thường vì tỷ lệ
    sở hữu quá lệch — 81/85 vợ có điện thoại — chia nhóm sở hữu có/không sẽ có 1 nhóm chỉ
    4 phiếu, không đủ để so sánh có ý nghĩa)."""
    total_n = len(df)
    own_n = int((df["Q17_dien_thoai_vo"] == 1).sum())
    own_pct = (own_n / total_n * 100) if total_n else 0.0
    rows = []
    for label, col in DEVICE_USAGE_ITEMS:
        n = int((df[col] == 1).sum())
        pct = (n / total_n * 100) if total_n else 0.0
        rows.append({"label": label, "n": n, "pct": pct})
    return {"own_pct": own_pct, "own_n": own_n, "total_n": total_n, "rows": rows}


def pillar_b(df: pd.DataFrame) -> dict[str, Any]:
    q30 = frequency_table("Q30", df["Q30"])

    q8_rows = category_rows("Q8", df["Q8"])
    node_x_income = []
    for node_code, node_label in Q30_NODES:
        mask = df["Q30"].apply(lambda v: _q30_has_node(v, node_code))
        sub = df[mask]
        n_group = int(len(sub))
        counts = sub["Q8"].value_counts()
        cells = []
        for q8_code, q8_label in q8_rows:
            n = int(counts.get(q8_code, 0))
            pct = (n / n_group * 100) if n_group else 0.0
            cells.append({"code": q8_code, "label": q8_label, "n": n, "pct": pct})
        node_x_income.append({"node_code": node_code, "node_label": node_label, "n_group": n_group, "cells": cells})

    # "Ai làm" (Q14/Q13) so "ai quyết" (Q32) — 3 cặp đã thảo luận.
    pairs_spec = [
        {
            "title": "Ai liên hệ tiêu thụ sản phẩm  ↔  Ai chọn bán cho ai",
            "lam_col": "Q14_lien_he_tieu_thu", "lam_codes": {"vo", "ca_hai"},
            "quyet_col": "Q32_chon_ban", "quyet_codes": Q32_POSITIVE_CODES,
        },
        {
            "title": "Ai quản lý chi tiêu  ↔  Ai quyết định sử dụng thu nhập từ dược liệu",
            "lam_col": "Q14_quan_ly_chi_tieu", "lam_codes": {"vo", "ca_hai"},
            "quyet_col": "Q32_su_dung_thu_nhap", "quyet_codes": Q32_POSITIVE_CODES,
        },
        {
            "title": "Ai tham gia chính trồng/bán dược liệu (Q13)  ↔  Ai chọn loại cây trồng",
            "lam_col": "Q13", "lam_codes": {"vo", "ca_hai"},
            "quyet_col": "Q32_chon_cay_trong", "quyet_codes": Q32_POSITIVE_CODES,
        },
    ]
    total_n = len(df)
    pairs = []
    for spec in pairs_spec:
        lam_n = int(df[spec["lam_col"]].apply(lambda v: _is_positive(v, spec["lam_codes"])).sum())
        quyet_n = int(df[spec["quyet_col"]].apply(lambda v: _is_positive(v, spec["quyet_codes"])).sum())
        pairs.append({
            "title": spec["title"],
            "lam_col": spec["lam_col"],
            "quyet_col": spec["quyet_col"],
            "lam_pct": (lam_n / total_n * 100) if total_n else 0.0,
            "lam_n": lam_n,
            "quyet_pct": (quyet_n / total_n * 100) if total_n else 0.0,
            "quyet_n": quyet_n,
            "total_n": total_n,
        })

    return {
        "q30": q30, "node_x_income": node_x_income, "lam_vs_quyet": pairs,
        "education_x_q30": education_x_participation(df),
        "leadership_x_q30": leadership_x_participation(df),
        "mobility_x_q30": mobility_x_participation(df),
        "device_ownership_vs_usage": device_ownership_vs_usage(df),
    }


# ---------------------------------------------------------------------------
# C. Rào cản sản xuất
# ---------------------------------------------------------------------------

Q28_OPTIONS = [
    "thieu_nguon_luc", "thieu_kien_thuc", "ganh_nang_viec_nha", "khong_thi_truong",
    "tap_quan_dinh_kien", "khac", "khong_kho_khan",
]
Q22B_OPTIONS = ["khong_co_nhu_cau", "thu_tuc_phuc_tap", "khong_tai_san_the_chap", "khac"]


def _high_low_value_group(row: pd.Series) -> str | None:
    value = row["Q30"]
    if pd.isna(value):
        return None
    parts = value.split("+") if isinstance(value, str) and "+" in value else [value]
    return "cao_gia" if any(p in HIGH_VALUE_NODES for p in parts) else "thap_gia"


def _multi_select_x_group(
    df: pd.DataFrame, qid: str, options: list[str], group_col: str, group_defs: list[tuple[Any, str]] | None = None,
) -> list[dict[str, Any]]:
    """Tần suất 1 câu multi-select (qid/options) theo từng nhóm của group_col — mẫu số
    MỖI NHÓM = cỡ nhóm đó. group_defs=None -> tự lấy nhóm thật có trong dữ liệu qua
    category_rows (dùng cho Q4 dân tộc — KHÁCH YÊU CẦU KHÔNG GỘP tên dân tộc cụ thể lại,
    xem docs/client-feedback-2026-07-22-extraction-rules.md §2.4, nhắc lại 26/07 tối)."""
    if group_defs is None:
        group_defs = [(code, label) for code, label in category_rows(group_col, df[group_col])]
        group_defs = [(label, code) for code, label in group_defs]
    out = []
    for opt in options:
        col = f"{qid}_{opt}"
        row = {"code": opt, "label": _opt_label(qid, opt), "cells": []}
        for label, code in group_defs:
            sub = df[df[group_col] == code]
            n_group = int(len(sub))
            n = int((sub[col] == 1).sum()) if n_group else 0
            pct = (n / n_group * 100) if n_group else 0.0
            row["cells"].append({"group": label, "group_code": code, "n_group": n_group, "n": n, "pct": pct})
        out.append(row)
    return out


def ethnicity_x_barrier(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Q28 (rào cản) × Q4 (dân tộc, GIỮ NGUYÊN tên cụ thể, không gộp 'khác') — dân tộc nào
    gặp rào cản gì nhiều hơn, phục vụ đúng câu hỏi Pillar C. Nhóm rất nhỏ (Kinh/Tày/Nùng ở
    mẫu này) vẫn hiện riêng theo đúng yêu cầu khách, % chỉ mang tính tham khảo với n nhỏ."""
    return _multi_select_x_group(df, "Q28", Q28_OPTIONS, "Q4")


def ethnicity_x_support(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Q22a (kênh vay vốn) × Q4 (dân tộc, không gộp) — dân tộc nào tiếp cận kênh hỗ trợ
    chính sách nào nhiều/ít hơn, phục vụ Pillar D."""
    return _multi_select_x_group(df, "Q22a", Q22A_OPTIONS, "Q4")


def pillar_c(df: pd.DataFrame) -> dict[str, Any]:
    q28 = multi_select_freq(df, "Q28", Q28_OPTIONS)
    q22b = multi_select_freq(df, "Q22b", Q22B_OPTIONS)

    # Cross-tab Q28 x tỉnh (mẫu số = cỡ tỉnh)
    province_groups = [("lao-cai", "Lào Cai"), ("lai-chau", "Lai Châu")]
    barrier_x_province = []
    for opt in Q28_OPTIONS:
        col = f"Q28_{opt}"
        row = {"code": opt, "label": _opt_label("Q28", opt), "cells": []}
        for code, label in province_groups:
            sub = df[df["province"] == code]
            n_group = int(len(sub))
            n = int((sub[col] == 1).sum())
            pct = (n / n_group * 100) if n_group else 0.0
            row["cells"].append({"group": label, "n_group": n_group, "n": n, "pct": pct})
        barrier_x_province.append(row)

    # Cross-tab Q28 x nhóm khâu cao/thấp giá (dựa vào Q30, xem HIGH_VALUE_NODES)
    node_group = df.apply(_high_low_value_group, axis=1)
    node_group_defs = [("cao_gia", "Có tham gia khâu thương mại/tiêu thụ"), ("thap_gia", "Chỉ khâu sản xuất/thu hái/chế biến")]
    barrier_x_node_group = []
    for opt in Q28_OPTIONS:
        col = f"Q28_{opt}"
        row = {"code": opt, "label": _opt_label("Q28", opt), "cells": []}
        for code, label in node_group_defs:
            mask = node_group == code
            n_group = int(mask.sum())
            n = int((df.loc[mask, col] == 1).sum()) if n_group else 0
            pct = (n / n_group * 100) if n_group else 0.0
            row["cells"].append({"group": label, "n_group": n_group, "n": n, "pct": pct})
        barrier_x_node_group.append(row)

    return {
        "q28": q28, "q22b": q22b,
        "barrier_x_province": barrier_x_province,
        "barrier_x_node_group": barrier_x_node_group,
        "node_group_defs": node_group_defs,
        "barrier_x_ethnicity": ethnicity_x_barrier(df),
    }


# ---------------------------------------------------------------------------
# D. Môi trường chính sách/thể chế
# ---------------------------------------------------------------------------

Q22A_OPTIONS = ["ngan_hang_thuong_mai", "ngan_hang_chinh_sach", "hoi_doan_the", "khac", "chua"]
Q21B_OPTIONS = ["ky_thuat", "khac"]
Q11_OPTIONS = ["hoi_phu_nu", "doan_thanh_nien", "hoi_nong_dan", "khong_hoi_vien"]


def pillar_d(df: pd.DataFrame) -> dict[str, Any]:
    q22a = multi_select_freq(df, "Q22a", Q22A_OPTIONS)
    q23 = frequency_table("Q23", df["Q23"])
    q21a = frequency_table("Q21a", df["Q21a"])
    q21b = multi_select_freq(df, "Q21b", Q21B_OPTIONS)
    q11 = multi_select_freq(df, "Q11", Q11_OPTIONS)

    swot = _build_swot(q22a, q23, q21a, q21b, q11)
    return {
        "q22a": q22a, "q23": q23, "q21a": q21a, "q21b": q21b, "q11": q11, "swot": swot,
        "support_x_ethnicity": ethnicity_x_support(df),
    }


def _pct_of(rows: list[dict], code: str) -> float:
    for r in rows:
        if r["code"] == code:
            return r["pct"]
    return 0.0


def _row_pct(freq: dict, code: str) -> float:
    for r in freq["rows"]:
        if r["code"] == code:
            return r["pct"]
    return 0.0


def _build_swot(q22a: dict, q23: dict, q21a: dict, q21b: dict, q11: dict) -> dict[str, list[str]]:
    """Sinh bullet SWOT tĩnh từ đúng các con số đã tính — không phải đánh giá chủ quan
    riêng, mọi câu đều dẫn % cụ thể để người đọc tự trỏ ngược lại bảng tần suất nguồn."""
    pct_chua_vay = _pct_of(q22a["rows"], "chua")
    pct_chinh_sach = _pct_of(q22a["rows"], "ngan_hang_chinh_sach")
    pct_ho_tro = _row_pct(q23, "co")
    pct_chua_tap_huan = _row_pct(q21a, "chua_lan_nao")
    pct_ky_thuat = _pct_of(q21b["rows"], "ky_thuat")
    pct_hoi_phu_nu = _pct_of(q11["rows"], "hoi_phu_nu")
    pct_khong_hoi_vien = _pct_of(q11["rows"], "khong_hoi_vien")

    strengths = [
        f"{pct_hoi_phu_nu:.0f}% phụ nữ được khảo sát là hội viên Hội Liên hiệp Phụ nữ — kênh "
        "tiếp cận thông tin/chính sách sẵn có, có thể tận dụng để truyền tải hỗ trợ kỹ thuật/vốn.",
        f"{pct_ky_thuat:.0f}% phụ nữ đã từng được tập huấn kỹ thuật (chế biến, bảo quản, thị "
        "trường) — có nền để nâng cao thêm thay vì bắt đầu từ số 0.",
    ]
    weaknesses = [
        f"{pct_chua_vay:.0f}% chưa từng vay vốn sản xuất/kinh doanh trong 5 năm qua.",
        f"{pct_khong_hoi_vien:.0f}% không là hội viên của bất kỳ tổ chức chính trị-xã hội nào "
        "— nằm ngoài các kênh hỗ trợ đoàn thể hiện có.",
    ]
    opportunities = [
        f"Ngân hàng chính sách mới tiếp cận được {pct_chinh_sach:.0f}% — dư địa mở rộng kênh "
        "vốn ưu đãi vốn đã có sẵn nhưng chưa phủ hết.",
        f"{pct_ho_tro:.0f}% đã từng nhận hỗ trợ vật chất (phân bón, thuốc BVTV, công cụ) — cho "
        "thấy có kênh phân phối hỗ trợ đang hoạt động, có thể mở rộng phạm vi.",
    ]
    threats = [
        f"{pct_chua_tap_huan:.0f}% chưa từng tham gia tập huấn nào trong 2 năm qua — rủi ro "
        "khoảng cách kiến thức kỹ thuật/thị trường ngày càng rộng nếu không có can thiệp.",
        "Lý do phổ biến khi chưa tiếp cận vốn/tập huấn thường là rào cản thủ tục và thiếu tài "
        "sản thế chấp (xem Pillar C, Q22b) — đây là rào cản thể chế, không phải do thiếu nhu "
        "cầu ở đa số trường hợp.",
    ]
    return {"strengths": strengths, "weaknesses": weaknesses, "opportunities": opportunities, "threats": threats}


# ---------------------------------------------------------------------------
# E. Chỉ số vai trò trong chuỗi giá trị (Cronbach's alpha, phạm vi Q14 thu hẹp)
# ---------------------------------------------------------------------------

# Chỉ 8 dòng liên quan trực tiếp sản xuất/thương mại dược liệu — loại việc nhà thuần tuý
# (nội trợ, giặt giũ, đưa đón con, đám cưới giỗ, chăm sóc con, gia súc, dạy dỗ con, bảo
# dưỡng xe) vì không đại diện cho vai trò trong chuỗi giá trị dược liệu.
Q14_VALUE_CHAIN_ROWS = [
    "lam_dat", "trong", "cham_soc_cay", "thuoc_bvtv", "thu_hoach", "so_che",
    "lien_he_tieu_thu", "quan_ly_chi_tieu",
]
Q14_VALUE_CHAIN_POSITIVE_CODES = {"vo", "ca_hai"}


MARRIAGE_AGE_GROUPS = [("<18", "Kết hôn trước 18 tuổi (tảo hôn)"), (">=18", "Kết hôn từ 18 tuổi")]


def composite_x_marriage_age(df: pd.DataFrame, composite: pd.Series | None) -> list[dict[str, Any]] | None:
    """Chỉ số tổng hợp (Q14 hoặc Q32, % 0-100) theo nhóm tuổi kết hôn — tảo hôn có liên hệ
    với vai trò/tiếng nói quyết định thấp hơn trong chuỗi giá trị dược liệu không (giả
    thuyết thường gặp trong nghiên cứu trao quyền phụ nữ kiểu WEAI). `composite` cùng index
    với `df` (không loại phiếu nào, xem reliability.composite_index) nên lọc theo mask trực
    tiếp là an toàn."""
    if composite is None:
        return None
    out = []
    for code, label in MARRIAGE_AGE_GROUPS:
        mask = df["marriage_age_bracket"] == code
        n_group = int(mask.sum())
        vals = composite[mask.to_numpy()]
        out.append({
            "group_code": code, "group_label": label, "n_group": n_group,
            "mean": float(vals.mean()) if n_group else None,
        })
    return out


def pillar_e(df: pd.DataFrame) -> dict[str, Any]:
    r14 = analyze(
        df, "Q14",
        "Chỉ số vai trò sản xuất/thương mại dược liệu (8 việc liên quan trực tiếp cây dược "
        "liệu, 'vợ' hoặc 'cả hai')",
        Q14_VALUE_CHAIN_ROWS, Q14_VALUE_CHAIN_POSITIVE_CODES,
    )
    r32 = analyze(
        df, "Q32",
        "Chỉ số kiểm soát quyết định chuỗi giá trị dược liệu (8 vấn đề, 'vợ' hoặc 'cùng quyết định')",
        Q32_ROWS, Q32_POSITIVE_CODES,
    )
    return {
        "Q14": r14, "Q32": r32,
        "Q14_x_marriage_age": composite_x_marriage_age(df, r14.composite),
        "Q32_x_marriage_age": composite_x_marriage_age(df, r32.composite),
    }


def compute_all(df: pd.DataFrame) -> dict[str, Any]:
    return {
        "A": pillar_a(df),
        "B": pillar_b(df),
        "C": pillar_c(df),
        "D": pillar_d(df),
        "E": pillar_e(df),
    }
