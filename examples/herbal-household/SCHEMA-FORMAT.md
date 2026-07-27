# Format Schema Bảng Hỏi — `questionnaire_v1.json`

Tài liệu này mô tả cách đọc và sửa file schema. Schema là **cấu hình duy nhất** mô tả cấu trúc bảng hỏi; mọi bước sau (ghép trang, trích xuất, gắn cờ, xuất JSON) đều đọc từ đây. Đổi mẫu phiếu → sửa file này, không sửa code.

## Cách chạy validator

```
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/validate_schema.py schema/questionnaire_v1.json
```

Kết quả kỳ vọng (v1): 46 mục câu hỏi (41 mục mã `Q`), **108 trường xuất ra**, `✅ Schema hợp lệ`. Con số 108 là mốc để bước export đối chiếu: mỗi bản ghi phiếu phải đủ 108 trường kể cả khi bỏ trống (giá trị `null`, không thiếu trường). Cách đếm xem §Đếm trường xuất ra.

Kiểm thử chính validator (nhánh pass + các nhánh bắt lỗi):

```
& "E:\anaconda3\envs\survey-digitizer\python.exe" tests/test_validate_schema.py
```

## Cấu trúc file

```
{
  "schema_version": "v1",
  "form_name": ..., "project": ..., "total_pages": 7,
  "conventions": { ... },       // quy ước giá trị đầu ra
  "questions": [ { ... }, ... ] // danh sách câu hỏi theo thứ tự phiếu
}
```

## Các loại câu (`type`)

| Type | Ý nghĩa | Giá trị xuất ra |
|------|---------|-----------------|
| `text` | Điền ngắn 1 dòng | chuỗi phiên âm, hoặc `null` |
| `free_text` | Tự luận nhiều dòng | chuỗi nguyên văn + `confidence` + `needs_review` |
| `single_select` | Chọn đúng 1 | `code` của option được đánh dấu |
| `multi_select` | Chọn nhiều | mảng `code` |
| `matrix` | Bảng dòng × cột | mỗi dòng → `code` cột được đánh (hoặc mảng nếu đa đánh) |
| `device_grid` | Lưới thiết bị × {Chồng, Vợ} | mỗi dòng → mảng cột được đánh |
| `composite` | Câu ghép nhiều thành phần khác loại | object các `components` |

## Các trường trên một câu hỏi

- `id` — **mã ổn định**, dùng xuyên suốt hệ thống. Theo đúng số in trên phiếu (`Q14`, `Q16a`). Không đánh lại số.
- `page` — trang bản in thật (đã đối chiếu scan, **không theo docx**).
- `section` — `header` / `consent` / `A` / `B1` / `B2` / `B3` / `meta`.
- `text` — nội dung câu hỏi (rút gọn).
- `type` — xem bảng trên.
- `options` / `rows` / `columns` — tuỳ loại câu.

### Trường bổ sung (thêm khi cần)

| Trường | Đặt ở | Ý nghĩa |
|--------|-------|---------|
| `pii: true` | câu | Trường định danh. **Vẫn trích xuất bình thường** vào bản đầy đủ; chỉ bị loại/che ở phép chiếu lớp thống kê (Q1). Bước tách PII cũng quét SĐT lẫn trong text. Xem [extraction-method.md §5](../docs/extraction-method.md). |
| `other_text: true` | option / row | Lựa chọn "Khác (ghi rõ)" kèm dòng điền tự do → **sinh thêm 1 trường text riêng** (xem §Đếm trường). |
| `exclusive: true` | option | Nếu chọn cùng option khác → cờ mâu thuẫn (vd "Không là hội viên", "Chưa", "Không gặp khó khăn"). |
| `subfield` | câu hoặc option | Trường phụ đi kèm → **sinh thêm 1 trường** (Q6 tuổi kết hôn, Q23 "cụ thể là gì"). Ở cấp **câu** có thể là mảng nhiều def (như `derived_subfield`) nếu sau này cần — chưa câu nào dùng dạng mảng. Ở cấp **option** vẫn chỉ hỗ trợ 1 def/option. |
| `derived_subfield` | câu | Trường suy ra từ nội dung câu, không in trên phiếu → **sinh thêm 1 trường mỗi def**; có thể là 1 object hoặc **mảng nhiều def** (Q9: `Q9_derived_start_year` + `Q9_derived_years_exp`, xem [client-feedback-2026-07-22-extraction-rules.md](../docs/client-feedback-2026-07-22-extraction-rules.md) §2.3). |
| `depends_on` | câu | Câu điều kiện `{question, <toán tử>}`. Dùng cho tầng gắn cờ, **không chặn trích xuất**. Xem §Toán tử depends_on. |
| `print_no` | option | Số in trên phiếu khi khác thứ tự tự nhiên (Q10 nhảy 1,2,3,4,6,7). |
| `group_header` | row của matrix | Dòng tiêu đề nhóm, **không phải dòng dữ liệu** (Q14 "Việc nhà"). Validator không đếm. |
| `row_content_column` | matrix | Cột text tự do đứng trước các cột lựa chọn (Q32 "Nội dung") → **sinh 1 trường text/dòng**. |
| `expected_data_rows` | matrix | Số dòng dữ liệu kỳ vọng (không kể `group_header`). Validator so số dòng thực với giá trị này — **nguồn chốt duy nhất**, khai ngay trong schema. |
| `strike_through_means_empty: true` | matrix | Gạch chéo xuyên cột = trống, không phải `ambiguous_mark` (Q32). |
| `per_page: true` | câu | Sinh **một trường cho mỗi trang** (PAGE_NOTES — ghi chú lề; v1 = 7 trường). |

## Toán tử depends_on

`depends_on` khai đúng **1** toán tử. Validator kiểm câu đích tồn tại và giá trị tham chiếu có trong option code câu đích.

| Toán tử | Giá trị | Dùng cho | Ví dụ |
|---------|---------|----------|-------|
| `equals` / `not_equals` | 1 code | câu đích `single_select` | Q21b: `{question: Q21a, not_equals: chua_lan_nao}` |
| `in` / `not_in` | mảng code | `single_select`, nhiều nhánh | Q27b: `{question: Q27a, not_in: [vo, ca_hai]}` |
| `contains` / `not_contains` | 1 code | câu đích `multi_select` (giá trị là mảng) | Q22b: `{question: Q22a, contains: chua}` |

Lưu ý: câu đích multi_select thì giá trị trả về là **mảng** — phải dùng `contains`, không dùng `equals` (so mảng với chuỗi luôn false).

## Đếm trường xuất ra

Con số validator in ra (`Tổng trường xuất`) = số trường tối thiểu mỗi bản ghi phải có (kể cả `null`). Quy tắc:

- `single/multi/text/free_text`: **1** trường trả lời, cộng thêm **1 cho mỗi def trong `subfield`** cấp câu (1 nếu là object, hoặc bằng số phần tử nếu là mảng), **1** cho mỗi option có `subfield` riêng, **1 cho mỗi def trong `derived_subfield`** (1 nếu là object, hoặc bằng số phần tử nếu là mảng — vd Q9 = 2), và mỗi option `other_text`.
- `composite`: tổng các `components`.
- `matrix`: **1** trường/dòng dữ liệu; cộng **1/dòng** nếu có `row_content_column`; cộng **1** cho mỗi dòng `other_text`.
- `device_grid`: **1** trường/dòng, cộng **1** nếu có `extra_option`.
- `per_page`: **total_pages** trường (v1 = 7).

v1 = **108** trường (con số gốc, trước phản hồi khách 22/07). Sai lệch số này ở bước export nghĩa là có trường bị bỏ sót hoặc đếm dư.

> **Cập nhật 22/07 — con số 108 cần tính lại, CHƯA làm trong lượt sửa docs này.** Khách xác nhận bỏ qua `row_content_column` ("Nội dung") của Q32 (xem [client-feedback-2026-07-22-extraction-rules.md](../docs/client-feedback-2026-07-22-extraction-rules.md) §2.8) — làm giảm số trường xuất ra của Q32 so với cách đếm gốc ở trên. Việc sửa `scripts/validate_schema.py` (bỏ đếm `row_content_column` khi field đó được đánh dấu bỏ qua) và chạy lại validator để lấy con số chính thức mới **chưa thực hiện** — thuộc phạm vi sửa code, ngoài phạm vi "cập nhật docs/schema annotation" của lượt này. Nhớ làm trước khi bắt đầu Task 4 (ma trận Q32).
>
> **Cập nhật 24/07 — `count_export_fields`/validator đã sửa để đếm `derived_subfield`, con số thực tế giờ là 110.** Q9 đổi `derived_subfield` từ 1 def thành mảng 2 def (`Q9_derived_start_year` + `Q9_derived_years_exp`, §2.3) mà trước đó `count_export_fields` không hề đếm tới (bug riêng, không liên quan việc bỏ `row_content_column` ở trên) — đã sửa `scripts/validate_schema.py` để cộng đúng số def trong `derived_subfield`, chạy validator ra 108 + 2 = **110**. Việc tính lại cho `row_content_column` ở caveat 22/07 phía trên vẫn CHƯA làm — con số cuối cùng còn có thể đổi tiếp sau khi làm việc đó.

## Quy ước giá trị đầu ra (`conventions`)

- **Giá trị dùng `code`, không dùng `label`.** Đổi cách diễn đạt label ở v2 không phá dữ liệu cũ.
- Mã option = slug tiếng Việt không dấu (`cay_duoc_lieu`).
- Ô/câu bỏ trống = `null`.
- Mọi câu có bất thường thêm trường `flags` (mảng), vd `["multi_mark_on_single_select", "ambiguous_mark"]`.

## Các điểm khác biệt bản in so với docx (đã xử lý trong v1)

Đây là những chỗ nếu chỉ dựa vào `pretest_VN.docx` sẽ sai — đã đối chiếu scan `LCA-LP-001/page-1.jpg`–`LCA-LP-001/page-7.jpg`:

1. **Q14: 18 dòng dữ liệu**, không phải 19. Dòng "Việc nhà" là `group_header`. 8 dòng sản xuất + 10 dòng việc nhà.
2. **Q32: có cột "Nội dung" text tự do** trước 4 cột lựa chọn; gạch xuyên suốt = trống.
3. **Q10: mã in nhảy số** 1,2,3,4,6,7 (không có 5) — giữ `print_no`.
4. **Q17 device_grid**: mỗi thiết bị tick độc lập Chồng/Vợ, có thể cả hai; "Không ai có" exclusive.
5. **PAGE_NOTES**: ghi chú viết tay ngoài vùng câu hỏi (trang 7 có) — không mất dữ liệu.
6. Page mapping thật: trang 1 (header+consent+Q1–Q8), trang 2 (Q9–Q13), trang 3 (Q14–Q16a), trang 4 (Q16b–Q21b), trang 5 (Q21c–Q27a), trang 6 (Q27b–Q31), trang 7 (Q32–Q34).

## Test case gắn cờ có sẵn trong phiếu mẫu

Phiếu `data/raw/lao-cai/lung-phinh/LCA-LP-001/` đã chứa sẵn các case để kiểm thử bước gắn cờ ở task sau (đầy đủ trong ground truth [`data/ground_truth/LCA-LP-001.json`](../data/ground_truth/LCA-LP-001.json), xem [docs/task-03a-report.md](../docs/task-03a-report.md)):
- **Q30**: tick 3 ô trên câu đơn lựa chọn → `multi_mark_on_single_select`.
- **Q10**: tick 2 ô ("Nông dân" + "Buôn bán, kinh doanh nhỏ") trên câu đơn lựa chọn → `multi_mark_on_single_select` (phát hiện ở Task 3a, ngoài Q30).
- **Q5**: ghi "Hết lớp 9" đồng thời tick "Trung cấp/CĐ/ĐH" → mâu thuẫn học vấn.
- **Q1**: SĐT viết kèm họ tên → bước tách PII phải bắt được.
- **Q14** (dòng `thuoc_bvtv`, `gia_suc_nho`, `gia_suc_lon`) và **Q32** (dòng `vay_von`): ô ghi chữ viết tắt "ko" thay vì tick → theo quy tắc diễn giải đánh dấu dưới đây, tính là **trống**, không phải `ambiguous_mark`.
- **Q14** (dòng `bao_duong_xe`): cột "Chồng" có tick hợp lệ, đồng thời cột "Người khác" có chữ viết tay xen vào → **cập nhật 22/07 theo quy tắc mới của khách (mục 5 dưới đây)**: chữ ở "Người khác" giờ tính là **đã chọn**, không còn bị bỏ qua — giá trị đúng là đa lựa chọn `["chong", "nguoi_khac"]`, xem rà lại ở `docs/task-03a-report.md`.

## Quy tắc diễn giải đánh dấu (áp dụng cho Task 3b/4 khi viết prompt VLM)

Rút ra từ việc nhập tay ground truth `LCA-LP-001` — đây là quy tắc nghiệp vụ thật, không phải suy đoán. **Cập nhật 22/07/2026 theo phản hồi khách hàng** (nguyên văn + lý do ở [docs/client-feedback-2026-07-22-extraction-rules.md](../docs/client-feedback-2026-07-22-extraction-rules.md)) — mục 1, 4, 5 dưới đây là quy tắc mới/sửa, mục 2–3 giữ nguyên từ bản gốc:

1. **Chỉ tick/X/khoanh/gạch chéo mới tính là "đã chọn".** Nếu ô ghi chữ (vd viết tắt "ko", "không") thay vì đánh dấu hình học, **coi như trống** (không tick) — nghĩa là hộ đó không có ai đảm nhiệm việc này theo cách được hỏi, **không phải** trường hợp mập mờ cần review.
2. **`ambiguous_mark` chỉ dùng khi ký hiệu rõ ràng là một lần đánh dấu nhưng không xác định được đánh vào cột nào** (vd nét đánh dấu vắt ngang 2 cột liền kề). Ghi chữ "ko"/"không" **không** thuộc diện này.
3. **~~Cột "Người khác" (hoặc "Khác") trong ma trận: nếu dòng đó đã có tick hợp lệ ở một cột khác, chữ viết tay ở cột "Người khác" bị bỏ qua~~ — ĐÃ THAY THẾ, xem mục 5.**
4. **Nhiều kiểu đánh dấu khác nhau tuỳ phiếu — không chỉ tick "✓"/"v".** Có phiếu dùng "x", "/", khoanh tròn, hoặc ký hiệu khác. Prompt VLM phải liệt kê rõ mọi dạng này là tương đương "đã chọn", không chỉ nhận diện 1 kiểu duy nhất. Đừng bỏ sót 1 lựa chọn chỉ vì ký hiệu đánh dấu không giống các câu khác trên cùng phiếu.
5. **Cột "Người khác" (hoặc "Khác") trong ma trận — quy tắc mới (22/07):** **bất kỳ chữ viết tay nào xuất hiện ở cột "Người khác"/"Khác" đều tính là đã chọn cột đó**, bất kể cột khác trên cùng dòng đã có tick hay chưa. Khác quy tắc cũ (đã bỏ, xem mục 3 gạch ngang): không còn "bỏ qua nếu dòng đã có tick ở cột khác" — giờ tính là **đa lựa chọn thật** (vd dòng có tick "Chồng" + chữ ở "Người khác" → giá trị `["chong", "nguoi_khac"]`, không phải chỉ `"chong"`). Case cụ thể cần rà lại: `Q14` dòng `bao_duong_xe` trong ground truth `LCA-LP-001` (xem `docs/task-03a-report.md`).
6. **Gạch bỏ rồi chọn lại (mới 22/07, mở rộng 24/07):** nếu thấy 1 dấu tick/X bị gạch bỏ (cancel — có nét gạch chồng lên rõ ràng thể hiện ý huỷ) và có dấu mới ở một lựa chọn khác trên cùng câu → chỉ tính lựa chọn **mới** (dấu đã gạch bỏ không tính là chọn), KHÔNG coi là đa lựa chọn/`multi_mark_on_single_select`. Phân biệt với trường hợp thật sự đa lựa chọn (2 dấu đều còn nguyên, không có nét gạch huỷ nào) — vẫn áp dụng `multi_mark_on_single_select` như case `Q10`/`Q30` đã biết. **Mở rộng 24/07 (phát hiện khi review `output/full/*.json`):** quy tắc này áp dụng **cả khi** 2 dấu xung đột là 1 lựa chọn thường + 1 lựa chọn `exclusive` (vd "Không"/"Không là hội viên của tổ chức nào" bị tick cùng lựa chọn khác, sinh flag `exclusive_conflict`/`conflicting_answer`) — nếu 1 trong 2 dấu bị gạch/tô xoá rõ ràng, chỉ lấy dấu còn nguyên, chốt 1 giá trị cụ thể, **đừng** giữ cả hai hay để trống chỉ vì hai lựa chọn "loại trừ nhau". Case thật đã biết: `LCA-BH-002` Q19, `LCH-SLL-001` Q11/Q23, `LCH-SLL-002` Q8/Q16a.
7. **Flag liberal khi nghi ngờ (nhắc lại, không phải quy tắc mới):** bất kỳ trang/câu nào có dấu hiệu bất thường — kiểu đánh dấu lạ, khó phân biệt đã gạch bỏ hay chưa, chữ viết không chắc — thà gắn cờ `needs_review` thừa còn hơn bỏ sót. Áp dụng cho toàn bộ pipeline (3b/4/5/6), không riêng 1 câu.
8. **Multi-mark suy ra từ ghi chú lề, không có tick hình học (mới 24/07):** nếu 1 câu `single_select` KHÔNG có ô nào được tick hình học rõ ràng, nhưng có ghi chú viết tay ở lề/dưới nhiều ô cùng chỉ ra rằng nhiều lựa chọn đều áp dụng (vd "như nhau", "2 vợ chồng như nhau", "làm tất cả mọi thứ") → coi **TẤT CẢ** các lựa chọn được ghi chú đó là đã chọn: trả về mảng đầy đủ và gắn `multi_mark_on_single_select`, xử lý giống hệt khi có tick hình học thật (mục 6 trên). Đây là ngoại lệ có chủ đích của mục 1 (chỉ tick hình học mới tính) — chỉ áp dụng khi ghi chú thể hiện rõ ý định chọn nhiều ô, không suy diễn thêm khi ghi chú mơ hồ. Case thật đã biết: Q30 phiếu `LCA-TPH-006`, `LCH-SLL-004` (và `LCH-SLL-004` Q14 dòng `so_che`).

## Cách thêm/sửa câu hỏi cho mẫu phiếu v2

1. Copy `questionnaire_v1.json` → `questionnaire_v2.json`, đổi `schema_version`.
2. Thêm/sửa/xoá phần tử trong `questions`. Giữ nguyên `id` của câu không đổi để dữ liệu vòng cũ vẫn khớp.
3. Nếu thêm ma trận mới, khai `expected_data_rows` **ngay trong schema** (không sửa validator nữa — validator đọc từ schema).
4. Chạy validator; sửa tới khi `✅`.
5. Đối chiếu thủ công 1 lượt với bản in mới trước khi dùng.
