#!/usr/bin/env python3
"""Kiem tra completeness cua 1 file JSON ket qua trich xuat thu cong so voi schema.

Muc dich: bat loi "bo sot cau hoi/dong ma tran" khi lam thu cong tren quy mo lon
(85 phieu), KHONG thay the cho viec doi chieu noi dung dung/sai (do la viec cua
con nguoi/Claude khi doc anh). Day la luoi an toan cau truc, chay bang code
thuong, khong goi API.

Cach dung:
    python validate_record.py schema/questionnaire_v1.json output/full/LCA-LP-001.json
    python validate_record.py schema/questionnaire_v1.json output/full/*.json --all

Exit code: 0 neu tat ca file pass, 1 neu co file loi.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def expected_matrix_rows(question: dict) -> list[str]:
    rows = []
    for row in question.get("rows", []):
        if "group_header" in row:
            continue
        rows.append(row["code"])
    return rows


def check_record(schema: dict, record: dict) -> list[str]:
    """Tra ve danh sach loi (rong = pass)."""
    errors: list[str] = []
    questions = schema["questions"]
    answers = record.get("answers")
    if not isinstance(answers, dict):
        return [f"Thieu hoac sai kieu truong 'answers' o cap top-level (co: {type(answers)})"]

    for q in questions:
        qid = q["id"]
        qtype = q["type"]

        if q.get("per_page"):
            # PAGE_NOTES: nam o record['page_notes'], khong nam trong 'answers'
            page_notes = record.get("page_notes")
            if not isinstance(page_notes, dict):
                errors.append(f"[{qid}] thieu truong top-level 'page_notes' (per_page=true)")
                continue
            total_pages = schema.get("total_pages", 7)
            for p in range(1, total_pages + 1):
                if str(p) not in page_notes:
                    errors.append(f"[{qid}] thieu page_notes['{p}']")
            continue

        if qid not in answers:
            errors.append(f"[{qid}] cau hoi bi thieu hoan toan trong 'answers' (kem ca khi bo trong phai la null, khong duoc thieu key)")
            continue

        entry = answers[qid]
        if entry is None:
            errors.append(f"[{qid}] gia tri la null truc tiep — phai la object dang {{'value': null}}, khong phai null tran")
            continue
        if not isinstance(entry, dict):
            errors.append(f"[{qid}] gia tri khong phai object ({type(entry)})")
            continue

        if qtype == "composite":
            comps = entry.get("components")
            if not isinstance(comps, dict):
                errors.append(f"[{qid}] composite nhung thieu 'components'")
            else:
                for comp in q.get("components", []):
                    cid = comp["id"]
                    if cid not in comps:
                        errors.append(f"[{qid}] thieu component '{cid}'")

        elif qtype in ("matrix", "device_grid"):
            rows_out = entry.get("rows")
            if not isinstance(rows_out, dict):
                errors.append(f"[{qid}] {qtype} nhung thieu 'rows'")
            else:
                expected_rows = expected_matrix_rows(q) if qtype == "matrix" else [r["code"] for r in q.get("rows", [])]
                for rc in expected_rows:
                    if rc not in rows_out:
                        errors.append(f"[{qid}] thieu dong '{rc}' trong rows")
                # Q32: neu row_content_column bi skip_extraction thi KHONG bat buoc co 'noi_dung'
                rcc = q.get("row_content_column")
                if rcc and not rcc.get("skip_extraction"):
                    for rc in expected_rows:
                        row_entry = rows_out.get(rc, {})
                        if isinstance(row_entry, dict) and rcc["code"] not in row_entry:
                            errors.append(f"[{qid}] dong '{rc}' thieu cot noi dung '{rcc['code']}'")

        else:
            # single_select / multi_select / text / free_text
            if "value" not in entry:
                errors.append(f"[{qid}] thieu key 'value'")

        # subfield o cap cau hoi (Q23 kieu nay) hoac o cap option (Q6 kieu nay).
        # Co the la 1 def hoac mang nhieu def (cung dang derived_subfield) --
        # hien chua cau nao dung mang nhung engine ho tro san.
        if "subfield" in q:
            sub_defs = q["subfield"] if isinstance(q["subfield"], list) else [q["subfield"]]
            sub_out = entry.get("subfield")
            for sub_def in sub_defs:
                sub_id = sub_def["id"]
                if not isinstance(sub_out, dict) or sub_id not in sub_out:
                    errors.append(f"[{qid}] thieu subfield '{sub_id}'")

        # derived_subfield: giong subfield nhung co the la 1 def hoac mang nhieu def (vd Q9 co 2)
        if "derived_subfield" in q:
            ds_defs = q["derived_subfield"] if isinstance(q["derived_subfield"], list) else [q["derived_subfield"]]
            ds_out = entry.get("derived_subfield")
            for ds_def in ds_defs:
                ds_id = ds_def["id"]
                if not isinstance(ds_out, dict) or ds_id not in ds_out:
                    errors.append(f"[{qid}] thieu derived_subfield '{ds_id}'")

        if qtype == "single_select":
            for opt in q.get("options", []):
                if "subfield" in opt:
                    sub_id = opt["subfield"]["id"]
                    # Chi bat buoc co subfield neu option nay DUOC chon
                    val = entry.get("value")
                    selected = val == opt["code"] if not isinstance(val, list) else opt["code"] in val
                    if selected:
                        sub_out = entry.get("subfield")
                        if not isinstance(sub_out, dict) or sub_id not in sub_out:
                            errors.append(f"[{qid}] da chon option '{opt['code']}' nhung thieu subfield '{sub_id}'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("schema_path")
    parser.add_argument("record_paths", nargs="+", help="1 hoac nhieu file JSON (ho tro glob qua shell)")
    args = parser.parse_args()

    schema = load_json(args.schema_path)

    all_paths: list[str] = []
    for p in args.record_paths:
        expanded = glob.glob(p)
        all_paths.extend(expanded if expanded else [p])

    total_errors = 0
    for path in sorted(set(all_paths)):
        try:
            record = load_json(path)
        except Exception as e:
            print(f"❌ {path}: khong doc duoc JSON ({e})")
            total_errors += 1
            continue
        errors = check_record(schema, record)
        if errors:
            print(f"❌ {path}: {len(errors)} loi")
            for e in errors:
                print(f"   - {e}")
            total_errors += len(errors)
        else:
            print(f"✅ {path}: OK ({len(schema['questions'])} cau hoi, day du)")

    print(f"\n=== Tong: {len(all_paths)} file, {total_errors} loi ===")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
