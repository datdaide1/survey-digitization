// Parser CSV tối giản kiểu RFC 4180 (đủ dùng cho docs/manual-extraction-progress.csv):
// hỗ trợ field có dấu phẩy/ngoặc kép/xuống dòng bên trong khi được bọc bởi "...".
// Chỉ đọc (read-only) — UI không ghi lại progress.csv để tránh làm hỏng
// định dạng file theo dõi tiến độ chính của dự án.

export function parseCSV(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  let i = 0;
  const n = text.length;

  function pushField() {
    row.push(field);
    field = "";
  }
  function pushRow() {
    pushField();
    rows.push(row);
    row = [];
  }

  while (i < n) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      field += c;
      i += 1;
      continue;
    }
    if (c === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (c === ",") {
      pushField();
      i += 1;
      continue;
    }
    if (c === "\r") {
      i += 1;
      continue;
    }
    if (c === "\n") {
      pushRow();
      i += 1;
      continue;
    }
    field += c;
    i += 1;
  }
  // last field/row (file có thể không kết thúc bằng \n)
  if (field.length > 0 || row.length > 0) {
    pushRow();
  }

  const filtered = rows.filter((r) => !(r.length === 1 && r[0] === ""));
  if (filtered.length === 0) return [];
  const header = filtered[0];
  return filtered.slice(1).map((r) => {
    const obj = {};
    header.forEach((h, idx) => {
      obj[h] = r[idx] ?? "";
    });
    return obj;
  });
}
