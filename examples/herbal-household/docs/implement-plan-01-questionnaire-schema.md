# Implement Plan — Task 1: Schema chuẩn từ mẫu phiếu gốc

**Sprint:** Số hóa phiếu khảo sát Sprint 1 (14–25/07/2026) — hạng mục P0 số 1, ước lượng 1 ngày
**Người đọc:** dev thực hiện task này; người review schema (đối chiếu với bảng hỏi gốc)
**Đầu vào:** `pretest_VN.docx` (mẫu bảng hỏi gốc), `LCA-LP-001/page-1.jpg`–`LCA-LP-001/page-7.jpg` (1 phiếu đã điền, dùng đối chiếu bố cục in thật)
**Đầu ra:** `schema/questionnaire_v1.json` + validator + tài liệu format

---

## 1. Mục tiêu

Tạo **một file schema khai báo** mô tả toàn bộ cấu trúc bảng hỏi (34 câu + phần header/đồng thuận), làm khung tham chiếu duy nhất cho mọi bước sau (trích xuất, gắn cờ, xuất JSON). Schema là **cấu hình, không phải code** — đổi mẫu phiếu v2 chỉ cần sửa file này (yêu cầu P2 trong đặc tả).

Tiêu chí nghiệm thu (từ đặc tả mục 5.1):
- Liệt kê đủ **tất cả** câu hỏi trong mẫu gốc, đối chiếu thủ công 1 lần.
- Mỗi câu có **mã ổn định** (Q1, Q14, Q16a, Q27b…) dùng xuyên suốt hệ thống — mã theo đúng số in trên phiếu, không đánh lại số.

## 2. Deliverables

| File | Nội dung |
|------|----------|
| `schema/questionnaire_v1.json` | Schema đầy đủ 34 câu + header + consent |
| `schema/SCHEMA-FORMAT.md` | Mô tả format: các loại câu, các trường, quy ước |
| `scripts/validate_schema.py` | Validator: mã trùng, thiếu trường, ma trận đúng dòng×cột |
| Bảng đối chiếu (mục 6 của SCHEMA-FORMAT.md) | Checklist 34 câu đã đối chiếu docx ↔ scan thật |

## 3. Thiết kế schema

### 3.1 Taxonomy loại câu (`type`)

| Type | Mô tả | Ví dụ |
|------|-------|-------|
| `single_select` | Chọn đúng 1 | Q3, Q8, Q10, Q24–Q26 |
| `multi_select` | Chọn nhiều | Q7, Q11, Q18, Q28 |
| `free_text` | Tự luận nhiều dòng, phiên âm nguyên văn | Q9, Q15, Q21c, Q34 |
| `text` | Điền ngắn 1 dòng | Q2 (năm sinh), Địa điểm |
| `matrix` | Bảng dòng × cột, mỗi dòng chọn cột | Q14, Q32 |
| `device_grid` | Lưới nhỏ: mỗi dòng thiết bị × {Chồng, Vợ} + option exclusive | Q17 |
| `composite` | Câu ghép nhiều thành phần khác loại | Q5, Q6 |

### 3.2 Cấu trúc một câu hỏi (ví dụ rút gọn)

```json
{
  "id": "Q7",
  "page": 1,
  "section": "A",
  "text": "Nguồn thu nhập chính là gì?",
  "type": "multi_select",
  "options": [
    {"code": "trong_trot", "label": "Trồng trọt"},
    {"code": "chan_nuoi", "label": "Chăn nuôi"},
    {"code": "cay_duoc_lieu", "label": "Cây dược liệu"},
    {"code": "lam_nghiep", "label": "Lâm nghiệp"},
    {"code": "phi_nong_nghiep", "label": "Phi nông nghiệp"}
  ]
}
```

Các trường bổ sung khi cần:
- `"pii": true` — Q1 (họ tên; SĐT thực tế cũng bị ghi vào đây — xem scan trang 1).
- `"other_text": true` trên option — lựa chọn "Khác (ghi rõ)" kèm dòng điền.
- `"exclusive": true` trên option — "Không là hội viên…" (Q11), "Không" (Q33), "Chưa" (Q22a), "Không ai có thiết bị nào" (Q17): nếu được chọn cùng option khác → gắn cờ mâu thuẫn.
- `"subfield"` — trường phụ đi kèm 1 option (Q6: "Đã kết hôn" kèm "kết hôn năm bao nhiêu tuổi"; Q16a: "Có" kèm ghi công việc).
- `"depends_on"` — câu điều kiện (Q21b/Q21c phụ thuộc Q21a; Q22b phụ thuộc Q22a="Chưa"; Q27b, Q29b/Q29c tương tự): dùng cho tầng gắn cờ mâu thuẫn, không chặn trích xuất.

### 3.3 Ma trận (đã đối chiếu với scan thật — khác docx ở chỗ quan trọng)

**Q14** (trang 3): **18 dòng dữ liệu** × 5 cột (`1. Vợ`, `2. Chồng`, `3. Cả hai như nhau`, `4. Con cái lớn`, `5. Người khác`). Dòng in nghiêng **"Việc nhà" là tiêu đề nhóm, KHÔNG phải dòng dữ liệu** — schema khai báo `"group_header"` để bước trích xuất không đếm nhầm dòng. 8 dòng nhóm sản xuất + 10 dòng nhóm việc nhà. Dòng "Khác (ghi rõ)" có `other_text`.

**Q32** (trang 7): **8 dòng dữ liệu** × 4 cột lựa chọn (`1. Vợ`, `2. Chồng`, `3. Cùng quyết định`, `4. Con cái`) **+ 1 cột "Nội dung" dạng text tự do** đứng trước các cột lựa chọn. Mẫu thật cho thấy cột "Nội dung" bị gạch một đường dài xuyên suốt → quy ước trong schema: `"strike_through_means_empty": true` (gạch chéo cả cột = trống, không phải ambiguous).

```json
{
  "id": "Q14",
  "page": 3,
  "type": "matrix",
  "columns": ["vo", "chong", "ca_hai", "con_cai_lon", "nguoi_khac"],
  "rows": [
    {"code": "lam_dat", "label": "Làm đất"},
    {"code": "trong", "label": "Trồng"},
    {"group_header": "Việc nhà"},
    {"code": "noi_tro", "label": "Công việc nội trợ (nấu nướng, đi chợ, lau dọn nhà cửa…)"},
    {"code": "khac", "label": "Khác (ghi rõ)", "other_text": true}
  ]
}
```

### 3.4 Ngoài 34 câu — phải có trong schema, dễ bỏ sót

| Mã | Nội dung | Ghi chú |
|----|----------|---------|
| `META_DATE` | "Ngày" đầu phiếu, viết tay | trang 1 |
| `META_LOCATION` | "Địa điểm", viết tay tự do | P1 đặc tả: chuẩn hóa tỉnh/huyện/xã — đang chờ quyết định, v1 chỉ phiên âm |
| `CONSENT_1` | Đồng ý tham gia | checkbox |
| `CONSENT_2` | Đồng ý ghi chép/ghi âm | checkbox — scan mẫu: chỉ tick ô 1 |
| `PAGE_NOTES` | Ghi chú viết tay ngoài vùng câu hỏi | scan trang 7 có đoạn viết thêm dưới lời cảm ơn — mỗi trang có trường này, kèm cờ `margin_note` |

## 4. Danh mục 34 câu (kê đủ để đối chiếu khi viết schema)

| Mã | Type | Điểm cần chú ý |
|----|------|----------------|
| Q1 | text | **PII** — họ tên; thực tế có cả SĐT viết kèm |
| Q2 | text (số) | năm sinh — dùng cho rule mâu thuẫn với Q6 |
| Q3 | single_select | Nam/Nữ |
| Q4 | single_select | Kinh / Khác + other_text |
| Q5 | **composite** | 2 checkbox độc lập + dòng text "lớp cao nhất" + checkbox TC/CĐ/ĐH — scan mẫu tick cả "TC/CĐ/ĐH" lẫn ghi "Hết lớp 9" → chính là case cờ mâu thuẫn trong đặc tả |
| Q6 | composite | single 4 option + subfield tuổi kết hôn |
| Q7 | multi_select | 5 options |
| Q8 | single_select | 4 khoảng % |
| Q9 | free_text | |
| Q10 | single_select | **mã in trên phiếu nhảy số: 1,2,3,4,6,7 — không có 5. Giữ nguyên mã in, không đánh lại** |
| Q11 | multi_select | option 4 "Không là hội viên" exclusive |
| Q12, Q13 | single_select | Vợ/Chồng/Cả hai/Khác + other_text |
| Q14 | **matrix 18×5** | + group header "Việc nhà"; xem 3.3 |
| Q15 | free_text | |
| Q16a | single + subfield | Không / Có (ghi công việc) |
| Q16b | free_text | |
| Q17 | **device_grid** | 3 thiết bị × {Chồng, Vợ} + "Không ai có" exclusive; lưu ý cả hai có thể cùng được tick |
| Q18 | multi_select | 8 options + other_text |
| Q19 | multi_select | 3 options + "Không" exclusive |
| Q20 | single_select | + other_text |
| Q21a | single_select | 1–3 lần / >3 / chưa |
| Q21b | multi_select | depends_on Q21a≠"chưa"; + other_text |
| Q21c | free_text | depends_on Q21a="chưa" |
| Q22a | multi_select | 2 option kèm ghi rõ; "Chưa" exclusive |
| Q22b | multi_select | depends_on Q22a="chưa"; + other_text |
| Q23 | single + subfield | Có/Không + "cụ thể là gì, từ ai" |
| Q24–Q26 | single_select | Có/Không |
| Q27a | single_select | 5 options (có "Không biết") |
| Q27b | free_text | depends_on Q27a ≠ vợ đứng tên |
| Q28 | multi_select | 7 options + 2 dòng other_text; "Không gặp khó khăn gì" exclusive |
| Q29a | single_select | Có/Không |
| Q29b | multi_select | depends_on Q29a="Có"; 3 options |
| Q29c | free_text | depends_on Q29a="Không" |
| Q30 | single_select | 5 khâu — scan mẫu tick 3 ô trên câu single → case cờ `multi_mark_on_single_select` có thật |
| Q31 | free_text | |
| Q32 | **matrix 8×4 + cột Nội dung** | xem 3.3 |
| Q33 | multi_select | "Không" exclusive |
| Q34 | free_text | scan mẫu có viết tràn ra ngoài dòng kẻ |

## 5. Các bước thực hiện (tổng ~1 ngày)

1. **Chốt format schema** — viết `SCHEMA-FORMAT.md` từ mục 3 của plan này. *(~1h)*
2. **Kê 34 câu thành JSON draft** từ `pretest_VN.docx`, theo bảng mục 4. *(~3h)*
3. **Đối chiếu từng trang scan** `LCA-LP-001/page-1.jpg`–`7.jpg` với draft: vị trí trang thật của từng câu (docx không phản ánh ngắt trang bản in), số dòng ma trận, các dòng kẻ điền text. Sửa `page` cho đúng bản in. *(~1h)*
4. **Viết `validate_schema.py`**: mã câu duy nhất; mọi câu có type hợp lệ; ma trận đủ dòng×cột (Q14: 18 data rows, Q32: 8); option exclusive không đứng một mình trong câu; mọi trường PII được đánh dấu; đếm tổng số trường xuất ra (để bước export đối chiếu "đủ trường kể cả null"). *(~1h)*
5. **Review nghiệm thu**: một lượt đối chiếu thủ công docx ↔ schema ↔ scan theo checklist mục 4; tick từng dòng. *(~1h)*
6. **Ghi chú cho v2**: mục "cách thêm/sửa câu hỏi" trong SCHEMA-FORMAT.md. *(~30ph)*

## 6. Quyết định đã chốt trong plan này

- **Mã câu = số in trên phiếu** (Q10 giữ gap số 5; Q16a/Q16b tách mã riêng vì là 2 trường dữ liệu).
- **Mã option = slug tiếng Việt không dấu** (`cay_duoc_lieu`) — dễ đọc khi phân tích, label đầy đủ vẫn nằm trong schema.
- **Giá trị xuất ra dùng `code`, không dùng label** — đổi cách diễn đạt label ở v2 không phá dữ liệu cũ.
- Cột "Nội dung" của Q32: giữ trong schema là text tự do, gạch xuyên suốt = trống.

## 7. Rủi ro riêng của task này

| Rủi ro | Giảm thiểu |
|--------|------------|
| Docx không khớp bản in thực tế (ngắt trang, dòng ma trận) | Bước 3 đối chiếu scan là bắt buộc, không bỏ qua dù đã có docx |
| Chỉ có 1 phiếu mẫu — có thể còn biến thể in khác (phiếu photo lại, méo trang) | Ghi rõ schema v1 dựa trên bộ scan `data/raw/lao-cai/lung-phinh/LCA-LP-001/`; khi nhận 10–15 phiếu thật, chạy lại bước đối chiếu trước khi pilot |
| Mã option đặt vội, sau muốn đổi | Chốt quy ước slug ngay bước 1; validator chặn trùng mã |
