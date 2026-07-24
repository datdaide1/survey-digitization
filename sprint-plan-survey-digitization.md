# Sprint Plan: Số hóa phiếu khảo sát — Scan → JSON (Sprint 1)

**Thời gian:** 14/07 — ~~25/07~~ **26/07/2026** (dời +1 ngày, có làm cuối tuần) | **Team:** 1 dev
**Cập nhật:** 15/07 — Task 1–2 xong; tách trục **Build** (chạy ngay với 1 phiếu mẫu) khỏi **Pilot & Calibration** (gate vào 10–15 phiếu); bỏ hạng mục lỗi thời.
**Cập nhật 22/07:** Blocker Task 7 đã gỡ — khách đã bàn giao **84 phiếu scan thật** (`data/raw/scan-16-7-2026/`, 6 vùng: 4/6/9(10)/16/23/25 phiếu mỗi vùng, 1 file PDF/phiếu), vượt xa ngưỡng 10–15 cần cho pilot. **Task 3b đã có code và 103 mock/unit checks pass; nghiệm thu live 31/31 còn chờ `ANTHROPIC_API_KEY`. Task 4–6 chưa bắt đầu.**
**Replan 22/07 — quyết định:** dời hạn sprint sang **26/07 (Chủ nhật)**, có làm cả T7–CN. 5 ngày lịch còn lại (22–26/07) = đúng bằng 5 ngày công việc P0 còn lại (3b–6) → **không có buffer**. Task 7 (Pilot, 1.5 ngày) và Task 8 (stretch) **dời sang Sprint 2**, bắt đầu ngay 27/07 — data thật (84 phiếu) đã sẵn sàng nên không mất thời gian chờ.

**Sprint Goal:** Cuối sprint, chạy được pipeline end-to-end: đưa vào folder scan của một phiếu → ra đúng 1 file JSON theo schema chuẩn, đầy đủ 108 trường (câu bỏ trống = null), có confidence cho tự luận, có flags cho mọi bất thường, và PII tách riêng — **khớp ground truth của phiếu mẫu `LCA-LP-001`**. Đo accuracy trên diện rộng thuộc pha Pilot, chỉ chạy khi có 10–15 phiếu thật.

## Nguồn tham chiếu

- Đặc tả: `spec/Survey_Digitization_Spec.docx` (v0.1, 2026-07-14)
- Phương pháp trích xuất (đã chốt): [docs/extraction-method.md](docs/extraction-method.md)
- Schema + format: [schema/questionnaire_v1.json](schema/questionnaire_v1.json) · [schema/SCHEMA-FORMAT.md](schema/SCHEMA-FORMAT.md)
- Cấu trúc data + quy ước mã phiếu: [data/README.md](data/README.md) (tên file trang: bất kỳ, không cần `page-N`)
- Phiếu mẫu: `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-001.pdf` (PDF 7 trang khách tự scan lại khi bàn giao batch chính thức; đường dẫn cập nhật 22/07, đã xác minh khớp ground truth — xem `data/README.md`)
- Report task: [docs/task-01-report.md](docs/task-01-report.md) · [docs/task-02-report.md](docs/task-02-report.md) · [docs/task-03b-report.md](docs/task-03b-report.md)
- Implement plan Task 3b (viết trước khi code): [docs/implement-plan-03b-mc-extraction.md](docs/implement-plan-03b-mc-extraction.md)

## Nguyên tắc chia task (chốt 15/07)

Hai trục tách bạch, đừng trộn:

| Trục | Cần data gì | Trả lời câu hỏi |
|------|-------------|-----------------|
| **Build** (Task 1–6) | 1 phiếu mẫu + ground truth + Claude API | "Pipeline build đúng chưa?" — verify bằng khớp ground truth `LCA-LP-001` |
| **Pilot & Calibration** (Task 7) | 10–15 phiếu thật | "Đạt ngưỡng chưa? Ngưỡng confidence để đâu?" — accuracy theo loại câu, hiệu chỉnh |

Mỗi task build có DoD "khớp ground truth phiếu mẫu" — đó là verify build, **không phải** đo metrics. Con số 98% và ngưỡng confidence thuộc Task 7, gate vào blocker data. Không tách kiểu 3.1/3.2 per-task vì pha đo cắt ngang cả 4 task trích xuất (3–6), không thuộc riêng task nào.

## Sprint Backlog

| Ưu tiên | Hạng mục | Ước lượng | Trạng thái | Tiêu chí xong |
|---------|----------|-----------|------------|----------------|
| P0 | **1. Schema chuẩn từ mẫu phiếu gốc** | 1 ngày | ✅ **Xong 14/07** | 46 mục / 108 trường, validator + 14 test — [report](docs/task-01-report.md) |
| P0 | **2. Ingest & assembly** — gom file theo folder phiếu, PDF→ảnh, kiểm toàn vẹn (đủ/thiếu/thừa/hỏng trang); KHÔNG đoán thứ tự theo nội dung | 1 ngày | ✅ **Xong 15/07** | 33 test pass; chạy thật trên phiếu mẫu tên xáo trộn — [report](docs/task-02-report.md). Số trang thật do Task 3 chốt theo nội dung |
| P0 | **3a. Ground truth phiếu mẫu** — nhập tay `LCA-LP-001` thành JSON chuẩn 108 trường | 0.5 ngày | ✅ **Xong 15/07** | 45 mục ghi tay, phát hiện thêm 5 case gắn cờ mới (Q10 multi-mark, Q14×3, Q32) — [report](docs/task-03a-report.md) |
| P0 | **3b. Trích xuất trắc nghiệm đơn/đa lựa chọn** — VLM theo trang + slice schema; stamp số trang thật theo nội dung, so `tentative_page` → cờ `page_order_mismatch` | 2 ngày | 🟡 **Code + mock test xong; chờ live 31/31 do thiếu API key** — [report](docs/task-03b-report.md) | Khớp ground truth phần trắc nghiệm của phiếu mẫu; câu single đánh ≥2 → ghi hết + cờ `multi_mark_on_single_select` (phiếu mẫu có sẵn case Q30); self-consistency 2 lần chạy, lệch → cờ |
| P0 | **4. Trích xuất 2 bảng ma trận Q14, Q32** | 1 ngày | ⬜ | Khớp ground truth phần ma trận; đọc nhãn dòng từ ảnh đối chiếu schema (chống lệch dòng); ô mập mờ → trống + `ambiguous_mark` + vùng ảnh |
| P0 | **5. Phiên âm tự luận viết tay** | 0.5 ngày | ⬜ | Đủ mọi câu tự luận (trống = null) + confidence + `needs_review`; đối chiếu ground truth ở mức "đọc được đúng ý" (chữ tay khó, không kỳ vọng khớp 100% ký tự) |
| P0 | **6. Flags + PII 2 lớp + export** — cờ mâu thuẫn theo `depends_on`/`exclusive`; bản đầy đủ (kèm PII) + bản thống kê (che PII, kể cả PII lạc trong tự luận); file gộp | 1.5 ngày | ⬜ | 3 case cờ có thật trong phiếu mẫu đều bắt đúng (Q30, Q5, Q1-SĐT); bản thống kê không còn PII ở bất kỳ đâu; đủ 108 trường kể cả null; file gộp mở được bằng bảng tính |
| P1 | **7. Pilot & Calibration** — chạy 10–15 phiếu thật, nhập tay đối chiếu 2–3 phiếu, đo accuracy theo loại câu, hiệu chỉnh ngưỡng confidence + prompt | 1.5 ngày | ➡️ **Dời sang Sprint 2** (27/07) — data (84 phiếu) đã sẵn sàng ở `data/raw/scan-16-7-2026/`, chỉ chờ Task 3b–6 xong | Bảng accuracy baseline (single/multi/matrix/tự luận); ngưỡng đã hiệu chỉnh; log các dạng đánh dấu ngoài dự kiến; đo cost/phiếu → ước tính 100 phiếu |
| P2 (stretch) | **8. Báo cáo review nhanh** — HTML danh sách trường bị cờ kèm ảnh crop | 1 ngày | ➡️ **Dời sang Sprint 2** | Người kiểm tra xem ảnh gốc cạnh giá trị trích xuất, không mở lại 7 trang |

Đã bỏ hạng mục cũ "Xử lý theo lô — tự nhóm ảnh theo phiếu" (stretch): lỗi thời vì quy ước *1 folder = 1 phiếu* + manifest đã giải quyết việc nhóm; `ingest.py` sẵn sàng chạy cả lô qua manifest.

### Capacity (replan 22/07)

| | |
|---|---|
| Đã dùng | ~2/9 ngày (Task 1–2 + 3 vòng review, 14–15/07) |
| Còn lại tới hạn mới 26/07 | 5 ngày lịch (T4 22/07 → CN 26/07, tính cả cuối tuần) |
| Việc P0 còn lại (3b+4+5+6) | 5 ngày đúng |
| **Load** | **100% — không có buffer.** Bất kỳ vướng mắc nào (API lỗi, ma trận lệch dòng, v.v.) sẽ đẩy Task 6 hoặc cả Task 7 trượt tiếp. Không nên thêm việc gì ngoài 3b–6 vào 26/07 |

## Definition of Done — 2 mức

**Mức Build (đóng sprint được, không cần data mới):**
- [ ] Chạy 1 lệnh trên folder `LCA-LP-001/` → 1 JSON hợp lệ, đủ 108 trường
- [ ] JSON khớp ground truth 3a (trắc nghiệm + ma trận khớp giá trị; tự luận khớp ý)
- [ ] 3 case cờ có thật (Q30 multi-mark, Q5 mâu thuẫn, Q1 SĐT) đều được gắn đúng
- [ ] Bản thống kê không chứa PII; bản đầy đủ có PII; liên kết qua `record_id`
- [ ] File gộp mở được bằng Excel không cần xử lý thêm
- [ ] README: cách chạy, cách sửa schema v2

**Mức Pilot (Sprint 2, bắt đầu 27/07 — data đã sẵn sàng, 84 phiếu):**
- [ ] Bảng accuracy baseline theo loại câu
- [ ] Ngưỡng confidence đã hiệu chỉnh trên data thật
- [ ] Ước tính cost cho 100 phiếu

## Rủi ro

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|--------|-----------|------------|
| 🔴 **Replan 22/07 — 0% buffer trên hạn mới 26/07** (5 ngày việc = đúng 5 ngày lịch) | Bất kỳ trục trặc nào ở 3b–6 đều đẩy hạn tiếp, không còn ngày dự phòng | Ưu tiên tuyệt đối 3b–6, không nhận thêm việc; nếu tới T7 24/07 mà 3b chưa xong → báo ngay để cắt phạm vi (vd. bỏ self-consistency 2 lần chạy ở Task 3b) thay vì âm thầm trễ tiếp |
| ~~10–15 phiếu thật về trễ/không về trong sprint~~ **Đã gỡ 22/07** | ~~Task 7 trượt khỏi sprint~~ 84 phiếu thật đã có ở `data/raw/scan-16-7-2026/` (6 vùng) | Không còn là blocker cho Task 7 — Task 7 giờ nằm ở Sprint 2, chạy được ngay khi 3b–6 xong |
| Overfit vào 1 phiếu mẫu | Ngưỡng/prompt sai trên data thật | Ground truth trước khi code (3a); không hard-code theo phiếu mẫu; ngưỡng coi là tạm cho tới Task 7 |
| Ma trận Q14 lệch dòng khi ảnh nghiêng | 18 ô sai âm thầm | Đọc nhãn dòng từ ảnh đối chiếu schema; fallback crop từng dòng (extraction-method §3.3.2) |
| Trang trùng + trang thiếu bù nhau qua Task 2 (giới hạn đã biết, có test khoá) | Phiếu khuyết lọt tới trích xuất | Task 3b đối chiếu số trang thật theo nội dung → bắt tại đây |
| PII lọt vào bản thống kê | Vi phạm ẩn danh | Quét PII bắt buộc trước khi ghi file thống kê; case thật Q1-SĐT nằm trong DoD |
| Chi phí/giới hạn Claude API | Chậm giai đoạn 2 | Đo cost/phiếu trong pilot |

## Mốc thời gian (replan 22/07)

| Ngày | Kế hoạch cũ | Thực tế / Kế hoạch mới |
|------|-------------|------------------------|
| T2 14/07 | Task 1 | ✅ Task 1 (schema) |
| T3 15/07 | Task 2 | ✅ Task 2 (ingest) + 3a (ground truth) + 3 vòng review |
| T4–T5 16–17/07 | 3a + bắt đầu 3b | ⬜ Không có tiến triển ghi nhận |
| T2 20/07 | Mid-sprint check | ⬜ Không có tiến triển ghi nhận |
| **T4 22/07 (hôm nay)** | Task 4+5 xong | Bắt đầu **Task 3b** (2 ngày) — khách bàn giao 84 phiếu thật cùng ngày |
| T5 23/07 | Task 6 xong | Task 3b tiếp / xong |
| T6 24/07 | Demo mức Build | **Task 4** (1 ngày) |
| T7 25/07 | Retro (hạn cũ) | **Task 5** (0.5 ngày) + bắt đầu Task 6 |
| **CN 26/07** | — | **Task 6 xong — pipeline end-to-end trên phiếu mẫu.** Hạn sprint mới, demo mức Build |
| T2 27/07 | — | Sprint 2 bắt đầu: Task 7 (Pilot, 84 phiếu thật) → Task 8 (stretch) |

## Việc cần người khác (blocker)

1. ~~Cung cấp 10–15 phiếu scan thật~~ — ✅ **Đã nhận 22/07**: 84 phiếu ở `data/raw/scan-16-7-2026/` (6 vùng: 4/6/9/16/23/25). Lưu ý: folder `9-phieu` thực chứa 10 file — cần đối soát tên folder với khách trước khi dùng làm căn cứ đếm.
2. **Claude API key/quyền truy cập** — cần từ Task 3b (task đầu tiên gọi API). ⚠️ Mới bổ sung — cần trước 16/07.
3. Quyết định: chuẩn hóa địa bàn ở bước số hóa? (đặc tả mục 8) — **giờ là câu hỏi thật, xem mục dưới**, không còn lý thuyết.
4. Quyết định: ai làm kiểm tra thủ công — ảnh hưởng thiết kế review UI sprint 2.
5. **Mới 22/07 — cần khách xác nhận tỉnh/xã ứng với từng folder trong `scan-16-7-2026/`** (folder chỉ đặt tên theo số lượng, không theo địa bàn) — xem chi tiết bên dưới. **Cập nhật 22/07 (khách phản hồi, 2 vòng):**
   - Vòng 1: Sa Pa xác nhận gồm 2 xã **Hàm Rồng** + **Tả Phìn** (đã tách đúng folder từ đầu) — đổi `sa-pa-25phieu` → `ham-rong-25phieu` (`LCA-SPA-*` → `LCA-HR-*`).
   - Vòng 2: **Nậm Mòn** xác nhận thực ra là xã **Bắc Hà** — đổi `nam-mon-6phieu` → `bac-ha-6phieu` (`LCA-NMO-*` → `LCA-BH-*`). ✅ Hết blocker này.
   - Vòng 2: **`LCA-TPH-011`** (Thôn Mã Tra) — khách yêu cầu **tách riêng, coi là 1 khu vực khác**, không gộp vào Tả Phìn nữa — đã tách folder riêng `ma-tra-1phieu/`, đổi record_id → `LCA-MTR-001`. Xã chính xác của Mã Tra **vẫn chưa xác nhận** (mã "MTR" là tạm) — không còn là vấn đề "gộp nhầm vùng" nữa, chỉ còn thiếu tên xã thật.
   - Xem bảng mã xã đầy đủ ở `data/README.md`. Không chặn Task 3b–6; cần xong nốt tên xã Mã Tra trước 27/07 để Task 7 (Sprint 2) chạy được ngay.
6. **Mới 22/07 — khách gửi quy tắc nghiệp vụ chi tiết cho toàn bộ 34 câu** (binning thống kê, quy tắc đánh dấu, phạm vi cần độ chính xác cao/thấp) — xem [docs/client-feedback-2026-07-22-extraction-rules.md](docs/client-feedback-2026-07-22-extraction-rules.md) (nguyên văn + đã map vào schema/SCHEMA-FORMAT.md). Đã cập nhật `schema/questionnaire_v1.json`, `schema/SCHEMA-FORMAT.md`, `docs/extraction-method.md`, `docs/implement-plan-03b-mc-extraction.md`, `data/ground_truth/LCA-LP-001.json` theo quy tắc mới.

## Dữ liệu thật đã nhận — cấu trúc khác giả định ban đầu (kiểm tra 22/07)

Giả định gốc trong [data/README.md](data/README.md): `raw/<tỉnh>/<xã>/<record_id>/<ảnh scan bất kỳ>` — **1 folder = 1 phiếu**, chứa các trang rời rác cần Task 2 gom + đoán thứ tự. Data khách bàn giao (`data/raw/scan-16-7-2026/`) khác ở 2 điểm:

- **1 file PDF = 1 phiếu đầy đủ** (đã kiểm: tất cả file trong 6 folder đều đúng 7 trang/file — không phải trang rời), không phải 1 folder = 1 phiếu.
- **1 folder = nhiều phiếu cùng vùng** (folder đặt tên theo số lượng: `4-phieu`, `6-phieu`, `9-phieu`, `16-phieu`, `23-phieu`, `25-phieu` — tổng 84 file — không theo tên tỉnh/xã).

Việc **data staging** (đối chiếu tỉnh/xã, gán `record_id`, soát trùng, xử lý file rời) đã xong — xem `data/manifest.csv` và cây thư mục `data/raw/{lai-chau,lao-cai}/`.

**Cập nhật 22/07 (muộn hơn) — bỏ luôn folder bọc `<record_id>/`.** Ban đầu staging vẫn theo quy ước cũ (`<tỉnh>/<xã>/<record_id>/<record_id>.pdf`) để khỏi đổi code. Nhưng vì *1 file PDF đã là 1 phiếu đầy đủ* (không phải 1 trang), folder bọc quanh đúng 1 file là thừa — đã **dời phẳng** toàn bộ 85 file thành `data/raw/<tỉnh>/<xã>/<record_id>.pdf`, xóa các folder `<record_id>/` rỗng. `scripts/ingest.py`/`scripts/lib/assembly.py` cập nhật để tự tìm file phẳng trước (`_resolve_source`), fallback sang folder chỉ khi phiếu thật sự gồm nhiều file rời (trường hợp mẫu pilot `LCA-LP-001`, 7 ảnh riêng — chưa gộp PDF). Quy ước mới ghi ở [data/README.md](data/README.md); test cập nhật ở `tests/test_ingest.py` (case file phẳng + case `ingest.run()` end-to-end không folder).

**3 điểm bất thường phát hiện khi kiểm — trạng thái sau 2 vòng phản hồi khách (22/07):**
- `9-phieu/` (nay là `ta-phin-10phieu/`) ban đầu chứa 11 file (10 + 1 lạc) — đã soát kỹ, không trùng nhau.
- ✅ **Đã xử lý**: file rời `202607152218.pdf` (8 trang, địa điểm ghi "Thôn Mã Tra, Sapa") ban đầu tạm xếp vào `ta-phin-10phieu/LCA-TPH-011.pdf`. Khách yêu cầu **tách riêng, coi là 1 khu vực khác** — đã tách thành `ma-tra-1phieu/LCA-MTR-001.pdf`. `ta-phin-10phieu/` giờ đúng lại 10 file. Còn thiếu: tên xã thật của Mã Tra (mã "MTR" là tạm).
- ✅ **Đã xác nhận**: tên xã `nam-mon-6phieu` đọc tạm từ chữ viết tay ("Nậm Mòn") — khách xác nhận đây là xã **Bắc Hà** — đã đổi thành `bac-ha-6phieu` (`LCA-BH-*`).

**Không chặn Task 3b–6** (chỉ chạy trên phiếu mẫu `LCA-LP-001`, đã có sẵn ground truth). Sprint 2 (27/07) chỉ còn chờ khách xác nhận tên xã thật của Mã Tra trước khi chạy Task 7 trên toàn bộ 85 phiếu — 2/3 điểm đã xong.

**Cập nhật 22/07 (muộn hơn nữa) — sự cố + sửa trước khi bắt đầu Task 3b.** Rà lại trước khi giao Task 3b phát hiện: folder ảnh gốc của phiếu mẫu `data/raw/lao-cai/lung-phinh/LCA-LP-001/` (7 ảnh xáo trộn tên, dùng làm oracle ground truth cho toàn bộ Task 3b–6) đã bị thất lạc trong đợt dời-phẳng 85 file cùng ngày — chạy `ingest.py` sẽ báo `source_not_found`. Sau 2 vòng sửa (vòng 1 đoán nhầm nguồn thay thế, đã tự sửa lại sau khi user chỉ ra) xác nhận: khách đã **tự scan lại đúng phiếu giấy này** khi bàn giao batch chính thức — file đã nằm sẵn trong `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-001.pdf` (từng bị staging đổi nhầm tên thành `LCA-LP-017.pdf`), xác minh khớp ground truth bằng cách render trang 1 và đối chiếu ngày/địa điểm/tên/SĐT. Đã dùng thẳng file đó, sửa `manifest.csv` (commune → `lung-phinh-16phieu`). Nhân tiện bỏ luôn quy ước folder-nhiều-file-rời khỏi `scripts/lib/assembly.py`/`scripts/ingest.py` (không còn phiếu nào — kể cả mẫu — cần đến nó); test cập nhật ở `tests/test_ingest.py`; đã chạy lại `ingest.py` thật (qua shim poppler thay pymupdf trong sandbox) trên toàn bộ 86 dòng manifest — xem kết quả ở `docs/task-02-report.md` §7b/§7c.
