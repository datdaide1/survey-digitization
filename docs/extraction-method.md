# Phương pháp trích xuất: Schema-guided VLM Extraction

**Dự án:** Số hóa phiếu khảo sát giấy → JSON có cấu trúc
**Trạng thái:** Đã chốt (brainstorm 14/07/2026) — làm nền cho Sprint 1
**Tài liệu liên quan:** [Đặc tả](../spec/Survey_Digitization_Spec.docx) · [Sprint plan](../sprint-plan-survey-digitization.md) · [Implement plan Task 1 — Schema](implement-plan-01-questionnaire-schema.md) · [Quy tắc nghiệp vụ từ khách 22/07](client-feedback-2026-07-22-extraction-rules.md)

---

## 1. Quyết định

Dùng **VLM (LLM có vision, Claude API) trích xuất theo từng trang, dẫn hướng bằng schema khai báo**, kèm một tầng kiểm soát bằng code thường bên ngoài VLM. Không dùng OCR/OMR truyền thống.

Nói đầy đủ: *schema-guided VLM extraction với validation và human-in-the-loop theo cờ* — không phải "đưa ảnh cho AI đọc".

## 2. Các phương án đã loại và lý do

| Phương án | Lý do loại |
|-----------|-----------|
| OCR truyền thống (Tesseract, Google Vision) | Kém với chữ viết tay tiếng Việt có dấu; trả về text thô, không hiểu ngữ nghĩa checkbox — vẫn phải tự map vào schema |
| OMR cổ điển (OpenCV, template matching) | Phiếu không có fiducial mark, đánh dấu tay đa dạng (tick/X/khoanh/tô), scan có thể nghiêng; chi phí xây + hiệu chỉnh vượt lợi ích ở quy mô ~100 phiếu |
| Document AI cloud (Azure DI custom, Textract) | Cần vài chục mẫu gán nhãn để train — hiện chỉ có 1 phiếu mẫu |
| VLM + schema (chọn) | Nhận được mọi kiểu đánh dấu, đọc chữ viết tay tiếng Việt, hiểu ngữ cảnh; ~700 ảnh (100 phiếu × 7 trang) — chi phí API không đáng kể |

## 3. Kiến trúc — 3 mảnh

### 3.1 VLM đọc ảnh

- Mỗi API call nhận **1 ảnh trang + slice schema của đúng trang đó** (không nhét cả 34 câu vào một prompt). Prompt nhỏ → ít ảo giác, debug được từng trang.
- Output **ép theo JSON schema** (structured output / tool use), giá trị dùng `code` của option, không dùng label.
- PDF đầu vào: render mỗi trang thành ảnh (~200 DPI, pymupdf/pdf2image) rồi đi chung pipeline với JPG — không có nhánh xử lý riêng cho PDF.

### 3.2 Schema dẫn hướng

- VLM không tự do mô tả trang — chỉ được điền vào khung câu hỏi đã khai báo trong `schema/questionnaire_v1.json` (34 câu + header/consent/`PAGE_NOTES`, xem implement plan Task 1).
- Schema là cấu hình, không phải code: đổi mẫu phiếu v2 chỉ sửa file schema (yêu cầu P2 của đặc tả).
- Schema phải có chỗ chứa cho cả những gì ngoài dự kiến (`PAGE_NOTES` + cờ `margin_note`) — nếu không, pipeline sẽ lặng lẽ vứt thông tin ngoài 34 câu.

### 3.3 Tầng kiểm soát ngoài VLM (code thường, không phải AI)

1. **Validation output**: đủ trường theo schema (câu bỏ trống = `null`, không thiếu trường); ma trận đúng số dòng × cột.
2. **Đối chiếu nhãn dòng ma trận**: VLM phải đọc lại *nhãn dòng từ ảnh* (không chỉ vị trí), code đối chiếu với schema — chống lệch dòng hàng loạt ở Q14 (18×5). Phương án B nếu vẫn lệch: crop bảng thành từng dòng, hỏi từng dòng.
3. **Self-consistency**: chạy trích xuất 2 lần (hoặc 2 prompt khác nhau) cho câu trắc nghiệm; chỗ nào 2 lần khác nhau → tự gắn cờ. Confidence tự khai của VLM không đáng tin — đây là nguồn tín hiệu "cần kiểm tra" thay thế.
4. **Quét PII** trên toàn bộ text sau trích xuất (kể cả tự luận) — xem mục 5.
5. **Gắn cờ**: `multi_mark_on_single_select`, `ambiguous_mark` (+ tọa độ vùng ảnh), `margin_note`, mâu thuẫn theo `depends_on`/`exclusive`… Không tự suy diễn đáp án.

> **Cập nhật 22/07 — quy tắc đánh dấu bổ sung từ khách** (chi tiết + nguyên văn: [client-feedback-2026-07-22-extraction-rules.md](client-feedback-2026-07-22-extraction-rules.md), đã đưa vào [schema/SCHEMA-FORMAT.md §Quy tắc diễn giải đánh dấu](../schema/SCHEMA-FORMAT.md)): (a) không phải phiếu nào cũng đánh dấu kiểu tick "✓" — có phiếu dùng "x", "/", khoanh tròn…, prompt VLM phải nhận diện mọi dạng; (b) nếu thấy 1 dấu bị gạch bỏ (huỷ) và 1 dấu mới ở lựa chọn khác → chỉ tính dấu mới, không phải đa lựa chọn; (c) cột "Người khác" trong ma trận — bất kỳ chữ viết tay nào cũng tính là đã chọn, **kể cả khi cột khác đã có tick** (đổi khác quy tắc gốc — xem lịch sử đổi ở [task-03a-report.md §8](task-03a-report.md)); (d) khi nghi ngờ, thà gắn cờ thừa còn hơn bỏ sót — áp dụng cho toàn bộ 34 câu, không riêng câu nào.

## 4. Định nghĩa thành công

Mục tiêu 98% trắc nghiệm đến từ **VLM (~90–95%) cộng tầng kiểm soát cộng vòng review theo cờ** — không phải từ VLM một mình.

Tiêu chí "số hóa toàn bộ nội dung" = **không có thông tin nào trên giấy rơi mất mà không có cờ**, chứ không phải "máy đọc đúng 100%". Máy được phép sai, miễn là sai có cờ để người review bắt được. 4 lớp nội dung với độ khó khác nhau:

| Lớp | Độ khó | Chiến lược |
|-----|--------|-----------|
| Trắc nghiệm đơn/đa (~20 câu) | Thấp | VLM + self-consistency, mục tiêu 98% |
| Ma trận Q14/Q32 | Cấu trúc — lệch 1 dòng = 18 ô sai âm thầm | Đọc nhãn dòng từ ảnh + đối chiếu schema; fallback crop từng dòng |
| Tự luận viết tay | Nội dung — chấp nhận ~60% không cần sửa tay | Phiên âm hết + confidence + luồng review |
| Ngoài 34 câu (ghi chú lề, SĐT chèn, viết thêm) | Dễ bị bỏ sót nhất | `PAGE_NOTES` + `margin_note` trong schema |

> **Cập nhật 22/07 — khách xác nhận lại tầng "Tự luận viết tay" không đồng nhất về yêu cầu chính xác.** Đa số câu tự luận (`Q15`, `Q16b`, `Q21c`, `Q27b`, `Q31`, `Q34`) là **best-effort thật sự** — đọc được là tốt, không phải tiêu chí chặn DoD (khớp tinh thần "~60% không cần sửa tay" ở trên, khách chỉ xác nhận lại rõ ràng hơn). **Ngoại lệ: `Q9`** — dù cũng là `free_text`, Task 5 phải cố rút ra được năm bắt đầu trồng dược liệu (hoặc số năm kinh nghiệm nếu ghi trực tiếp) thành 1 trường phụ có cấu trúc, vì Task 6 cần con số này để tính bucket thống kê "<1 năm / ≥1 năm kinh nghiệm". Chi tiết đầy đủ mọi câu: [client-feedback-2026-07-22-extraction-rules.md](client-feedback-2026-07-22-extraction-rules.md).

## 5. PII — thiết kế 2 lớp

Yêu cầu khách hàng: dữ liệu **đầy đủ** (kể cả họ tên/SĐT), dù không dùng cho thống kê. Không xóa gì cả:

- **Lớp đầy đủ** (giao khách hàng): mỗi phiếu 1 JSON đủ mọi trường — họ tên, SĐT, 34 câu, ghi chú lề.
- **Lớp thống kê** (phân tích): là **phép chiếu** của lớp đầy đủ — sinh bằng một bước lọc, không chạy trích xuất 2 lần. Trừ trường PII, cộng `record_id` để lần ngược.
- PII lạc trong tự luận (thực tế: SĐT viết ngay Q1 ở phiếu mẫu): **giữ nguyên ở bản đầy đủ, che ở bản thống kê** (thay bằng `[SĐT]`/`[TÊN]`) + gắn cờ để review xác nhận.

Cần chốt với khách hàng: họ nhận file đầy đủ kèm PII, hay chỉ cần biết "thông tin được lưu, tra được khi cần" (giao file thống kê + kho PII giữ lại — an toàn hơn khi truyền file).

## 6. Rủi ro chính

| Rủi ro | Giảm thiểu |
|--------|-----------|
| Overfit vào 1 phiếu mẫu duy nhất (`LCA-LP-001.pdf`, 7 trang) | Nhập tay phiếu mẫu thành **ground truth JSON trước khi viết code** — thành bộ eval cho mọi lần chỉnh prompt; xin 10–15 phiếu thật (blocker số 1) |
| Ma trận Q14 lệch dòng khi ảnh nghiêng | Mục 3.3.2; đây là vùng rủi ro kỹ thuật cao nhất |
| Confidence VLM không phản ánh sai số thật | Self-consistency thay vì tin điểm tự khai |
| PII lọt vào file thống kê | Quét PII bắt buộc trước khi ghi file (mục 5) |
| Chi phí/giới hạn API lô lớn | Đo cost/phiếu ngay trong pilot |

## 7. Bài test nghiệm thu "toàn bộ nội dung" (phiếu mẫu)

Sau khi pipeline chạy xong `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-001.pdf` (7 trang): cầm JSON và 7 tờ scan, hỏi — *có thông tin nào trên giấy mà không tìm được chỗ tương ứng trong JSON không?* (kể cả SĐT, ký hiệu "R" góc trang 1, đoạn viết thêm dưới lời cảm ơn trang 7). "Không còn gì" = đạt.
