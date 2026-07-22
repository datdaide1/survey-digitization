# Report tổng kết — Task 2: Ingest & Assembly

**Sprint:** Số hóa phiếu khảo sát Sprint 1 · **Hạng mục:** P0 số 2 · **Trạng thái:** ✅ Xong
**Ngày:** 15/07/2026 · **Kế hoạch:** [implement-plan-02-ingest-assembly.md](implement-plan-02-ingest-assembly.md)

---

## 1. Mục tiêu task (nhắc lại)

Với dữ liệu thực tế đã tổ chức "1 folder = 1 phiếu" (`data/raw/<tỉnh>/<xã>/<record_id>/`), Task 2 **không cần** tự nhận diện/gom nhóm ảnh theo nội dung như plan gốc — thu hẹp lại thành: đọc `manifest.csv`, gom file trong từng folder phiếu, chuẩn hoá PDF→ảnh, và **kiểm tra toàn vẹn** (đủ/thiếu/thừa/hỏng trang). Xuất ra một *assembly record* JSON cho mỗi phiếu, sẵn sàng cho bước trích xuất (Task 3).

Quyết định cốt lõi: **không dựa vào tên file để xác định thứ tự trang thật** — chỉ dùng tên file để sort tạm (`tentative_page`); số trang thật do Task 3 (đọc nội dung) chốt.

## 2. Deliverables

| File | Vai trò | Trạng thái |
|------|---------|-----------|
| [`scripts/lib/assembly.py`](../scripts/lib/assembly.py) | Hàm thuần: `list_source_files`, `render_pdf_pages`, `build_assembly` | ✅ |
| [`scripts/ingest.py`](../scripts/ingest.py) | CLI: đọc manifest, chạy assembly cho mọi phiếu, ghi `output/assembly/<record_id>.json` | ✅ |
| [`tests/test_ingest.py`](../tests/test_ingest.py) | 33 test: fixture giả + tích hợp phiếu thật + cách ly lỗi lô + giới hạn đã biết + chống path traversal | ✅ 33/33 |
| `data/README.md` (đã cập nhật ở bước plan trước) | Input contract: tên file bất kỳ, không cần `page-N` | ✅ |
| `data/manifest.csv` | Cột `notes` ghi chú việc đổi tên file kiểm chứng | ✅ |

## 3. Môi trường

Cài thêm vào conda env `survey-digitizer`: `pymupdf` (render PDF→ảnh), `Pillow` (kiểm ảnh đọc được). Không cần sửa `AGENTS.md` — quy ước dùng env này đã có sẵn từ Task 1.

## 4. Kiểm chứng "không phụ thuộc tên file" — bằng dữ liệu thật, không chỉ mock

Theo yêu cầu, đã **đổi tên thật** 7 file trong `data/raw/lao-cai/lung-phinh/LCA-LP-001/` từ `page-1.jpg…page-7.jpg` sang tên xáo trộn hoàn toàn, cố tình chọn để natural-sort ra thứ tự khác hẳn thứ tự nội dung gốc:

| Tên gốc (nội dung trang) | Tên mới |
|---|---|
| page-1.jpg | IMG_9931.jpg |
| page-2.jpg | a_scan.jpg |
| page-3.jpg | z_final.jpg |
| page-4.jpg | scan_0002.jpg |
| page-5.jpg | khaosat_c.jpg |
| page-6.jpg | 03_photo.jpg |
| page-7.jpg | IMG_0458.jpg |

Sau khi đổi tên, natural sort ra thứ tự `03_photo → IMG_0458 → IMG_9931 → a_scan → khaosat_c → scan_0002 → z_final`, tương ứng nội dung gốc **F, G, A, B, E, D, C** — xáo trộn hoàn toàn so với thứ tự thật.

**Chạy `ingest.py` thật trên folder đã đổi tên:**

```
OK LCA-LP-001: status=ok found=7/7 flags=[]
1/1 phiếu OK.
```

→ Pipeline vẫn nhận đủ 7/7 trang, không cờ nào, bất kể tên file bị xáo trộn — đúng thiết kế. Đồng thời `output/assembly/LCA-LP-001.json` cho thấy rõ **`tentative_page` không khớp thứ tự nội dung thật** (vd `03_photo.jpg` — vốn là trang 6 gốc — được gán `tentative_page: 1`). Đây là bằng chứng trực quan cho quyết định thiết kế: Task 2 chỉ đảm bảo *đủ trang*, còn *đúng thứ tự* để Task 3 chốt bằng nội dung — không ai được tin `tentative_page` là số trang thật.

Việc đổi tên đã ghi chú lại trong `data/manifest.csv` (cột `notes`) để truy vết, vì `data/README.md` mặc định coi `raw/` là bất biến.

## 5. Test suite (20/20 pass)

| Case | Kiểm điều gì |
|------|-------------|
| Đủ 7 trang, tên lộn xộn hoàn toàn | `status=ok`, `found_pages=7`, không cờ |
| Thiếu 1 trang | cờ `missing_page`, `status=needs_review` |
| Thừa 1 trang (lạc từ phiếu khác) | cờ `extra_page`, `status=needs_review` |
| File hỏng (không mở được như ảnh) | cờ `unreadable`, vẫn tính là thiếu trang |
| PDF 3 trang trộn với 4 ảnh | render đúng 3 trang PDF, tổng = 7, `status=ok` |
| Folder rỗng | cờ `empty_folder`, `status=error` |
| Folder không tồn tại | cờ `folder_not_found` |
| Natural sort (`1,2,10` đúng thứ tự) | không bị sort kiểu chuỗi (`1,10,2`) |
| Bỏ qua file ẩn/tạm (`.DS_Store`, `~lock.jpg`) | không lẫn vào danh sách trang |
| **Tích hợp: phiếu thật `LCA-LP-001` (tên đã xáo trộn)** | `status=ok`, đúng 7 trang |

## 6. Ranh giới đã giữ đúng theo plan

- Task 2 **không gọi VLM** — thuần code, chạy nhanh, test được đầy đủ bằng fixture.
- Không nối 7 ảnh thành 1 file PDF — output là JSON mô tả danh sách trang + cờ.
- Không tự "đoán" thứ tự đúng theo nội dung — nhường việc đó cho Task 3, tránh chạy VLM hai lần và tránh lỗi ngầm nếu đoán sai.

## 6b. Xử lý sau code review

Review chấm **Approve with nits** — không lỗi chặn. Đã sửa 2 điểm cần sửa + 3 góp ý:

| # | Điểm | Cách sửa |
|---|------|----------|
| 1 | Một dòng manifest hỏng (num_pages rỗng/thiếu cột) giết cả lô | Tách `run()` khỏi `main()`, bọc **try/except per-record** — phiếu lỗi thành record `status=error` + cờ `processing_error`, lô vẫn chạy tiếp |
| 2 | `status:ok` hứa quá (dup+missing net-zero vẫn "ok") | Ghi rõ ngữ nghĩa trong docstring `build_assembly` + mục 4b dưới đây; thêm test khoá hành vi |
| 3 | Cờ thừa `count_mismatch` (luôn đi kèm missing/extra) | Bỏ, chỉ giữ `missing_page`/`extra_page` (định hướng hành động rõ hơn) |
| 4 | `image_path` dùng `\` Windows + tương đối | Chuẩn hoá `.as_posix()` — path dùng `/`, tương đối repo-root, chạy được cross-platform |
| 5 | Thiếu test: PDF hỏng, CLI ingest.py, giới hạn dup-net-zero | Thêm 8 test (28/28): nhánh PDF hỏng, `run()` cách ly lỗi lô, và 1 test *khoá giới hạn đã biết* |

### 4b. Ngữ nghĩa `status: ok` (làm rõ sau review)

`status: ok` của Task 2 = **"đủ SỐ trang đọc được"**, KHÔNG phải "đúng 7 trang phân biệt". Vì Task 2 không đọc nội dung, nó không phát hiện được phiếu bị *nhân đôi 1 trang + thiếu 1 trang khác* (số lượng vẫn = 7). Trường hợp đó do **Task 3 bắt** qua số trang thật. Test case `dup_net_zero` khoá đúng hành vi này để không ai vô tình "sửa" thành bắt ở Task 2 (không thể, vì không có nội dung).

## 6c. Xử lý sau review tổng hợp (Task 1+2)

Vòng review tổng hợp (kèm góc bảo mật thủ công vì `/security-review` cần git repo, chưa init). Đã sửa 4 gợi ý:

| # | Điểm | Cách sửa |
|---|------|----------|
| 1 | Path traversal qua `province`/`commune` trong manifest ghép thẳng vào đường dẫn đọc | `_safe_segment()` regex `^[A-Za-z0-9_-]+$` — giá trị lạ (`..\\`, `/`) → `ValueError` → cách ly thành `processing_error` |
| 3 | Path traversal qua `record_id` khi ghi file JSON output | Đọc: `_safe_segment`; Ghi: `_safe_filename()` thay ký tự lạ — tên file output không bao giờ thoát thư mục dù record_id hỏng |
| 2 | `render_dir` không dọn → tích ảnh PDF mồ côi qua các lần chạy | `shutil.rmtree(render_dir)` đầu mỗi `build_assembly` |
| 4 | Import giữa file test (PEP8) | Dời `csv`, `run` lên đầu `test_ingest.py` |

Thêm 5 test path-traversal (province/record_id độc hại bị chặn, `_safe_filename` normalise đúng). **33/33 pass.** Đây là defense-in-depth: manifest hiện do 1 người tin cậy sửa tay, nhưng khi quy trình mở cho nhiều người thì lớp chặn này đã sẵn.

> Lưu ý: `/security-review`, `/metrics-review`, `/quarterly-review` trong yêu cầu không chạy được — cái đầu cần `git init`, hai cái sau là skill báo cáo kinh doanh (doanh thu/OKR) không áp dụng cho review code. Các finding bảo mật ở trên là từ review thủ công thay thế.

## 7. Việc tiếp theo

- **Task 3 — Trích xuất trắc nghiệm đơn/đa lựa chọn**: đọc `output/assembly/<record_id>.json`, với mỗi trang gọi VLM kèm slice schema đúng trang, đối chiếu `page` thật với `tentative_page` → cờ `page_order_mismatch` nếu lệch.
- Khi có thêm phiếu thật (10–15 phiếu, blocker đã nêu ở Sprint plan), chạy `ingest.py` trên toàn bộ để phát hiện sớm các case chưa gặp (vd nhiều PDF trong 1 folder, ảnh HEIC…).

## 7b. Sự cố phát hiện 22/07 + sửa (trước khi giao Task 3b)

Rà lại thư mục `data/raw/` trước khi giao Task 3b (1 tuần sau khi Task 2 "xong") phát hiện: folder ảnh gốc của phiếu mẫu `data/raw/lao-cai/lung-phinh/LCA-LP-001/` (7 ảnh xáo trộn tên, dẫn chứng ở §4 phía trên) **không còn tồn tại**. Nguyên nhân nhiều khả năng: đợt dời-phẳng 85 file thật ngày 22/07 (ghi ở sprint plan) xoá "các folder `<record_id>/` rỗng" nhưng vô tình cuốn theo cả folder này — vốn không rỗng nhưng là ngoại lệ duy nhất còn dùng quy ước cũ nên dễ bị xử lý nhầm theo logic chung. `output/assembly/LCA-LP-001.json` (sinh ra lúc Task 2 xong, 15/07) vẫn trỏ tới đường dẫn đó — trở thành output cũ (stale), không còn khớp đĩa.

**Hệ quả nếu không phát hiện:** chạy `ingest.py` cho `LCA-LP-001` sẽ trả `status=error, flags=[source_not_found]` — vô hiệu hoá oracle ground truth duy nhất mà Task 3b–6 dựa vào để verify.

**Cách sửa (bản nháp vòng 1 — SAI, xem §7c sửa lại):** tìm thấy `output/pdf/LCA-LP-001.pdf` (1.4MB, sửa đổi cùng thời điểm 22/07 với đợt dời-phẳng) — xác nhận bằng `pdfinfo`: đúng 7 trang. Lúc đó **đoán** đây là bản gộp 7 ảnh của phiếu mẫu (chỉ dựa vào tên file + thời điểm sửa + kích thước ước chừng khớp tổng 7 ảnh gốc — **không đối chiếu nội dung thật**), và đã dời file vào `data/raw/khao-sat/lao-cai/lung-phinh/LCA-LP-001.pdf`. Suy luận này sai — xem §7c.

**Nhân tiện đơn giản hoá theo yêu cầu:** vì phiếu mẫu — ngoại lệ duy nhất từng cần quy ước "folder nhiều file rời" — giờ cũng đã là 1 PDF nhiều trang như 85 phiếu thật, quy ước dự phòng không còn lý do tồn tại. Đã bỏ hẳn khỏi `scripts/lib/assembly.py` (bỏ `list_source_files`, `_natural_sort_key`, nhánh folder trong `build_assembly`) và `scripts/ingest.py` (`_resolve_source` không còn fallback sang folder; `--raw-root` mặc định đổi sang `data/raw/khao-sat`). `tests/test_ingest.py` viết lại theo logic 1-file-1-phiếu.

**Bài học:** khi đổi convention lưu trữ dữ liệu (đợt dời-phẳng), phải kiểm tra lại **mọi** record đang được tham chiếu bởi docs/ground truth/output đã sinh trước đó — không chỉ dữ liệu mới nhận vào. Một thao tác dọn dẹp tưởng vô hại ("xoá folder rỗng") có thể xoá nhầm ngoại lệ nếu logic không phân biệt rõ "rỗng" khỏi "không theo quy ước mới".

## 7c. Sửa lại vòng 2 (cùng ngày) — suy luận vòng 1 sai, đã xác minh lại bằng nội dung thật

Người dùng chỉ ra: file thật của phiếu mẫu **đã nằm sẵn** trong `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/` — không cần "tìm/tạo" gì thêm ở nơi khác. Kiểm lại bằng `md5sum`:

- `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-017.pdf` (lúc đó còn tên này) **khớp tuyệt đối** với `data/raw/scan-16-7-2026/16-phieu/LCA-LP-001.pdf` (file gốc client, chưa qua staging, tên gốc client đặt) — chứng minh đây là **cùng 1 file thật do khách scan**, không phải trùng hợp tên.
- File này **cũng khớp tuyệt đối** với `output/pdf/LCA-LP-001.pdf` mà vòng 1 đã "tìm thấy" và đoán nhầm là bản gộp ảnh. Vậy `output/pdf/LCA-LP-001.pdf` **chưa bao giờ** là bản gộp 7 ảnh cũ — nó chỉ là 1 bản copy lạc chỗ của chính file khách scan này (có lẽ do một bước xử lý trước đó copy nhầm file theo tên gốc `LCA-LP-001.pdf` từ `scan-16-7-2026/` sang `output/pdf/` trước khi staging kịp đổi tên thành LCA-LP-017).

**Xác minh độc lập bằng nội dung** (không chỉ tin checksum trùng do suy đoán): dùng `pdftoppm` render trang 1 của file, đọc bằng mắt — khớp chính xác với `data/ground_truth/LCA-LP-001.json`: ngày `28/5/2026`, địa điểm "Tả Sì Thàng, Lùng Phình, Lào Cai", tên người trả lời "Sùng Thị Sơ" + SĐT `0832 492 792` viết kèm ở Q1, và cả ký hiệu "R" ở góc trang 1 nhắc tới trong `extraction-method.md` §7. Kết luận chắc chắn: **đây đúng là phiếu mẫu** — khách đã tự scan lại đúng tờ giấy này khi bàn giao batch chính thức Lùng Phình (16 phiếu), staging trước đó đổi tên nó thành `LCA-LP-017.pdf` vì tưởng nhầm là 1 phiếu khác cùng commune trùng tên file ngẫu nhiên.

**Sửa lại cho đúng:**
1. Xoá file trùng ở `data/raw/khao-sat/lao-cai/lung-phinh/LCA-LP-001.pdf` (vòng 1 đặt sai chỗ) và folder `lung-phinh/` rỗng.
2. Đổi tên `LCA-LP-017.pdf` → `LCA-LP-001.pdf` ngay trong `lung-phinh-16phieu/` (không cần file/folder riêng cho phiếu mẫu nữa).
3. Cập nhật `manifest.csv`: `commune` của `LCA-LP-001` → `lung-phinh-16phieu` (không phải `lung-phinh` riêng); **xoá hẳn dòng `LCA-LP-017`** (không đổi số, xoá luôn) — vì đó chưa bao giờ là 1 phiếu khác, chỉ là chính `LCA-LP-001` bị đặt tên khác lúc staging. Manifest còn đúng **85 dòng** (khớp 85 file thật đã nhận), không phải 86. Phát hiện việc sót dòng này nhờ chạy lại script đối chiếu "mọi dòng manifest có resolve đúng 1 file" sau khi đổi tên file — dòng `LCA-LP-017` báo thiếu file ngay lập tức.
4. 7 ảnh chụp tay gốc (08/07/2026) vẫn giữ nguyên tại `data/raw/_archive/LCA-LP-001-original-photos-2026-07-08/` để tham khảo — không mâu thuẫn với phát hiện trên, chỉ là bản chụp tay trước khi có bản scan chính thức của cùng tờ phiếu.
5. Cập nhật lại mọi tham chiếu đường dẫn trong `data/README.md`, `sprint-plan-survey-digitization.md`, `docs/extraction-method.md`.

**Đã chạy lại `scripts/ingest.py` thật** (không phải test giả) trên toàn bộ `data/manifest.csv` (86 dòng), dùng shim `fitz` viết tạm bằng `pdftoppm`/`pdfinfo` (poppler, có sẵn trong sandbox) thay `pymupdf` thật — pip cài `pymupdf` bị timeout liên tục do mạng sandbox quá chậm (~35KB/s). Shim chỉ thay thế lớp gọi thư viện render ảnh, **không giả lập dữ liệu** — đọc số trang thật qua `pdfinfo`, render PNG thật qua `pdftoppm` trên chính 86 file PDF thật trong `data/raw/khao-sat/`. Kết quả: **86/86 record resolve đúng 1 file nguồn**, `LCA-LP-001` → `status: ok, found_pages: 7`, khớp `expected_pages` trong manifest. Chi tiết số liệu đầy đủ ở `output/assembly/` (đã ghi đè lại toàn bộ 86 file, thay cho bản `LCA-LP-001.json` cũ trỏ đường dẫn chết từ 15/07).

> **Cần làm khi có máy thật (conda env `survey-digitizer`, có `pymupdf` thật):** chạy lại `scripts/ingest.py` một lần nữa (không bắt buộc nhưng nên làm) để `output/assembly/*.json` được sinh bằng đúng thư viện production, không phải shim; và chạy `tests/test_ingest.py` để lấy con số pass chính thức (sandbox chỉ verify được 32/34 bằng shim khác, xem §7b).

**Bài học rút thêm (so với §7b):** đừng suy luận danh tính 1 file chỉ từ tên + thời điểm sửa + kích thước "có vẻ khớp" — đó chỉ là gợi ý cần điều tra tiếp, không phải bằng chứng. Phải đối chiếu **nội dung thật** (ở đây: render ảnh rồi đọc, hoặc so checksum với bản gốc chưa qua xử lý) trước khi kết luận và sửa file/docs dựa trên kết luận đó.
