"""Pure ingest/assembly helpers for one PDF or image source per record.

This layer checks file readability, renders PDF pages and compares the observed
page count with the project expectation. It does not interpret page content;
``tentative_page`` is only the source-file order.
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

    ``status=ok`` means the expected number of readable pages was found. Content
    order and duplicate-page detection remain extraction/review responsibilities.
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
