# Implement Plan — Thống kê tổng hợp & báo cáo gửi khách (DOCX + XLSX)

**Ngày viết:** 2026-07-24, brainstorm ban đầu theo 7 tầng kỹ thuật chung.
**Cập nhật:** 2026-07-26 — **thay khung tổ chức**, không còn theo "7 tầng thống kê" mà theo đúng
4 trụ cột trong tên dự án: **thị trường, chuỗi giá trị, rào cản sản xuất, môi trường chính sách**.
Lý do đổi: bản 7 tầng cũ liệt kê phép tính theo loại kỹ thuật (tần suất → cross-tab → tương
quan → effect size → so sánh nhóm → alpha → factor/cluster), không nối các phép tính lại
thành 1 câu chuyện phục vụ đúng câu hỏi nghiên cứu của dự án. Bản này giữ lại các kỹ thuật
đã có (tần suất, cross-tab, Cronbach's alpha) nhưng **tổ chức lại theo mục tiêu**, bỏ phần
không phục vụ mục tiêu nào cụ thể (ma trận tương quan đầy đủ 99×99, effect size/so sánh
nhóm phi tham số áp cho toàn bộ biến, factor/cluster analysis áp cho toàn bộ Q14/Q32).

Xem thêm bối cảnh nghiên cứu đứng sau quyết định này ở `memory/project_dubieu_value_chain_scope.md`
(ngoài repo, ghi nhớ của trợ lý) — tóm tắt: dự án dùng khung Value Chain Analysis (Kaplinsky
et al. 2000), WEAI/pro-WEAI (IFPRI/CGIAR) và GALS (Oxfam) cho phần giới, và SWOT/barrier-index
cho phần rào cản-chính sách; ví dụ thực tế gần nhất là Nguyen et al. 2025 (PLOS ONE) — VCA cho
Giảo cổ lam ở Cao Bằng Geopark.

**Trạng thái:** 85/85 phiếu đã qua Review UI (xem `docs/review-summary-report.md`), `output/combined.csv`
đã tồn tại và được rebuild nhiều lần theo các quyết định 25–26/07 (gộp dân tộc Dao, tách Q5,
mẫu số 85, bỏ so sánh vùng...). Plan này build trên nền `combined.csv` hiện tại, không cần
review lại.

## 0. Phạm vi trường dùng để thống kê (không đổi so với bản gốc)

Dùng toàn bộ **trường có cấu trúc** trong `schema/questionnaire_v1.json` (108 trường xuất
ra / 46 mục câu hỏi), loại các câu tự luận thuần (`Q15, Q16b, Q21c, Q27b, Q29c, Q31, Q34,
PAGE_NOTES`). Giữ `Q9` qua 2 trường derived (`Q9_derived_start_year`, dùng gián tiếp qua
`Q9_derived_years_exp`). `Q1` (họ tên/SĐT) không vào bất kỳ bảng thống kê nào. Sau khi nổ
multi-select/ma trận thành cột nhị phân, tổng ~99 cột. Chi tiết đầy đủ: xem
`scripts/lib/flatten.py` (nguồn thật, không liệt kê lại tay ở đây để tránh lệch).

## 1. Bốn trụ cột — thay cho 7 tầng cũ

### A. Thị trường & mức độ gắn bó với dược liệu

Trả lời: hộ phụ thuộc thị trường dược liệu đến đâu, và gắn bó lâu hơn có đi cùng phụ thuộc
thị trường nhiều hơn không.

- Tần suất Q7 (nguồn thu nhập chính, multi-select), Q8 (tỷ lệ thu nhập từ dược liệu, 4 bậc).
- Bảng mô tả Q9_derived_years_exp (n, mean, median, mode, SD, min, max, Q1/Q3) — vẫn giữ
  nguyên cách tính cũ (công thức Excel gốc AVERAGE/MEDIAN/MODE/STDEV/QUARTILE).
- **Cross-tab (mới, thay cho cross-tab nhân khẩu cũ):** `experience_years_bracket` (<1 năm /
  ≥1 năm) × Q8 (4 bậc thu nhập) — mẫu số = cỡ nhóm kinh nghiệm (không phải 85 cố định, theo
  đúng quy ước cross-tab cũ ở `crosstab.py`, khác quy ước Tầng-1-cũ vì đây là bảng so sánh
  giữa 2 nhóm, không phải tần suất 1 biến).

### B. Vị trí trong chuỗi giá trị dược liệu

Trả lời: phụ nữ tham gia nhiều nhất ở khâu nào, khâu đó có "giá" hơn không, và "ai làm" có
khớp với "ai quyết" hay không (đúng chỗ, đúng khâu có giá trị kinh tế).

- Tần suất Q30 (khâu tham gia: sản xuất/thu hái/chế biến/thương mại/tiêu thụ — combo-aware,
  1 phiếu có thể tham gia nhiều khâu).
- **Cross-tab Q30 (từng khâu, combo-aware) × Q8** — trong số phiếu có tham gia khâu X, tỷ lệ
  thu nhập từ dược liệu phân bố ra sao. Đây là bản đồ tham gia mức hộ, KHÔNG phải value-added
  tài chính đầy đủ kiểu VCA (không có giá/chi phí — xem giới hạn ở §4).
- **Bảng "ai làm" so "ai quyết"** — 3 cặp đã thảo luận, so % "vợ"/"cả hai" (Q14) cạnh %
  "vợ"/"cùng quyết định" (Q32) cho cùng 1 chủ đề:
  - Q14 `lien_he_tieu_thu` (liên hệ tiêu thụ sản phẩm) ↔ Q32 `chon_ban` (chọn bán cho ai)
  - Q14 `quan_ly_chi_tieu` (quản lý chi tiêu) ↔ Q32 `su_dung_thu_nhap` (sử dụng thu nhập dược liệu)
  - Q13 (ai tham gia chính trồng/bán) ↔ Q32 `chon_cay_trong` (chọn loại cây trồng)

### C. Rào cản sản xuất

Trả lời: rào cản nào phổ biến nhất, và rào cản có giữ chân phụ nữ ở khâu thấp giá (sản
xuất/thu hái) thay vì lên khâu cao giá (thương mại/tiêu thụ) không.

- Tần suất Q28 (7 lựa chọn rào cản, multi-select) + Q22b (lý do chưa vay vốn, multi-select).
- Cross-tab Q28 × tỉnh (Lào Cai/Lai Châu) — mẫu số = cỡ tỉnh, theo đúng quy ước cross-tab.
- **Cross-tab Q28 × nhóm khâu tham gia (mới)** — chia phiếu thành 2 nhóm theo Q30: "có tham
  gia khâu cao giá" (thương mại và/hoặc tiêu thụ) và "chỉ khâu thấp giá" (chỉ sản xuất/thu
  hái/chế biến, không có thương mại/tiêu thụ) — so tỷ lệ từng rào cản giữa 2 nhóm. Đây là
  liên kết trực tiếp "rào cản nào cản trở việc lên khâu có giá hơn".

### D. Môi trường chính sách/thể chế

Trả lời: kênh hỗ trợ nào đang có tác dụng, kênh nào chưa tiếp cận được và vì sao — tổng hợp
thành SWOT thay vì dừng ở tần suất rời rạc.

- Tần suất Q22a (vay vốn theo nguồn, gồm "ngân hàng chính sách"), Q23 (hỗ trợ vật chất),
  Q21a/Q21b (tần suất + nội dung tập huấn), Q11 (hội đoàn thể).
- **Bảng SWOT tổng hợp (mới)** — sinh từ đúng các tần suất trên, không phải đánh giá chủ
  quan riêng: Điểm mạnh/Cơ hội = kênh có tỷ lệ tiếp cận cao nhất; Điểm yếu/Thách thức = tỷ
  lệ "chưa" cao + lý do cụ thể (Q22b). Văn bản SWOT viết tĩnh (không phải công thức Excel
  sống), nhưng mọi số dẫn trong đó đều trỏ được về đúng khối tần suất nguồn.

### E. Chỉ số vai trò trong chuỗi giá trị (Cronbach's alpha — giữ lại từ Tầng 6 cũ, đổi phạm vi)

- **Q32 (8 dòng ra quyết định)** — giữ nguyên như bản cũ, toàn bộ 8 dòng đều là quyết định
  liên quan trực tiếp chuỗi giá trị (chọn cây trồng, mua vật tư, chọn bán, vay vốn, giá bán,
  sử dụng thu nhập, sử dụng đất) — không cần tách.
- **Q14 — CHỈ lấy tập con "việc sản xuất/thương mại dược liệu"** (`lam_dat, trong,
  cham_soc_cay, thuoc_bvtv, thu_hoach, so_che, lien_he_tieu_thu, quan_ly_chi_tieu` — 8 dòng),
  loại các dòng việc nhà thuần túy (nội trợ, giặt giũ, đưa đón con, đám cưới giỗ, chăm sóc
  con, gia súc, dạy dỗ con, bảo dưỡng xe) — vì việc nhà không đại diện cho vai trò trong
  chuỗi giá trị dược liệu, gộp chung sẽ làm loãng chỉ số. Đặt tên "chỉ số vai trò sản xuất/
  thương mại dược liệu" thay vì "chỉ số phân công lao động" chung chung.
- Tính Cronbach's alpha cho cả 2 tập, mốc quyết định vẫn ≥0.7 (Nunnally). Composite (%) từng
  phiếu vẫn là công thức Excel sống (như bản cũ), chỉ đổi phạm vi dòng Q14.

## 2. Bỏ khỏi bản mới (so với 7 tầng cũ)

- **Ma trận tương quan đầy đủ 99×99** (Tầng 3 cũ) — không phục vụ câu hỏi nào cụ thể ở §1,
  chỉ còn lại nếu khách yêu cầu lại "xem tất cả các cặp" — code cũ (`association.py`,
  `association_sheet.py`) vẫn giữ nguyên trong repo, không xoá, chỉ không gọi trong script
  build mới.
- **Effect size áp toàn bộ + so sánh nhóm phi tham số áp toàn bộ** (Tầng 4-5 cũ) — thay bằng
  các cross-tab có mục tiêu cụ thể ở §1.B/§1.C. Code cũ (`effect_size.py`, `nonparametric.py`)
  vẫn giữ nguyên, không gọi trong script build mới.
- **Factor analysis / cluster analysis áp cho toàn bộ Q14 (18 dòng)/Q32 (8 dòng)** (Tầng 7
  cũ) — bỏ khỏi bản chính thức gửi khách vì n=85 mỏng cho 18 item và không phục vụ câu hỏi
  giá trị/rào cản/chính sách cụ thể. Code cũ (`factor_analysis.py`, `cluster_analysis.py`)
  vẫn giữ nguyên, có thể bật lại làm phụ lục nếu khách hỏi lại.

## 3. Giữ nguyên từ bản gốc

- Tầng tần suất trải phẳng cho TOÀN BỘ ~99 biến (giờ là sheet nền "Thống kê trải phẳng",
  không phải sản phẩm chính) — vẫn bắt buộc, vì mọi con số ở 4 trụ cột A-D đều dựng trên đó
  và khách cần tra cứu ngược được.
- PII: sheet "Dữ liệu đã số hóa" dùng lớp `output/full` (có PII), mọi phần thống kê dùng lớp
  `output/stats`/`combined.csv` (ẩn danh).
- Định dạng file: DOCX (báo cáo chính, đọc/sửa được) + XLSX (dữ liệu đầy đủ + phụ lục thống
  kê), không PDF/HTML/CSV thô — khách non-tech.
- Văn phong (bản gốc §9, không đổi): ngôn ngữ đời thường gắn thực tế trồng trọt/gia đình,
  không thuật ngữ thống kê trong narrative, không quy kết/đánh giá thiếu sót, "liên hệ quan
  sát" chứ không phải quan hệ nhân quả, luôn nhắc n=85 là mẫu nhỏ mang tính gợi ý.

## 4. Giới hạn cần ghi rõ trong báo cáo

Phiếu `pretest_VN.docx` (bảng hỏi bán cấu trúc với phụ nữ) chỉ là 1 module hộ/phụ nữ trong dự
án lớn hơn — không thu thập giá bán, chi phí, hay dữ liệu phía thương lái/chế biến/thu mua.
Vì vậy phần "chuỗi giá trị" ở đây dừng ở mức **bản đồ tham gia + rào cản + vai trò quyết
định**, chưa phải phân tích tài chính chuỗi giá trị đầy đủ kiểu Kaplinsky (value added/gross
margin từng khâu). Nếu khách cần lớp tài chính đó, cần thêm phiếu khảo sát phía thu mua/chế
biến, tương tự thiết kế nghiên cứu Giảo cổ lam ở Cao Bằng Geopark (Nguyen et al. 2025, PLOS
ONE) — 106 tác nhân đa vai trò, phỏng vấn 7 bước, tính margin/value-added mỗi kênh.

## 5. Định dạng file gửi khách — sheet layout mới (XLSX)

1. **A. Thị trường & mức độ gắn bó** — tần suất Q7/Q8 + mô tả Q9 + cross kinh nghiệm×Q8.
2. **B. Vị trí chuỗi giá trị** — tần suất Q30 + cross Q30×Q8 + bảng "ai làm vs ai quyết".
3. **C. Rào cản sản xuất** — tần suất Q28/Q22b + cross theo tỉnh + cross theo khâu cao/thấp giá.
4. **D. Môi trường chính sách** — tần suất Q22a/Q23/Q21a/Q21b/Q11 + bảng SWOT tổng hợp.
5. **Chỉ số vai trò chuỗi giá trị** — Cronbach's alpha Q14 (tập con 8 dòng) + Q32 (8 dòng),
   composite (%) từng phiếu, công thức sống.
6. **Biểu đồ** — 1 chart Excel gốc cho mỗi bảng chính ở sheet 1–4.
7. **Thống kê trải phẳng** — tần suất toàn bộ ~99 biến, lớp nền/tra cứu (Tầng 1 cũ, giữ nguyên).
8. **Dữ liệu đã số hóa** — bản đầy đủ có PII, không đổi.
9. **Dữ liệu (ẩn danh)** — sheet ẩn, nguồn công thức sống cho sheet 1–7 (không đổi).

DOCX kể chuyện theo đúng thứ tự A→B→C→D→E ở trên, đứng trên góc nhìn chuyên gia nghiên cứu
dự án (không phải người đọc SPSS thô), mỗi phần nêu phát hiện chính bằng lời trước, số liệu
minh hoạ sau, kết bằng 1 câu gợi ý chính sách/can thiệp nếu có.

## 6. Việc chưa chốt — hỏi lại khách khi cần

- Ngưỡng "nhóm barrier cao/thấp giá" ở §1.C dùng thương mại+tiêu thụ làm mốc "cao giá" — có
  thể cần khách xác nhận lại đúng thứ tự giá trị các khâu (chế biến có nên tính là "cao giá"
  không, hiện đang xếp vào nhóm thấp cùng sản xuất/thu hái).
- Có cần thêm phiếu khảo sát phía thu mua/chế biến để tính value-added tài chính đầy đủ theo
  §4 hay không — optional, chưa có yêu cầu rõ từ khách.
- Mốc alpha cụ thể (gợi ý ≥0.7, chuẩn Nunnally, chưa chốt với khách) không đổi so với bản gốc.

## 8. Bổ sung 26/07 (tối) — gắn tuổi/dân tộc/hôn nhân/học thức/thiết bị/xe/lãnh đạo vào 4 trụ cột

Phản hồi khách (tối 26/07): các biến nhân khẩu-xã hội (tuổi, dân tộc, tỷ lệ/tuổi kết hôn,
năm bắt đầu trồng cây, học thức, thiết bị, công việc, xe cộ, lãnh đạo) **không được bỏ khỏi
thống kê** — đã có đủ ở sheet "Thống kê trải phẳng" (§3 trên, không đổi) từ bản 26/07 sáng,
nhưng chỉ nằm đó, chưa gắn vào câu chuyện 4 trụ cột. Mục này bổ sung 6 phân tích nối các
biến đó vào đúng câu hỏi nghiên cứu của A-E, theo khung WEAI/GALS đã dùng cho dự án (xem
`memory/project_dubieu_value_chain_scope.md`) — domain "leadership/collective agency"
(Q33), "mobility/instrumental agency" (Q25), "resources/asset ownership" (Q17) khớp trực
tiếp các domain trao quyền chuẩn của WEAI, còn học thức/tuổi kết hôn dùng như biến kiểm
soát/nhóm so sánh (thông lệ phổ biến trong nghiên cứu trao quyền phụ nữ theo chuỗi giá trị).

Làm rõ 2 điểm nhầm ở vòng thảo luận trước:

- **"Xe cộ" = Q24 (biết đi xe máy) + Q25 (có xe máy riêng tự đi lại)**, không phải
  `Q14_bao_duong_xe` (mục phân công ai bảo dưỡng xe trong việc nhà — vẫn giữ nguyên ở tần
  suất trải phẳng + sheet Q14 đầy đủ, KHÔNG đưa thêm vào đây vì đó là phân công lao động,
  không phải năng lực đi lại độc lập).
- **Dân tộc (Q4) KHÔNG được gộp** (nhắc lại đúng quyết định đã chốt 22/07,
  `docs/client-feedback-2026-07-22-extraction-rules.md` §2.4) — mọi cross-tab dân tộc dưới
  đây dùng ĐÚNG 5 tên quan sát được (Kinh, Dao, Mông, Nùng, Tày), không tự gộp
  "Kinh/dân tộc thiểu số" hay bất kỳ nhóm gộp nào khác. Nhóm rất nhỏ (Tày n=4, Nùng n=2)
  vẫn hiện riêng, kèm caveat mẫu nhỏ ngay trong sheet.

### 6 phân tích mới

1. **Học thức (Q5, `education_grade_bracket`) × Khâu tham gia chuỗi giá trị (Q30)** —
   Pillar B. Học vấn cao hơn có đi cùng tham gia khâu thương mại/tiêu thụ (gần khách hàng
   hơn, giá trị gia tăng thường cao hơn) nhiều hơn không.
2. **Có vai trò lãnh đạo nhóm SX/HTX/quản lý rừng (Q33) × Q30** — Pillar B. Domain
   "leadership" của WEAI — phụ nữ có vai trò lãnh đạo có tham gia khâu cao giá nhiều hơn
   không. Mẫu nhóm "có lãnh đạo" rất nhỏ (n≈5/85) — số liệu chỉ gợi ý.
3. **Có xe máy riêng tự đi lại (Q25) × Q30** — Pillar B. Domain "mobility/instrumental
   agency" — nhiều khâu (đặc biệt thương mại/tiêu thụ) cần di chuyển đến chợ/điểm thu mua.
4. **Sở hữu thiết bị số (Q17, vợ) so với DÙNG thiết bị đó cho mục đích kinh tế (Q18/Q19)**
   — Pillar B. Không chia nhóm sở hữu có/không (tỷ lệ sở hữu quá lệch, 81/85 có — nhóm
   "không" chỉ 4 phiếu) — thay vào đó so trực tiếp % sở hữu với % dùng thực tế cho buôn
   bán/quảng bá, khoảng cách 2 số này là điều đáng chú ý (sở hữu ~95% nhưng dùng để giao
   dịch/quảng bá/bán online chỉ 18-53%).
5. **Rào cản (Q28) và kênh vay vốn (Q22a) × Dân tộc (Q4, không gộp)** — Pillar C/D. Dân
   tộc nào gặp rào cản gì/tiếp cận kênh hỗ trợ nào nhiều/ít hơn.
6. **Chỉ số vai trò/quyết định (Pillar E composite, Q14 và Q32) × Nhóm tuổi kết hôn
   (`marriage_age_bracket`)** — kết hôn sớm (tảo hôn, <18 tuổi) có đi cùng chỉ số thấp hơn
   không. Kết quả thực tế (85 phiếu): KHÔNG theo chiều giả thuyết thường gặp — nhóm tảo hôn
   có chỉ số trung bình CAO hơn nhóm kết hôn từ 18 tuổi ở cả Q14 (81.3 so với 73.2) và Q32
   (73.5 so với 63.3) — nêu đúng như quan sát được, không ép theo hướng giả thuyết ban đầu.

Không đổi: mẫu số/quy ước cross-tab (cỡ nhóm, không phải 85 cố định — §0/§1 trên), văn
phong (§3), và toàn bộ 4 trụ cột + chỉ số E gốc — 6 mục trên là bổ sung nối thêm, không
thay thế nội dung đã có.

## 8b. Bổ sung 26/07 (tối, vòng 2) — gộp multi-select/ma trận thành 1 bảng/câu

Phản hồi khách: sheet "Thống kê trải phẳng" (và các khối Q7/Q28/Q22a/Q22b/Q21b/Q11 ở
Pillar A/C/D) trước đó tách MỖI lựa chọn của 1 câu multi-select thành 1 khối riêng, mỗi khối
tự so "Có chọn (n/%)" với "Không chọn (n/%)" — đúng như khách chỉ ra, "không nhà phân tích
thống kê nào trình bày multi-select kiểu đó". Sửa: mọi cột đã nổ từ CÙNG 1 câu multi-select
(`MULTI_SELECT_FIELDS`: Q7, Q11, Q18, Q19, Q21b, Q22a, Q22b, Q28, Q29b, Q33), ma trận
(`MATRIX_ROW_FIELDS`: Q14, Q32), hay device-grid (`DEVICE_GRID_FIELDS`: Q17) trong
`schema/questionnaire_v1.json`/`scripts/lib/flatten.py` giờ gộp thành ĐÚNG 1 bảng/câu — mỗi
lựa chọn (hoặc mỗi việc/vấn đề × lựa chọn, với Q14/Q32) là 1 dòng, % các lựa chọn nằm cạnh
nhau để so sánh trực tiếp (có thể cộng vượt 100% — bản chất multi-select, ghi rõ trong note
mỗi bảng). Áp dụng nhất quán ở cả sheet trải phẳng lẫn Pillar A ( Q7)/C (Q28, Q22b)/D (Q22a,
Q21b, Q11) — xem `_write_grouped_binary_block`/`_write_matrix_freq_block`/
`_write_device_grid_freq_block` (`scripts/lib/report/xlsx_writer.py`). Cross-tab theo
tỉnh/nhóm khâu/dân tộc ở Pillar C/D (mỗi rào cản × 1 biến nhóm) KHÔNG đổi — đó là so sánh
giữa các NHÓM cho từng lựa chọn, khác hẳn vấn đề "có chọn/không chọn" đã sửa ở trên.

## 9. Liên quan

- `memory/project_dubieu_value_chain_scope.md` — bối cảnh nghiên cứu (VCA, WEAI, GALS, SWOT)
  đứng sau quyết định đổi khung ở bản này.
- [Review summary report](review-summary-report.md) — trạng thái review (85/85 xong).
- [Schema format](../schema/SCHEMA-FORMAT.md) — danh sách đầy đủ 108 trường.
- [README](../README.md) — mục "5. Statistical engine" và "6. Phân tích và báo cáo".
