# Cấu trúc lưu data phiếu khảo sát

```
data/
  raw/khao-sat/<tỉnh>/<xã>/<record_id>.<ext>      # QUY ƯỚC DUY NHẤT — 1 file (ảnh hoặc PDF nhiều trang) = 1 phiếu đầy đủ
  manifest.csv                                    # nguồn chuẩn cho metadata phiếu
  ground_truth/<record_id>.json                   # bản ghi tay đối chiếu (kèm PII) — kiểm soát truy cập như output/full/
output/                                           # sinh ra bởi pipeline, không sửa tay
  assembly/<record_id>.json # kết quả ingest: danh sách trang + cờ toàn vẹn (Task 2)
  extract_mc/<record_id>.json # mã lựa chọn Task 3b + cờ QC — dữ liệu hạn chế truy cập
  full/<record_id>.json     # bản đầy đủ kèm PII — kiểm soát truy cập, giao khách hàng
  stats/<record_id>.json    # bản thống kê — KHÔNG chứa PII
  combined.csv              # file gộp toàn bộ phiếu (lớp thống kê)
```

`output/extract_mc/` không chủ đích phiên âm trường chữ viết tay, nhưng vẫn phải
được kiểm soát truy cập như dữ liệu nguồn: theo hợp đồng Task 3b, nếu model trả
option code sai sau lần retry, giá trị thô được giữ lại để review và về nguyên tắc
có thể chứa chuỗi ngoài dự kiến. Comparator vì vậy che expected/actual mặc định.

**Cập nhật 22/07/2026 — bỏ hẳn quy ước folder dự phòng.** Trước đây có 2 quy ước song song: file phẳng `<record_id>.<ext>` (mặc định) và folder `<record_id>/` chứa nhiều file rời (dự phòng, dùng cho phiếu mẫu `LCA-LP-001` — 7 ảnh scan riêng lẻ chưa gộp). Thực tế: **không còn phiếu nào cần quy ước dự phòng** — phiếu mẫu `LCA-LP-001` giờ dùng thẳng bản PDF 7 trang mà khách đã tự scan lại khi bàn giao batch chính thức (xem sự cố + xác minh bên dưới). `scripts/ingest.py`/`scripts/lib/assembly.py` đã đơn giản hoá theo — chỉ còn nhận **đúng 1 file/phiếu**, không còn nhánh gom nhiều file rời trong folder. Đường dẫn gốc cũng đổi từ `data/raw/<tỉnh>/...` sang `data/raw/khao-sat/<tỉnh>/...` (thêm 1 lớp thư mục `khao-sat/` bọc ngoài, khớp với cách dữ liệu đã được tổ chức lại) — `--raw-root` mặc định của `ingest.py` đã cập nhật theo.

> **Sự cố + cách sửa thật (ghi lại để tránh lặp lại — bản đã xác minh, sửa bản nháp trước đó).** Đợt dời-phẳng 85 file thật ngày 22/07 vô tình khiến folder `LCA-LP-001/` (7 ảnh xáo trộn tên, dùng làm ground truth cho toàn bộ Task 3b–6) bị thất lạc khỏi `data/raw/`. Ban đầu tưởng nhầm `output/pdf/LCA-LP-001.pdf` (1.4MB, sửa cùng ngày) là bản gộp 7 ảnh đó — **sai**: so `md5sum` với `data/raw/scan-16-7-2026/16-phieu/LCA-LP-001.pdf` (file gốc client, chưa qua staging) cho khớp tuyệt đối — đây thực ra là **chính file khách đã scan phiếu giấy `LCA-LP-001` khi bàn giao batch chính thức** (khách tự đặt tên trùng với record_id của mẫu; lúc staging 85 phiếu, script từng đổi tên file này thành `LCA-LP-017.pdf` vì tưởng nó là phiếu khác trùng tên). Đã render trang 1 bằng `pdftoppm` và đối chiếu bằng mắt với `data/ground_truth/LCA-LP-001.json`: khớp chính xác ngày (28/5/2026), địa điểm ("Tả Sì Thàng, Lùng Phình, Lào Cai"), tên + SĐT người trả lời ("Sùng Thị Sơ", 0832 492 792), kể cả ký hiệu "R" góc trang — **xác nhận đây đúng là phiếu mẫu**, không phải 2 phiếu trùng tên ngẫu nhiên. Đã bỏ file trùng ở vị trí cũ, dùng thẳng `data/raw/khao-sat/lao-cai/lung-phinh-16phieu/LCA-LP-001.pdf` (đổi tên lại từ LCA-LP-017), cập nhật `manifest.csv` (`commune` = `lung-phinh-16phieu`, không phải `lung-phinh` riêng). 7 ảnh chụp tay gốc (08/07/2026, trước khi có bản scan chính thức) vẫn giữ lại tham khảo tại `data/raw/_archive/LCA-LP-001-original-photos-2026-07-08/`. Chi tiết đầy đủ: `docs/task-02-report.md` §7b/§7c. Bài học kép: (1) đổi convention lưu trữ phải kiểm tra lại **mọi** record được docs/ground truth tham chiếu, không chỉ dữ liệu mới nhận; (2) đừng suy luận danh tính file chỉ từ tên/kích thước/thời điểm sửa — **đối chiếu nội dung thật** (checksum, hoặc ở đây là render ảnh rồi nhìn) trước khi kết luận.

**Tên file: bất kỳ, không cần đổi.** Thứ tự trang lấy từ thứ tự nội bộ của chính file PDF (không cần đổi tên `page-1..7`); với phiếu ảnh đơn trang thì không có vấn đề thứ tự. Số trang thật (đối chiếu nội dung) do Task 3 chốt. Tên gốc lưu ở cột `original_filename` để truy vết. Chấp nhận `.jpg/.png` (ảnh đơn trang) và `.pdf` (nhiều trang).

## Quy ước mã phiếu (`record_id`)

Định dạng: `<MÃ_TỈNH>-<MÃ_XÃ>-<số thứ tự 3 chữ số>`, ví dụ `LCA-LP-001`.

| Mã tỉnh | Tỉnh | Mã xã | Xã | Thư mục `data/raw/khao-sat/<tỉnh>/` |
|---------|------|-------|-----|------|
| LCA | Lào Cai | LP | Lùng Phình | `lung-phinh-16phieu` |
| LCA | Lào Cai | BH | Bắc Hà, huyện Bắc Hà — sửa 22/07 từ "Nậm Mòn" (đọc tạm chữ viết tay) sau khi khách xác nhận đây là xã Bắc Hà | `bac-ha-6phieu` |
| LCA | Lào Cai | TPH | Tả Phìn (TP Sa Pa) | `ta-phin-10phieu` |
| LCA | Lào Cai | MTR | Mã Tra (thôn) — **tách riêng 22/07 theo yêu cầu khách**, coi là 1 khu vực khác, KHÔNG gộp vào Tả Phìn nữa; xã chính xác **chưa xác nhận**, "MTR" là mã tạm | `ma-tra-1phieu` |
| LCA | Lào Cai | HR | Hàm Rồng (TP Sa Pa) — sửa 22/07 từ "Phường Sa Pa/Kim Long 3" sau phản hồi khách: Sa Pa gồm 2 xã Hàm Rồng + Tả Phìn, đã tách folder riêng từ đầu | `ham-rong-25phieu` |
| LCH | Lai Châu | SLL | Sì Lở Lầu | `si-lo-lau-4phieu` |
| LCH | Lai Châu | MSP | Mao Sao Phìn (huyện Sìn Hồ) | `mao-sao-phin-23phieu` |

Vùng mới → thêm dòng vào bảng này **trước** khi gán mã. Mã tỉnh 3 ký tự để tránh trùng (Lào Cai / Lai Châu). Số thứ tự đếm riêng trong từng xã. Tên thư mục batch hiện đặt theo số lượng phiếu nhận từ khách (`<mã-xã-slug>-<n>phieu`), không phải theo mã xã chuẩn — đây là do lịch sử nhận data theo lô, không đổi lại vì `manifest.csv` mới là nguồn chuẩn cho `province`/`commune` dùng để resolve file (xem `scripts/ingest.py`).

## Quy tắc bắt buộc

1. **Không dùng tên người** trong bất kỳ tên file/folder nào — họ tên là PII, chỉ tồn tại bên trong `output/full/`, `data/ground_truth/` (và trên chính ảnh scan).
2. **Gán mã một lần lúc nhận phiếu**: nếu nhận bản cứng, ghi `record_id` bằng bút chì lên góc trang 1 trước khi scan — từ đó giấy ↔ file khớp bằng mã. Nếu chỉ nhận file, ghi tên file gốc vào cột `original_filename` của manifest để lần ngược về lô bàn giao.
3. **Đối chứng**: JSON ↔ file scan qua `record_id` (khớp tên file `<record_id>.<ext>`); file scan ↔ bản cứng qua mã bút chì, hoặc họ tên/ngày/địa điểm viết tay trên trang 1.
4. `manifest.csv` **không bao giờ có cột họ tên/SĐT**.
5. Trang thiếu/hỏng: vẫn tạo file, ghi chú vào cột `notes` — pipeline sẽ báo thiếu trang thay vì xử lý khuyết.

## manifest.csv — các cột

| Cột | Ý nghĩa |
|-----|---------|
| `record_id` | Mã phiếu ẩn danh, khớp tên file `<record_id>.<ext>` |
| `province`, `commune` | Slug vùng, khớp đường dẫn (manifest là nguồn chuẩn, đường dẫn chỉ để duyệt tiện) |
| `num_pages` | Số trang thực nhận (chuẩn: 7) |
| `survey_date` | Ngày trên phiếu (YYYY-MM-DD) |
| `original_filename` | Tên file gốc lúc nhận từ hiện trường, phân tách `;` |
| `notes` | Ghi chú tự do (thiếu trang, scan mờ, phiếu photo…) |
