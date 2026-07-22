# Report tổng kết — Task 1: Schema chuẩn từ mẫu phiếu gốc

**Sprint:** Số hóa phiếu khảo sát Sprint 1 · **Hạng mục:** P0 số 1 · **Trạng thái:** ✅ Xong (đã qua review + sửa)
**Ngày:** 14/07/2026

---

## 1. Mục tiêu task (nhắc lại)

Tạo một file schema khai báo mô tả toàn bộ cấu trúc bảng hỏi, làm khung tham chiếu duy nhất cho mọi bước sau. Tiêu chí nghiệm thu (đặc tả 5.1): liệt kê đủ mọi câu hỏi mẫu gốc; mỗi câu có mã ổn định dùng xuyên suốt.

## 2. Deliverables

| File | Vai trò | Trạng thái |
|------|---------|-----------|
| [`schema/questionnaire_v1.json`](../schema/questionnaire_v1.json) | Schema đầy đủ: 34 câu in (41 mã `Q`) + header/consent + PAGE_NOTES = 46 mục | ✅ |
| [`schema/SCHEMA-FORMAT.md`](../schema/SCHEMA-FORMAT.md) | Tài liệu format: loại câu, trường bổ sung, toán tử `depends_on`, cách đếm trường, cách làm v2 | ✅ |
| [`scripts/validate_schema.py`](../scripts/validate_schema.py) | Validator: id/type/code/exclusive/matrix/page/depends_on + đếm trường | ✅ pass |
| [`tests/test_validate_schema.py`](../tests/test_validate_schema.py) | 14 test: nhánh pass + 10 nhánh bắt lỗi + 2 test tích hợp schema thật | ✅ 14/14 |

**Kết quả validator hiện tại:** `✅ Schema hợp lệ` — 46 mục (41 mã Q), **108 trường xuất ra**, exit 0.
**Kết quả test suite:** 14/14 pass, exit 0.

## 3. Điểm khác biệt bản in vs docx đã xử lý

Đối chiếu chéo `pretest_VN.docx` với cả 7 trang scan `LCA-LP-001/page-1.jpg`–`LCA-LP-001/page-7.jpg` — những chỗ chỉ tin docx sẽ thành lỗi dữ liệu:

- **Q14 = 18 dòng dữ liệu** (không phải 19): dòng "Việc nhà" là `group_header`. Lệch 1 dòng ở đây = 18 ô sai âm thầm.
- **Q32 có cột "Nội dung"** text tự do trước 4 cột lựa chọn; gạch xuyên suốt = trống (không phải `ambiguous_mark`).
- **Q10 mã in nhảy số** 1,2,3,4,6,7 (không có 5) — giữ `print_no`.
- **Q17 device_grid**: mỗi thiết bị tick độc lập Chồng/Vợ, "Không ai có" exclusive.
- **PAGE_NOTES** mỗi trang: hứng ghi chú viết tay ngoài vùng câu hỏi (trang 7 có thật).
- Page mapping thật của 7 trang được chốt trong schema.

## 4. Quyết định thiết kế đã chốt

- Mã câu = số in trên phiếu; giá trị đầu ra dùng `code` (slug không dấu), không dùng label → v2 đổi diễn đạt không phá dữ liệu cũ.
- 3 test case gắn cờ có thật trong phiếu mẫu (Q30 tick 3 ô, Q5 mâu thuẫn học vấn, Q1 có SĐT) ghi vào schema làm eval cho task sau.

## 5. Xử lý sau code review

Review chấm "Request changes (nhỏ)" với 5 lỗi + 5 gợi ý. Đã sửa **toàn bộ 5 lỗi** và **3/5 gợi ý** low-risk:

### Lỗi đã sửa

| # | Lỗi | Cách sửa | Ảnh hưởng |
|---|-----|----------|-----------|
| 1 | `count_export_fields` đếm PAGE_NOTES là 1 thay vì 7 | Nhánh `per_page` trả về `total_pages` | Benchmark trường đúng lại |
| 2 | Matrix bỏ sót cột `row_content_column` của Q32 | Cộng 1 trường/dòng khi có `row_content_column` | +8 trường Q32 |
| 3 | Chưa có quy ước export cho `other_text` | Chốt: mỗi `other_text` = 1 trường text riêng; đếm + ghi doc | +14 trường; nhất quán |
| 4 | Q27b `depends_on` thiếu case "Cả hai" → cờ giả | Đổi thành `not_in: [vo, ca_hai]` | Hết cờ giả khi chọn "Cả hai" |
| 5 | Q22b `equals` so mảng multi_select luôn false | Đổi thành `contains: chua` | depends_on Q22b chạy đúng |

Kết quả: benchmark trường **79 → 108** (con số đúng sau khi mô phỏng đầy đủ hình dạng bản ghi). Đây là mốc bước export sẽ đối chiếu.

### Gợi ý đã làm

- **Kiểm tra `page`** ∈ 1..`total_pages` (hoặc null khi `per_page`) — bắt typo trang.
- **Kiểm tra giá trị `depends_on`** có trong option code câu đích (không chỉ kiểm câu tồn tại).
- **Đưa `expected_data_rows` vào schema** thay cho hằng số hardcode trong validator — v2 chỉ sửa 1 file. Validator giờ **báo lỗi nếu matrix thiếu `expected_data_rows`**.

### Gợi ý chưa làm (ghi nhận, không chặn)

- Type `checkbox` riêng cho CONSENT_1/2 (hiện dùng `single_select` 1 option — chạy đúng). Cân nhắc khi thấy cần phân biệt "không tick" vs "không đọc được".

## 5b. Xử lý sau code review vòng 2

Review vòng 2 chấm **Approve**, còn 3 góp ý không chặn — đã sửa hết:

| # | Góp ý | Cách sửa |
|---|-------|----------|
| 1 | `count_export_fields.total_pages` là function-attribute (2 phong cách trong 1 file) | Truyền `total_pages` làm tham số, bỏ attribute — thống nhất với `validate()` |
| 2 | Negative test chạy ad-hoc rồi xóa, không giữ lại | Tạo [`tests/test_validate_schema.py`](../tests/test_validate_schema.py): 14 test cố định, không phụ thuộc pytest, chạy bằng env `survey-digitizer` |
| 3a | `depends_on` trỏ tới component của composite bị báo sai "câu không tồn tại" | `by_id` giờ index cả component composite |
| 3b | `in`/`not_in` nhận chuỗi thay vì mảng → thông báo khó hiểu | Thêm guard: báo rõ "cần giá trị là mảng" |

Bộ test cover: id trùng, mọi option exclusive, page sai khoảng, `per_page` có page, matrix thiếu/sai số dòng, 4 loại lỗi `depends_on`, cùng 2 nhánh pass (composite component, `in` mảng) và 2 test tích hợp (schema thật hợp lệ + đúng 108 trường). Toàn bộ 14/14 pass.

## 6. Kiểm chứng

- **Positive:** validator trên `questionnaire_v1.json` → pass, 108 trường, exit 0.
- **Negative:** chạy thử trên schema cố tình hỏng (page 99, depends_on trỏ code/câu không tồn tại, matrix thiếu `expected_data_rows`) → bắt đúng cả 4 lỗi, exit 1. Validator không "luôn pass".

## 7. Ghi chú môi trường

- Mọi lệnh Python dùng conda env **`survey-digitizer`** (Python 3.12) — đã ghi vào [AGENTS.md](../AGENTS.md).
- Script phải ép `sys.stdout` UTF-8 (console Windows mặc định cp1258 không in được tiếng Việt) — đã có sẵn trong validator, mẫu cho script sau.

## 8. Việc tiếp theo

- **Task 2 — Ingest & ghép trang** (P0 số 2): nhận nhiều ảnh/PDF, nhận diện số trang, ghép thành 1 phiếu; thiếu trang thì báo.
- Chưa gỡ được: cần 10–15 phiếu scan thật (blocker số 1) để pilot; quyết định chuẩn hóa địa bàn; ai làm review thủ công.
