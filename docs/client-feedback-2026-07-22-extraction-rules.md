# Phản hồi khách hàng 22/07/2026 — quy tắc trích xuất & thống kê

**Nguồn:** khách hàng gửi trực tiếp qua chat, nguyên văn giữ lại ở §1. Diễn giải + map vào schema/docs ở §2–§4.
**Áp dụng cho:** `schema/questionnaire_v1.json`, `schema/SCHEMA-FORMAT.md`, `docs/extraction-method.md`, `docs/implement-plan-03b-mc-extraction.md`, `data/ground_truth/LCA-LP-001.json`.

---

## 1. Nguyên văn khách gửi

> Địa điểm: Sapa có 2 xã (thôn Hàm Rồng Tả Phìn) — từng khu vực đã được chia riêng thành các folder.
> 2. Năm sinh: chia ra các khoảng dưới 35, 35-45 tuổi, >45 tuổi
> 3. Giới tính: chủ yếu Nữ
> 4. Dân tộc: Ghi rõ (nếu khác Kinh)
> 5. Chia cấp học (cấp 1, cấp 2, cấp 3)
> 6. Kết hôn năm bao nhiêu tuổi: chia khoảng — <18 tảo hôn, >18 bình thường
> 9. Bắt số năm (tính số năm kinh nghiệm tính đến 2026, chia khoảng <1 và >=1)
> 10. Nghề nghiệp
> 14. Dòng việc nhà có dấu gạch dưới là mô tả, không phải lựa chọn. Ô có chữ "ko" tức là không chọn. Chỗ "người khác" có text thì tính là có tick chọn.
> 15. Không cần detect chuẩn — có thì tốt thôi.
> 16. Lấy 16a, chỉ chia là tick cái nào thôi.
> 21b. Chỉ chia là có tick cái nào thôi (khác tính chung là khác kể cả có ghi thêm text hay không).
> 21c. Giống 15 và 16b, không cần detect.
> 22a, b. Chỗ khác cũng tính chung là khác.
> 27a. Nếu tick khác cũng tính chung là khác kể cả có ghi thêm mô tả khác là gì.
> 27b. Tương tự như mấy câu viết khác, bỏ qua.
> 32. Cột nội dung bỏ qua (kể cả có ghi text hay là các dấu gạch); ô có ký tự dạng "ko" cũng là không chọn (người khảo sát không làm việc đó).
> 34. Bỏ qua vì là câu trả lời viết tay.
>
> Ghi chú chung: chú ý những câu sẽ chọn, xong gạch đi và chọn cái khác. Không phải phiếu nào cũng dùng tick "v" — có phiếu dùng x, /, ... Đánh dấu lại TẤT CẢ những câu/phiếu nghi ngờ.

(Các số không có ghi chú riêng — 3, 7, 8, 11, 12, 13, 17, 18, 19, 20, 23, 24, 25, 26, 28, 29, 30, 31, 33 — hiểu là **không đổi gì so với schema hiện tại**, trừ khi rule chung ở dưới áp dụng.)

## 2. Diễn giải & quyết định thiết kế

### 2.1 Địa bàn — đã xử lý, xem `data/README.md`

Xác nhận: Sa Pa = 2 xã Hàm Rồng + Tả Phìn. `ta-phin-10phieu` đã đúng từ đầu. `sa-pa-25phieu` (trước ghi tạm "Phường Sa Pa/Kim Long 3") đổi thành `ham-rong-25phieu`, record_id `LCA-SPA-*` → `LCA-HR-*`. **Chưa xác nhận**: `Nậm Mòn`, `LCA-TPH-011` (Thôn Mã Tra) — vẫn còn trong blocker sprint plan.

### 2.2 Nguyên tắc phân tầng: KHÔNG đổi cái VLM đọc, chỉ thêm tầng "bucket cho thống kê"

Điểm mấu chốt (đã nói rõ ở cuối yêu cầu khách: *"những chỗ bảo chia khoảng... là để sau này thống kê"*): việc chia khoảng tuổi/cấp học/năm kinh nghiệm **không phải là thứ VLM phải tự quyết định lúc đọc ảnh**. VLM vẫn đọc giá trị thô như cũ (năm sinh viết tay, tuổi kết hôn viết tay, câu trả lời tự luận Q9). Một **tầng tính toán bằng code thường** (thuộc Task 6 — export/thống kê, không phải Task 3b/4/5) sẽ suy ra bucket từ giá trị thô đó. Lý do: (a) VLM tự bucket sẽ mất thông tin gốc, không sửa lại được nếu đổi ngưỡng; (b) một số bucket cần phép tính (tuổi = 2026 − năm sinh; số năm kinh nghiệm = 2026 − năm bắt đầu) — code làm chính xác hơn để VLM tự trừ.

→ Đã thêm khối `"stats_bucketing"` vào từng câu liên quan trong `schema/questionnaire_v1.json` (xem §3), mô tả **công thức bucket**, KHÔNG phải giá trị bucket có sẵn. Việc **code hoá** công thức này là của Task 6 (chưa làm ở plan này — plan này chỉ khai báo trong schema để Task 6 đọc).

### 2.3 Câu 9 — trường hợp đặc biệt: `free_text` nhưng cần rút ra 1 số

Q9 (`"Chị bắt đầu trồng cây dược liệu từ khi nào và vì sao?"`) vẫn là `free_text` (Task 5 transcribe) — nhưng khác các free_text khác, Task 5 **phải cố gắng rút ra năm bắt đầu** (hoặc số năm kinh nghiệm nếu ghi trực tiếp kiểu "10 năm nay") từ câu trả lời, ghi vào 1 trường phụ `Q9_derived_start_year` (hoặc `Q9_derived_years_exp` nếu câu trả lời ghi thẳng số năm chứ không ghi năm) — để Task 6 tính bucket `<1 năm` / `≥1 năm` (số năm kinh nghiệm = 2026 − năm bắt đầu). Nếu không đọc được năm/số năm rõ ràng (chữ khó đọc, trả lời mơ hồ như "từ lâu rồi") → để `null` + `needs_review`, **không suy đoán liều**.

### 2.4 Nguyên tắc chung "Khác (ghi rõ)" — generic bucket, TRỪ Q4

Với mọi câu có option "Khác (ghi rõ)" mà khách liệt kê rõ (`Q10`, `Q21b`, `Q22a`, `Q22b`, `Q27a` — và suy rộng ra cùng pattern cho `Q12`, `Q13`, `Q20`, `Q28` dù khách không liệt kê tên nhưng cùng dạng câu "ai làm việc X"/nhiều lựa chọn có "Khác"): bản thống kê chỉ cần biết **có chọn "Khác" hay không** (code `khac`), **không cần** nội dung chữ viết tay đi kèm cho mục đích thống kê. Điều này **khớp sẵn** với kiến trúc Task 3b đã thiết kế (3b chỉ đọc mã lựa chọn, không đọc `other_text` — xem `implement-plan-03b-mc-extraction.md` §2.2) — **không cần sửa gì ở Task 3b**, chỉ cần Task 6 khi tổng hợp thống kê KHÔNG hiển thị chi tiết `other_text` của các câu này (dù bản đầy đủ/`output/full/` vẫn giữ, vì khách yêu cầu dữ liệu đầy đủ không xoá gì).

**Ngoại lệ — Q4 (Dân tộc):** ngược lại hoàn toàn — bản thống kê **phải hiện tên dân tộc cụ thể** (Mông, Dao, Tày...) khi khác Kinh, không gộp chung "khác". Đây là lý do phải phân biệt rõ theo từng câu, không áp dụng 1 rule chung cho mọi "Khác".

### 2.5 Câu chỉ cần best-effort (không bắt buộc đọc đúng)

`Q15`, `Q16b`, `Q21c`, `Q27b`, `Q31`, `Q34` (và `PAGE_NOTES`, cùng bản chất) — mọi câu `free_text` thuần tự luận, khách xác nhận: cố gắng đọc là tốt, **không bắt buộc chính xác 100%, không phải tiêu chí chặn DoD**. Khác với `Q9` (§2.3) vẫn cần cố đọc ra được con số. Đây **không phải rule mới về mặt kỹ thuật** — khớp đúng tinh thần đặc tả gốc "chấp nhận ~60% tự luận không cần sửa tay" (`extraction-method.md` §4) — khách chỉ đang xác nhận lại, nên chỉ cần ghi rõ vào docs, không đổi kiến trúc.

### 2.6 Q16a, Q21b — chỉ lấy mã lựa chọn

Xác nhận (không phải thay đổi): `Q16a` chỉ cần mã lựa chọn (đã đúng scope Task 3b sẵn — subfield `Q16a_chi_tiet` thuộc Task 5). `Q21b` tương tự — chỉ tick, không cần phân biệt nội dung "Khác" (đã khớp §2.4).

### 2.7 Q14 (ma trận) — 2 điều chỉnh

1. **"Dòng việc nhà có dấu gạch dưới là mô tả, không phải lựa chọn"** — làm rõ: đây là mô tả `group_header: "Việc nhà"` đã có sẵn trong schema (dòng phân cách, không phải dữ liệu — validator không đếm). Khách xác nhận đúng cách hiểu hiện tại, không đổi gì, chỉ ghi rõ vào note để VLM prompt không hiểu nhầm dòng tiêu đề là 1 lựa chọn.
2. **"Người khác có text thì tính là có tick chọn"** — **ĐÂY LÀ THAY ĐỔI THẬT**, ngược với quy tắc cũ ở `SCHEMA-FORMAT.md` (bản trước: chữ ở cột "Người khác" bị bỏ qua nếu dòng đã có tick hợp lệ ở cột khác). Quy tắc mới: **bất kỳ chữ viết tay nào ở cột "Người khác"/"Khác" đều tính là đã chọn cột đó**, bất kể cột khác đã tick hay chưa → dòng có thể thành đa lựa chọn (`["chong", "nguoi_khac"]` chẳng hạn). Đã sửa `SCHEMA-FORMAT.md` §Quy tắc diễn giải đánh dấu (xem diff) và rà lại ground truth `LCA-LP-001` dòng `bao_duong_xe` theo quy tắc mới (xem `docs/task-03a-report.md` phần bổ sung).

### 2.8 Q32 — bỏ cột "Nội dung"

`row_content_column` ("Nội dung", cột text tự do trước 4 cột lựa chọn) — khách xác nhận **bỏ qua hoàn toàn**, kể cả khi có chữ viết hay dấu gạch chéo. Điều chỉnh: Task 4 (ma trận Q32) sẽ không trích xuất trường `noi_dung` nữa — số trường xuất ra của Q32 giảm (ảnh hưởng tới con số 108 trường ở `SCHEMA-FORMAT.md` §Đếm trường xuất ra, xem §3 dưới). "ô có chữ 'ko'" ở Q32 áp dụng đúng quy tắc `ko` = trống như Q14 (không đổi).

### 2.9 Quy tắc đánh dấu chung (áp dụng toàn bộ, không riêng câu nào)

1. **Đa dạng kiểu đánh dấu**: không chỉ tick "✓"/"v" — có phiếu dùng "x", "/", khoanh tròn, v.v. Prompt VLM phải liệt kê rõ các dạng này là tương đương "đã chọn", không chỉ nhận diện 1 kiểu.
2. **Gạch bỏ rồi chọn lại**: nếu thấy 1 dấu bị gạch bỏ/xoá (cancel) và có dấu mới ở lựa chọn khác → chỉ tính lựa chọn **mới**, dấu bị gạch bỏ không tính, KHÔNG coi là đa lựa chọn.
3. **Flag liberal**: bất kỳ trang/câu nào nghi ngờ (đánh dấu lạ, chữ viết không chắc, kiểu đánh dấu khác thường) → gắn cờ `needs_review`, thà thừa cờ còn hơn bỏ sót — nhắc lại tinh thần đã có ở `extraction-method.md` §4, khách chỉ nhấn mạnh lại.

## 3. Cập nhật số đếm trường (108 → cần tính lại)

Bỏ `row_content_column` của Q32 (§2.8) làm giảm số trường so với `SCHEMA-FORMAT.md` hiện ghi 108. **Chưa cập nhật con số chính thức trong plan này** — cần chạy lại `scripts/validate_schema.py` sau khi sửa `questionnaire_v1.json` (đã đánh dấu việc này trong schema bằng note, xem §4; con số 108 cũ vẫn còn trong `SCHEMA-FORMAT.md` cho tới khi ai đó chạy validator và cập nhật — **việc còn lại, chưa làm trong lượt này** vì thay đổi field-count ảnh hưởng tới `scripts/validate_schema.py` code, thuộc phạm vi sửa lớn hơn ngoài phạm vi "cập nhật docs" của lượt này).

## 4. Danh sách file đã sửa theo phản hồi này

- `data/README.md` — bảng mã tỉnh/xã, folder Sa Pa/Hàm Rồng.
- `data/manifest.csv` — record_id + commune Hàm Rồng.
- `schema/SCHEMA-FORMAT.md` — quy tắc diễn giải đánh dấu (đa dạng ký hiệu, gạch-bỏ-chọn-lại, "Người khác" đổi rule).
- `schema/questionnaire_v1.json` — thêm `stats_bucketing` cho Q2/Q5/Q6/Q9, note cho Q4/Q14/Q32, đánh dấu Q15/16b/21c/27b/31/34 là best-effort.
- `data/ground_truth/LCA-LP-001.json` — rà lại Q14 `bao_duong_xe` theo rule "Người khác" mới.
- `docs/task-03a-report.md` — ghi chú bổ sung việc rà lại ground truth.
- `docs/extraction-method.md` — tham chiếu chính sách best-effort + quy tắc đánh dấu mới.
- `docs/implement-plan-03b-mc-extraction.md` — tham chiếu file này, xác nhận kiến trúc 3b đã khớp sẵn (không cần đổi code plan).
- `sprint-plan-survey-digitization.md` — cập nhật blocker địa bàn + trỏ tới file này.
