# Task 3b report — Trích xuất câu đơn/đa lựa chọn

**Trạng thái 22/07/2026:** 🟡 phần triển khai và kiểm thử mock đã xong; Definition
of Done live trên `LCA-LP-001` chưa thể chốt vì môi trường chưa có
`ANTHROPIC_API_KEY`.

## 1. Phạm vi đã triển khai

- 31 parent question IDs trên đủ 7 trang theo implement plan.
- Mỗi trang gửi đúng 1 ảnh cùng schema slice động, gọi độc lập hai lần.
- Tool output dùng strict schema; code tiếp tục validate, canonicalize và retry đúng
  một lần khi gặp option code ngoài schema.
- So sánh self-consistency không phụ thuộc thứ tự array; khi lệch giữ run 1 làm
  giá trị chính, gắn `self_consistency_mismatch` và lưu cả hai run trong `_debug`.
- `trang_khop_du_kien=false` ở bất kỳ run nào tạo `page_order_mismatch`; không tự
  remap trang.
- CLI mặc định chỉ chạy record được nêu bằng `--record-id`; batch toàn manifest
  phải chủ động dùng `--all`.

Các file chính:

- `scripts/lib/mc_extraction.py` — schema slice, request, transport, validation và
  self-consistency.
- `scripts/extract_mc.py` — CLI và ghi `output/extract_mc/<record_id>.json`.
- `scripts/compare_ground_truth.py` — comparator `--fields task3b`.
- `tests/test_mc_extraction.py` — mock/unit coverage, không gọi mạng.

## 2. Hợp đồng dữ liệu cần giữ cho Task 6

- Câu thường: `answers.<id> = {"value": <code|codes|null>, "flags": [...]}`.
- Q5 là composite ngoại lệ nhưng vẫn chiếm một parent ID: `value` là object gồm
  đúng ba component checkbox boolean (`Q5_khong_di_hoc`,
  `Q5_khong_tieng_pho_thong`, `Q5_trung_cap_dh`). Component text
  `Q5_lop_cao_nhat` thuộc Task 5 và không xuất hiện ở đây.
- Q17: `value.rows.<device>` là array code thành viên hộ và
  `value.khong_ai_co` là boolean.
- `depends_on` và `exclusive` không gate hoặc sửa giá trị ở Task 3b; logic đó thuộc
  Task 6.

Nếu option code vẫn sai sau retry, Task 3b giữ raw value và gắn
`invalid_option_code` để review theo implement plan. Vì raw value có thể là chuỗi
ngoài dự kiến, `output/extract_mc/` được coi là dữ liệu hạn chế truy cập và
comparator che expected/actual mặc định.

## 3. Safety và kiểm thử

- Chỉ cho phép endpoint Anthropic chính thức; image path phải nằm trong root cho
  phép và đúng `record_id`.
- Preflight đủ schema + ảnh của cả 7 trang trước cuộc gọi trả phí đầu tiên.
- HTTP retry gồm 429/5xx/529 và tôn trọng `Retry-After`; lỗi auth/permission/model
  hoặc lỗi dịch vụ đã hết retry dừng batch thay vì lặp trên mọi phiếu.
- Kết quả local hiện tại: schema `14/14`, ingest `32/32`, Task 3b `103/103` pass.

## 4. Lệnh nghiệm thu còn thiếu

```powershell
$env:ANTHROPIC_API_KEY = "..."
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/extract_mc.py --record-id LCA-LP-001
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/compare_ground_truth.py LCA-LP-001 --fields task3b
```

Chỉ đánh dấu Task 3b hoàn tất khi comparator live báo `31/31 fields matched` và đã
kiểm tra trực tiếp các case Q10, Q30, Q17 cùng cờ page order.
