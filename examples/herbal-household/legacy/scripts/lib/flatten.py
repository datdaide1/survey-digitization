"""Nổ 1 record output/full/*.json thành 2 dạng bảng phẳng:

- ``flatten_full``  — TOÀN BỘ field trong schema (kể cả Q1 PII, các câu tự luận thuần
  bị loại khỏi thống kê, PAGE_NOTES) — dùng cho sheet "Dữ liệu đã số hóa" (§10, có PII).
  Đi bằng cách duyệt schema/questionnaire_v1.json thay vì liệt kê tay, để không lệch
  khi schema đổi.
- ``flatten_stats`` — chỉ phạm vi §1 của docs/implement-plan-statistics-and-client-report.md
  (~99 cột: loại Q1, loại các câu tự luận thuần, loại META_LOCATION là biến — chỉ dùng
  province/commune từ manifest). Multi-select/device_grid nổ thành cột nhị phân theo
  option; matrix (Q14/Q32) giữ mỗi dòng là 1 cột categorical (không nổ theo cột) —
  đúng theo cách biểu diễn biểu đồ stacked-bar ở §11. Q2/Q5/Q6/Q9 áp dụng đúng công
  thức stats_bucketing trong scripts/lib/bucketing.py.

Phạm vi stats được liệt kê TƯỜNG MINH (không sinh tự động từ schema) vì mỗi field cần
quyết định thủ công: nổ nhị phân hay giữ categorical, có bucket hay không, có áp dụng
ngoại lệ Q4 (giữ tên dân tộc cụ thể thay vì gộp "khác") hay không.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import bucketing
from .records import as_code_list, as_single_category, get_value

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "questionnaire_v1.json"

# ---------------------------------------------------------------------------
# Phạm vi biến thống kê (§1) — nguồn: schema/questionnaire_v1.json + SCHEMA-FORMAT.md
# ---------------------------------------------------------------------------

# single_select đơn giản, không bucket, không subfield cần giữ riêng — dùng thẳng code.
# Q4 xử lý riêng bên dưới (ngoại lệ giữ other_text thay vì gộp "khac").
# Q3 (giới tính) CỐ Ý loại khỏi phạm vi thống kê (26/07, yêu cầu khách) — 100% phiếu là
# nữ, biến hằng số không mang thông tin, giữ lại sẽ chỉ tạo variance=0 gây nhiễu ma trận
# tương quan/factor analysis ở các tầng sau. Vẫn còn nguyên trong flatten_full (sheet
# "Dữ liệu đã số hóa", §10) — chỉ bỏ khỏi combined.csv/report thống kê.
SINGLE_SELECT_STATS_FIELDS = [
    "Q4", "Q8", "Q10", "Q12", "Q13", "Q16a", "Q20", "Q21a",
    "Q23", "Q24", "Q25", "Q26", "Q27a", "Q29a", "Q30",
]

MULTI_SELECT_FIELDS: dict[str, list[str]] = {
    "Q7": ["trong_trot", "chan_nuoi", "cay_duoc_lieu", "lam_nghiep", "phi_nong_nghiep"],
    "Q11": ["hoi_phu_nu", "doan_thanh_nien", "hoi_nong_dan", "khong_hoi_vien"],
    "Q18": [
        "goi_nhan_tin", "doc_tin_tuc", "giai_tri", "tim_kiem_thong_tin",
        "giao_dich_ban_hang", "lam_viec_hoc_online", "mang_xa_hoi", "khac",
    ],
    "Q19": ["quang_ba", "quan_ly_sx_tc", "ban_hang_online", "khong"],
    "Q21b": ["ky_thuat", "khac"],
    "Q22a": ["ngan_hang_thuong_mai", "ngan_hang_chinh_sach", "hoi_doan_the", "khac", "chua"],
    "Q22b": ["khong_co_nhu_cau", "thu_tuc_phuc_tap", "khong_tai_san_the_chap", "khac"],
    "Q28": [
        "thieu_nguon_luc", "thieu_kien_thuc", "ganh_nang_viec_nha", "khong_thi_truong",
        "tap_quan_dinh_kien", "khac", "khong_kho_khan",
    ],
    "Q29b": ["them_thu_nhap", "nang_cao_kien_thuc", "tham_gia_cong_dong"],
    "Q33": ["ban_chu_nhiem_htx", "nhom_san_xuat", "quan_ly_rung", "khong"],
}

MATRIX_ROW_FIELDS: dict[str, list[str]] = {
    "Q14": [
        "lam_dat", "trong", "cham_soc_cay", "thuoc_bvtv", "thu_hoach", "so_che",
        "lien_he_tieu_thu", "khac_san_xuat", "noi_tro", "giat_giu", "dua_don_con",
        "dam_cuoi_gio", "cham_soc_con", "gia_suc_nho", "gia_suc_lon",
        "quan_ly_chi_tieu", "day_do_con", "bao_duong_xe",
    ],
    "Q32": [
        "chon_cay_trong", "mua_vat_tu", "chon_ban", "vay_von", "gia_ban",
        "su_dung_thu_nhap", "su_dung_dat", "khac",
    ],
}

DEVICE_GRID_FIELDS: dict[str, dict[str, Any]] = {
    "Q17": {
        "rows": ["dien_thoai", "may_tinh", "may_tinh_bang"],
        "columns": ["chong", "vo"],
        "extra_option": "khong_ai_co",
    },
}

# 26/07: các câu tự luận viết tay thuần (đã loại khỏi phạm vi thống kê 25/07, xem
# docs/client-feedback-2026-07-25-freetext-skip-review.md) giờ cũng bỏ luôn khỏi
# flatten_full — không dùng vào đâu thì không cần dump nguyên văn chữ viết tay trong sheet
# "Dữ liệu đã số hóa" nữa. Q9 là ngoại lệ khác: bỏ câu trả lời chữ (lý do bắt đầu trồng)
# nhưng GIỮ 2 trường derived_subfield (Q9_derived_start_year, Q9_derived_years_exp) — 2 số
# này vẫn dùng cho thống kê nên không được đụng tới đoạn derived_subfield bên dưới.
FREETEXT_DROPPED_FROM_FULL_DUMP = {"Q9", "Q15", "Q16b", "Q21c", "Q27b", "Q29c", "Q31", "Q34"}

# 26/07 — yêu cầu khách: sheet "Dữ liệu đã số hóa" chỉ giữ mã phiếu + phần định danh
# (tên, địa điểm, giới tính) + các trường THẬT SỰ dùng cho thống kê, bỏ hết phần còn lại
# (không phải xoá dữ liệu — output/full/*.json vẫn giữ nguyên đầy đủ, chỉ sheet này thu
# hẹp cột hiển thị).
#
# - Giữ định danh dù không phải biến thống kê: record_id, Q1 (tên), META_LOCATION (địa
#   điểm), Q3 (giới tính — bị loại khỏi flatten_stats vì hằng số, nhưng khách muốn giữ
#   ở đây để nhận diện phiếu).
# - Bỏ hẳn: META_DATE, CONSENT_1, CONSENT_2 (không phải biến thống kê, không phải định
#   danh) và PAGE_NOTES (ghi chú lề tay, không dùng thống kê).
NON_STATS_META_DROPPED_FROM_FULL_DUMP = {"META_DATE", "CONSENT_1", "CONSENT_2"}

# other_text ("Khác, ghi rõ") — theo §2.4 client-feedback-2026-07-22, thống kê KHÔNG dùng
# nội dung chữ viết tay của "Khác" cho bất kỳ câu nào, TRỪ Q4 (dân tộc cụ thể được gộp
# thẳng vào giá trị Q4 khi thống kê — xem flatten_stats). Vì vậy other_text chỉ giữ cho
# Q4 trong sheet "Dữ liệu đã số hóa", các câu khác (Q10/Q12/Q13/Q20/Q21b/Q22a/Q22b/Q27a/
# Q28...) bỏ other_text.
OTHER_TEXT_KEPT_QIDS = {"Q4"}

# subfield/derived_subfield không thuộc phạm vi thống kê (Q16a_chi_tiet/Q23_chi_tiet:
# best-effort, Task 5; Q9_derived_start_year: 26/07, bỏ vì trùng lặp thông tin với
# Q9_derived_years_exp, xem flatten_stats) — khác Q6_tuoi_ket_hon (subfield của Q6, LÀ
# biến thống kê nên không nằm trong set này).
DROPPED_SUBFIELD_IDS = {"Q16a_chi_tiet", "Q23_chi_tiet", "Q9_derived_start_year"}


def _row_answer(field_answer: dict[str, Any] | None, row_code: str) -> dict[str, Any] | None:
    if not isinstance(field_answer, dict):
        return None
    rows = field_answer.get("rows")
    if not isinstance(rows, dict):
        return None
    return rows.get(row_code)


def flatten_stats(record: dict[str, Any], manifest_row: dict[str, str]) -> dict[str, Any]:
    """1 record -> 1 dict phẳng, phạm vi §1, dùng cho output/combined.csv."""
    answers = record.get("answers", {})
    row: dict[str, Any] = {
        "record_id": record["record_id"],
        "province": manifest_row["province"],
        "commune": manifest_row["commune"],
    }

    # --- Q2: tuổi (liên tục) + age_bracket ---
    birth_year = get_value(answers.get("Q2"))
    age = bucketing.age_from_birth_year(birth_year)
    row["Q2_tuoi"] = age
    row["age_bracket"] = bucketing.age_bracket(age)

    # --- single_select đơn giản (Q4 có ngoại lệ other_text) ---
    for qid in SINGLE_SELECT_STATS_FIELDS:
        answer = answers.get(qid)
        category = as_single_category(get_value(answer))
        if qid == "Q4":
            if category == "khac" and isinstance(answer, dict):
                other = answer.get("other_text")
                category = other if other else "khac"
            category = bucketing.normalize_ethnicity(category)
        row[qid] = category

    # --- Q5 composite: 3 tick vẫn thống kê % riêng (cột boolean độc lập) NHƯNG
    # education_grade_bracket giờ gộp lại 2 trong 3 tick (26/07, đảo lại quyết định
    # 25/07 — xem bucketing.education_grade_bracket): Q5_trung_cap_dh -> "thpt",
    # Q5_khong_di_hoc -> bucket riêng "khong_di_hoc", còn lại mới bucket theo
    # Q5_lop_cao_nhat như cũ.
    q5 = answers.get("Q5") or {}
    components = q5.get("components", {}) if isinstance(q5, dict) else {}
    khong_di_hoc = get_value(components.get("Q5_khong_di_hoc"))
    khong_tieng_pho_thong = get_value(components.get("Q5_khong_tieng_pho_thong"))
    trung_cap_dh = get_value(components.get("Q5_trung_cap_dh"))
    lop_cao_nhat = get_value(components.get("Q5_lop_cao_nhat"))
    row["Q5_khong_di_hoc"] = khong_di_hoc
    row["Q5_khong_tieng_pho_thong"] = khong_tieng_pho_thong
    row["Q5_trung_cap_dh"] = trung_cap_dh
    row["education_grade_bracket"] = bucketing.education_grade_bracket(lop_cao_nhat, khong_di_hoc, trung_cap_dh)

    # --- Q6: tình trạng hôn nhân + tuổi kết hôn (liên tục) + marriage_age_bracket ---
    q6 = answers.get("Q6") or {}
    row["Q6"] = as_single_category(get_value(q6))
    q6_subfield = q6.get("subfield", {}) if isinstance(q6, dict) else {}
    marriage_age_raw = get_value(q6_subfield.get("Q6_tuoi_ket_hon"))
    row["Q6_tuoi_ket_hon"] = bucketing.safe_float(marriage_age_raw)
    row["marriage_age_bracket"] = bucketing.marriage_age_bracket(marriage_age_raw)

    # --- Q9: số năm kinh nghiệm (liên tục) + experience_years_bracket ---
    # 26/07: BỎ Q9_derived_start_year khỏi phạm vi thống kê (quyết định user) — trùng lặp
    # thông tin với Q9_derived_years_exp (chỉ lệch nhau đúng 2026 - X), không cần thống kê
    # riêng cả 2. Vẫn giữ nguyên trong output/full/*.json (dữ liệu gốc đã trích xuất),
    # chỉ không đưa vào combined.csv/report thống kê nữa.
    q9 = answers.get("Q9") or {}
    derived = q9.get("derived_subfield", {}) if isinstance(q9, dict) else {}
    years_exp_raw = get_value(derived.get("Q9_derived_years_exp"))
    row["Q9_derived_years_exp"] = bucketing.safe_float(years_exp_raw)
    row["experience_years_bracket"] = bucketing.experience_years_bracket(years_exp_raw)

    # --- multi_select -> cột nhị phân theo option (None nếu câu chưa trả lời) ---
    for qid, options in MULTI_SELECT_FIELDS.items():
        answer = answers.get(qid)
        value = get_value(answer)
        codes = as_code_list(value) if value is not None else None
        for opt in options:
            row[f"{qid}_{opt}"] = None if codes is None else int(opt in codes)

    # --- matrix (Q14/Q32) -> mỗi dòng 1 cột categorical (khớp cách biểu diễn stacked bar) ---
    for qid, row_codes in MATRIX_ROW_FIELDS.items():
        field_answer = answers.get(qid)
        for row_code in row_codes:
            value = get_value(_row_answer(field_answer, row_code))
            row[f"{qid}_{row_code}"] = as_single_category(value)

    # --- device_grid (Q17) -> cột nhị phân theo (row, column) + extra_option ---
    for qid, spec in DEVICE_GRID_FIELDS.items():
        field_answer = answers.get(qid) or {}
        for row_code in spec["rows"]:
            cell_answer = _row_answer(field_answer, row_code)
            value = get_value(cell_answer)
            codes = as_code_list(value) if cell_answer is not None else None
            for col_code in spec["columns"]:
                col_name = f"{qid}_{row_code}_{col_code}"
                row[col_name] = None if codes is None else int(col_code in codes)
        extra_key = spec["extra_option"]
        row[f"{qid}_{extra_key}"] = field_answer.get(extra_key) if isinstance(field_answer, dict) else None

    return row


# ---------------------------------------------------------------------------
# flatten_full — dump toàn bộ schema (bao gồm PII), duyệt schema thay vì liệt kê tay
# ---------------------------------------------------------------------------

_schema_cache: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    global _schema_cache
    if _schema_cache is None:
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            _schema_cache = json.load(f)
    return _schema_cache


def _joined(value: Any) -> Any:
    """Dump giá trị thô dễ đọc cho sheet 'Dữ liệu đã số hóa' — list nối bằng '; '."""
    if value is None:
        return None
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return value


def flatten_full(record: dict[str, Any]) -> dict[str, Any]:
    """1 record -> 1 dict phẳng, TOÀN BỘ field trong schema (có PII) — dump nguyên văn,
    không bucket/không nổ nhị phân — dùng cho sheet "Dữ liệu đã số hóa" (§10)."""
    schema = _load_schema()
    answers = record.get("answers", {})
    row: dict[str, Any] = {"record_id": record["record_id"]}

    for question in schema["questions"]:
        qid = question["id"]
        qtype = question["type"]
        answer = answers.get(qid)

        if qid in NON_STATS_META_DROPPED_FROM_FULL_DUMP:
            continue

        if question.get("per_page"):
            # PAGE_NOTES — ghi chú tay ngoài vùng câu hỏi, không phải biến thống kê, bỏ
            # khỏi sheet "Dữ liệu đã số hóa" (vẫn còn nguyên trong output/full/*.json).
            continue

        if qtype == "composite":
            components = (answer or {}).get("components", {}) if isinstance(answer, dict) else {}
            for component in question["components"]:
                cid = component["id"]
                row[cid] = _joined(get_value(components.get(cid)))
            continue

        if qtype == "matrix":
            rows_def = question["rows"]
            for row_def in rows_def:
                if "group_header" in row_def:
                    continue
                row_code = row_def["code"]
                cell = _row_answer(answer, row_code)
                row[f"{qid}_{row_code}"] = _joined(get_value(cell))
            content_col = question.get("row_content_column")
            if content_col and not content_col.get("skip_extraction"):
                for row_def in rows_def:
                    if "group_header" in row_def:
                        continue
                    row_code = row_def["code"]
                    cell = _row_answer(answer, row_code)
                    if isinstance(cell, dict):
                        row[f"{qid}_{row_code}_{content_col['code']}"] = cell.get(content_col["code"])
            continue

        if qtype == "device_grid":
            for row_def in question["rows"]:
                row_code = row_def["code"]
                cell = _row_answer(answer, row_code)
                row[f"{qid}_{row_code}"] = _joined(get_value(cell))
            extra = question.get("extra_option")
            if extra:
                row[f"{qid}_{extra['code']}"] = (answer or {}).get(extra["code"]) if isinstance(answer, dict) else None
            continue

        # text / free_text / single_select / multi_select
        if qid not in FREETEXT_DROPPED_FROM_FULL_DUMP:
            row[qid] = _joined(get_value(answer))
        if isinstance(answer, dict):
            if qid in OTHER_TEXT_KEPT_QIDS and answer.get("other_text") is not None:
                row[f"{qid}_other_text"] = answer["other_text"]
            subfield = answer.get("subfield")
            if isinstance(subfield, dict):
                for sub_id, sub_answer in subfield.items():
                    if sub_id in DROPPED_SUBFIELD_IDS:
                        continue
                    row[sub_id] = _joined(get_value(sub_answer))
            derived = answer.get("derived_subfield")
            if isinstance(derived, dict):
                for sub_id, sub_answer in derived.items():
                    if sub_id in DROPPED_SUBFIELD_IDS:
                        continue
                    row[sub_id] = _joined(get_value(sub_answer))

    return row
