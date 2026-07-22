# Report tổng kết — Task 3a: Ground truth phiếu mẫu

**Sprint:** Số hóa phiếu khảo sát Sprint 1 · **Hạng mục:** P0 số 3a (Build) · **Trạng thái:** ✅ Xong
**Ngày:** 15/07/2026 · **Sprint plan:** [sprint-plan-survey-digitization.md](../sprint-plan-survey-digitization.md)

---

## 1. Mục tiêu

Nhập tay toàn bộ 7 trang scan của `LCA-LP-001` thành 1 JSON chuẩn theo schema v1, **trước khi viết code trích xuất**. Đây là bộ eval cho Task 3b–6: mọi lần build/tinh chỉnh prompt đều đối chiếu lại với file này thay vì tin cảm tính "nhìn có vẻ đúng" — biện pháp chống overfit đã nêu trong [extraction-method.md](extraction-method.md) rủi ro #1.

## 2. Deliverable

| File | Nội dung |
|------|----------|
| [`data/ground_truth/LCA-LP-001.json`](../data/ground_truth/LCA-LP-001.json) | 45 mục câu hỏi (metadata + 41 câu Q + consent), transcribe từ 7 ảnh scan thật |

Đã cập nhật [`data/README.md`](../data/README.md) — thêm `data/ground_truth/` vào cây thư mục, ghi rõ chứa PII nên kiểm soát truy cập như `output/full/`.

## 3. Phương pháp

- Đọc lại cả 7 ảnh theo đúng **thứ tự nội dung thật** (không theo tên file — tên file trong `LCA-LP-001/` đã bị xáo trộn từ Task 2), dùng mapping đã ghi trong [task-02-report.md §4](task-02-report.md).
- Với mỗi câu: ghi `value` theo đúng `code` trong schema (không dùng label).
- Câu tự luận: ghi `confidence` (thấp/trung bình) trung thực theo độ khó đọc chữ viết tay — **không đoán chắc** khi không chắc, đúng tinh thần "chấp nhận ~60% cần review" của đặc tả.
- Mọi bất thường thấy được (đánh dấu mập mờ, mâu thuẫn, đa lựa chọn sai quy định) ghi `flags` + `note` giải thích — kể cả những case chưa từng được ghi nhận trước đây.

## 4. Phát hiện mới (ngoài 3 case đã biết trong schema)

Đọc kỹ để làm ground truth lộ ra thêm anomaly thật mà các lần đọc trước (khi viết schema) đã bỏ sót:

| Vị trí | Phát hiện | Xử lý |
|--------|-----------|-------|
| **Q10** | Tick cả "2. Nông dân" và "4. Buôn bán, kinh doanh nhỏ" trên câu **đơn** lựa chọn | Case `multi_mark_on_single_select` thứ 2 (ngoài Q30) — đã thêm vào note của Q10 trong schema và vào danh sách test case ở SCHEMA-FORMAT.md |
| **Q14** dòng `thuoc_bvtv`, `gia_suc_nho`, `gia_suc_lon` | Ký hiệu đánh dấu dạng vòng tròn lạ, không giống tick chuẩn nào | `ambiguous_mark` — đúng thiết kế schema, chỉ là case cụ thể mới ghi nhận |
| **Q32** dòng `vay_von` | Cùng dạng ký hiệu lạ | `ambiguous_mark` |
| **Q14** dòng `bao_duong_xe` | Cột "Chồng" tick rõ, nhưng cột "Người khác" có chữ viết tay không rõ nghĩa xen vào | `ambiguous_mark` + ghi PAGE_NOTES trang 6 |
| **Q27a** | Chọn "Khác" kèm ghi rõ "bố mẹ chú" | Ban đầu tôi tưởng là schema thiếu `other_text` cho option này — **kiểm tra lại thì schema đã khai đúng từ trước** (`"other_text": true` có sẵn). Đã sửa lại note trong ground truth cho chính xác, không phải một finding thật |

Điểm #5 đáng chú ý: tự phát hiện và tự sửa nhầm lẫn của chính mình trước khi báo cáo — tránh đưa thông tin sai vào tài liệu.

## 4b. Sửa sau phản hồi domain expert (15/07, cùng ngày)

Sau khi giao ground truth, nhận phản hồi làm rõ 2 quy tắc diễn giải đánh dấu mà tôi (không có kiến thức nghiệp vụ hiện trường) đã đọc sai:

| Diễn giải ban đầu (sai) | Sửa lại theo domain knowledge |
|---|---|
| Ký hiệu vòng tròn lạ ở Q14 (`thuoc_bvtv`, `gia_suc_nho`, `gia_suc_lon`) và Q32 (`vay_von`) → gắn cờ `ambiguous_mark`, value null cần review | Đây là chữ viết tắt **"ko"** (không) — quy ước hiện trường có nghĩa hộ đó **không có ai đảm nhiệm việc này**. Value vẫn null nhưng **không** phải ambiguous, không cần review — là trạng thái trống hợp lệ |
| Q14 `bao_duong_xe`: value `["chong"]` + cờ `ambiguous_mark` vì cột "Người khác" có chữ lạ | Dòng đã có tick hợp lệ ở "Chồng" → chữ ở cột "Người khác" **bị bỏ qua theo quy tắc**, không phải bất thường. Value đơn `"chong"`, không cờ |

Đã sửa `data/ground_truth/LCA-LP-001.json` và thêm **§Quy tắc diễn giải đánh dấu** vào [SCHEMA-FORMAT.md](../schema/SCHEMA-FORMAT.md) — đây là quy tắc nghiệp vụ thật cần đưa vào prompt VLM ở Task 3b/4, không chỉ sửa 1 lần cho ground truth.

**Bài học phương pháp:** ground truth do người không có domain knowledge hiện trường transcribe (dù đọc ảnh cẩn thận) vẫn có rủi ro diễn giải sai ký hiệu địa phương/quy ước riêng của điều tra viên. Ground truth dùng cho Build (task 3a) đã đủ tốt sau vòng sửa này; nhưng với ground truth dùng để **đo accuracy chính thức** (Task 7 Pilot), càng cần người có hiểu biết thực địa tham gia — khớp đúng tinh thần đặc tả mục 7: "một người độc lập nhập tay lại toàn bộ" nên là người hiểu quy ước hiện trường, không chỉ đọc ảnh thuần túy.

## 5. Điểm khó khi transcribe (trung thực, không che giấu)

Vài câu tự luận/trường viết tay không đọc được chắc chắn — ghi `confidence: "thap"` + `needs_review: true` thay vì đoán liều:

- **Q6 subfield tuổi kết hôn**: chữ viết tắt không rõ nghĩa, để `null`.
- **Q9, Q15, Q31**: chữ viết tay khó đọc trọn vẹn, transcribe best-effort phần đọc được.
- **META_LOCATION**: tên thôn khó đọc chính xác tuyệt đối.
- **Q34**: câu trả lời viết tràn xuống dưới cả dòng in "Xin chân thành cảm ơn..." — gộp vào cùng 1 câu trả lời (không tách thành ghi chú lề riêng, vì rõ ràng là phần tiếp của Q34 do hết chỗ viết).

## 6. Cập nhật schema đi kèm

- `Q10.note`: thêm mô tả case multi-mark thực tế.
- `schema/SCHEMA-FORMAT.md` §Test case: bổ sung 5 case mới (Q10, Q14×3 dòng, Q32 dòng vay_von) vào danh sách test case có sẵn.
- Validator chạy lại xác nhận: **vẫn 108 trường, hợp lệ** — sửa note không ảnh hưởng cấu trúc.

## 7. Việc tiếp theo

- **Task 3b — Trích xuất trắc nghiệm đơn/đa lựa chọn**: xây pipeline VLM, đối chiếu output với chính `data/ground_truth/LCA-LP-001.json` cho phần câu trắc nghiệm. Cần Claude API key (blocker đã nêu trong sprint plan).
- Ground truth này sẽ tiếp tục dùng làm eval cho Task 4 (ma trận), 5 (tự luận), 6 (flags + PII) — không cần lặp lại bước nhập tay.

## 8. Sửa lại 22/07/2026 — quy tắc "Người khác" đổi theo phản hồi khách

Khách gửi bộ quy tắc nghiệp vụ chi tiết cho toàn bộ 34 câu (xem [docs/client-feedback-2026-07-22-extraction-rules.md](client-feedback-2026-07-22-extraction-rules.md)), trong đó có 1 điểm **đổi ngược lại** quy tắc diễn giải "Người khác" đã chốt ở mục 4b phía trên: quy tắc cũ (chốt 15/07, sau phản hồi domain expert) là *"dòng đã có tick hợp lệ ở cột khác → chữ ở cột Người khác bị bỏ qua"*; quy tắc mới (khách xác nhận 22/07) là **bất kỳ chữ viết tay nào ở cột Người khác đều tính là đã chọn**, không còn điều kiện "bỏ qua nếu đã có tick khác".

Đã render lại trang 3 gốc (`pdftoppm`, không phải suy đoán) và xác nhận: dòng `bao_duong_xe` — cột "Chồng" có tick X rõ, cột "5. Người khác" có chữ viết tay (khó đọc rõ nghĩa). Theo rule mới, giá trị đúng đổi từ `"chong"` (đơn) thành `["chong", "nguoi_khac"]` (đa lựa chọn). Đã sửa `data/ground_truth/LCA-LP-001.json` và `schema/SCHEMA-FORMAT.md` §Quy tắc diễn giải đánh dấu (mục 5).

**Bài học phương pháp (lặp lại từ mục 4b):** đây là quy tắc nghiệp vụ thứ 2 mà khách phải tự sửa lại sau khi thấy cách người không có domain knowledge hiện trường diễn giải ký hiệu trên phiếu — củng cố thêm luận điểm ở mục 4b rằng ground truth dùng cho đo accuracy chính thức (Task 7) nên có người hiểu quy ước hiện trường tham gia, không chỉ đọc ảnh thuần túy. Ngoài ra, quy tắc lần này **thay đổi theo thời gian** (không phải chỉ là sửa lỗi đọc sai) — nghĩa là bất kỳ lần khách góp ý thêm sau này về cách diễn giải đánh dấu đều có thể làm ground truth đã "chốt" trước đó cần rà lại, không nên coi ground truth là bất biến sau Task 3a.
