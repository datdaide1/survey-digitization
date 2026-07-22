#!/usr/bin/env python3
"""Test cho Task 2 — ingest & assembly.

Dựng file phiếu giả (1 file/phiếu — ảnh hoặc PDF) trong thư mục tạm hệ thống cho
từng case (đủ trang, thiếu, thừa, hỏng, ảnh đơn trang, không tìm thấy) — không đụng
data/raw/ thật. Không phụ thuộc pytest.

Cập nhật 22/07/2026: bỏ toàn bộ case liên quan quy ước folder nhiều file rời (đã
loại khỏi assembly.py/ingest.py — mọi phiếu thật, kể cả phiếu mẫu LCA-LP-001, giờ
đều là đúng 1 file PDF/ảnh). Xem docs/task-02-report.md §7b.

Chạy:
  & "E:\\anaconda3\\envs\\survey-digitizer\\python.exe" tests/test_ingest.py
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import csv as _csv  # noqa: E402
from lib.assembly import build_assembly  # noqa: E402
from ingest import run, _safe_segment, _safe_filename  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_results = []
_tmp_root = Path(tempfile.mkdtemp(prefix="ingest_test_"))


def check(name, cond, detail=None):
    _results.append((name, bool(cond), detail))


def make_image(path, size=(20, 20), color=(255, 0, 0)):
    from PIL import Image
    Image.new("RGB", size, color).save(path)


def make_pdf(path, n_pages=3):
    import fitz
    doc = fitz.open()
    for i in range(n_pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {i + 1}")
    doc.save(path)
    doc.close()


def case_dir(name):
    d = _tmp_root / name
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---- Case 1: PDF đủ 7 trang -> status ok ----
d = case_dir("full_pdf")
make_pdf(d / "T1.pdf", n_pages=7)
record = build_assembly("T1", d / "T1.pdf", expected_pages=7, render_dir=d / "_render")
check("PDF đủ 7 trang -> status ok", record["status"] == "ok", record)
check("PDF đủ 7 trang -> found_pages=7", record.get("found_pages") == 7, record)
check("PDF đủ 7 trang -> không cờ nào", record["flags"] == [], record["flags"])
check("mọi page kind=pdf_page", all(p["kind"] == "pdf_page" for p in record["pages"]), record["pages"])
check("tentative_page theo đúng thứ tự trang trong PDF",
      [p["tentative_page"] for p in record["pages"]] == list(range(1, 8)), record["pages"])

# ---- Case 2: thiếu trang (PDF ít hơn expected) ----
d = case_dir("missing_pages")
make_pdf(d / "T2.pdf", n_pages=6)
record = build_assembly("T2", d / "T2.pdf", expected_pages=7, render_dir=d / "_render")
check("PDF 6/7 trang -> flag missing_page", "missing_page" in record["flags"], record["flags"])
check("PDF 6/7 trang -> status needs_review", record["status"] == "needs_review")
check("PDF 6/7 trang -> found_pages=6", record.get("found_pages") == 6)

# ---- Case 3: thừa trang (PDF nhiều hơn expected, vd phiếu 8 trang thay vì 7 chuẩn) ----
d = case_dir("extra_pages")
make_pdf(d / "T3.pdf", n_pages=8)
record = build_assembly("T3", d / "T3.pdf", expected_pages=7, render_dir=d / "_render")
check("PDF 8/7 trang -> flag extra_page", "extra_page" in record["flags"], record["flags"])
check("PDF 8/7 trang -> status needs_review", record["status"] == "needs_review")
check("không còn cờ thừa count_mismatch", "count_mismatch" not in record["flags"], record["flags"])

# ---- Case 4: PDF hỏng (không mở được) -> unreadable, status error ----
d = case_dir("corrupt_pdf")
(d / "T4.pdf").write_bytes(b"%PDF-1.4 not a real pdf body")
record = build_assembly("T4", d / "T4.pdf", expected_pages=7, render_dir=d / "_render")
check("PDF hỏng -> flag unreadable", "unreadable" in record["flags"], record["flags"])
check("PDF hỏng -> status error", record["status"] == "error")
check("PDF hỏng -> found_pages=0, pages rỗng", record["found_pages"] == 0 and record["pages"] == [])

# ---- Case 5: ảnh đơn trang hợp lệ (phiếu 1 trang) -> status ok ----
d = case_dir("single_image")
make_image(d / "T5.jpg")
record = build_assembly("T5", d / "T5.jpg", expected_pages=1, render_dir=d / "_render")
check("ảnh đơn trang -> status ok", record["status"] == "ok", record)
check("ảnh đơn trang -> kind=image", record["pages"][0]["kind"] == "image", record["pages"])

# ---- Case 6: ảnh hỏng (không mở được như ảnh) -> unreadable, status error ----
d = case_dir("corrupt_image")
(d / "T6.jpg").write_bytes(b"not a real image content")
record = build_assembly("T6", d / "T6.jpg", expected_pages=1, render_dir=d / "_render")
check("ảnh hỏng -> flag unreadable", "unreadable" in record["flags"], record["flags"])
check("ảnh hỏng -> status error", record["status"] == "error")

# ---- Case 7: không tìm thấy file nguồn -> source_not_found ----
record = build_assembly("T7", _tmp_root / "khong_ton_tai.pdf", expected_pages=7, render_dir=_tmp_root / "_r7")
check("file không tồn tại -> flag source_not_found", "source_not_found" in record["flags"])
check("file không tồn tại -> status error", record["status"] == "error")

# ---- Case 8: đuôi file không hợp lệ (vd .docx) -> source_not_found ----
d = case_dir("bad_ext")
(d / "T8.docx").write_bytes(b"junk")
record = build_assembly("T8", d / "T8.docx", expected_pages=7, render_dir=d / "_render")
check("đuôi file không hợp lệ -> source_not_found", "source_not_found" in record["flags"], record["flags"])

# ---- Case 9: đúng 7 trang thật từ data/raw thật (integration, nếu tồn tại) ----
real_pdf = Path(__file__).parent.parent / "data" / "raw" / "khao-sat" / "lao-cai" / "lung-phinh" / "LCA-LP-001.pdf"
if real_pdf.is_file():
    record = build_assembly("LCA-LP-001", real_pdf, expected_pages=7,
                             render_dir=_tmp_root / "_real_render")
    check("phiếu mẫu thật LCA-LP-001.pdf -> status ok", record["status"] == "ok", record)
    check("phiếu mẫu thật LCA-LP-001.pdf -> đúng 7 trang", record.get("found_pages") == 7)

# ---- Case 10: ingest.run() cách ly lỗi — 1 dòng manifest hỏng không giết cả lô ----
batch = case_dir("batch")
raw = batch / "raw"
prov_dir = raw / "prov" / "comm"
prov_dir.mkdir(parents=True)
make_pdf(prov_dir / "R1.pdf", n_pages=2)  # phiếu tốt: R1 đủ 2 trang
manifest = batch / "manifest.csv"
with open(manifest, "w", encoding="utf-8", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["record_id", "province", "commune", "num_pages"])
    w.writerow(["R1", "prov", "comm", "2"])
    w.writerow(["R2", "prov", "comm", ""])  # num_pages hỏng
records = run(manifest, raw, batch / "out")
by_id = {r["record_id"]: r for r in records}
check("lô hỏng 1 dòng vẫn xử lý đủ 2 phiếu (không crash)", len(records) == 2, records)
check("phiếu tốt R1 -> ok", by_id.get("R1", {}).get("status") == "ok", by_id.get("R1"))
check("phiếu lỗi R2 -> status error + flag processing_error",
      by_id.get("R2", {}).get("status") == "error"
      and "processing_error" in by_id.get("R2", {}).get("flags", []), by_id.get("R2"))
check("phiếu lỗi R2 vẫn được ghi file JSON", (batch / "out" / "R2.json").exists())

# ---- Case 11: ingest.run() end-to-end — record_id.pdf phẳng, _resolve_source tìm đúng ----
batch2 = case_dir("batch_flat")
raw3 = batch2 / "raw"
flat_dir = raw3 / "prov" / "comm"
flat_dir.mkdir(parents=True)
make_pdf(flat_dir / "R3.pdf", n_pages=4)
manifest3 = batch2 / "manifest.csv"
with open(manifest3, "w", encoding="utf-8", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["record_id", "province", "commune", "num_pages"])
    w.writerow(["R3", "prov", "comm", "4"])
records3 = run(manifest3, raw3, batch2 / "out")
check("record_id.pdf phẳng -> ingest.run() tìm thấy, status ok",
      records3[0]["status"] == "ok" and records3[0]["found_pages"] == 4, records3)

# ---- Case 12: ingest.run() — record_id không có file nào khớp -> source_not_found ----
batch4 = case_dir("batch_missing")
raw4 = batch4 / "raw"
(raw4 / "prov" / "comm").mkdir(parents=True)
manifest4 = batch4 / "manifest.csv"
with open(manifest4, "w", encoding="utf-8", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["record_id", "province", "commune", "num_pages"])
    w.writerow(["R4", "prov", "comm", "7"])
records4 = run(manifest4, raw4, batch4 / "out")
check("record_id không có file -> status error + source_not_found",
      records4[0]["status"] == "error" and "source_not_found" in records4[0]["flags"], records4)

# ---- Case 13: path traversal trong manifest bị chặn ----
trav = case_dir("traversal")
raw2 = trav / "raw"
manifest2 = trav / "manifest.csv"
with open(manifest2, "w", encoding="utf-8", newline="") as f:
    w = _csv.writer(f)
    w.writerow(["record_id", "province", "commune", "num_pages"])
    w.writerow(["R1", "..\\..\\Windows", "comm", "7"])   # province traversal
    w.writerow(["../evil", "prov", "comm", "7"])          # record_id traversal
records = run(manifest2, raw2, trav / "out")
by_id2 = {r["record_id"]: r for r in records}
check("province traversal -> processing_error, không đọc ngoài raw",
      by_id2.get("R1", {}).get("status") == "error"
      and "processing_error" in by_id2.get("R1", {}).get("flags", []), by_id2.get("R1"))
check("record_id traversal -> file output không thoát thư mục out",
      not (trav / "out" / ".." / "evil.json").resolve().exists(), None)
try:
    _safe_segment("../x", "record_id")
    check("_safe_segment ném lỗi với '../x'", False)
except ValueError:
    check("_safe_segment ném lỗi với '../x'", True)
check("_safe_filename thay ký tự lạ", _safe_filename("../evil") == "___evil", _safe_filename("../evil"))
check("_safe_filename giữ nguyên slug hợp lệ", _safe_filename("LCA-LP-001") == "LCA-LP-001")


def main():
    failed = [r for r in _results if not r[1]]
    for name, ok, detail in _results:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if not ok and detail is not None:
            line += f"  -> {detail}"
        print(line)

    print(f"\n{len(_results) - len(failed)}/{len(_results)} pass")
    shutil.rmtree(_tmp_root, ignore_errors=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
