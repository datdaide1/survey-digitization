# Survey Intelligence Platform

> **Biến phiếu khảo sát thành bằng chứng có thể kiểm tra, số liệu có thể phân tích và báo cáo có thể ra quyết định.**

Đây không phải một dự án OCR. OCR/VLM chỉ là một mắt xích nhỏ ở cửa vào.

Mục tiêu của dự án là xây dựng một **hệ thống dữ liệu khảo sát end-to-end**: tiếp nhận phiếu giấy, kiểm soát chất lượng, chuẩn hóa dữ liệu, bảo vệ thông tin cá nhân, tính chỉ số thống kê và tạo đầu ra phục vụ phân tích — trong khi vẫn truy ngược được mỗi con số về phiếu nguồn.

```text
Phiếu giấy / PDF
        ↓
Tiếp nhận & kiểm tra toàn vẹn
        ↓
Số hóa có schema + confidence + cờ nghi ngờ
        ↓
Kiểm duyệt và đối soát chất lượng
        ↓
Dữ liệu sạch, ẩn danh, có thể tái lập
        ↓
Chỉ số → phân tổ → so sánh địa bàn → báo cáo
        ↓
Quyết định chương trình và bằng chứng kiểm chứng được
```

## Bài toán thật sự

Một file Excel “đã nhập xong” chưa phải là dữ liệu đáng tin. Muốn dùng kết quả khảo sát để báo cáo, hệ thống phải trả lời được đồng thời:

- Phiếu nào thiếu trang, hỏng trang hoặc có lựa chọn mâu thuẫn?
- Giá trị nào chắc chắn, giá trị nào cần người kiểm tra?
- Quy tắc nghiệp vụ nào đã biến câu trả lời thô thành nhóm thống kê?
- Dữ liệu dùng để phân tích đã loại PII chưa?
- Một tỷ lệ trong báo cáo có thể lần ngược về các bản ghi và phiếu gốc không?
- Khi thay đổi cách chia nhóm, có thể tính lại mà không OCR lại toàn bộ hay không?

Kiến trúc của dự án giữ riêng **dữ liệu thô**, **dữ liệu diễn giải**, **dữ liệu thống kê** và **đầu ra báo cáo**. Nhờ vậy, mọi phép biến đổi đều có thể kiểm tra và chạy lại.

## Phạm vi sản phẩm

### 1. Thu nhận và quản trị dữ liệu khảo sát

- Mỗi phiếu có `record_id` ẩn danh và metadata trong manifest.
- Kiểm tra file nguồn, số trang kỳ vọng, trang thiếu/thừa/hỏng.
- Chuẩn hóa PDF/ảnh thành đầu vào nhất quán cho pipeline.
- Giữ liên kết từ bản ghi phân tích về đúng phiếu nguồn.

### 2. Số hóa có kiểm soát

- Schema hiện mô tả **46 mục, 108 trường đầu ra**, gồm câu đơn lựa chọn, đa lựa chọn, ma trận, trường ghép và tự luận.
- Nhận diện nhiều kiểu đánh dấu thực địa: tick, `x`, `/`, khoanh tròn, dấu sửa lựa chọn.
- Không đoán liều: trường không chắc chắn đi kèm confidence, `needs_review` và cờ bất thường.
- Ground truth được lập thủ công để kiểm chứng pipeline trước khi pilot diện rộng.

### 3. Kiểm định chất lượng

- Đối chiếu tự động với ground truth theo từng loại câu hỏi.
- Đo accuracy riêng cho single-select, multi-select, matrix và free text.
- Phát hiện lựa chọn loại trừ, câu phụ không thỏa điều kiện, nhiều dấu trên câu đơn chọn và dấu bị gạch bỏ.
- Hàng đợi review chỉ đưa ra trường đáng ngờ kèm vùng ảnh liên quan, thay vì bắt người kiểm tra đọc lại toàn bộ phiếu.
- Theo dõi tỷ lệ cần sửa tay và chi phí xử lý trên mỗi phiếu.

### 4. Lớp dữ liệu an toàn cho thống kê

Hệ thống tạo hai lớp dữ liệu liên kết bằng `record_id`:

| Lớp | Mục đích | PII |
|---|---|---|
| `full` | Lưu trữ đầy đủ, đối soát và bàn giao có kiểm soát | Có |
| `stats` | Phân tích, tổng hợp và báo cáo | Không |

PII trong trường định danh và PII vô tình xuất hiện trong câu tự luận đều phải được che khỏi lớp thống kê. Việc tách hai lớp là một bước bắt buộc trước khi tổng hợp báo cáo.

### 5. Statistical engine — từ câu trả lời thành chỉ số

Lớp thống kê không chỉ đếm lựa chọn. Nó thực hiện các phép biến đổi có khai báo, có phiên bản và có thể chạy lại:

- Tính tuổi từ năm sinh rồi phân nhóm: `<35`, `35–45`, `>45`.
- Chuẩn hóa cấp học thành cấp 1, cấp 2, cấp 3.
- Phân loại tuổi kết hôn: `<18` là tảo hôn, `≥18` là bình thường.
- Suy ra số năm kinh nghiệm trồng dược liệu và chia `<1 năm`, `≥1 năm`.
- Giữ tên dân tộc cụ thể khi khác Kinh; các lựa chọn “Khác” ở câu khác có thể gộp theo quy tắc nghiệp vụ.
- Chuẩn hóa mã lựa chọn nhưng vẫn bảo toàn giá trị thô để có thể đổi ngưỡng và tính lại sau này.

Nguyên tắc cốt lõi: **mô hình đọc giá trị thô; code thống kê mới tính bucket**. Không giao phép tính xác định cho mô hình thị giác và không làm mất dữ liệu gốc chỉ để tiện vẽ biểu đồ.

### 6. Phân tích và báo cáo

Đích đến của pipeline là một lớp dữ liệu sẵn sàng cho các sản phẩm phân tích:

- Hồ sơ mẫu khảo sát: địa bàn, nhóm tuổi, giới tính, dân tộc, học vấn, nghề nghiệp.
- Bảng tần suất và tỷ lệ cho từng câu hỏi.
- Cross-tab theo tỉnh/xã, nhóm nhân khẩu học và nhóm kinh nghiệm.
- Chỉ số phân công lao động, quyền ra quyết định, tiếp cận nguồn lực và các ma trận vai trò trong hộ.
- So sánh giữa địa bàn và phát hiện nhóm có chênh lệch đáng chú ý.
- Theo dõi `n`, số thiếu, mẫu số hợp lệ và tỷ lệ cần review bên cạnh mọi phần trăm.
- Xuất bảng dữ liệu sạch, bảng tổng hợp, biểu đồ và báo cáo có thể tái lập.

Một con số trong báo cáo không đứng một mình. Nó phải đi kèm định nghĩa chỉ số, mẫu số, bộ lọc, phiên bản schema và khả năng truy vết về dữ liệu nguồn.

## Kiến trúc dữ liệu

```text
data/raw/                     Phiếu nguồn — dữ liệu hạn chế truy cập
data/manifest.csv             Danh mục và metadata chuẩn
schema/questionnaire_v1.json  Schema câu hỏi + logic + quy tắc thống kê
output/assembly/              Kết quả kiểm tra và render đầu vào
output/extract_mc/            Mã lựa chọn Task 3b + cờ QC (hạn chế truy cập)
output/full/                  Bản số hóa đầy đủ có PII
output/stats/                 Bản ẩn danh phục vụ phân tích
output/combined.csv           Bảng phẳng dùng cho thống kê
reports/                      Bảng, biểu đồ và báo cáo sinh từ dữ liệu sạch
```

`output/` là sản phẩm sinh tự động và không được sửa tay. Quy tắc chi tiết về dữ liệu nằm tại [data/README.md](data/README.md); định dạng schema nằm tại [schema/SCHEMA-FORMAT.md](schema/SCHEMA-FORMAT.md).

## Trạng thái hiện tại

| Năng lực | Trạng thái |
|---|---|
| Schema chuẩn và validator | ✅ Hoàn thành |
| Manifest, ingest, render và kiểm tra toàn vẹn | ✅ Hoàn thành |
| Ground truth cho phiếu mẫu | ✅ Hoàn thành |
| Trích xuất câu đơn/đa lựa chọn | 🟡 Code + mock test xong; chờ API key để nghiệm thu live 31/31 |
| Trích xuất ma trận | ⏳ Kế tiếp |
| Tự luận và trường số dẫn xuất | ⏳ Kế tiếp |
| Cờ logic, tách PII và export | ⏳ Kế tiếp |
| Pilot accuracy trên dữ liệu thật | ⏳ Sau khi pipeline build hoàn chỉnh |
| Statistical engine | 🧭 Đã khai báo quy tắc, chưa hoàn thiện code |
| Dashboard và báo cáo phân tích | 🧭 Đích sản phẩm |

Repository hiện có dữ liệu thật để phát triển và pilot. Trạng thái chi tiết, tiêu chí hoàn thành và rủi ro được theo dõi trong [sprint-plan-survey-digitization.md](sprint-plan-survey-digitization.md).

## Chạy nhanh

### Yêu cầu môi trường

- Windows + PowerShell
- Conda environment `survey-digitizer`
- Python 3.12 tại `E:\anaconda3\envs\survey-digitizer\python.exe`

Mọi lệnh Python trong dự án phải dùng đúng interpreter này.

### 1. Kiểm tra schema

```powershell
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/validate_schema.py schema/questionnaire_v1.json
```

Kết quả hiện tại: schema hợp lệ, 46 mục và 108 trường đầu ra.

### 2. Chạy ingest toàn bộ manifest

```powershell
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/ingest.py `
  --manifest data/manifest.csv `
  --raw-root data/raw/khao-sat `
  --out-dir output/assembly
```

Mỗi phiếu tạo một JSON assembly chứa danh sách trang, trạng thái toàn vẹn và các cờ lỗi. Pipeline tiếp tục xử lý từng phiếu ngay cả khi một bản ghi trong lô bị lỗi.

### 3. Trích xuất Task 3b cho một phiếu

```powershell
$env:ANTHROPIC_API_KEY = "..."
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/extract_mc.py `
  --record-id LCA-LP-001
& "E:\anaconda3\envs\survey-digitizer\python.exe" scripts/compare_ground_truth.py `
  LCA-LP-001 --fields task3b
```

Mỗi trang được gửi hai lần độc lập để kiểm tra self-consistency. Chạy cả manifest
là thao tác opt-in bằng `--all`; không truyền lựa chọn sẽ không upload dữ liệu.

### 4. Chạy test

```powershell
& "E:\anaconda3\envs\survey-digitizer\python.exe" tests/test_validate_schema.py
& "E:\anaconda3\envs\survey-digitizer\python.exe" tests/test_ingest.py
& "E:\anaconda3\envs\survey-digitizer\python.exe" tests/test_mc_extraction.py
```

## Nguyên tắc kỹ thuật

1. **Schema-first** — cấu trúc bảng hỏi và logic nghiệp vụ là hợp đồng dữ liệu.
2. **Raw first, derived later** — giữ giá trị gốc; bucket và chỉ số là lớp dẫn xuất.
3. **Uncertainty is data** — không che giấu độ không chắc chắn của mô hình.
4. **Human review by exception** — con người xử lý ngoại lệ, không nhập lại toàn bộ.
5. **Privacy by construction** — lớp phân tích không chứa thông tin định danh.
6. **Traceability end-to-end** — báo cáo phải truy được về bản ghi và phiếu nguồn.
7. **Reproducible reporting** — cùng dữ liệu, schema và cấu hình phải sinh cùng kết quả.

## Tài liệu chính

- [Sprint plan](sprint-plan-survey-digitization.md) — tiến độ và Definition of Done.
- [Phương pháp trích xuất](docs/extraction-method.md) — kiến trúc OCR/VLM, confidence, review và PII.
- [Quy tắc trích xuất & thống kê](docs/client-feedback-2026-07-22-extraction-rules.md) — diễn giải nghiệp vụ đã chốt.
- [Schema format](schema/SCHEMA-FORMAT.md) — hợp đồng dữ liệu và logic kiểm tra.
- [Task 1 report](docs/task-01-report.md) — schema và validator.
- [Task 2 report](docs/task-02-report.md) — ingest và assembly.
- [Task 3a report](docs/task-03a-report.md) — ground truth và bài học từ dữ liệu thực địa.
- [Task 3b report](docs/task-03b-report.md) — trích xuất lựa chọn, self-consistency và trạng thái nghiệm thu live.

## Định nghĩa thành công

Dự án thành công không phải khi “OCR đọc được chữ”. Nó thành công khi:

- dữ liệu đủ sạch để thống kê mà không phải sửa tay hàng loạt;
- mọi ngoại lệ quan trọng được phát hiện thay vì âm thầm biến thành số liệu sai;
- PII không lọt vào tập phân tích;
- chỉ số được tính nhất quán theo quy tắc đã duyệt;
- báo cáo cho thấy cả kết quả lẫn chất lượng bằng chứng phía sau kết quả đó;
- và khi có câu hỏi về một con số, đội dự án có thể lần ngược đến đúng bản ghi nguồn.

**Số hóa phiếu là bước đầu. Năng lực biến dữ liệu thành bằng chứng đáng tin mới là sản phẩm.**
