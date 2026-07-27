#!/usr/bin/env python3
"""Validator cho schema bảng hỏi số hóa phiếu khảo sát.

Chạy:  python scripts/validate_schema.py schema/questionnaire_v1.json

Kiểm tra:
  - Mã câu hỏi (id) không trùng.
  - Mọi câu có type hợp lệ.
  - Option/row/column có code không trùng trong cùng một câu.
  - Option 'exclusive' không được là lựa chọn duy nhất của câu.
  - Matrix có đủ rows (data) và columns; số dòng khớp expected_data_rows khai trong schema.
  - page nằm trong 1..total_pages (hoặc null với câu per_page).
  - depends_on: câu đích tồn tại, toán tử hợp lệ, giá trị tham chiếu có trong option code câu đích.
  - Đếm tổng số trường xuất ra (để bước export đối chiếu "đủ trường kể cả null").

Thoát mã 0 nếu hợp lệ, 1 nếu có lỗi.
"""

import json
import sys
from collections import Counter

# Console Windows mặc định cp1258 không in được tiếng Việt/emoji — ép UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

VALID_TYPES = {
    "text", "free_text", "single_select", "multi_select",
    "matrix", "device_grid", "composite",
}

# Toán tử depends_on: tên -> giá trị là danh sách (True) hay vô hướng (False).
DEPENDS_OPERATORS = {
    "equals": False, "not_equals": False,
    "contains": False, "not_contains": False,
    "in": True, "not_in": True,
}


def err(errors, qid, msg):
    errors.append(f"[{qid}] {msg}")


def data_rows(q):
    """Dòng dữ liệu của matrix, bỏ group_header."""
    return [r for r in q.get("rows", []) if "group_header" not in r]


def option_codes(q):
    """Tập code của mọi option/extra_option trong một câu (rỗng nếu câu không có option)."""
    codes = {o["code"] for o in q.get("options", []) if "code" in o}
    extra = q.get("extra_option")
    if extra and "code" in extra:
        codes.add(extra["code"])
    return codes


def count_export_fields(q, total_pages):
    """Số trường một câu sinh ra trong bản ghi JSON đầu ra.

    Quy ước (xem SCHEMA-FORMAT.md §Đếm trường):
      - single/multi/text/free_text: 1 trường trả lời
          + 1 mỗi subfield (trên câu hoặc trên option)
          + 1 mỗi derived_subfield (1 def hoặc mảng nhiều def, vd Q9)
          + 1 mỗi option other_text (dòng "ghi rõ" riêng)
      - composite: tổng các components
      - matrix: 1 trường/dòng dữ liệu
          + 1/dòng nếu có row_content_column (cột "Nội dung")
          + 1 mỗi dòng other_text
      - device_grid: 1 trường/dòng + 1 nếu có extra_option
      - per_page: 1 trường cho mỗi trang (total_pages)
    """
    t = q["type"]
    if q.get("per_page"):
        return total_pages
    if t in ("text", "free_text", "single_select", "multi_select"):
        n = 1
        if "subfield" in q:  # subfield trực tiếp trên câu (vd Q23); có thể là mảng nhiều def
            sf = q["subfield"]
            n += len(sf) if isinstance(sf, list) else 1
        if "derived_subfield" in q:  # 1 def (cũ) hoặc mảng nhiều def (vd Q9: start_year + years_exp)
            ds = q["derived_subfield"]
            n += len(ds) if isinstance(ds, list) else 1
        for opt in q.get("options", []):
            if "subfield" in opt:  # subfield trên option (vd Q6, Q16a)
                n += 1
            if opt.get("other_text"):  # dòng "Khác (ghi rõ)" (vd Q4, Q10)
                n += 1
        return n
    if t == "composite":
        return sum(count_export_fields(c, total_pages) for c in q.get("components", []))
    if t == "matrix":
        rows = data_rows(q)
        n = len(rows)
        if q.get("row_content_column"):  # cột "Nội dung" — 1 text/dòng (Q32)
            n += len(rows)
        n += sum(1 for r in rows if r.get("other_text"))  # dòng "Khác"
        return n
    if t == "device_grid":
        return len(q.get("rows", [])) + (1 if "extra_option" in q else 0)
    return 1


def validate(schema, total_pages):
    errors = []
    questions = schema.get("questions", [])
    ids = [q["id"] for q in questions]

    # 1. id trùng
    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        err(errors, "GLOBAL", f"Mã câu hỏi trùng: {dup}")
    # by_id gồm cả component của composite (depends_on có thể trỏ tới, vd Q5_trung_cap_dh)
    by_id = {}
    for q in questions:
        by_id[q["id"]] = q
        if q.get("type") == "composite":
            for c in q.get("components", []):
                by_id[c["id"]] = c

    for q in questions:
        qid = q.get("id", "??")

        # 2. type hợp lệ
        if q.get("type") not in VALID_TYPES:
            err(errors, qid, f"type không hợp lệ: {q.get('type')}")

        # 3. code trùng trong options / rows / columns
        for key in ("options", "rows", "columns"):
            codes = [x["code"] for x in q.get(key, []) if "code" in x]
            d = [k for k, v in Counter(codes).items() if v > 1]
            if d:
                err(errors, qid, f"{key} có code trùng: {d}")

        # 4. exclusive không được đứng một mình
        opts = q.get("options", [])
        if opts and all(o.get("exclusive") for o in opts):
            err(errors, qid, "mọi option đều exclusive — sai logic")

        # 5. matrix: đủ rows/columns, số dòng khớp expected_data_rows (khai trong schema)
        if q.get("type") == "matrix":
            if not q.get("columns"):
                err(errors, qid, "matrix thiếu columns")
            dr = data_rows(q)
            if not dr:
                err(errors, qid, "matrix thiếu rows dữ liệu")
            expected = q.get("expected_data_rows")
            if expected is None:
                err(errors, qid, "matrix thiếu expected_data_rows (cần khai để chốt số dòng)")
            elif len(dr) != expected:
                err(errors, qid, f"số dòng dữ liệu = {len(dr)}, expected_data_rows = {expected}")

        # 6. device_grid: có rows + columns
        if q.get("type") == "device_grid":
            if not q.get("rows") or not q.get("columns"):
                err(errors, qid, "device_grid cần cả rows và columns")

        # 7. page hợp lệ: 1..total_pages, hoặc null khi per_page
        page = q.get("page")
        if q.get("per_page"):
            if page is not None:
                err(errors, qid, "câu per_page nên có page = null")
        elif not (isinstance(page, int) and 1 <= page <= total_pages):
            err(errors, qid, f"page không hợp lệ: {page} (phải trong 1..{total_pages})")

        # 8. depends_on: câu đích tồn tại, toán tử hợp lệ, giá trị có trong option code
        dep = q.get("depends_on")
        if dep:
            target = dep.get("question")
            if target not in by_id:
                err(errors, qid, f"depends_on trỏ tới câu không tồn tại: {target}")
            else:
                ops = [k for k in dep if k in DEPENDS_OPERATORS]
                if len(ops) != 1:
                    err(errors, qid, f"depends_on cần đúng 1 toán tử, thấy: {ops or 'không có'}")
                else:
                    op = ops[0]
                    raw = dep[op]
                    if DEPENDS_OPERATORS[op]:  # in/not_in cần mảng
                        if not isinstance(raw, list):
                            err(errors, qid, f"depends_on toán tử '{op}' cần giá trị là mảng, thấy {type(raw).__name__}")
                            raw = []
                        values = raw
                    else:
                        values = [raw]
                    valid = option_codes(by_id[target])
                    if valid:  # chỉ kiểm khi câu đích có option (bỏ qua matrix/text)
                        unknown = [v for v in values if v not in valid]
                        if unknown:
                            err(errors, qid, f"depends_on tham chiếu code không có ở {target}: {unknown}")

    return errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "schema/questionnaire_v1.json"
    with open(path, encoding="utf-8") as f:
        schema = json.load(f)

    questions = schema.get("questions", [])
    total_pages = schema.get("total_pages", 1)

    errors = validate(schema, total_pages)

    total_fields = sum(count_export_fields(q, total_pages) for q in questions)
    numbered = [q["id"] for q in questions if q["id"].startswith("Q")]

    print(f"File:            {path}")
    print(f"Tổng câu hỏi:    {len(questions)} (trong đó {len(numbered)} câu đánh số Q)")
    print(f"Tổng trường xuất: {total_fields} (mọi bản ghi phải đủ bấy nhiêu trường, kể cả null)")

    if errors:
        print(f"\n❌ {len(errors)} lỗi:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)

    print("\n✅ Schema hợp lệ.")
    sys.exit(0)


if __name__ == "__main__":
    main()
