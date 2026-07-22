"""Hàm thuần cho Task 2 — Ingest & Assembly.

Không phụ thuộc CLI/manifest — chỉ thao tác trên nguồn của một phiếu.
Xem docs/implement-plan-02-ingest-assembly.md để biết bối cảnh & quyết định thiết kế.

Quy ước (chốt 22/07/2026): mỗi phiếu là ĐÚNG 1 file — ảnh đơn trang hoặc PDF nhiều
trang — đặt phẳng tại `<province>/<commune>/<record_id>.<ext>`. Đã bỏ hẳn quy ước cũ
"nhiều file rời trong 1 folder `<record_id>/`": toàn bộ data thật (85 phiếu +
phiếu mẫu `LCA-LP-001`) đều đã về dạng 1 file/phiếu, không còn phiếu nào cần gộp
từ nhiều ảnh rời. Vì chỉ có 1 file/phiếu, thứ tự trang lấy trực tiếp từ thứ tự
trang nội bộ của file đó (PDF) — không cần natural-sort tên nhiều file nữa.

Nguyên tắc vẫn giữ: Task 2 KHÔNG đọc nội dung trang. `tentative_page` chỉ là thứ
tự trang trong chính file nguồn — Task 3 (VLM đọc nội dung) mới chốt số trang thật.
"""

import shutil
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
PDF_EXT = ".pdf"
ACCEPTED_EXTS = IMAGE_EXTS | {PDF_EXT}


def render_pdf_pages(pdf_path, out_dir, dpi=200):
    """Render mỗi trang PDF thành 1 ảnh PNG trong out_dir. Trả về list Path ảnh đã tạo.

    Ném lỗi nếu PDF không mở được / hỏng — gọi nơi khác bắt và gắn cờ 'unreadable'.
    """
    import fitz  # pymupdf — import trễ để lib này test được cả khi thiếu dependency

    pdf_path = Path(pdf_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    out_paths = []

    doc = fitz.open(pdf_path)
    try:
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix)
            out_path = out_dir / f"{pdf_path.stem}__p{i}.png"
            pix.save(out_path)
            out_paths.append(out_path)
    finally:
        doc.close()

    return out_paths


def _is_readable_image(path):
    """True nếu file mở được như ảnh hợp lệ (không kiểm nội dung khảo sát, chỉ kiểm file không hỏng)."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def _error_record(record_id, expected_pages, flag):
    return {
        "record_id": record_id,
        "expected_pages": expected_pages,
        "found_pages": 0,
        "pages": [],
        "flags": [flag],
        "status": "error",
    }


def build_assembly(record_id, source, expected_pages, render_dir):
    """Xây assembly record cho một phiếu.

    record_id: mã phiếu (khớp tên file theo quy ước manifest).
    source: Path tới file nguồn duy nhất của phiếu — `<province>/<commune>/<record_id>.<ext>`
      (ảnh đơn trang hoặc PDF nhiều trang). Không còn nhánh folder nhiều file rời.
    expected_pages: số trang kỳ vọng (từ manifest num_pages).
    render_dir: nơi ghi ảnh render ra từ PDF (output/assembly/_render/<record_id>/).

    Trả về dict assembly record — xem docs/implement-plan-02-ingest-assembly.md §4.

    LƯU Ý ngữ nghĩa status="ok": nghĩa là "đủ SỐ trang đọc được", KHÔNG phải "đúng 7 trang
    phân biệt về nội dung". Task 2 không đọc nội dung nên không phát hiện được trang bị
    nhân đôi/lệch thứ tự bên trong chính file PDF — việc đó do Task 3 (đọc nội dung) bắt
    qua số trang thật. Đừng coi status="ok" ở đây là "phiếu đã sạch".
    """
    source = Path(source)
    render_dir = Path(render_dir)

    # Dọn cache render cũ để không tích ảnh PDF mồ côi qua các lần chạy lại.
    if render_dir.exists():
        shutil.rmtree(render_dir, ignore_errors=True)

    if not (source.is_file() and source.suffix.lower() in ACCEPTED_EXTS):
        return _error_record(record_id, expected_pages, "source_not_found")

    pages = []
    if source.suffix.lower() == PDF_EXT:
        try:
            rendered = render_pdf_pages(source, render_dir)
        except Exception:
            return _error_record(record_id, expected_pages, "unreadable")
        for i, r in enumerate(rendered, start=1):
            pages.append({
                "source_file": source.name,
                "kind": "pdf_page",
                "image_path": r.as_posix(),
                "tentative_page": i,
            })
    else:
        if not _is_readable_image(source):
            return _error_record(record_id, expected_pages, "unreadable")
        pages.append({
            "source_file": source.name,
            "kind": "image",
            "image_path": source.as_posix(),
            "tentative_page": 1,
        })

    flags = []
    n = len(pages)
    # missing_page / extra_page đã hàm ý "sai số trang" — không thêm count_mismatch (thừa).
    if n < expected_pages:
        flags.append("missing_page")
    elif n > expected_pages:
        flags.append("extra_page")

    status = "ok" if not flags else "needs_review"

    return {
        "record_id": record_id,
        "expected_pages": expected_pages,
        "found_pages": n,
        "pages": pages,
        "flags": flags,
        "status": status,
    }
