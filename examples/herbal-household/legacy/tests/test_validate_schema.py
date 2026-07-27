#!/usr/bin/env python3
"""Test cho validate_schema — cả nhánh pass lẫn các nhánh bắt lỗi.

Không phụ thuộc pytest (env survey-digitizer bare). Chạy trực tiếp:

  python tests/test_validate_schema.py

Thoát mã 0 nếu mọi test pass, 1 nếu có test fail.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import validate_schema as vs  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")
REAL_SCHEMA = os.path.join(REPO, "schema", "questionnaire_v1.json")

_results = []


def q(qid="Q1", **over):
    """Một câu single_select hợp lệ; override field để tạo case hỏng."""
    base = {
        "id": qid, "page": 1, "type": "single_select",
        "options": [{"code": "a", "label": "A"}, {"code": "b", "label": "B"}],
    }
    base.update(over)
    return base


def schema(*questions, total_pages=7):
    return {"total_pages": total_pages, "questions": list(questions)}


def expect_error(name, sch, substring, total_pages=7):
    """Case hỏng: ít nhất một lỗi phải chứa `substring`."""
    errors = vs.validate(sch, total_pages)
    hit = any(substring in e for e in errors)
    _results.append((name, hit, errors if not hit else None))


def expect_clean(name, sch, total_pages=7):
    errors = vs.validate(sch, total_pages)
    _results.append((name, not errors, errors or None))


# ---- Nhánh bắt lỗi ----
expect_error("id trùng", schema(q("Q1"), q("Q1")), "trùng")
expect_error(
    "mọi option exclusive",
    schema(q("Q1", options=[
        {"code": "a", "label": "A", "exclusive": True},
        {"code": "b", "label": "B", "exclusive": True},
    ])),
    "exclusive",
)
expect_error("page ngoài khoảng", schema(q("Q1", page=99)), "page không hợp lệ")
expect_error(
    "per_page có page",
    schema(q("Q1", type="free_text", options=[], per_page=True, page=1)),
    "per_page nên có page = null",
)
expect_error(
    "matrix thiếu expected_data_rows",
    schema(q("Q1", type="matrix",
             columns=[{"code": "x", "label": "X"}],
             rows=[{"code": "r1", "label": "R1"}])),
    "expected_data_rows",
)
expect_error(
    "matrix sai số dòng",
    schema(q("Q1", type="matrix", expected_data_rows=3,
             columns=[{"code": "x", "label": "X"}],
             rows=[{"code": "r1", "label": "R1"}])),
    "số dòng dữ liệu",
)
expect_error(
    "depends_on câu đích không tồn tại",
    schema(q("Q1"), q("Q2", type="free_text", options=[],
                      depends_on={"question": "QNONE", "equals": "a"})),
    "không tồn tại",
)
expect_error(
    "depends_on code không có ở câu đích",
    schema(q("Q1"), q("Q2", type="free_text", options=[],
                      depends_on={"question": "Q1", "equals": "zzz"})),
    "code không có",
)
expect_error(
    "depends_on 2 toán tử",
    schema(q("Q1"), q("Q2", type="free_text", options=[],
                      depends_on={"question": "Q1", "equals": "a", "not_equals": "b"})),
    "đúng 1 toán tử",
)
expect_error(
    "in/not_in không phải mảng",
    schema(q("Q1"), q("Q2", type="free_text", options=[],
                      depends_on={"question": "Q1", "in": "a"})),
    "cần giá trị là mảng",
)

# ---- Nhánh hợp lệ ----
expect_clean(
    "depends_on in đúng (mảng, code tồn tại)",
    schema(q("Q1"), q("Q2", type="free_text", options=[],
                      depends_on={"question": "Q1", "in": ["a", "b"]})),
)
expect_clean(
    "depends_on trỏ component của composite",
    schema(
        q("Q5", type="composite", options=[], components=[
            {"id": "Q5_x", "page": 1, "type": "single_select",
             "options": [{"code": "yes", "label": "Yes"}]},
        ]),
        q("Q6", type="free_text", options=[],
          depends_on={"question": "Q5_x", "equals": "yes"}),
    ),
)


def main():
    # Test tích hợp: schema thật phải hợp lệ và ra đúng 110 trường.
    # (22/07: 108 trường gốc; 24/07: +2 vì Q9.derived_subfield đổi thành mảng
    # 2 def (Q9_derived_start_year + Q9_derived_years_exp) thay vì 1 def duy nhất
    # trước đó không được count_export_fields đếm tới — xem SCHEMA-FORMAT.md.)
    with open(REAL_SCHEMA, encoding="utf-8") as f:
        real = json.load(f)
    tp = real.get("total_pages", 1)
    real_errors = vs.validate(real, tp)
    _results.append(("schema thật hợp lệ", not real_errors, real_errors or None))
    total = sum(vs.count_export_fields(qq, tp) for qq in real["questions"])
    _results.append(("schema thật = 110 trường", total == 110,
                     None if total == 110 else f"đếm được {total}"))

    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if not ok and detail:
            line += f"  -> {detail}"
        print(line)

    print(f"\n{len(_results) - len(failed)}/{len(_results)} pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
