# Báo cáo — Trích xuất thủ công toàn bộ 85 phiếu (implement-plan-manual-full-record-extraction.md)

**Ngày hoàn tất trích xuất:** 2026-07-24
**Trạng thái:** ✅ Cả 85/85 phiếu đã có `output/full/<record_id>.json`, đều pass `scripts/validate_record.py` (46 câu hỏi, đầy đủ trường, 0 lỗi).

**Bước hiện tại (sau khi trích xuất xong):** Review thủ công để verify lại toàn bộ 85 bản ghi trước khi tổng hợp thống kê theo yêu cầu khách hàng. Ưu tiên 57 phiếu có `needs_review: true` (xem §3, §7) và 2 case cần khách xác nhận (§4.1, §4.2). Việc build pipeline code tự động (API/VLM, Task 3b trở đi) **không phải việc đang chạy** — đã dời thành phần nghiên cứu/roadmap dài hạn, chỉ cân nhắc lại nếu dự án tiếp tục với số lượng phiếu lớn hơn nhiều so với 85 phiếu hiện tại (xem "Trạng thái hiện tại" trong [README.md](../README.md)).

---

## 1. Tổng quan

Theo kế hoạch ở `docs/implement-plan-manual-full-record-extraction.md`: thay vì gọi Claude API (`scripts/extract_mc.py`, cần `ANTHROPIC_API_KEY`), phiên Claude Code này tự đọc trực tiếp ảnh từng trang đã render sẵn (`output/assembly/_render/<record_id>/*.png`) và tự điền JSON theo `schema/questionnaire_v1.json`, đối chiếu format với `data/ground_truth/LCA-LP-001.json`.

- 1 phiếu (`LCA-LP-001`) đã có sẵn từ Task 3a (ground truth thủ công) — chỉ copy sang `output/full/`.
- 84 phiếu còn lại được đọc và điền trong nhiều phiên Claude Code khác nhau (theo dõi qua `docs/manual-extraction-progress.csv`); phiên này xử lý nốt 16 phiếu cuối (`LCA-HR-011..025` và `LCA-MTR-001`).
- Validator (`scripts/validate_record.py`) chỉ bắt lỗi **thiếu trường cấu trúc**, không bắt lỗi đọc sai nội dung — độ chính xác nội dung dựa vào việc đọc ảnh cẩn thận + cơ chế tự-đối-chiếu 2 lượt cho câu nghi ngờ (§5 của plan), không có tầng self-consistency 2-API-call như pipeline gốc.

## 2. Kết quả theo khu vực (`data/manifest.csv`)

| Khu vực | Số phiếu | Prefix record_id |
|---|---|---|
| Lùng Phình (Lào Cai) | 16 | `LCA-LP-*` |
| Tả Phìn (Lào Cai) | 10 | `LCA-TPH-*` |
| Hàm Rồng (Lào Cai) | 25 | `LCA-HR-*` |
| Mã Tra (Lào Cai, mã tạm) | 1 | `LCA-MTR-001` |
| Bắc Hà (Lào Cai) | 6 | `LCA-BH-*` |
| Mao Sao Phìn (Lai Châu) | 23 | `LCH-MSP-*` |
| Sì Lở Lầu (Lai Châu) | 4 | `LCH-SLL-*` |
| **Tổng** | **85** | |

(Bảng mã vùng đầy đủ xem `data/README.md`.)

## 3. Thống kê cờ (flags) gắn trong toàn bộ 85 bản ghi

Quét tự động `answers.*.flags` trên toàn bộ `output/full/*.json`:

| Flag | Số lần xuất hiện |
|---|---|
| `multi_mark_on_single_select` | 180 |
| `ambiguous_mark` | 19 |
| `conflicting_answer` | 16 |
| `exclusive_conflict` | 10 |

- **57/85 phiếu** có ít nhất 1 trường gắn `needs_review: true` — phần lớn là các câu tự luận best-effort (Q15, Q16b, Q21c, Q27b, Q31, Q34) chữ viết tay khó đọc, hoặc các case đa lựa chọn/mâu thuẫn cần người review xác nhận cách diễn giải.
- `multi_mark_on_single_select` là cờ phổ biến nhất — phần lớn ở Q8, Q10, Q11, Q20, Q21a, Q30 (câu đơn lựa chọn nhưng người trả lời tick nhiều ô), và Q14 (matrix, nhiều dòng tick >1 cột).
- `exclusive_conflict` (10 lần) — case option loại trừ ("Không"/"Không là hội viên"/"Không gặp khó khăn gì") bị tick cùng lựa chọn khác mà không có dấu gạch huỷ rõ ràng ở dấu nào; theo quy tắc 6 mở rộng, các case này được giữ nguyên (không tự chọn 1 trong 2) và gắn cờ để người review quyết định.

## 4. Các phiếu có vấn đề đáng chú ý (cần khách/PM xem lại)

### 4.1. `LCA-HR-021` — Sai lệch địa bàn
`META_LOCATION` viết tay trên phiếu ghi **"Tà Phìn, P. Sa Pa, LC"**, nhưng phiếu này thuộc batch 25 phiếu `LCA-HR-*` mà khách đã xác nhận 22/07/2026 là xã **Hàm Rồng** (xem `data/manifest.csv`). Dân tộc người trả lời (Q4 = "Dao") cũng khớp với Tả Phìn hơn Hàm Rồng (các phiếu HR khác thường là Mông). **Chưa tự đổi record_id/xã** — cần khách xác nhận đây có phải điều tra viên đi khảo sát chéo địa bàn, hay có sai sót gán batch.

### 4.2. `LCA-HR-024` — Q32 có người quyết định ngoài schema
Nhiều dòng của Q32 ghi chữ "bme ch"/"bm chồng" (bố mẹ chồng) là người quyết định thực tế, nhưng schema Q32 chỉ có 4 lựa chọn (Vợ/Chồng/Cùng quyết định/Con cái) — không có option cho người ngoài vợ-chồng-con. Đã để `null` + ghi chú đầy đủ, không tự chế thêm option. Người trả lời còn rất trẻ (sinh 2005, mới kết hôn, sống cùng bố mẹ chồng) — có thể cần thêm option "khác/người khác" cho Q32 ở schema v2 nếu case này lặp lại ở phiếu khác.

### 4.3. `LCA-MTR-001` — 8 trang thay vì 7 (đã giải thích được)
Phiếu có `expected_pages=8` (khác chuẩn 7 trang) do điều tra viên viết dở bảng Q14 ở 1 trang, gạch huỷ, rồi làm lại toàn bộ bảng trên 1 trang chèn thêm. Đã xác định đúng trang chứa dữ liệu thật (trang làm lại, không bị gạch) và dùng trang đó — không dùng dữ liệu rỗng ở trang bị huỷ. Chi tiết trong `note_record_level` của `output/full/LCA-MTR-001.json`. record_id "MTR" vẫn là mã tạm (xã Mã Tra chưa xác nhận chính thức với khách).

### 4.4. `LCA-HR-025` — Case tảo hôn nghiêm trọng
Người trả lời kết hôn năm **14 tuổi** (2022), sinh năm 2008 (17-18 tuổi lúc điền phiếu 2026). Đã ghi nhận trung thực theo phiếu, không chỉnh sửa. `Q9` (năm bắt đầu trồng dược liệu = 2018) tạo ra mâu thuẫn tuổi tác nhẹ (mới 10 tuổi lúc đó) — có thể câu trả lời tính theo mốc gia đình bắt đầu trồng chứ không phải cá nhân, đã ghi chú `needs_review`, không tự suy diễn.

### 4.5. `LCA-HR-011` — Case tảo hôn khác
Kết hôn năm 14 tuổi (suy ra từ ghi chú lề "26 năm rồi" + "14 tuổi", khớp nội bộ với năm sinh 1986).

## 5. Quy trình đã áp dụng

Theo đúng §6 của implement plan cho từng phiếu:
1. Đọc `output/assembly/<record_id>.json` xác nhận `status: "ok"`.
2. Đọc lần lượt các ảnh trang theo page mapping chuẩn (7 trang) — riêng `LCA-MTR-001` có page mapping điều chỉnh do 8 trang.
3. Điền JSON theo cấu trúc `data/ground_truth/LCA-LP-001.json`, áp toàn bộ 8 quy tắc đánh dấu ở `schema/SCHEMA-FORMAT.md`.
4. Chạy `scripts/validate_record.py` tới khi ✅.
5. Cập nhật `docs/manual-extraction-progress.csv` ngay sau mỗi phiếu (status=done, done_by, done_date, note tóm tắt các flag chính).

Không phiếu nào rơi vào các điều kiện dừng-hỏi ở §7 (status assembly khác "ok", ảnh mờ không đọc được định danh, PDF nghi gộp 2 phiếu, câu hỏi lạ ngoài schema) — 2 trường hợp gần giống (`LCA-HR-021` sai địa bàn, `LCA-HR-024` Q32 ngoài schema) được xử lý bằng cách **ghi chú đầy đủ và tiếp tục trích xuất** thay vì dừng hẳn, vì đây là bất thường ở 1 câu/1 trường thông tin, không phải lỗi cấu trúc file/PDF.

## 6. Ngoài phạm vi (để lại cho việc khác — thuần code, không cần đọc ảnh)

Theo đúng §1 của implement plan, các việc sau **chưa làm** trong task này:
- Bucket thống kê (`age_bracket`, `education_level_bracket`, `marriage_age_bracket`, `experience_years_bracket`) — Task 6, tính từ giá trị thô đã có sẵn trong `output/full/*.json`.
- Bản thống kê che PII (`output/stats/`) và `combined.csv` — Task 6.
- Đo accuracy chính thức so với đáp án tay — Task 7 (Pilot & Calibration), cần dữ liệu đối chiếu tay thật, ngoài phạm vi task này.
- Quyết định xây pipeline API tự động lâu dài — chưa chốt với khách, không tự ý code thêm.

## 7. Khuyến nghị bước tiếp theo

1. Xác nhận với khách 2 case ở mục 4.1 và 4.2 (địa bàn `LCA-HR-021`, option thiếu ở Q32 cho `LCA-HR-024`).
2. Review có trọng điểm 57 phiếu có `needs_review` — ưu tiên các flag `exclusive_conflict` (10) và `conflicting_answer` (16) vì đây là mâu thuẫn logic rõ ràng, dễ verify nhanh so với chữ viết tay khó đọc thuần tuý.
3. Khi bắt đầu tổng hợp thống kê, nhớ chạy lại `scripts/validate_schema.py` để chốt số trường xuất ra chính thức (bỏ `row_content_column` của Q32 — xem ghi chú ở `schema/SCHEMA-FORMAT.md` §Đếm trường xuất ra, hiện vẫn ghi 108 cũ, cần cập nhật).

## 8. Trạng thái hiện tại và hướng đi tiếp theo (cập nhật 2026-07-24)

- **Đang làm:** review thủ công toàn bộ 85 bản ghi ở `output/full/` để verify nội dung (không chỉ cấu trúc), chuẩn bị dữ liệu sạch cho bước tổng hợp thống kê theo yêu cầu khách hàng.
- **Chưa làm, chờ sau review:** bucket thống kê (age/education/marriage/experience), tách lớp `output/stats/` ẩn danh, `combined.csv`, và các bảng/báo cáo thống kê thực tế cho khách.
- **Phần code pipeline tự động (API/VLM):** toàn bộ phần trích xuất bằng code (`scripts/extract_mc.py`, Task 3b sống với API key, ma trận, tự luận tự động, statistical engine chạy tự động...) **giữ nguyên ở trạng thái nghiên cứu** — không phải việc cần hoàn thiện ngay. Có giá trị nếu sau này dự án tiếp tục với số lượng phiếu lớn hơn nhiều (hàng trăm/nghìn phiếu) và làm tay không còn khả thi. Xem bảng "Trạng thái hiện tại" ở [README.md](../README.md) để biết việc nào đang chạy thật và việc nào là roadmap dài hạn.
