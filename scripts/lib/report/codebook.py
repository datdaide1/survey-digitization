"""Metadata (nhãn tiếng Việt, loại biến, danh sách lựa chọn) cho từng cột trong
output/combined.csv — sinh từ schema/questionnaire_v1.json + các constant phạm vi
thống kê trong scripts/lib/flatten.py, KHÔNG liệt kê tay lần 2 để tránh lệch.

4 "kind" của 1 cột:
- "continuous"  — Q2_tuoi, Q6_tuoi_ket_hon, Q9_derived_years_exp.
- "binary"      — cột nổ từ multi_select/device_grid (giá trị 0/1/None).
- "boolean"     — cột Python bool/None (Q5 3 component, Q17 khong_ai_co).
- "categorical" — mọi trường hợp còn lại (single_select, bucket, matrix row, province/commune).

``options`` là list[(code, label)] cố định lấy từ schema khi biết trước (vd single_select
thường, bucket). Để None khi tập giá trị không cố định trước (Q4 dân tộc cụ thể, matrix
row có thể multi-mark) — lúc đó bảng tần suất phải tự lấy danh sách giá trị PHÂN BIỆT
xuất hiện thật trong dữ liệu (xem scripts/lib/report/frequency.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..flatten import (
    DEVICE_GRID_FIELDS,
    MATRIX_ROW_FIELDS,
    MULTI_SELECT_FIELDS,
    SINGLE_SELECT_STATS_FIELDS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "questionnaire_v1.json"

BUCKET_OPTIONS: dict[str, list[tuple[str, str]]] = {
    "age_bracket": [("<35", "Dưới 35 tuổi"), ("35-45", "35–45 tuổi"), (">45", "Trên 45 tuổi")],
    # 26/07 — gộp lại 2 trong 3 tick vào bucket này (đảo lại quyết định tách riêng
    # 25/07, xem docs/client-feedback-2026-07-25-q5-grade-split.md và
    # bucketing.education_grade_bracket): Q5_trung_cap_dh -> "thpt", Q5_khong_di_hoc ->
    # bucket riêng "khong_di_hoc". Q5_khong_tieng_pho_thong vẫn KHÔNG gộp (thống kê %
    # độc lập, xem docx_writer "Trình độ học vấn").
    "education_grade_bracket": [
        ("khong_di_hoc", "Chưa từng đi học chính quy"),
        ("tieu_hoc", "Học hết tiểu học (chưa học xong lớp 9)"),
        ("thcs", "Học hết THCS/cấp 2 (xong lớp 9, chưa xong lớp 12)"),
        ("thpt", "Học hết THPT/cấp 3 trở lên (xong lớp 12, gồm cả trung cấp/cao đẳng/đại học)"),
    ],
    "marriage_age_bracket": [("<18", "Kết hôn trước 18 tuổi (tảo hôn)"), (">=18", "Kết hôn từ 18 tuổi")],
    "experience_years_bracket": [("<1", "Dưới 1 năm kinh nghiệm"), (">=1", "Từ 1 năm kinh nghiệm trở lên")],
}

# 26/07 — đổi từ nguyên văn câu hỏi (q["text"]) sang tên ngắn gọn kèm số thứ tự câu
# (Qxx), theo yêu cầu khách: bảng/biểu đồ không cần chép lại nguyên văn câu hỏi dài,
# chỉ cần tên đủ hiểu + số câu để đối chiếu ngược lại phiếu gốc/schema khi cần.
# 26/07: bỏ Q9_derived_start_year (trùng lặp thông tin với Q9_derived_years_exp — chỉ
# lệch nhau đúng 2026 - X, quyết định user, xem flatten.py).
CONTINUOUS_LABELS: dict[str, str] = {
    "Q2_tuoi": "Q2 – Tuổi (tính đến 2026)",
    "Q6_tuoi_ket_hon": "Q6 – Tuổi kết hôn",
    "Q9_derived_years_exp": "Q9 – Số năm kinh nghiệm trồng cây dược liệu (tính đến 2026)",
}

Q5_BOOLEAN_LABELS: dict[str, str] = {
    "Q5_khong_di_hoc": "Q5 – Không đi học",
    "Q5_khong_tieng_pho_thong": "Q5 – Không nói được tiếng phổ thông",
    "Q5_trung_cap_dh": "Q5 – Trung cấp/Cao đẳng/Đại học",
}

# Tên ngắn cho từng câu hỏi single/multi-select, ma trận, device-grid — thay cho
# q["text"] nguyên văn. Luôn ghép "Qxx – " phía trước khi dùng (xem build_codebook).
SHORT_LABELS: dict[str, str] = {
    "Q4": "Dân tộc",
    "Q6": "Tình trạng hôn nhân",
    "Q7": "Nguồn thu nhập chính",
    "Q8": "Tỷ lệ thu nhập từ dược liệu",
    "Q10": "Nghề nghiệp chính",
    "Q11": "Hội đoàn thể tham gia",
    "Q12": "Ai làm chính việc nhà",
    "Q13": "Ai tham gia chính trồng/bán dược liệu",
    "Q14": "Phân công lao động trong gia đình",
    "Q16a": "Thay đổi vai trò giới",
    "Q17": "Sở hữu thiết bị",
    "Q18": "Mục đích dùng thiết bị",
    "Q19": "Ứng dụng công nghệ trong sản xuất/kinh doanh",
    "Q20": "Ai tham gia hội họp/tập huấn",
    "Q21a": "Tần suất tham gia tập huấn",
    "Q21b": "Nội dung tập huấn",
    "Q22a": "Vay vốn sản xuất/kinh doanh",
    "Q22b": "Lý do chưa vay vốn",
    "Q23": "Nhận hỗ trợ vật chất",
    "Q24": "Biết đi xe máy",
    "Q25": "Có xe máy riêng",
    "Q26": "Phải xin phép khi tham gia hoạt động xã hội",
    "Q27a": "Ai đứng tên quyền sử dụng đất",
    "Q28": "Khó khăn khi trồng/kinh doanh dược liệu",
    "Q29a": "Lợi ích từ trồng/bán dược liệu",
    "Q29b": "Lợi ích cụ thể",
    "Q30": "Khâu tham gia trong chuỗi giá trị",
    "Q32": "Ai quyết định các vấn đề trong gia đình",
    "Q33": "Vai trò lãnh đạo",
}


def _qlabel(qid: str) -> str:
    return f"{qid} – {SHORT_LABELS[qid]}"


def _load_schema() -> dict[str, Any]:
    with open(_SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def build_codebook() -> dict[str, dict[str, Any]]:
    schema = _load_schema()
    questions = {q["id"]: q for q in schema["questions"]}
    codebook: dict[str, dict[str, Any]] = {}

    codebook["province"] = {"kind": "categorical", "label": "Tỉnh", "options": None, "section": "META"}
    codebook["commune"] = {"kind": "categorical", "label": "Xã", "options": None, "section": "META"}

    _CONTINUOUS_SECTION = {
        "Q2_tuoi": "A", "Q6_tuoi_ket_hon": "A", "Q9_derived_years_exp": "A",
    }
    for col, label in CONTINUOUS_LABELS.items():
        codebook[col] = {"kind": "continuous", "label": label, "options": None, "section": _CONTINUOUS_SECTION[col]}

    _BUCKET_SECTION = {
        "age_bracket": "A", "education_grade_bracket": "A",
        "marriage_age_bracket": "A", "experience_years_bracket": "A",
    }
    for col, options in BUCKET_OPTIONS.items():
        codebook[col] = {"kind": "categorical", "label": _BUCKET_TITLES[col], "options": options, "section": _BUCKET_SECTION[col]}

    for col, label in Q5_BOOLEAN_LABELS.items():
        codebook[col] = {"kind": "boolean", "label": label, "options": None, "section": "A"}

    codebook["Q6"] = {
        "kind": "categorical",
        "label": _qlabel("Q6"),
        "options": [(o["code"], o["label"]) for o in questions["Q6"]["options"]],
        "section": questions["Q6"]["section"],
    }

    for qid in SINGLE_SELECT_STATS_FIELDS:
        q = questions[qid]
        if qid == "Q4":
            # Chính tả đã chuẩn hoá ở scripts/lib/bucketing.normalize_ethnicity — tên dân
            # tộc cụ thể (Mông, Dao, Tày...) không cố định trước, để options=None và lấy
            # danh sách giá trị phân biệt thật sự có trong dữ liệu (xem frequency.py).
            codebook[qid] = {"kind": "categorical", "label": _qlabel(qid), "options": [("Kinh", "Kinh")], "section": q["section"]}
            continue
        codebook[qid] = {
            "kind": "categorical",
            "label": _qlabel(qid),
            "options": [(o["code"], o["label"]) for o in q.get("options", [])],
            "section": q["section"],
        }

    for qid, option_codes in MULTI_SELECT_FIELDS.items():
        q = questions[qid]
        label_by_code = {o["code"]: o["label"] for o in q["options"]}
        for code in option_codes:
            codebook[f"{qid}_{code}"] = {
                "kind": "binary",
                "label": f"{_qlabel(qid)} — {label_by_code.get(code, code)}",
                "options": None,
                "section": q["section"],
            }

    for qid, row_codes in MATRIX_ROW_FIELDS.items():
        q = questions[qid]
        row_label_by_code = {r["code"]: r["label"] for r in q["rows"] if "code" in r}
        col_options = [(c["code"], c["label"]) for c in q["columns"]]
        for row_code in row_codes:
            codebook[f"{qid}_{row_code}"] = {
                "kind": "categorical",
                "label": f"{_qlabel(qid)} — {row_label_by_code.get(row_code, row_code)}",
                "options": col_options,
                "section": q["section"],
            }

    for qid, spec in DEVICE_GRID_FIELDS.items():
        q = questions[qid]
        row_label_by_code = {r["code"]: r["label"] for r in q["rows"]}
        col_label_by_code = {c["code"]: c["label"] for c in q["columns"]}
        for row_code in spec["rows"]:
            for col_code in spec["columns"]:
                codebook[f"{qid}_{row_code}_{col_code}"] = {
                    "kind": "binary",
                    "label": f"{_qlabel(qid)} — {row_label_by_code[row_code]} — {col_label_by_code[col_code]}",
                    "options": None,
                    "section": q["section"],
                }
        extra = q.get("extra_option")
        if extra:
            codebook[f"{qid}_{extra['code']}"] = {"kind": "boolean", "label": extra["label"], "options": None, "section": q["section"]}

    return codebook


_BUCKET_TITLES = {
    "age_bracket": "Q2 – Nhóm tuổi",
    "education_grade_bracket": "Q5 – Cấp học cao nhất đã hoàn thành",
    "marriage_age_bracket": "Q6 – Nhóm tuổi kết hôn",
    "experience_years_bracket": "Q9 – Nhóm kinh nghiệm trồng dược liệu",
}
