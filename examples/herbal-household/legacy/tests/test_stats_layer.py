#!/usr/bin/env python3
"""Unit tests cho tầng dữ liệu thống kê (scripts/lib/records.py, bucketing.py, flatten.py, pii.py).

Chạy trực tiếp trên các record thật trong output/full/ (không mock) để cover cả 2
dạng needs_review, multi-mark list value, Q32 có/không noi_dung, Q9 edge case
years_exp=0/range string — xem docs/implement-plan-statistics-and-client-report.md.

Run:
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" tests/test_stats_layer.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lib.bucketing as bucketing  # noqa: E402
from lib.flatten import flatten_full, flatten_stats  # noqa: E402
from lib.pii import to_stats_record  # noqa: E402
from lib.records import (  # noqa: E402
    as_code_list,
    as_single_category,
    clean_commune,
    count_needs_review,
    get_value,
    is_flagged_review,
    load_json,
    load_manifest,
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RESULTS: list[tuple[str, bool, object | None]] = []
TMP_ROOT = Path(tempfile.mkdtemp(prefix="stats_layer_test_"))
FULL_DIR = REPO_ROOT / "output" / "full"
MANIFEST = REPO_ROOT / "data" / "manifest.csv"


def check(name: str, condition: object, detail: object | None = None) -> None:
    RESULTS.append((name, bool(condition), detail))


# ---------------------------------------------------------------------------
# records.py — bucketing helpers
# ---------------------------------------------------------------------------

check("clean_commune bỏ hậu tố -Nphieu", clean_commune("lung-phinh-16phieu") == "lung-phinh")
check("clean_commune giữ nguyên nếu không có hậu tố", clean_commune("sa-pa") == "sa-pa")

check("as_code_list(None) -> []", as_code_list(None) == [])
check("as_code_list(list) giữ nguyên", as_code_list(["a", "b"]) == ["a", "b"])
check("as_code_list(scalar) -> [scalar]", as_code_list("a") == ["a"])

check("as_single_category(None) -> None", as_single_category(None) is None)
check("as_single_category(scalar) -> str", as_single_category("chong") == "chong")
check(
    "as_single_category(list) nối bằng '+', đã sort",
    as_single_category(["nguoi_khac", "chong"]) == "chong+nguoi_khac",
)

check(
    "is_flagged_review: boolean needs_review=true",
    is_flagged_review({"value": "x", "needs_review": True}) is True,
)
check(
    "is_flagged_review: chỉ có trong flags array (phiếu cũ)",
    is_flagged_review({"value": "x", "flags": ["needs_review", "ambiguous_mark"]}) is True,
)
check(
    "is_flagged_review: không có gì -> False",
    is_flagged_review({"value": "x", "flags": ["multi_mark_on_single_select"]}) is False,
)
check("is_flagged_review: answer None -> False", is_flagged_review(None) is False)

# ---------------------------------------------------------------------------
# bucketing.py — công thức stats_bucketing
# ---------------------------------------------------------------------------

check("age_from_birth_year('1995') = 31 (2026-1995)", bucketing.age_from_birth_year("1995") == 31)
check("age_from_birth_year(None) -> None", bucketing.age_from_birth_year(None) is None)
check("age_bracket(30) = '<35'", bucketing.age_bracket(30) == "<35")
check("age_bracket(35) = '35-45'", bucketing.age_bracket(35) == "35-45")
check("age_bracket(45) = '35-45'", bucketing.age_bracket(45) == "35-45")
check("age_bracket(46) = '>45'", bucketing.age_bracket(46) == ">45")
check("age_bracket(None) -> None", bucketing.age_bracket(None) is None)

check(
    # 25/07 phản hồi khách (docs/client-feedback-2026-07-25-q5-grade-split.md): bucket
    # theo lớp ĐÃ HỌC XONG, không phải khoảng lớp đang học — thay cho bucket 5 mức cũ
    # education_level_bracket (đã bỏ, từng gộp chung tick+điền).
    "education_grade_bracket: 'Hết lớp 9' -> 'thcs' (xong lớp 9)",
    bucketing.education_grade_bracket("Hết lớp 9") == "thcs",
)
check(
    "education_grade_bracket: 'Hết lớp 7' -> 'tieu_hoc' (CHƯA xong lớp 9, ví dụ khách chốt)",
    bucketing.education_grade_bracket("Hết lớp 7") == "tieu_hoc",
)
check(
    "education_grade_bracket: 'Lớp 12' -> 'thpt' (xong lớp 12)",
    bucketing.education_grade_bracket("Lớp 12") == "thpt",
)
check(
    "education_grade_bracket: 'Hết lớp 11' -> 'thcs' (xong lớp 9 nhưng CHƯA xong lớp 12)",
    bucketing.education_grade_bracket("Hết lớp 11") == "thcs",
)
check(
    "education_grade_bracket: '9/12' -> 'thcs' (số đầu là lớp đã xong, không phải phân số)",
    bucketing.education_grade_bracket("9/12") == "thcs",
)
check(
    "education_grade_bracket: '12/12' -> 'thpt'",
    bucketing.education_grade_bracket("12/12") == "thpt",
)
check(
    "education_grade_bracket: 'Lớp 5' -> 'tieu_hoc'",
    bucketing.education_grade_bracket("Lớp 5") == "tieu_hoc",
)
check(
    "education_grade_bracket: chữ 'Tiểu học' không số (case LCH-MSP-013) -> 'tieu_hoc'",
    bucketing.education_grade_bracket("Tiểu học") == "tieu_hoc",
)
check(
    "education_grade_bracket: không đọc được số lớp -> None",
    bucketing.education_grade_bracket(None) is None,
)

check("marriage_age_bracket(16) = '<18' (tảo hôn, case LCA-LP-004)", bucketing.marriage_age_bracket(16) == "<18")
check("marriage_age_bracket(18) = '>=18'", bucketing.marriage_age_bracket(18) == ">=18")
check("marriage_age_bracket(None) -> None", bucketing.marriage_age_bracket(None) is None)

check("experience_years_bracket(9) = '>=1' (case LCA-LP-004)", bucketing.experience_years_bracket(9) == ">=1")
check("experience_years_bracket(0) = '<1'", bucketing.experience_years_bracket(0) == "<1")
check(
    "experience_years_bracket('7-8') -> None (range string, case LCA-HR-016, không suy đoán)",
    bucketing.experience_years_bracket("7-8") is None,
)
check("experience_years_bracket(None) -> None", bucketing.experience_years_bracket(None) is None)

# ---------------------------------------------------------------------------
# flatten.py + pii.py trên record thật
# ---------------------------------------------------------------------------

manifest = load_manifest(MANIFEST)


def _flatten(record_id: str) -> dict:
    record = load_json(FULL_DIR / f"{record_id}.json")
    return flatten_stats(record, manifest[record_id])


# LCA-LP-004: phiếu "sạch" (0 flags theo review-summary-report.md), đã qua Review UI,
# có tảo hôn (Q6_tuoi_ket_hon=16), Q9 start_year=2017 -> years_exp=9, Q4 dân tộc "Mông".
lp004 = load_json(FULL_DIR / "LCA-LP-004.json")
lp004_flat = flatten_stats(lp004, manifest["LCA-LP-004"])

check("flatten LCA-LP-004: record_id giữ nguyên", lp004_flat["record_id"] == "LCA-LP-004")
check("flatten LCA-LP-004: province từ manifest", lp004_flat["province"] == "lao-cai")
check("flatten LCA-LP-004: commune đã bỏ hậu tố -Nphieu", lp004_flat["commune"] == "lung-phinh")
check("flatten LCA-LP-004: Q2_tuoi = 2026-1999 = 27", lp004_flat["Q2_tuoi"] == 27)
check("flatten LCA-LP-004: age_bracket = '<35'", lp004_flat["age_bracket"] == "<35")
check("flatten LCA-LP-004: Q4 ngoại lệ giữ tên dân tộc cụ thể 'Mông'", lp004_flat["Q4"] == "Mông")
check("flatten LCA-LP-004: Q6_tuoi_ket_hon = 16", lp004_flat["Q6_tuoi_ket_hon"] == 16)
check("flatten LCA-LP-004: marriage_age_bracket = '<18' (tảo hôn)", lp004_flat["marriage_age_bracket"] == "<18")
check("flatten LCA-LP-004: KHÔNG có Q9_derived_start_year (26/07 — bỏ khỏi phạm vi thống kê, trùng lặp với years_exp)", "Q9_derived_start_year" not in lp004_flat)
check("flatten LCA-LP-004: Q9_derived_years_exp = 9", lp004_flat["Q9_derived_years_exp"] == 9)
check("flatten LCA-LP-004: experience_years_bracket = '>=1'", lp004_flat["experience_years_bracket"] == ">=1")
check("flatten LCA-LP-004: Q7 multi-select nổ nhị phân đúng", (
    lp004_flat["Q7_trong_trot"] == 1
    and lp004_flat["Q7_cay_duoc_lieu"] == 1
    and lp004_flat["Q7_chan_nuoi"] == 0
    and lp004_flat["Q7_lam_nghiep"] == 0
    and lp004_flat["Q7_phi_nong_nghiep"] == 0
))
check("flatten LCA-LP-004: Q11 multi-select exclusive option", lp004_flat["Q11_khong_hoi_vien"] == 1)
check("flatten LCA-LP-004: Q14 matrix row categorical (lam_dat=ca_hai)", lp004_flat["Q14_lam_dat"] == "ca_hai")
check("flatten LCA-LP-004: Q14 row null giữ null (thuoc_bvtv)", lp004_flat["Q14_thuoc_bvtv"] is None)
check(
    "flatten LCA-LP-004: Q17 device_grid nhị phân theo (row,col) — dien_thoai cả 2 vợ chồng",
    lp004_flat["Q17_dien_thoai_chong"] == 1 and lp004_flat["Q17_dien_thoai_vo"] == 1,
)
check(
    "flatten LCA-LP-004: Q17 row rỗng ([]) -> cả 2 cột = 0, không phải None",
    lp004_flat["Q17_may_tinh_chong"] == 0 and lp004_flat["Q17_may_tinh_vo"] == 0,
)
check("flatten LCA-LP-004: Q17 khong_ai_co = False", lp004_flat["Q17_khong_ai_co"] is False)
check("flatten LCA-LP-004: Q32 matrix row (chon_cay_trong)", lp004_flat["Q32_chon_cay_trong"] == "cung_quyet_dinh")
check("flatten LCA-LP-004: Q32 row null (vay_von, ký hiệu 'ko')", lp004_flat["Q32_vay_von"] is None)
check("flatten LCA-LP-004: không có cột Q1 (PII)", "Q1" not in lp004_flat)
check("flatten LCA-LP-004: không có cột META_LOCATION", "META_LOCATION" not in lp004_flat)

lp004_stats_record = to_stats_record(lp004)
check("to_stats_record: bỏ Q1 khỏi answers", "Q1" not in lp004_stats_record["answers"])
check("to_stats_record: giữ nguyên các field khác", "Q2" in lp004_stats_record["answers"])
check("to_stats_record: không sửa record gốc (deepcopy)", "Q1" in lp004["answers"])

lp004_full = flatten_full(lp004)
check("flatten_full LCA-LP-004: có Q1 (định danh, dùng cho sheet 'Dữ liệu đã số hóa')", "Q1" in lp004_full)
check("flatten_full LCA-LP-004: có Q3 (giới tính, giữ để định danh dù không phải biến thống kê)", "Q3" in lp004_full)
check("flatten_full LCA-LP-004: có META_LOCATION (địa điểm, giữ để định danh)", "META_LOCATION" in lp004_full)
check(
    "flatten_full LCA-LP-004: KHÔNG có Q15 (26/07 — sheet chỉ giữ trường có thống kê + định danh)",
    "Q15" not in lp004_full,
)
check("flatten_full LCA-LP-004: KHÔNG có PAGE_NOTES (26/07 — không phải biến thống kê)", "PAGE_NOTES_p1" not in lp004_full)
check("flatten_full LCA-LP-004: KHÔNG có META_DATE/CONSENT_1/CONSENT_2 (26/07)", not ({"META_DATE", "CONSENT_1", "CONSENT_2"} & lp004_full.keys()))
check("flatten_full LCA-LP-004: KHÔNG có Q16a_chi_tiet (best-effort, ngoài phạm vi thống kê)", "Q16a_chi_tiet" not in lp004_full)
check("flatten_full LCA-LP-004: KHÔNG có Q9_derived_start_year (26/07 — trùng lặp với years_exp)", "Q9_derived_start_year" not in lp004_full)
check("flatten_full LCA-LP-004: subfield Q6_tuoi_ket_hon = 16", lp004_full.get("Q6_tuoi_ket_hon") == 16)
check(
    "flatten_full LCA-LP-004: derived Q9_derived_years_exp = 9",
    lp004_full.get("Q9_derived_years_exp") == 9,
)

# LCA-HR-001: phiếu CHƯA qua Review UI, needs_review dạng boolean sibling key (Q4/Q8/Q9),
# Q8 multi-mark list value ["25_50","51_75"].
hr001 = load_json(FULL_DIR / "LCA-HR-001.json")
check("LCA-HR-001: count_needs_review > 0 (phiếu chưa review)", count_needs_review(hr001) > 0)
hr001_flat = flatten_stats(hr001, manifest["LCA-HR-001"])
check(
    "flatten LCA-HR-001: Q8 multi-mark list -> category nối bằng '+', sort",
    hr001_flat["Q8"] == "25_50+51_75",
)
check("flatten LCA-HR-001: Q4 ngoại lệ dân tộc 'Mông' dù needs_review", hr001_flat["Q4"] == "Mông")

# LCA-TPH-007: phiếu nhiều flags nhất (20) theo docs/review-summary-report.md, đã review
# (0 needs_review còn lại) — chỉ cần flatten không crash và record_id đúng.
tph007 = load_json(FULL_DIR / "LCA-TPH-007.json")
tph007_flat = flatten_stats(tph007, manifest["LCA-TPH-007"])
check("flatten LCA-TPH-007 (nhiều flags nhất) không crash", tph007_flat["record_id"] == "LCA-TPH-007")

# Toàn bộ 85 phiếu: flatten_stats/flatten_full không được crash trên bất kỳ record nào.
from lib.records import iter_full_records  # noqa: E402

crash_count = 0
crash_detail = None
processed = 0
for record in iter_full_records(FULL_DIR):
    processed += 1
    rid = record["record_id"]
    if rid not in manifest:
        crash_count += 1
        crash_detail = f"{rid}: không có trong manifest"
        continue
    try:
        flatten_stats(record, manifest[rid])
        flatten_full(record)
        to_stats_record(record)
    except Exception as exc:  # pragma: no cover - diagnostic path
        crash_count += 1
        crash_detail = f"{rid}: {type(exc).__name__}: {exc}"

check("toàn bộ 85 phiếu được duyệt qua iter_full_records", processed == 85, f"processed={processed}")
check("flatten_stats/flatten_full/to_stats_record không crash trên bất kỳ phiếu nào", crash_count == 0, crash_detail)


def main() -> int:
    failed = [result for result in RESULTS if not result[1]]
    for name, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if not ok and detail is not None:
            line += f"  -> {detail}"
        print(line)
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} pass")
    shutil.rmtree(TMP_ROOT, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
