# Implement Plan — Task 2: Ingest & Assembly (gom phiếu, chuẩn hoá trang)

**Sprint:** Số hóa phiếu khảo sát Sprint 1 — hạng mục P0 số 2, ước lượng ~1 ngày
**Người đọc:** dev thực hiện; người thu thập dữ liệu (phần Input contract)
**Đầu vào:** cây thư mục `data/raw/<tỉnh>/<xã>/<record_id>.<ext>` (mặc định) hoặc `data/raw/<tỉnh>/<xã>/<record_id>/` (dự phòng, xem cập nhật 22/07 ở §2) + `data/manifest.csv`
**Đầu ra:** với mỗi phiếu, một *assembly record* (danh sách ảnh trang đã chuẩn hoá + cờ toàn vẹn) sẵn sàng cho bước trích xuất.

---

## 1. Thay đổi hướng tiếp cận so với plan gốc

Plan gốc giả định dữ liệu hiện trường **rời rạc, không phân nhóm** → máy phải *tự nhận diện nhóm và thứ tự trang* theo nội dung (phần phức tạp & rủi ro nhất sprint, dễ sinh lỗi ngầm khi máy đoán sai).

Thực tế dữ liệu **đã được tổ chức 1 folder = 1 phiếu** (theo `record_id`). Việc gom nhóm — phần đắt nhất — đã do con người làm lúc thu thập. Vì vậy Task 2 **co lại** từ "nhận diện + ghép" thành **"chuẩn hoá + kiểm tra toàn vẹn"**. Bỏ hẳn phần tự gom nhóm/tự xếp thứ tự theo nội dung khỏi P0 (không làm cả hai — thừa và dễ mâu thuẫn).

## 2. Input contract (bắt buộc — cho người thu thập)

> **Cập nhật 22/07:** dữ liệu thật cho thấy 1 file (PDF) thường đã là 1 phiếu đầy đủ, không phải 1 trang — nên quy ước dưới đây đổi thành **mặc định 1 file phẳng `<record_id>.<ext>`, không bọc folder**. Folder `<record_id>/` (mô tả gốc bên dưới) chỉ còn là quy ước dự phòng khi phiếu thật sự gồm nhiều file rời. Chi tiết + lý do: [data/README.md](../data/README.md). `ingest.py`/`assembly.py` đã cập nhật để tự nhận cả 2 dạng (`_resolve_source`, `build_assembly`).
>
> **Cập nhật 22/07 (muộn hơn) — bỏ luôn quy ước dự phòng.** Phiếu mẫu `LCA-LP-001` (trường hợp duy nhất từng cần folder nhiều file rời) cũng đã được gộp thành 1 PDF 7 trang. Không còn phiếu nào — kể cả mẫu — cần nhánh folder. `_resolve_source`/`build_assembly` đã đơn giản hoá về đúng 1 nhánh: 1 file/phiếu. Xem sự cố + cách sửa ở [data/README.md](../data/README.md) và [task-02-report.md §7b](task-02-report.md).

- **1 file = 1 phiếu (mặc định).** Tên file = `record_id.<ext>` (`LCA-LP-001.pdf`), đặt trực tiếp trong `<tỉnh>/<xã>/`, không cần folder con.
- **Dự phòng — 1 folder = 1 phiếu**, dùng khi phiếu gồm nhiều file rời (ảnh từng trang chưa gộp). Tên folder = `record_id`. Đây là cách máy biết ảnh nào thuộc phiếu nào trong trường hợp này.
- **Mọi file trong folder (khi dùng quy ước dự phòng) phải thuộc đúng phiếu đó.** Đây là kỷ luật con người duy nhất cần giữ.
- **Tên file để nguyên bản gốc, thứ tự bất kỳ.** *Không cần* đổi tên thành `page-1..7`. Máy tự xác định số trang bằng nội dung (xem §5). Tên file gốc ghi vào cột `original_filename` của manifest để truy vết.
- Định dạng chấp nhận: ảnh (`.jpg/.jpeg/.png`) và `.pdf`. Một phiếu có thể trộn nhiều định dạng (vd 6 ảnh + 1 pdf).
- Mỗi phiếu có một dòng trong `manifest.csv` với `num_pages` (chuẩn: 7).

> Vì sao không cần `page-N`: thứ tự trang lấy từ (a) sort tên file gốc làm phỏng đoán ban đầu, và (b) **nội dung trang** làm nguồn chốt ở bước trích xuất — 7 trang rất khác nhau nên VLM đọc là biết trang mấy. Đổi tên tay vừa tốn công vừa không bắt được lỗi xếp nhầm trang; kiểm theo nội dung thì bắt được.

## 3. Ranh giới Task 2 ↔ Task 3 (trích xuất)

| Việc | Chủ | Ghi chú |
|------|-----|---------|
| Gom nhóm ảnh theo phiếu | **Con người** (folder) | Input contract |
| Discovery, đối chiếu manifest ↔ folder | Task 2 | |
| PDF → ảnh từng trang | Task 2 | Đưa PDF về chung một dạng ảnh |
| Kiểm tra toàn vẹn (đủ/thiếu/thừa/đọc được) | Task 2 | Cờ ở mức phiếu |
| Thứ tự trang *tạm* (sort tên file) | Task 2 | Chỉ là phỏng đoán |
| **Số trang thật (theo nội dung)** | **Task 3** | VLM đọc trang → stamp `page` thật; lệch với thứ tự tạm → cờ `page_order_mismatch` |
| Đối chiếu đủ trang 1..N cuối cùng | Task 3 | Sau khi có số trang thật |

Điểm mấu chốt: **Task 2 không cần VLM** — thuần code, dễ test. Việc xác định số trang theo nội dung để bước trích xuất làm (nó đọc trang sẵn rồi), tránh chạy VLM hai lần.

## 4. Deliverables

| File | Nội dung |
|------|----------|
| `scripts/ingest.py` | Discovery + PDF→ảnh + kiểm tra toàn vẹn; xuất assembly record/phiếu |
| `scripts/lib/assembly.py` | Hàm thuần (discover, render_pdf, natural_sort, integrity_check) để test riêng |
| `tests/test_ingest.py` | Test toàn vẹn: đủ trang, thiếu, thừa, file hỏng, PDF nhiều trang, trộn định dạng |
| Cập nhật `data/README.md` | Ghi rõ input contract mới (tên file bất kỳ) |

### Assembly record (đề xuất) — `output/assembly/<record_id>.json`

```json
{
  "record_id": "LCA-LP-001",
  "expected_pages": 7,
  "pages": [
    {"tentative_page": 1, "source_file": "1.jpg", "kind": "image"},
    {"tentative_page": 2, "source_file": "2.jpg", "kind": "image"}
  ],
  "flags": [],
  "status": "ok"
}
```

`tentative_page` = thứ tự theo sort tên file (chưa chốt). Bước trích xuất sẽ ghi `page` thật và so lại.

## 5. Các bước xử lý một phiếu

1. **Discovery**: đọc `manifest.csv`; với mỗi `record_id`, tìm folder tương ứng theo `province/commune`. Folder có trong manifest mà không có trên đĩa (hoặc ngược lại) → cờ `manifest_folder_mismatch`.
2. **Thu thập file**: liệt kê mọi `.jpg/.png/.pdf` trong folder (bỏ file ẩn/tạm).
3. **Chuẩn hoá PDF**: mỗi PDF render ra ảnh từng trang (~200 DPI, `pymupdf`) → nhập chung danh sách ảnh với các JPG. Một PDF 7 trang = 7 ảnh.
4. **Sắp thứ tự tạm**: natural sort theo tên file (`2.jpg` trước `10.jpg`) → gán `tentative_page` 1..N.
5. **Kiểm tra toàn vẹn** (§6).
6. **Xuất assembly record** + tổng hợp cờ.

## 6. Quy tắc toàn vẹn & cờ (mức phiếu)

| Điều kiện | Cờ | Xử lý |
|-----------|-----|-------|
| Số trang (sau render PDF) ít hơn `num_pages` | `missing_page` | Dừng phiếu, đưa vào danh sách cần bổ sung |
| Số trang nhiều hơn `num_pages` (trùng/lạc) | `extra_page` | Dừng phiếu, cần người xác nhận |
| File không mở được / hỏng (ảnh hoặc PDF) | `unreadable` (kèm tên file) | Dừng phiếu |
| Folder rỗng nhưng có trong manifest | `empty_folder` | Dừng phiếu |
| Dòng manifest hỏng (num_pages sai kiểu, thiếu cột) | `processing_error` | Cách ly — chỉ hỏng phiếu đó, lô vẫn chạy |
| (P1) ảnh mờ/nghiêng/thiếu góc | `low_quality` (cảnh báo) | Không dừng, đánh dấu để ưu tiên review |

`missing_page`/`extra_page` đã hàm ý sai số trang — không thêm cờ `count_mismatch` (thừa).

Triết lý giữ nguyên từ đặc tả: **thiếu/bất thường thì báo, không xử lý tiếp với dữ liệu khuyết**. Không có trang nào bị bỏ âm thầm.

**Giới hạn đã biết:** Task 2 chỉ đếm *số* trang, không đọc nội dung — nên phiếu bị *nhân đôi 1 trang + thiếu 1 trang khác* (số vẫn khớp) sẽ qua với `status: ok`. Đây là việc của Task 3 (số trang thật theo nội dung). `status: ok` ở Task 2 = "đủ số trang đọc được", không phải "đúng 7 trang phân biệt".

## 7. Tiêu chí nghiệm thu (từ đặc tả 5.1 + điều chỉnh)

- Chạy trên `LCA-LP-001/` (7 ảnh) → assembly record 7 trang, `status: ok`, không cờ.
- Xoá thử 1 ảnh → báo đúng `missing_page`, thiếu 1 trang, không tạo record "ok".
- Thêm 1 ảnh lạ vào folder → `extra_page`.
- Bỏ 1 PDF 3 trang thay cho 3 ảnh → render đúng 3 trang, tổng vẫn khớp.
- Đổi tên file lộn xộn (`z.jpg, a.jpg…`) → vẫn thu đủ 7 trang (thứ tự tạm có thể sai, đúng theo thiết kế — Task 3 chốt lại theo nội dung).

## 8. Rủi ro

| Rủi ro | Giảm thiểu |
|--------|-----------|
| Sort tên file ≠ thứ tự trang thật (file upload lộn xộn) | Chấp nhận — `tentative_page` chỉ là phỏng đoán; Task 3 chốt theo nội dung và cờ `page_order_mismatch` |
| Người thu thập bỏ nhầm trang phiếu khác vào folder | `extra_page` bắt khi đổi số lượng; Task 3 (đọc nội dung) bắt nốt trang lạc mà số lượng vẫn khớp |
| PDF scan chất lượng thấp sau render | Chọn DPI đủ cao; cờ `low_quality` (P1) |
| `pymupdf` chưa cài trong env | `pip install pymupdf` vào env `survey-digitizer` ngay bước 1 |

## 9. Các bước làm (tổng ~1 ngày)

1. Cài `pymupdf` vào env `survey-digitizer`; viết `lib/assembly.py` (discover, natural_sort, render_pdf, integrity_check). *(~3h)*
2. `ingest.py` ghép các hàm + đọc manifest + xuất assembly record. *(~2h)*
3. `tests/test_ingest.py` — dựng folder giả trong scratchpad cho các case §7. *(~2h)*
4. Chạy thật trên `LCA-LP-001/`, đối chiếu output. *(~30ph)*
5. Cập nhật `data/README.md` input contract. *(~30ph)*

## 10. Quyết định đã chốt

- Bỏ tự gom nhóm/tự xếp thứ tự theo nội dung khỏi P0 — dùng folder (nhóm) + nội dung ở Task 3 (thứ tự thật).
- **Không yêu cầu đổi tên `page-N`** — tên file gốc giữ nguyên, đưa vào `original_filename`.
- Task 2 thuần code, không gọi VLM — số trang thật thuộc về Task 3.
- "Ghép" = tạo assembly record logic, **không nối thành 1 PDF**.
