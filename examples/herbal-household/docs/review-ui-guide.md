# Review UI — sửa/duyệt `output/full/*.json` cạnh ảnh phiếu scan

**Ngày viết:** 2026-07-24
**Vị trí code:** `scripts/review_ui/` (`index.html`, `style.css`, `main.js`, `schemaEngine.js`, `fsAccess.js`, `idb.js`, `csv.js`)

## Vấn đề nó giải quyết

Trước đây review 1 phiếu nghĩa là mở `output/full/<record_id>.json` bằng tay, mở lại ảnh scan (`output/assembly/_render/<record_id>/*.png`) bằng tay, rồi so từng câu. UI này gộp 2 việc đó vào 1 màn hình: ảnh trang bên trái (zoom/pan được), form các câu hỏi của đúng trang đó bên phải — sửa giá trị/flags/confidence/note ngay tại chỗ, **lưu thẳng vào đúng file JSON gốc**, không qua bước trung gian nào.

Chạy hoàn toàn phía trình duyệt (File System Access API) — không có backend, không gửi dữ liệu đi đâu cả, không cần cài thêm gì ngoài Chrome/Edge.

## Cách chạy

```powershell
& "E:\anaconda3\envs\survey-digitizer\python.exe" -m http.server 8765 --directory scripts/review_ui
```

Mở `http://localhost:8765` bằng **Chrome hoặc Edge bản mới** (bắt buộc — Firefox/Safari chưa hỗ trợ File System Access API). Bấm **"Chọn thư mục dự án (STARTUP)"**, chọn đúng thư mục gốc `E:\STARTUP` (nơi có sẵn `schema/`, `docs/`, `output/`). Lần sau mở lại không cần chọn lại thư mục (quyền truy cập được nhớ qua IndexedDB của trình duyệt) — chỉ cần bấm nút "Cấp lại quyền…" nếu trình duyệt hỏi lại.

Dùng xong tắt server bằng `Ctrl+C` trong PowerShell.

## Luồng làm việc

1. Sidebar bên trái liệt kê toàn bộ phiếu trong `docs/manual-extraction-progress.csv` (đọc, **không ghi lại** file này — xem "Giới hạn" bên dưới). Chấm màu: xám = pending (chưa có `output/full/*.json`), xanh = đã có file và sạch (0 needs_review), vàng = có needs_review, đỏ = file JSON lỗi cú pháp (không parse được — UI tự phát hiện, không cần chờ chạy script riêng).
2. Bấm 1 phiếu → hiện ảnh trang hiện tại (mặc định nhảy thẳng tới trang đầu tiên có needs_review nếu có) + form các câu của trang đó.
3. Sửa trực tiếp: chọn/bỏ chọn đáp án, sửa ô tự luận, tick flags, đặt confidence, tick needs_review, ghi note. Nút **"+REVIEW:"** cạnh ô note chèn sẵn tiền tố `REVIEW: ` đúng quy ước đã dùng trong các phiếu đã review trước đó (`grep REVIEW output/full/*.json` để xem ví dụ cũ).
4. Tự động lưu ~1 giây sau lần sửa cuối (debounce), hoặc bấm nút **Lưu** / `Ctrl+S`. Mỗi lần lưu, bản cũ được sao vào `<record_id>.json.bak` (ghi đè lần trước) — 1 bước hoàn tác nếu lỡ sửa nhầm.
5. Banner phía trên form báo **cấu trúc hợp lệ / thiếu trường** — chạy lại logic y hệt `scripts/validate_record.py` ngay trong trình duyệt (đã đối chiếu cho khớp 1:1, xem `docs/task-*-report.md` nếu cần lịch sử). Đây chỉ là lưới an toàn cấu trúc (bắt lỗi *thiếu trường*), **không** kiểm tra nội dung đọc đúng/sai — việc đó vẫn là việc của người review khi nhìn ảnh.
6. Nút **"Câu review tiếp theo →"** (hoặc phím `J`) nhảy sang trang kế tiếp còn needs_review trong phiếu. `←`/`→` đổi trang. Checkbox "chỉ hiện câu cần review" lọc bớt các câu đã sạch.
7. Phiếu `pending` (chưa có file) hiện nút **"Tạo file mới (trống)"** — khởi tạo đủ 46 câu theo schema (rỗng), có thể dùng UI này để nhập từ đầu thay vì gõ tay JSON, không chỉ để review.

## Giới hạn đã biết

- **Không ghi lại `docs/manual-extraction-progress.csv`** — cố ý, để tránh làm hỏng định dạng file theo dõi tiến độ chính. Sau khi review xong 1 phiếu, vẫn cần cập nhật cột `status/done_by/done_date/note` trong CSV đó bằng tay (hoặc nhờ Claude) như quy trình cũ.
- Không khoá đồng thời nhiều tab/nhiều người cùng sửa 1 phiếu — nếu 2 phiên cùng mở 1 record và cùng lưu, phiên lưu sau ghi đè phiên trước (không merge). Dự án hiện chỉ 1 người làm nên chưa cần xử lý.
- Backup chỉ giữ **1 bước** (`.bak` bị ghi đè mỗi lần lưu tiếp theo), không phải lịch sử đầy đủ. Nếu cần lịch sử đầy đủ, dùng git (repo đã có `.git`, nhưng theo `sprint-plan-survey-digitization.md` có lúc từng chưa init hẳn — kiểm tra `git status` nếu muốn dựa vào git để phục hồi).
- `option.exclusive` không tự loại trừ lựa chọn khác khi tick (giữ đúng triết lý toàn pipeline: đọc đúng những gì có trên giấy, người review tự quyết định xung đột bằng flags/note — xem `schema/SCHEMA-FORMAT.md` mục "Quy tắc diễn giải đánh dấu").
- Panel "Xem JSON thô" chỉ đọc (không sửa trực tiếp trong đó) — muốn set `value: null` tường minh cho `multi_select` (case hiếm, "không thể xác định giá trị") thì vẫn cần sửa tay ngoài UI.

## Liên quan

- Quy tắc đánh dấu áp dụng khi review: `schema/SCHEMA-FORMAT.md` §"Quy tắc diễn giải đánh dấu" (8 mục, cập nhật 24/07).
- Hướng dẫn trích xuất thủ công gốc (Claude đọc ảnh lần đầu, không qua UI này): `docs/implement-plan-manual-full-record-extraction.md`.
- Theo dõi tiến độ: `docs/manual-extraction-progress.csv`.
