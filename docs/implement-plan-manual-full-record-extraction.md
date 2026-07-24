# Implement Plan — Trích xuất thủ công toàn bộ 85 phiếu (không qua Claude API)

**Ngày viết:** 2026-07-23
**Lý do tồn tại của plan này:** Task 3b có code gọi Claude API (`scripts/extract_mc.py`), nhưng tốn tiền theo token và Task 4/5/6 (ma trận, tự luận, flags/PII/export) còn chưa viết code. Khách xác nhận: **cuối tuần này chỉ cần kết quả JSON** cho 85 phiếu thật, **chưa quyết định** có cần pipeline tự động chạy lại trong tương lai hay không. Vì vậy quyết định: một phiên Claude (đang chat trực tiếp với người dùng, có khả năng đọc ảnh — Cowork/Claude Code, KHÔNG phải gọi Anthropic API) sẽ **tự đọc từng ảnh trang đã render sẵn và tự điền JSON theo schema**, thay cho việc set `ANTHROPIC_API_KEY` và chạy Task 3b–6. Cách này không tốn API, không cần viết thêm code trích xuất — nhưng KHÔNG có tầng self-consistency 2-lần-API-call gốc, nên plan này có bước tự-đối-chiếu thay thế (xem §5).

**Nếu bạn là Claude đọc plan này:** đây là toàn bộ ngữ cảnh bạn cần. Không cần hỏi lại người dùng trừ khi gặp đúng các điểm nêu ở §7 (Khi nào phải dừng lại hỏi).

---

## 1. Mục tiêu & phạm vi

**Mục tiêu:** Với mỗi phiếu thật trong `data/manifest.csv` (85 dòng), tạo 1 file `output/full/<record_id>.json` — JSON đầy đủ 46 mục câu hỏi (kể cả PII, kể cả bỏ trống = `null`), đúng format của ground truth mẫu `data/ground_truth/LCA-LP-001.json`, có `flags`/`confidence`/`needs_review` khi cần.

**KHÔNG thuộc phạm vi plan này** (để lại cho việc khác, thuần code, không cần đọc ảnh):
- Bucket thống kê (`stats_bucketing` trong schema — tuổi/cấp học/năm kinh nghiệm) — đây là phép tính từ giá trị thô, thuộc Task 6, làm bằng script sau khi có đủ `output/full/*.json`.
- Bản thống kê che PII (`output/stats/`) và file gộp `combined.csv` — cũng là Task 6, code thường.
- Quyết định có xây pipeline API tự động lâu dài hay không — **chưa chốt với khách**, không tự ý code thêm phần này.

Nói cách khác: plan này chỉ lo phần "đọc ảnh ra JSON", để dữ liệu sẵn sàng cho bất kỳ bước xử lý nào sau đó.

## 2. Vì sao KHÔNG cần đụng vào PDF gốc

Task 2 (ingest & assembly) đã chạy xong cho toàn bộ 85 phiếu, ảnh từng trang đã được render sẵn dạng PNG:

```
output/assembly/<record_id>.json          # danh sách 7 trang + đường dẫn ảnh, đã có sẵn
output/assembly/_render/<record_id>/<record_id>__p1.png ... p7.png
```

→ **Chỉ cần đọc trực tiếp các file `.png` này**, không cần mở PDF, không cần chạy lại `ingest.py`. Nếu `output/assembly/<record_id>.json` báo `"status": "ok"` và đủ 7 trang thì dùng thẳng. Nếu khác `"ok"` hoặc thiếu trang → xem §7 (dừng lại hỏi), không tự đoán.

## 3. Tài liệu tham chiếu bắt buộc đọc trước khi bắt đầu

Đọc theo đúng thứ tự này (đừng bỏ qua, các quy tắc đánh dấu rất dễ làm sai nếu không đọc kỹ):

1. `schema/questionnaire_v1.json` — cấu trúc 46 mục câu hỏi (nguồn chuẩn duy nhất, không phải con số "108" — số đó đang chờ tính lại, xem `schema/SCHEMA-FORMAT.md` mục "Đếm trường xuất ra").
2. `schema/SCHEMA-FORMAT.md` — đặc biệt mục "Quy tắc diễn giải đánh dấu" (8 quy tắc, cập nhật 24/07: mục 6 mở rộng cho xung đột dạng exclusive, thêm mục 8 cho multi-mark suy ra từ ghi chú lề) và mục "Page mapping thật" (trang nào chứa câu nào).
3. `docs/client-feedback-2026-07-22-extraction-rules.md` — quy tắc nghiệp vụ khách gửi 22/07, đặc biệt §2.3 (Q9 phải rút ra năm), §2.4 (câu "Khác" không cần nội dung trừ Q4), §2.5 (6 câu tự luận chỉ cần best-effort), §2.7–2.8 (Q14/Q32).
4. `data/ground_truth/LCA-LP-001.json` — **ví dụ mẫu format output chính xác**, copy cấu trúc y hệt, đổi giá trị theo phiếu đang đọc. Đây là "đáp án" duy nhất từng được nhân công đối chiếu — dùng làm chuẩn hình dạng JSON.

## 4. Quy tắc đánh dấu — bản rút gọn (đọc thêm bản đầy đủ ở SCHEMA-FORMAT.md nếu phân vân)

1. Chỉ tick/X/khoanh tròn/gạch chéo = "đã chọn". Chữ viết (vd "ko", "không") thay vì đánh dấu hình học = **trống**, không phải `ambiguous_mark`.
2. `ambiguous_mark` chỉ dùng khi rõ ràng có 1 dấu nhưng không biết đánh vào ô nào (vd vắt ngang 2 cột). Chữ "ko" không thuộc diện này.
3. Nhiều kiểu đánh dấu khác nhau tuỳ phiếu (tick, x, /, khoanh tròn...) — đều tính là đã chọn, đừng chỉ nhận 1 kiểu.
4. Cột "Người khác"/"Khác" trong ma trận (Q14, Q17...): **bất kỳ chữ viết tay nào** ở cột này = đã chọn cột đó, kể cả khi dòng đã có tick ở cột khác (→ thành đa lựa chọn, vd `["chong","nguoi_khac"]`).
5. Gạch bỏ rồi chọn lại: nếu thấy 1 dấu bị gạch huỷ rõ ràng + 1 dấu mới ở lựa chọn khác → chỉ tính dấu **mới**, không phải multi-mark. **Áp dụng cả khi 2 dấu xung đột là 1 lựa chọn thường + 1 lựa chọn exclusive** (vd "Không"/"Không là hội viên của tổ chức nào" bị tick cùng lựa chọn khác — case thật: `LCA-BH-002` Q19, `LCH-SLL-001` Q11/Q23, `LCH-SLL-002` Q8/Q16a): nếu 1 trong 2 dấu bị gạch/tô xoá rõ ràng → chỉ lấy dấu còn nguyên, chốt 1 giá trị cụ thể, **đừng** giữ cả hai hay để trống chỉ vì hai lựa chọn "loại trừ nhau" (`exclusive_conflict`). Nếu không chắc dấu nào bị gạch, vẫn gắn `needs_review` nhưng ghi rõ trong `note` dấu hiệu nghi ngờ để người review quyết định nhanh.
6. Q32: cột "Nội dung" (text tự do đầu mỗi dòng) **bỏ qua hoàn toàn**, không trích xuất (khách xác nhận 22/07). Gạch chéo xuyên dòng ở Q32 = trống.
7. Khi nghi ngờ bất kỳ điều gì (kiểu đánh dấu lạ, chữ không chắc, đã gạch hay chưa) → gắn cờ `needs_review` thừa còn hơn bỏ sót. Áp dụng toàn bộ câu, không riêng câu nào.
8. **Multi-mark suy ra từ ghi chú lề, không có tick hình học** (mới 24/07, phát hiện khi review `output/full/*.json`): nếu 1 câu `single_select` KHÔNG có ô nào được tick hình học rõ ràng, nhưng có ghi chú viết tay ở lề/dưới nhiều ô cùng chỉ ra rằng nhiều lựa chọn đều áp dụng (vd "như nhau", "2 vợ chồng như nhau", "làm tất cả mọi thứ") → coi **TẤT CẢ** các lựa chọn được ghi chú đó là đã chọn, trả về mảng đầy đủ + gắn `multi_mark_on_single_select`, xử lý giống hệt khi có tick hình học thật (mục 4 dưới). Đây là ngoại lệ có chủ đích của mục 1 (chỉ tick hình học mới tính) — chỉ áp dụng khi ghi chú thể hiện rõ ý định chọn nhiều ô, không suy diễn thêm. Case thật đã biết: Q30 phiếu `LCA-TPH-006`, `LCH-SLL-004` (và `LCH-SLL-004` Q14 dòng `so_che`).

**Câu chỉ cần best-effort** (đọc được là tốt, không phải tiêu chí chặn): `Q15, Q16b, Q21c, Q27b, Q31, Q34`, và `page_notes`.

**Ngoại lệ — Q9**: dù là `free_text`, PHẢI cố rút ra năm bắt đầu (hoặc số năm kinh nghiệm nếu ghi trực tiếp) vào 1 field phụ `Q9_derived_start_year` (hoặc `Q9_derived_years_exp`). Không đọc được rõ → `null` + `needs_review`, không suy đoán liều.

**Câu "Khác (ghi rõ)"**: với `Q10, Q21b, Q22a, Q22b, Q27a` (và cùng dạng `Q12, Q13, Q20, Q28`) — vẫn ghi `other_text` như bình thường vào bản đầy đủ (khách yêu cầu dữ liệu đầy đủ, không xoá gì) dù sau này bản thống kê sẽ không hiển thị. **Ngoại lệ Q4 (Dân tộc)**: phải ghi rõ tên dân tộc cụ thể khi khác Kinh, không gộp "khác".

## 5. Thay thế cho self-consistency 2-lần-API-call

Vì không gọi API 2 lần độc lập, làm bù bằng cách này cho MỌI câu đơn/đa lựa chọn và ma trận:

1. Đọc trang, điền giá trị lần đầu.
2. Trước khi ghi file, **nhìn lại riêng các câu vừa điền có dấu hiệu mơ hồ** (nhiều hơn 1 dấu, dấu không rõ ràng, kiểu đánh dấu lạ so với các câu khác cùng phiếu) — đọc lại lần 2 độc lập (đừng nhìn giá trị vừa ghi trước, đọc lại ảnh như lần đầu). Nếu 2 lần ra khác nhau → gắn cờ `needs_review` thay vì tự chọn 1 trong 2.
3. Với ma trận (Q14, Q17, Q32): **đọc nhãn dòng thật từ ảnh** rồi mới đối chiếu với `rows[].label` trong schema theo đúng thứ tự — đây là chỗ dễ lệch dòng nhất (lệch 1 dòng = sai âm thầm cả dòng). Đừng giả định thứ tự dòng trong ảnh khớp 100% với schema mà không nhìn lại nhãn.

## 6. Quy trình từng phiếu

```
Với mỗi record_id trong docs/manual-extraction-progress.csv có status = pending:
  1. Đọc output/assembly/<record_id>.json — xác nhận status "ok", đủ 7 trang.
     Nếu KHÔNG → xem §7, ghi vào cột note của progress file, chuyển phiếu khác.
  2. Đọc lần lượt 7 ảnh output/assembly/_render/<record_id>/<record_id>__p1.png .. p7.png
     (dùng Read tool, page mapping: trang1=header/consent/Q1-8, trang2=Q9-13,
     trang3=Q14-16a, trang4=Q16b-21b, trang5=Q21c-27a, trang6=Q27b-31, trang7=Q32-34)
  3. Điền JSON theo đúng cấu trúc data/ground_truth/LCA-LP-001.json, áp quy tắc §4-5.
  4. Ghi ra output/full/<record_id>.json
  5. Chạy: python scripts/validate_record.py schema/questionnaire_v1.json output/full/<record_id>.json
     Nếu ❌ → sửa ngay, chạy lại tới khi ✅ (script chỉ bắt lỗi THIẾU trường,
     không bắt lỗi đọc sai nội dung — vẫn phải tự cẩn thận nội dung).
  6. Cập nhật docs/manual-extraction-progress.csv: status=done, done_by=<tên/id phiên>,
     done_date=<ngày>.
  7. Lặp lại phiếu tiếp theo.
```

**Phiếu `LCA-LP-001`**: đã có `data/ground_truth/LCA-LP-001.json` làm bằng tay (Task 3a), không cần đọc lại ảnh từ đầu. Chỉ cần copy file đó thành `output/full/LCA-LP-001.json` (cấu trúc đã đúng chuẩn output). Progress file đã đánh dấu `done` sẵn cho phiếu này.

**Khuyến nghị hiệu chỉnh (không bắt buộc, nên làm nếu còn quota)**: trước khi làm 84 phiếu thật, đọc `data/ground_truth/LCA-LP-001.json` cùng lúc với 2-3 ảnh trang có case gắn cờ đã biết (`Q30` multi-mark, `Q5` mâu thuẫn, `Q14` dòng `bao_duong_xe`) để hiểu đúng tinh thần trước khi áp cho phiếu chưa có đáp án — rẻ hơn nhiều so với làm sai hàng loạt rồi sửa lại 84 phiếu.

## 7. Khi nào phải DỪNG LẠI hỏi người dùng, không tự đoán

- `output/assembly/<record_id>.json` có `status` khác `"ok"`, hoặc thiếu trang, hoặc `flags` không rỗng.
- Ảnh mờ tới mức không đọc được thông tin định danh cơ bản (tên, ngày, địa điểm) — không đoán bừa `record_id` nào tương ứng.
- Phát hiện 1 file PDF có vẻ chứa 2 phiếu khác nhau gộp lại (đã từng xảy ra thật — xem sự cố `LCA-LP-001`/`LCA-LP-017` trong `data/README.md`) — đừng tự tách, báo lại.
- Bất kỳ câu hỏi/lựa chọn nào trên ảnh KHÔNG khớp với bất kỳ mục nào trong schema (mẫu phiếu khác version) — dừng, không tự chế field mới.

## 8. Theo dõi tiến độ — BẮT BUỘC vì việc này sẽ trải dài nhiều phiên (quota tuần)

File `docs/manual-extraction-progress.csv` (85 dòng, 1 dòng/phiếu) là nguồn chuẩn duy nhất về phiếu nào đã xong. **Luôn đọc file này đầu tiên** khi bắt đầu 1 phiên mới — lọc `status = pending`, làm tiếp từ đó, không làm lại phiếu đã `done`. Cập nhật ngay sau mỗi phiếu xong (đừng gộp cập nhật cuối phiên — phiên có thể bị ngắt giữa chừng do hết quota).

Ước lượng tải: 85 phiếu × 7 ảnh = ~595 lượt đọc ảnh + 85 lượt ghi/validate. Đây là khối lượng lớn — **đừng cố làm hết trong 1 phiên**, cứ làm tới đâu chắc tới đó rồi dừng, phiên sau đọc progress file tiếp tục.

## 9. Sau khi cả 85 phiếu done

Viết `docs/task-manual-extraction-report.md` (theo đúng pattern báo cáo cũ của dự án — xem `docs/task-03b-report.md` làm mẫu): tổng số phiếu, số case gắn cờ theo loại, các phiếu gặp vấn đề ở §7, thời gian/số phiên đã dùng. Không cần đo accuracy chính thức (đó là Task 7 — Pilot & Calibration, cần data thật đối chiếu tay, không thuộc phạm vi plan này).
