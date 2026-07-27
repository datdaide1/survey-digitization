# Implement Plan — Task 3b: Trích xuất trắc nghiệm đơn/đa lựa chọn

**Sprint:** Số hóa phiếu khảo sát Sprint 1 — hạng mục P0 số 3b, ước lượng ~2 ngày
**Người đọc:** dev/agent thực hiện (kể cả Codex — xem §9 "Giao cho Codex")
**Trạng thái khi viết plan này:** Task 1–2 xong, Task 3a (ground truth) xong. Task 3b **chưa bắt đầu code** — đây là plan viết trước khi code, theo đúng khuôn `implement-plan-NN → code → task-NN-report.md` đã dùng ở Task 1–2.
**Input:** `output/assembly/<record_id>.json` (Task 2) + `schema/questionnaire_v1.json` + `schema/SCHEMA-FORMAT.md` §Quy tắc diễn giải đánh dấu + Claude API (vision + tool use)
**Output:** `output/extract_mc/<record_id>.json` — xem §4
**Oracle verify:** `data/ground_truth/LCA-LP-001.json` (chỉ đối chiếu phần trong scope, xem §2)

---

## 0. Việc đã chạy trước khi viết plan này (theo yêu cầu — xem báo cáo đầy đủ ở docs/task-02-report.md §7b/§7c)

Trước khi viết plan này đã rà lại toàn bộ `data/raw/` vì phát hiện phiếu mẫu `LCA-LP-001` — oracle duy nhất cho Task 3b–6 — bị lệch giữa docs và đĩa thật sau đợt tổ chức lại data 22/07. Đã sửa xong và **xác minh bằng nội dung thật** (không chỉ suy đoán):

- File nguồn thật của `LCA-LP-001` hiện ở `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-001.pdf` (7 trang) — khách đã tự scan lại đúng phiếu giấy này khi bàn giao batch chính thức Lùng Phình. Đã xác nhận bằng cách render trang 1 (`pdftoppm`) và đọc bằng mắt: khớp đúng ngày 28/5/2026, địa điểm "Tả Sì Thàng, Lùng Phình, Lào Cai", tên+SĐT người trả lời trong ground truth.
- `manifest.csv` đã cập nhật (`commune: lung-phinh-16phieu`).
- Đã bỏ hẳn quy ước "folder nhiều file rời" khỏi `scripts/lib/assembly.py`/`scripts/ingest.py` (không còn phiếu nào cần) và cập nhật `--raw-root` mặc định thành `data/raw/khao-sat`.
- Đã chạy lại `scripts/ingest.py` thật trên toàn bộ 86 dòng manifest (dùng shim `pdftoppm`/`pdfinfo` thay `pymupdf` vì sandbox không cài được qua mạng — shim chỉ thay lớp gọi thư viện, render ảnh thật trên file thật) → **86/86 record resolve đúng 1 file nguồn**; `LCA-LP-001` → `status: ok, found_pages: 7`. `output/assembly/LCA-LP-001.json` đã được ghi đè lại, không còn trỏ đường dẫn chết.
- **Việc còn lại cho bạn:** chạy lại `scripts/ingest.py` một lần bằng conda env `survey-digitizer` thật (có `pymupdf` thật) để `output/assembly/*.json` được sinh bằng đúng thư viện production — không bắt buộc (kết quả logic đã giống hệt) nhưng nên làm cho sạch. Chạy `tests/test_ingest.py` bằng env đó để lấy con số pass chính thức (sandbox chỉ verify được bằng 2 shim khác nhau, xem task-02-report.md §7b/§7c).

Task 3b build trên nền dữ liệu đã đúng — không còn blocker dữ liệu.

## 1. Bối cảnh & mục tiêu

Đây là task trích xuất đầu tiên trong 4 task (3b, 4, 5, 6) cùng tiêu thụ `output/assembly/<record_id>.json` và cùng ghi vào các file trung gian mà Task 6 sẽ gộp lại thành `output/full/`+`output/stats/`+`combined.csv`. Phạm vi Task 3b: **đọc mọi câu `type: single_select`, `type: multi_select`, và `Q17` (`type: device_grid`)** trong `schema/questionnaire_v1.json`, dùng VLM (Claude, vision + structured output) theo từng trang, xuất `code` của lựa chọn được đánh dấu — theo đúng phương pháp đã chốt ở [extraction-method.md](extraction-method.md). Q17 gộp vào đây dù type khác tên — lý do ở §2.3 (bản chất vẫn là đọc tick, không phải phiên âm).

**Không thuộc phạm vi Task 3b** (xem §2 để biết lý do & ranh giới chính xác):
- `matrix` (Q14, Q32) → Task 4 — **khác Q17**: đây là bảng lớn (18 dòng × 5 cột) có rủi ro lệch dòng thật + cột `other_text`/`Người khác`, cần cơ chế đối chiếu nhãn dòng riêng, xem §2.3.
- `free_text` (Q9, Q15, Q16b, Q21c, Q27b, Q29c, Q31, Q34, `PAGE_NOTES`) → Task 5.
- Mọi chuỗi cần **phiên âm chữ viết tay** dù ngắn: `text` cấp câu (`META_DATE`, `META_LOCATION`, `Q1`, `Q2`), mọi `subfield` (`Q5_lop_cao_nhat`, `Q6_tuoi_ket_hon`, `Q16a_chi_tiet`, `Q23_chi_tiet`), và mọi chuỗi `other_text` write-in → **Task 5**, không phải Task 3b. Lý do & hệ quả ở §2.2.
- Đối chiếu `exclusive`, `depends_on` giữa các câu, tách PII, export bản đầy đủ/thống kê → Task 6.

## 2. Ranh giới phạm vi — các quyết định thiết kế cần biết trước khi code

### 2.1 Danh sách 31 câu trong scope, theo trang (để cắt schema slice cho prompt)

Bảng dưới là **input trực tiếp** cho việc sinh schema slice mỗi trang (§3.2) — không cần tự suy ra lại từ `questionnaire_v1.json`.

| Trang | Câu trong scope Task 3b | Số câu |
|-------|------------------------|--------|
| 1 | `CONSENT_1`, `CONSENT_2`, `Q3`, `Q4`, `Q5` (3 component select, KHÔNG gồm `Q5_lop_cao_nhat`), `Q6` (chỉ mã lựa chọn, KHÔNG gồm `Q6_tuoi_ket_hon`), `Q7`, `Q8` | 8 |
| 2 | `Q10`, `Q11`, `Q12`, `Q13` | 4 |
| 3 | `Q16a` (chỉ mã lựa chọn, KHÔNG gồm `Q16a_chi_tiet`) | 1 |
| 4 | `Q17` (`device_grid` — 3 dòng × 2 cột + `khong_ai_co` exclusive, xem §2.3/§3.2), `Q18`, `Q19`, `Q20`, `Q21a`, `Q21b` | 6 |
| 5 | `Q22a`, `Q22b`, `Q23` (chỉ mã lựa chọn), `Q24`, `Q25`, `Q26`, `Q27a` | 7 |
| 6 | `Q28`, `Q29a`, `Q29b`, `Q30` | 4 |
| 7 | `Q33` | 1 |
| **Tổng** | | **31** |

Ghi chú áp dụng mọi câu trên trang, không riêng câu nào:
- **`depends_on` KHÔNG chặn trích xuất.** Trích xuất `Q21b`/`Q22b`/`Q29b` bình thường dù câu điều kiện (`Q21a`/`Q22a`/`Q29a`) không khớp — đối chiếu điều kiện là việc của Task 6 (đúng như đã ghi trong `SCHEMA-FORMAT.md`).
- **`exclusive` KHÔNG chặn trích xuất.** Nếu VLM thấy `Q11` tick cả "Không là hội viên" (exclusive) lẫn "Hội Nông dân" — vẫn ghi cả 2 vào mảng, không tự ý loại bỏ. Mâu thuẫn exclusive là cờ của Task 6.
- **`print_no`** (Q10) chỉ dùng để đối chiếu nội bộ khi đọc phiếu in — output vẫn luôn là `code`, không bao giờ là `print_no`.

### 2.2 Vì sao subfield/other_text/text KHÔNG thuộc Task 3b

Đây là quyết định kiến trúc, không phải mặc định ngẫu nhiên — nêu rõ để người review/Codex không tự ý đổi:

`single_select`/`multi_select` là việc **đọc dấu tick** (nhị phân: có đánh dấu ở ô này hay không) — thuần thị giác, self-consistency (2 lần chạy) verify tốt vì câu trả lời chỉ có N giá trị rời rạc hữu hạn (option codes), lệch giữa 2 lần chạy dễ phát hiện. Ngược lại, `subfield`/`other_text`/`text` là **phiên âm chữ viết tay tự do** — không gian giá trị vô hạn, cùng độ khó và cùng chiến lược (transcribe + confidence + needs_review) như `free_text` tự luận (Q9, Q15...). Gộp 2 việc khác bản chất vào 1 task sẽ làm mơ hồ DoD ("khớp ground truth" nghĩa là khớp *chính xác từng ký tự* hay khớp *đúng ý*, tuỳ loại câu).

Hệ quả kiến trúc: **Task 6 (export) phải merge output của 3b + Task 4 + Task 5 theo `question_id`** trước khi ghi `output/full/<record_id>.json` — vd giá trị cuối cùng của `Q4` = `{"value": "<code từ 3b>", "other_text": "<chuỗi từ Task 5, nếu code là 'khac'>"}`. Đây không phải việc mới phát sinh ngoài kế hoạch — Task 6 vốn đã được mô tả trong sprint plan là bước "export" tổng hợp; plan này chỉ làm rõ nó phải hợp nhất theo `question_id`, không phải nối file thô.

### 2.3 Q17 (`device_grid`) — đã chốt: gộp vào Task 3b (22/07)

Sprint backlog ghi Task 4 là **"2 bảng ma trận Q14, Q32"** — không nhắc `Q17`. Bản nháp đầu của plan này đề xuất mặc định đẩy Q17 sang Task 4 chỉ vì tên type khác (`device_grid` ≠ `single_select`/`multi_select`), bắt chước cách đặt tên của Q14/Q32 — **đây là lý do yếu, không phải rủi ro kỹ thuật thật**. Xét lại theo đúng tiêu chí đã dùng để tách Task 4 khỏi Task 3b ở §2.2 (bản chất "đọc tick" khác "phiên âm chữ viết tay tự do"):

| Tiêu chí | Q14/Q32 (ở lại Task 4) | Q17 |
|---|---|---|
| Kích thước bảng | 18 dòng × 5 cột (Q14), tương tự ở Q32 | 3 dòng × 2 cột |
| Rủi ro lệch dòng khi ảnh nghiêng | Cao — lệch 1 dòng = 18 ô sai âm thầm, cần cơ chế đối chiếu nhãn dòng từ ảnh + fallback crop từng dòng (extraction-method.md §3.3.2) | Thấp — chỉ 3 dòng, dễ đối chiếu bằng mắt/model trong 1 lần đọc |
| Có `other_text`/chữ viết tay xen vào ô | Có (`Q14.bao_duong_xe` cột "Người khác") → cần Task 5 xử lý song song | Không — mọi ô chỉ là tick nhị phân |
| Bản chất việc đọc | Tick + phiên âm hỗn hợp | Thuần tick, giống hệt `single_select`/`multi_select` |

Kết luận: Q17 **không có** đặc điểm khiến Q14/Q32 cần tách task riêng — gộp vào Task 3b. Đã cập nhật bảng §2.1 (31 câu, page 4), cách mã hoá giá trị + JSON Schema ở §3.2, ví dụ output ở §4.

## 3. Kiến trúc

### 3.1 Luồng xử lý (mỗi phiếu)

```
output/assembly/<record_id>.json (Task 2: 7 ảnh trang + tentative_page)
        │
        ▼
┌───────────────────────────────────────────────────┐
│ Với mỗi trang (1..7):                              │
│  1. Lấy schema slice của trang đó (bảng §2.1)      │
│  2. Gọi Claude API 2 LẦN ĐỘC LẬP (self-consistency)│
│     — ảnh trang + slice schema + quy tắc §3.3      │
│  3. Diff 2 kết quả theo từng câu → flag chỗ lệch   │
│  4. Validate output (đủ trường, code hợp lệ) §3.4  │
│  5. Kiểm page_order (đối chiếu nội dung) §3.5      │
└───────────────────────────────────────────────────┘
        │
        ▼
output/extract_mc/<record_id>.json (§4)
```

### 3.2 Prompt & structured output — mỗi lần gọi API là 1 trang

- **1 ảnh trang + đúng slice schema của trang đó** (bảng §2.1) — không nhét cả 30 câu vào 1 prompt, đúng nguyên tắc đã chốt ở `extraction-method.md` §3.1 ("prompt nhỏ → ít ảo giác, debug được từng trang").
- **Bắt buộc structured output** — dùng Claude tool-use (function calling) với JSON Schema sinh **động** từ slice câu hỏi của trang đó: mỗi câu hỏi → 1 property, kiểu dữ liệu theo `type`:
  - `single_select` → property kiểu `oneOf[string (1 trong các option code), array-of-string]` — mảng chỉ dùng khi VLM thấy ≥2 dấu tick (xem §3.3 điểm 2).
  - `multi_select` → property kiểu `array of string`, mỗi phần tử phải thuộc tập option code của câu đó (validate ở §3.4, không dựa vào model tự giác).
  - Câu **không có dấu tick nào** → giá trị `null` (không phải mảng rỗng cho `single_select`; `multi_select` có thể là mảng rỗng `[]` — hai ngữ nghĩa khác nhau: "không chọn gì" (multi, hợp lệ) khác "không xác định được" (nên hiếm khi xảy ra vì multi luôn quan sát được).
  - `Q17` (`device_grid`) → property kiểu `object` với 2 khoá: `rows` (object, key là `row.code` — `dien_thoai`, `may_tinh`, `may_tinh_bang` — value `array of string` gồm `column.code` đã tick ở dòng đó, `chong`/`vo`, có thể cả 2, có thể rỗng `[]`) và `khong_ai_co` (`bool`, ứng với `extra_option.khong_ai_co`). **Khớp đúng định dạng đã dùng sẵn trong `data/ground_truth/LCA-LP-001.json` (`answers.Q17.rows.<code>.value` + `answers.Q17.khong_ai_co`)** — không tự bịa cấu trúc khác, để `compare_ground_truth.py` diff thẳng không cần tầng chuyển đổi. Mỗi dòng vẫn cùng logic `multi_select` áp lên 1 ô, không phải cơ chế mới. **Không tự đối chiếu exclusive** (vd nếu model vừa trả `khong_ai_co: true` vừa có dòng khác không rỗng) — ghi nguyên cả 2, đúng nguyên tắc đã chốt ở §2.1 ("`exclusive` KHÔNG chặn trích xuất... mâu thuẫn là cờ của Task 6").
  - Mọi property đều **required** trong JSON Schema (ép model trả lời đủ, kể cả `null`) — tránh model bỏ sót câu.
- **Không hỏi model tự chấm điểm `confidence`** cho các câu này — đúng nguyên tắc đã chốt: "Confidence tự khai của VLM không đáng tin — self-consistency mới là tín hiệu thật" (extraction-method.md §3.3.3). Field `confidence` do đó **không xuất hiện** trong output single/multi_select (khác với `free_text` ở Task 5, nơi confidence vẫn cần ghi vì không có self-consistency 2 lần rẻ tiền như ở đây).

### 3.3 Quy tắc nghiệp vụ bắt buộc đưa vào prompt (lấy nguyên văn từ SCHEMA-FORMAT.md, không diễn giải lại)

Bê nguyên 3 quy tắc ở [`schema/SCHEMA-FORMAT.md` §Quy tắc diễn giải đánh dấu](../schema/SCHEMA-FORMAT.md) vào system/user prompt:

1. Chỉ tick/X/khoanh/gạch chéo mới tính là "đã chọn"; chữ viết (vd "ko", "không") thay cho tick = **trống**, không phải mập mờ.
2. `ambiguous_mark` chỉ dùng khi rõ ràng có 1 lần đánh dấu nhưng không xác định được đánh vào cột/ô nào.
3. Áp dụng trực tiếp cho `Q17` (`device_grid`, nay thuộc Task 3b — xem §2.3) khi đọc từng ô của bảng; với các câu `single_select`/`multi_select` trang phẳng còn lại thì vẫn nên đưa vào prompt chung vì mẫu phiếu có thể có option "Khác" tương tự.

Riêng cho `single_select`: **nếu thấy từ 2 dấu tick hợp lệ trở lên trên 1 câu chỉ cho phép chọn 1** → **không được tự chọn 1 cái** — trả về **mảng tất cả code đã tick** + tự thêm flag `multi_mark_on_single_select` vào property `flags` của câu đó (xem case thật đã biết: `Q10`, `Q30` — dùng 2 case này làm few-shot example ngay trong prompt, vì đã có ground truth chính xác).

> **Cập nhật 22/07 — 2 quy tắc bổ sung từ khách, áp dụng trực tiếp lên phạm vi 3b** (nguyên văn + lý do: [client-feedback-2026-07-22-extraction-rules.md](client-feedback-2026-07-22-extraction-rules.md) §2.9; đã đưa vào `schema/SCHEMA-FORMAT.md` mục 4/6):
> 1. **Đa dạng kiểu đánh dấu** — không chỉ tick "✓"/"v", có phiếu dùng "x", "/", khoanh tròn. Prompt phải liệt kê rõ, không chỉ nhận 1 kiểu.
> 2. **Gạch bỏ rồi chọn lại** — nếu 1 dấu bị gạch bỏ (huỷ) và có dấu mới ở lựa chọn khác, chỉ tính dấu mới, **không** phải `multi_mark_on_single_select`. Trước khi gắn flag này cho `Q10`/`Q30` (hay bất kỳ câu nào), self-consistency + validate phải phân biệt được "2 dấu đều còn nguyên" (multi-mark thật) với "1 dấu cũ bị gạch bỏ + 1 dấu mới" (không phải multi-mark) — thêm việc này vào tầng validate §3.4 nếu phát hiện case thật cần xử lý (phiếu mẫu `LCA-LP-001` hiện không có case gạch-bỏ-chọn-lại nào đã biết, nhưng 85 phiếu thật ở Sprint 2/Task 7 có thể có).

### 3.4 Tầng validate bằng code thường (không phải AI) — sau khi có kết quả từ VLM

1. **Đủ trường theo bảng §2.1** — 30/30 câu có mặt trong output, kể cả `null`. Thiếu câu nào → lỗi cứng (không phải flag, dừng và báo lỗi phiếu đó), vì đây là lỗi tool-use, không phải lỗi đọc phiếu.
2. **Option code hợp lệ** — mọi giá trị trả về (kể cả trong mảng đa lựa chọn) phải thuộc đúng tập `options[].code` của câu đó trong `questionnaire_v1.json`. Code lạ → coi là lỗi model, thử lại (retry) tối đa 1 lần trước khi flag `invalid_option_code` + giữ giá trị thô để review.
3. **`single_select` trả mảng nhưng KHÔNG có flag `multi_mark_on_single_select`** (hoặc ngược lại) → coi là lỗi tự-đối-chiếu nội bộ của model, tự thêm flag còn thiếu bằng code (không tin model tự gắn cờ đúng 100%).

### 3.5 Self-consistency (2 lần chạy độc lập)

- Gọi API **2 lần riêng biệt** cho mỗi trang (không phải 1 lần rồi hỏi lại "bạn chắc không") — đúng tinh thần "tín hiệu độc lập", tránh model tự củng cố câu trả lời đầu.
- Diff theo từng câu: giá trị (sau chuẩn hoá — mảng so sánh không phân biệt thứ tự phần tử) khác nhau giữa lần 1 và lần 2 → flag `self_consistency_mismatch`, **giữ giá trị của lần 1** làm giá trị chính thức, ghi cả 2 giá trị vào `_debug.self_consistency_runs` (xem §4) để người review đối chiếu — **không tự động chọn "đa số"** vì chỉ có 2 lần chạy (không có "đa số" thật sự), 2 lần khác nhau nghĩa là cả 2 đều đáng ngờ như nhau.
- Cost/thời gian: 30 câu × 7 trang → 7 trang × 2 lần gọi = **14 lần gọi API/phiếu** (không phải 30 lần — mỗi lần gọi xử lý nguyên 1 trang). Với ~85 phiếu thật (Sprint 2), ước tính ~1190 lần gọi — đo cost thật ở Task 7 Pilot theo đúng kế hoạch, Task 3b chỉ cần đúng cơ chế, chưa cần tối ưu chi phí.

### 3.6 Đối chiếu thứ tự trang (`page_order_mismatch`)

Vì data thật giờ là PDF nguyên bản do khách scan (không còn bị xáo trộn tên file như phiếu mẫu test ở Task 2), `tentative_page` với hầu hết phiếu thật **sẽ đúng theo thứ tự nội dung**. Task 3b vẫn phải **kiểm tra**, không giả định đúng:

- Cách làm: khi gọi API cho `tentative_page = N`, kèm theo câu hỏi phụ (1 property bool trong cùng tool-use schema): `"trang_khop_du_kien": <bool>` — hỏi model "trang này có chứa đúng các câu từ {danh sách câu trong slice} không, hay là nội dung khác (trang khác của phiếu, hoặc trang trắng/hỏng)?".
- `trang_khop_du_kien = false` ở 1 trong 2 lần self-consistency → flag `page_order_mismatch` cho trang đó, **không cố tự sửa số trang** (không đủ căn cứ để suy ra trang thật thay thế trong phạm vi Task 3b) — để nguyên giá trị đã trích xuất (có thể sai) kèm cờ, con người quyết định ở vòng review.
- **Ngoài phạm vi Task 3b** (ghi rõ để không ai kỳ vọng nhầm): tự động tìm lại đúng thứ tự trang thật khi phát hiện lệch (vd thử khớp slice trang khác) — nếu cần, đây là việc bổ sung riêng, không nằm trong ước lượng 2 ngày của task này.

## 4. Output contract — `output/extract_mc/<record_id>.json`

```json
{
  "record_id": "LCA-LP-001",
  "schema_version": "v1",
  "extracted_at": "2026-07-23T10:00:00+07:00",
  "model": "<tên model Claude dùng, vd claude-sonnet-4-5-20250929>",
  "answers": {
    "CONSENT_1": {"value": "yes", "flags": []},
    "Q10": {"value": ["nong_dan", "buon_ban"], "flags": ["multi_mark_on_single_select"]},
    "Q11": {"value": ["hoi_phu_nu"], "flags": []},
    "Q17": {"value": {"rows": {"dien_thoai": ["chong", "vo"], "may_tinh": ["chong"], "may_tinh_bang": []}, "khong_ai_co": false}, "flags": []},
    "Q30": {"value": ["san_xuat", "thu_hai", "tieu_thu"], "flags": ["multi_mark_on_single_select"]},
    "...": "... đủ 31 câu theo bảng §2.1, kể cả null ..."
  },
  "pages": {
    "1": {"tentative_page": 1, "page_order_mismatch": false},
    "...": "... đủ 7 trang ..."
  },
  "_debug": {
    "self_consistency_runs": {
      "Q10": {"run1": ["nong_dan", "buon_ban"], "run2": ["nong_dan", "buon_ban"], "match": true}
    },
    "raw_model_output_paths": "tuỳ chọn — nếu muốn lưu raw JSON từng lần gọi API để debug, ghi path tại đây thay vì nhúng thẳng (tránh phình file)"
  }
}
```

Quy ước:
- `answers.<id>.value`: `null` (trống) | `string` (1 code, `single_select` bình thường) | `array[string]` (nhiều code — `multi_select` luôn, hoặc `single_select` bất thường kèm flag) | `object{rows: {row_code: array[string]}, khong_ai_co: bool}` (riêng `Q17`, xem §3.2 — khớp đúng cấu trúc đã có sẵn trong `data/ground_truth/LCA-LP-001.json`).
- `answers.<id>.flags`: mảng rỗng nếu sạch; giá trị có thể có: `multi_mark_on_single_select`, `ambiguous_mark`, `invalid_option_code`, `self_consistency_mismatch`.
- File này **không chứa PII** trực tiếp (30 câu trong scope không có câu nào `pii: true`) — nhưng vẫn nên coi cả thư mục `output/extract_mc/` như dữ liệu nội bộ chưa phải bản giao khách, chưa qua bước tách PII/thống kê của Task 6.
- `output/extract_mc/` là thư mục mới — cập nhật cây thư mục trong `data/README.md` khi bắt đầu code task này (chưa cập nhật trong plan này để tránh đoán trước cấu trúc Task 4/5 output, nhưng nguyên tắc đặt tên nên nhất quán: `output/extract_matrix/`, `output/extract_free_text/`).

## 5. Deliverables

| File | Nội dung |
|------|----------|
| `scripts/extract_mc.py` | CLI: đọc `output/assembly/<record_id>.json`, gọi API theo trang, ghi `output/extract_mc/<record_id>.json`. Theo đúng convention CLI của `ingest.py` (`--manifest`, `--assembly-dir`, `--out-dir`, xử lý cách ly lỗi từng phiếu). |
| `scripts/lib/mc_extraction.py` | Hàm thuần: sinh schema slice/trang (bảng §2.1) từ `questionnaire_v1.json`, build tool-use JSON Schema động, gọi Claude API, diff self-consistency, validate (§3.4). Tách khỏi CLI để test được bằng fixture, không cần gọi API thật trong unit test (mock response). |
| `scripts/compare_ground_truth.py` | **Oracle so sánh** — đọc `output/extract_mc/<record_id>.json` + `data/ground_truth/<record_id>.json`, so từng câu **trong scope Task 3b** (bảng §2.1), in bảng khớp/lệch + tổng kết pass rate. Dùng cho cả Task 4/5 sau này (nhận `--fields` để lọc phạm vi so sánh theo task). Đây là script mà Codex (hoặc bạn) dùng làm vòng lặp build→chạy→so→sửa prompt. |
| `tests/test_mc_extraction.py` | Test hàm thuần trong `mc_extraction.py` bằng response Claude API **giả lập** (mock) — không gọi API thật trong test tự động: sinh slice đúng câu/trang, validate bắt đúng code lạ, diff self-consistency đúng, xử lý `null` vs `[]` đúng ngữ nghĩa. |
| Cập nhật `data/README.md` | Thêm `output/extract_mc/` vào cây thư mục output. |

## 6. Test plan — vòng lặp build thật (không phải chỉ unit test)

1. **Unit test trước** (không cần API key): mock response Claude, verify toàn bộ logic ở `mc_extraction.py` — schema slice đúng, validate đúng, diff đúng. Chạy được ngay, không tốn cost.
2. **Chạy thật trên `LCA-LP-001`** (cần Claude API key — blocker #2 sprint plan, xác nhận đã có trước khi làm bước này): `python scripts/extract_mc.py --record-id LCA-LP-001`.
3. **Đối chiếu**: `python scripts/compare_ground_truth.py LCA-LP-001 --fields task3b` → xem % khớp theo bảng §2.1 (31 câu).
4. **Lặp**: câu nào lệch, xem lại prompt (đặc biệt: câu có `other_text`/`exclusive`/`depends_on` dễ bị model tự "sửa hộ" logic dù đã dặn không chặn trích xuất) → chỉnh → chạy lại bước 2–3.
5. **DoD đạt khi**: 31/31 câu khớp ground truth (giá trị `value`, kể cả trường hợp `null`/object rỗng ở `Q17`), 2 case `multi_mark_on_single_select` đã biết (`Q10`, `Q30`) được bắt đúng kèm flag, không câu nào bị bỏ sót field.

## 7. Rủi ro

| Rủi ro | Giảm thiểu |
|--------|-----------|
| Model tự "sửa hộ" theo `depends_on`/`exclusive` (vd tự bỏ trống `Q21b` vì thấy `Q21a = chưa lần nào`) dù ảnh có đánh dấu thật | Prompt nói rõ: "đọc đúng những gì đã đánh dấu trên trang, không tự suy luận theo câu khác"; test case cụ thể trong `tests/test_mc_extraction.py` |
| `Q4`/`Q10`/`Q12`/`Q13`/`Q20`/`Q27a` có `other_text` — model có thể lẫn lộn ghi cả chuỗi viết tay vào `value` thay vì chỉ code | Tool-use schema ép kiểu `value` chỉ nhận option code (enum), không nhận free text — model không có chỗ để nhét chuỗi vào sai chỗ |
| Chi phí 14 lần gọi API/phiếu nhân 85 phiếu thật | Đo thật ở Task 7 (Pilot), Task 3b chỉ build đúng cơ chế trên 1 phiếu mẫu |
| `Q17` dùng cấu trúc `value` khác các câu còn lại (`object` thay vì `string`/`array`) — `compare_ground_truth.py`/`mc_extraction.py` cần xử lý riêng nhánh này, dễ bị code tổng quát hoá sai nếu viết ẩu | Viết test case riêng cho Q17 trong `tests/test_mc_extraction.py` (dòng rỗng, dòng tick cả 2 cột, `khong_ai_co = true` kèm dòng khác không rỗng — case mâu thuẫn cố ý, verify không bị tự sửa) |
| Claude API key chưa cấp | Blocker đã ghi ở sprint plan mục "Việc cần người khác" #2 — xác nhận trước khi chạy §6 bước 2 |

## 8. Definition of Done

- [ ] `scripts/extract_mc.py` chạy được 1 lệnh trên `LCA-LP-001`, ghi `output/extract_mc/LCA-LP-001.json` đủ 31 câu (bảng §2.1, gồm `Q17`), không thiếu trường.
- [ ] `scripts/compare_ground_truth.py LCA-LP-001 --fields task3b` báo 31/31 khớp.
- [ ] 2 case `multi_mark_on_single_select` thật (`Q10`, `Q30`) được gắn đúng flag.
- [ ] `Q17` khớp ground truth theo đúng cấu trúc `object{row_code: array}` + `khong_ai_co` (không quy về `string`/`array` phẳng).
- [ ] `tests/test_mc_extraction.py` pass toàn bộ bằng mock, không cần API key để chạy CI/test thường xuyên.
- [ ] `page_order_mismatch` được kiểm tra (dù phiếu mẫu thật khả năng không trigger vì thứ tự đã đúng) — verify bằng 1 test case cố ý đưa nhầm ảnh trang khác vào 1 slot.

## 9. Giao cho Codex (hoặc coding agent khác)

Plan này đủ chi tiết để giao thẳng cho Codex code mà không cần ngồi cầm tay từng bước, với điều kiện:

1. **Đã có Claude API key** cấp cho Codex dùng (biến môi trường, vd `ANTHROPIC_API_KEY`) — không có key thì Codex chỉ làm được tới hết §6 bước 1 (unit test mock), không tự verify được vòng lặp thật.
2. Codex có `scripts/compare_ground_truth.py` (§5) làm **oracle tự động** — nghĩa là Codex có thể tự chạy `extract_mc.py` → `compare_ground_truth.py` → đọc % khớp → tự sửa prompt trong `mc_extraction.py` → lặp lại, **không cần hỏi lại người trong vòng lặp build**, chỉ cần báo cáo khi đạt DoD (§8) hoặc khi bí (vd thử >5 lần vẫn không khớp 1 câu cụ thể — lúc đó mới cần người quyết định, có thể là do domain knowledge như case "ko" ở Task 3a).
3. Đưa cho Codex đúng 4 file cần đọc trước khi code: file plan này, `schema/SCHEMA-FORMAT.md` (đặc biệt §Quy tắc diễn giải đánh dấu), `docs/extraction-method.md`, `data/ground_truth/LCA-LP-001.json`.
4. Codex **không** cần quyền truy cập `data/raw/` gốc ngoài `LCA-LP-001.pdf` — Task 3b chỉ chạy trên phiếu mẫu, không đụng 85 phiếu thật (đó là Task 7, Sprint 2, có blocker riêng cần xác nhận vùng/xã trước — xem sprint plan).

## 10. Cập nhật 22/07 — đối chiếu với phản hồi khách hàng chi tiết

Khách gửi quy tắc nghiệp vụ cho toàn bộ 34 câu sau khi plan này đã viết xong (đầy đủ: [client-feedback-2026-07-22-extraction-rules.md](client-feedback-2026-07-22-extraction-rules.md)). Đối chiếu lại: **kiến trúc §2.2 (3b chỉ đọc mã lựa chọn, không đọc `other_text`/subfield) đã khớp sẵn** với toàn bộ yêu cầu "khác tính chung là khác" của khách (Q10, Q21b, Q22a, Q22b, Q27a, Q28) — không cần sửa code/kiến trúc 3b vì việc này. 2 điểm cần chú ý thêm khi code:

- Đã thêm 2 quy tắc đánh dấu mới vào §3.3 (đa dạng kiểu đánh dấu, gạch bỏ rồi chọn lại) — ảnh hưởng trực tiếp tới prompt và tầng validate.
- Việc "chia khoảng để thống kê" (tuổi, cấp học, tuổi kết hôn, năm kinh nghiệm) **không thuộc Task 3b** — đó là tầng tính toán của Task 6, đọc từ `stats_bucketing` đã khai trong `schema/questionnaire_v1.json`. Task 3b chỉ cần biết: KHÔNG có câu nào trong 30 câu ở bảng §2.1 cần bucket (`Q2`, `Q5`, `Q6`, `Q9` đều là `text`/`free_text`/`composite`-có-text, không phải `single_select`/`multi_select` thuần) — nên bảng §2.1 và scope 3b **không đổi**.
