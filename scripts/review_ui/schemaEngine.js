// Engine sinh form sửa/review từ schema được project.json khai báo, và validate cấu
// trúc record theo đúng logic scripts/validate_record.py (port 1-1 sang JS) để
// không lệch với validator gốc của pipeline.

export const FLAG_VOCAB = [
  "ambiguous_mark",
  "multi_mark_on_single_select",
  "exclusive_conflict",
  "conflicting_answer",
  "self_consistency_mismatch",
  "margin_note",
];

export const CONFIDENCE_LEVELS = ["cao", "trung_binh", "thap"];

// ---------------------------------------------------------------------------
// DOM helper nhỏ gọn (không dùng framework — tránh phụ thuộc build step vì
// đây là app chạy thẳng bằng http.server tĩnh trên máy người dùng).
// ---------------------------------------------------------------------------

function h(tag, props = {}, children = []) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === false || v === null || v === undefined) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, String(v));
  }
  for (const child of [].concat(children)) {
    if (child === null || child === undefined) continue;
    el.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return el;
}

// ---------------------------------------------------------------------------
// Mặc định rỗng theo loại câu hỏi — khớp cấu trúc validate_record.py mong đợi.
// ---------------------------------------------------------------------------

function isBooleanComponent(comp) {
  return comp.type === "single_select" && Array.isArray(comp.options) && comp.options.length === 1;
}

function defaultEntryFor(question) {
  let entry;
  switch (question.type) {
    case "composite": {
      const components = {};
      for (const c of question.components || []) {
        components[c.id] = { value: isBooleanComponent(c) ? false : null };
      }
      entry = { components };
      break;
    }
    case "matrix": {
      const rows = {};
      for (const r of question.rows || []) {
        if (r.group_header !== undefined) continue;
        rows[r.code] = { value: null };
      }
      entry = { rows };
      break;
    }
    case "device_grid": {
      const rows = {};
      for (const r of question.rows || []) rows[r.code] = { value: [] };
      entry = { rows };
      if (question.extra_option && question.extra_option.code) entry[question.extra_option.code] = false;
      break;
    }
    case "multi_select":
      entry = { value: [] };
      break;
    default:
      entry = { value: null };
  }
  // A question-level subfield is always represented regardless of the value.
  // Option-level subfields remain empty until their option is selected.
  // Both a single definition and an array of definitions are supported.
  if (question.subfield) {
    entry.subfield = {};
    for (const subDef of toArray(question.subfield)) entry.subfield[subDef.id] = { value: null };
  }
  return entry;
}

export function ensureAnswerEntry(record, question) {
  if (!record.answers) record.answers = {};
  const existing = record.answers[question.id];
  if (existing && typeof existing === "object") return existing;
  const fresh = defaultEntryFor(question);
  record.answers[question.id] = fresh;
  return fresh;
}

export function createEmptyRecord(schema, recordId) {
  const record = {
    record_id: recordId,
    schema_version: schema.schema_version,
    authored_by: "review-ui (khởi tạo trống, chưa đọc ảnh)",
    answers: {},
    page_notes: {},
  };
  for (const q of schema.questions) {
    if (q.per_page) continue;
    record.answers[q.id] = defaultEntryFor(q);
  }
  const totalPages = Number(schema.total_pages);
  for (let p = 1; p <= totalPages; p++) record.page_notes[String(p)] = null;
  return record;
}

export function groupQuestionsByPage(schema) {
  const map = new Map();
  for (const q of schema.questions) {
    if (q.per_page) continue;
    if (!map.has(q.page)) map.set(q.page, []);
    map.get(q.page).push(q);
  }
  return map;
}

// ---------------------------------------------------------------------------
// needs_review: quét đệ quy toàn bộ answers (kể cả subfield/derived_subfield/
// components/rows) — dùng cho badge sidebar + nút "câu tiếp theo cần review".
// ---------------------------------------------------------------------------

export function walkNeedsReview(schema, record) {
  const hits = [];
  function visit(entry, qid, page, pathLabel) {
    if (!entry || typeof entry !== "object") return;
    if (entry.needs_review) hits.push({ qid, page, pathLabel });
    for (const key of ["subfield", "derived_subfield", "components", "rows"]) {
      const container = entry[key];
      if (container && typeof container === "object") {
        for (const [ck, cv] of Object.entries(container)) {
          visit(cv, qid, page, `${pathLabel}.${key}.${ck}`);
        }
      }
    }
  }
  const answers = record.answers || {};
  for (const q of schema.questions) {
    if (q.per_page) continue;
    visit(answers[q.id], q.id, q.page, q.id);
  }
  return hits;
}

export function countNeedsReview(schema, record) {
  return walkNeedsReview(schema, record).length;
}

function entryHasAnyNeedsReview(entry) {
  if (!entry || typeof entry !== "object") return false;
  if (entry.needs_review) return true;
  for (const key of ["subfield", "derived_subfield", "components", "rows"]) {
    const container = entry[key];
    if (container && typeof container === "object") {
      for (const v of Object.values(container)) {
        if (entryHasAnyNeedsReview(v)) return true;
      }
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Validate cấu trúc — port 1:1 của scripts/validate_record.py::check_record
// ---------------------------------------------------------------------------

export function validateRecord(schema, record) {
  const errors = [];
  const answers = record.answers;
  if (!answers || typeof answers !== "object") {
    return ["Thiếu hoặc sai kiểu trường 'answers' ở cấp top-level"];
  }
  for (const q of schema.questions) {
    const qid = q.id;
    const qtype = q.type;

    if (q.per_page) {
      const pageNotes = record.page_notes;
      if (!pageNotes || typeof pageNotes !== "object") {
        errors.push(`[${qid}] thiếu trường top-level 'page_notes'`);
        continue;
      }
      const totalPages = Number(schema.total_pages);
      for (let p = 1; p <= totalPages; p++) {
        if (!(String(p) in pageNotes)) errors.push(`[${qid}] thiếu page_notes['${p}']`);
      }
      continue;
    }

    if (!(qid in answers)) {
      errors.push(`[${qid}] câu hỏi bị thiếu hoàn toàn trong 'answers'`);
      continue;
    }
    const entry = answers[qid];
    if (entry === null || typeof entry !== "object") {
      errors.push(`[${qid}] giá trị phải là object dạng {value: ...}, không phải ${entry === null ? "null" : typeof entry}`);
      continue;
    }

    if (qtype === "composite") {
      const comps = entry.components;
      if (!comps || typeof comps !== "object") {
        errors.push(`[${qid}] composite nhưng thiếu 'components'`);
      } else {
        for (const c of q.components || []) {
          if (!(c.id in comps)) errors.push(`[${qid}] thiếu component '${c.id}'`);
        }
      }
    } else if (qtype === "matrix" || qtype === "device_grid") {
      const rowsOut = entry.rows;
      if (!rowsOut || typeof rowsOut !== "object") {
        errors.push(`[${qid}] ${qtype} nhưng thiếu 'rows'`);
      } else {
        const expectedRows =
          qtype === "matrix"
            ? (q.rows || []).filter((r) => r.group_header === undefined).map((r) => r.code)
            : (q.rows || []).map((r) => r.code);
        for (const rc of expectedRows) {
          if (!(rc in rowsOut)) errors.push(`[${qid}] thiếu dòng '${rc}' trong rows`);
        }
        const rcc = q.row_content_column;
        if (rcc && !rcc.skip_extraction) {
          for (const rc of expectedRows) {
            const rowEntry = rowsOut[rc] || {};
            if (typeof rowEntry === "object" && !(rcc.code in rowEntry)) {
              errors.push(`[${qid}] dòng '${rc}' thiếu cột nội dung '${rcc.code}'`);
            }
          }
        }
      }
    } else {
      if (!("value" in entry)) errors.push(`[${qid}] thiếu key 'value'`);
    }

    if (q.subfield) {
      const subDefs = Array.isArray(q.subfield) ? q.subfield : [q.subfield];
      const subOut = entry.subfield;
      for (const subDef of subDefs) {
        if (!subOut || typeof subOut !== "object" || !(subDef.id in subOut)) {
          errors.push(`[${qid}] thiếu subfield '${subDef.id}'`);
        }
      }
    }

    if (q.derived_subfield) {
      const dsDefs = Array.isArray(q.derived_subfield) ? q.derived_subfield : [q.derived_subfield];
      const dsOut = entry.derived_subfield;
      for (const dsDef of dsDefs) {
        if (!dsOut || typeof dsOut !== "object" || !(dsDef.id in dsOut)) {
          errors.push(`[${qid}] thiếu derived_subfield '${dsDef.id}'`);
        }
      }
    }

    if (qtype === "single_select") {
      for (const opt of q.options || []) {
        if (opt.subfield) {
          const subId = opt.subfield.id;
          const val = entry.value;
          const selected = Array.isArray(val) ? val.includes(opt.code) : val === opt.code;
          if (selected) {
            const subOut = entry.subfield;
            if (!subOut || typeof subOut !== "object" || !(subId in subOut)) {
              errors.push(`[${qid}] đã chọn option '${opt.code}' nhưng thiếu subfield '${subId}'`);
            }
          }
        }
      }
    }
  }
  return errors;
}

// ---------------------------------------------------------------------------
// Renderer — 1 thẻ (card) cho mỗi câu hỏi, chỉnh sửa trực tiếp trên `record`
// (mutate in-place — mọi key không được UI này quản lý vẫn được giữ nguyên
// khi lưu, vì ta không dựng lại object từ đầu).
// ---------------------------------------------------------------------------

function addFlag(entry, flag) {
  const flags = new Set(entry.flags || []);
  flags.add(flag);
  entry.flags = Array.from(flags);
}
function removeFlag(entry, flag) {
  if (!entry.flags) return;
  entry.flags = entry.flags.filter((f) => f !== flag);
  if (!entry.flags.length) delete entry.flags;
}
function updateCardHighlight(cardEl, entry) {
  cardEl.classList.toggle("needs-review", entryHasAnyNeedsReview(entry));
}

function renderMetaBlock(entry, { cardEl, onDirty }) {
  const hasContent = !!(entry.needs_review || (entry.flags && entry.flags.length) || entry.confidence || entry.note);
  const wrap = h("div", { class: "meta-block" });
  const toggleBtn = h(
    "button",
    { type: "button", class: "meta-toggle" },
    (hasContent ? "▾" : "▸") + " confidence / flags / note"
  );
  const body = h("div", { class: "meta-body" });
  body.style.display = hasContent ? "grid" : "none";
  toggleBtn.addEventListener("click", () => {
    const showing = body.style.display !== "none";
    body.style.display = showing ? "none" : "grid";
    toggleBtn.textContent = (showing ? "▸" : "▾") + " confidence / flags / note";
  });

  const confWrap = h("div", {}, [h("label", {}, "Độ tin cậy")]);
  const confSelect = h("select", {
    onChange: (e) => {
      if (e.target.value) entry.confidence = e.target.value;
      else delete entry.confidence;
      onDirty();
    },
  });
  confSelect.append(h("option", { value: "" }, "(chưa đặt)"));
  for (const lvl of CONFIDENCE_LEVELS) {
    const opt = h("option", { value: lvl }, lvl);
    if (entry.confidence === lvl) opt.selected = true;
    confSelect.append(opt);
  }
  confWrap.append(confSelect);

  const nrWrap = h("div", {}, [h("label", {}, "Cần review")]);
  const nrLabel = h("label", { class: "chip-toggle" });
  const nrCheckbox = h("input", {
    type: "checkbox",
    onChange: (e) => {
      if (e.target.checked) entry.needs_review = true;
      else delete entry.needs_review;
      updateCardHighlight(cardEl, entry);
      onDirty();
    },
  });
  nrCheckbox.checked = !!entry.needs_review;
  nrLabel.append(nrCheckbox, document.createTextNode(" needs_review"));
  nrWrap.append(nrLabel);

  const flagsWrap = h("div", { class: "full" }, [h("label", {}, "Flags")]);
  const flagList = h("div", { class: "flag-list" });
  for (const flag of FLAG_VOCAB) {
    const chip = h("label", { class: "flag-chip" });
    const cb = h("input", {
      type: "checkbox",
      onChange: (e) => {
        if (e.target.checked) addFlag(entry, flag);
        else removeFlag(entry, flag);
        onDirty();
      },
    });
    cb.checked = Array.isArray(entry.flags) && entry.flags.includes(flag);
    chip.append(cb, document.createTextNode(" " + flag));
    flagList.append(chip);
  }
  flagsWrap.append(flagList);

  const noteWrap = h("div", { class: "full" }, [h("label", {}, "Note")]);
  const noteRow = h("div", { class: "note-row" });
  const noteArea = h("textarea", {
    rows: "2",
    placeholder: "Ghi chú / lý do…",
    onInput: (e) => {
      const v = e.target.value;
      if (v.trim()) entry.note = v;
      else delete entry.note;
      onDirty();
    },
  });
  noteArea.value = entry.note || "";
  const reviewBtn = h(
    "button",
    {
      type: "button",
      class: "btn btn-sm",
      title: "Chèn tiền tố REVIEW: theo đúng quy ước ghi chú đã dùng trong dự án",
      onClick: () => {
        const cur = noteArea.value || "";
        const sep = cur && !cur.endsWith(" ") ? " " : "";
        noteArea.value = cur + sep + "REVIEW: ";
        noteArea.dispatchEvent(new Event("input"));
        noteArea.focus();
        noteArea.selectionStart = noteArea.selectionEnd = noteArea.value.length;
      },
    },
    "+REVIEW:"
  );
  noteRow.append(noteArea, reviewBtn);
  noteWrap.append(noteRow);

  body.append(confWrap, nrWrap, flagsWrap, noteWrap);
  wrap.append(toggleBtn, body);
  return wrap;
}

function getOrInitSubfield(parentEntry, subId) {
  if (!parentEntry.subfield) parentEntry.subfield = {};
  if (!parentEntry.subfield[subId] || typeof parentEntry.subfield[subId] !== "object") {
    parentEntry.subfield[subId] = { value: null };
  }
  return parentEntry.subfield[subId];
}

function renderSubfieldBox(subfieldDef, parentEntry, onDirty, cardEl) {
  const subEntry = getOrInitSubfield(parentEntry, subfieldDef.id);
  const box = h("div", { class: "subfield-box" });
  box.append(h("div", { class: "subfield-title" }, `${subfieldDef.id} — ${subfieldDef.text || ""}`));
  const input = h("textarea", { rows: "1" });
  input.value = subEntry.value ?? "";
  input.addEventListener("input", () => {
    subEntry.value = input.value.trim() ? input.value : null;
    onDirty();
  });
  box.append(input);
  box.append(renderMetaBlock(subEntry, { cardEl, onDirty }));
  return box;
}

function getOrInitDerived(entry, dsId) {
  if (!entry.derived_subfield) entry.derived_subfield = {};
  if (!entry.derived_subfield[dsId] || typeof entry.derived_subfield[dsId] !== "object") {
    entry.derived_subfield[dsId] = { value: null };
  }
  return entry.derived_subfield[dsId];
}

function renderDerivedSubfieldBox(dsDef, entry, onDirty, cardEl) {
  const subEntry = getOrInitDerived(entry, dsDef.id);
  const box = h("div", { class: "subfield-box" });
  box.append(h("div", { class: "subfield-title" }, `${dsDef.id} (rút ra từ nội dung, không in trên phiếu)`));
  const input = h("input", { type: "text" });
  input.value = subEntry.value ?? "";
  input.addEventListener("input", () => {
    subEntry.value = input.value.trim() ? input.value : null;
    onDirty();
  });
  box.append(input);
  box.append(renderMetaBlock(subEntry, { cardEl, onDirty }));
  return box;
}

function renderOtherTextBox(entry, onDirty) {
  const box = h("div", { class: "nested-field" });
  box.append(h("label", {}, "other_text (Khác, ghi rõ)"));
  const input = h("input", { type: "text" });
  input.value = entry.other_text ?? "";
  input.addEventListener("input", () => {
    if (input.value.trim()) entry.other_text = input.value;
    else delete entry.other_text;
    onDirty();
  });
  box.append(input);
  return box;
}

function renderChoiceChips(options, { isChecked, onToggle, nestedFor }) {
  const wrap = h("div", {});
  const list = h("div", { class: "option-list" });
  const nestedBoxes = [];
  for (const opt of options) {
    const chip = h("label", { class: "option-chip" });
    const cb = h("input", { type: "checkbox" });
    cb.checked = isChecked(opt.code);
    chip.append(cb, document.createTextNode(" " + opt.label));
    if (opt.print_no) chip.append(h("span", { class: "option-print-no" }, ` #${opt.print_no}`));
    if (opt.exclusive) chip.append(h("span", { class: "badge badge-neutral" }, "exclusive"));
    list.append(chip);
    const nested = nestedFor ? nestedFor(opt) : null;
    if (nested) {
      nested.style.display = cb.checked ? "" : "none";
      nestedBoxes.push(nested);
    }
    cb.addEventListener("change", () => {
      onToggle(opt.code, cb.checked);
      if (nested) nested.style.display = cb.checked ? "" : "none";
    });
  }
  wrap.append(list);
  for (const box of nestedBoxes) wrap.append(box);
  return wrap;
}

function applySingleSelectCodes(entry, codes) {
  if (codes.length === 0) {
    entry.value = null;
    removeFlag(entry, "multi_mark_on_single_select");
  } else if (codes.length === 1) {
    entry.value = codes[0];
    removeFlag(entry, "multi_mark_on_single_select");
  } else {
    entry.value = codes;
    addFlag(entry, "multi_mark_on_single_select");
  }
}

// Chuẩn hoá 1 giá trị thành mảng: null/undefined -> [], đã là mảng -> bản sao,
// còn lại -> bọc trong mảng 1 phần tử. Dùng chung cho mọi chỗ cần xử lý "1 hoặc nhiều".
function toArray(value) {
  if (value == null) return [];
  return Array.isArray(value) ? value.slice() : [value];
}

function getCodesFromValue(value) {
  return toArray(value);
}

function renderSingleSelectEditor(question, entry, ctx) {
  return renderChoiceChips(question.options || [], {
    isChecked: (code) => getCodesFromValue(entry.value).includes(code),
    onToggle: (code, checked) => {
      const set = new Set(getCodesFromValue(entry.value));
      if (checked) set.add(code);
      else set.delete(code);
      applySingleSelectCodes(entry, Array.from(set));
      ctx.onDirty();
    },
    nestedFor: (opt) => {
      if (opt.subfield) return renderSubfieldBox(opt.subfield, entry, ctx.onDirty, ctx.cardEl);
      if (opt.other_text) return renderOtherTextBox(entry, ctx.onDirty);
      return null;
    },
  });
}

function renderMultiSelectEditor(question, entry, ctx) {
  if (!Array.isArray(entry.value)) entry.value = entry.value == null ? [] : [entry.value];
  return renderChoiceChips(question.options || [], {
    isChecked: (code) => entry.value.includes(code),
    onToggle: (code, checked) => {
      const set = new Set(entry.value);
      if (checked) set.add(code);
      else set.delete(code);
      entry.value = Array.from(set);
      ctx.onDirty();
    },
    nestedFor: (opt) => {
      if (opt.subfield) return renderSubfieldBox(opt.subfield, entry, ctx.onDirty, ctx.cardEl);
      if (opt.other_text) return renderOtherTextBox(entry, ctx.onDirty);
      return null;
    },
  });
}

function renderTextEditor(question, entry, ctx, { multiline }) {
  const originalWasNumber = typeof entry.value === "number";
  const field = h(multiline ? "textarea" : "input", multiline ? { rows: "3" } : { type: "text" });
  field.value = entry.value ?? "";
  field.addEventListener("input", () => {
    const raw = field.value;
    if (!raw.trim()) {
      entry.value = null;
      ctx.onDirty();
      return;
    }
    if (originalWasNumber) {
      const num = Number(raw);
      entry.value = Number.isFinite(num) ? num : raw;
    } else {
      entry.value = raw;
    }
    ctx.onDirty();
  });
  const box = h("div", {});
  box.append(field);
  return box;
}

function renderCompositeEditor(question, entry, ctx) {
  if (!entry.components) entry.components = {};
  const wrap = h("div", {});
  for (const comp of question.components || []) {
    if (!entry.components[comp.id]) {
      entry.components[comp.id] = { value: isBooleanComponent(comp) ? false : null };
    }
    const compEntry = entry.components[comp.id];
    const row = h("div", { class: "nested-field", style: "margin-top:6px" });
    row.append(h("label", {}, `${comp.id} — ${comp.text}`));
    if (isBooleanComponent(comp)) {
      const cb = h("input", { type: "checkbox" });
      cb.checked = !!compEntry.value;
      cb.addEventListener("change", () => {
        compEntry.value = cb.checked;
        ctx.onDirty();
      });
      row.append(cb);
    } else {
      const input = h("input", { type: "text" });
      input.value = compEntry.value ?? "";
      input.addEventListener("input", () => {
        compEntry.value = input.value.trim() ? input.value : null;
        ctx.onDirty();
      });
      row.append(input);
    }
    const metaBtn = h(
      "button",
      { type: "button", class: "btn btn-sm btn-ghost", title: "confidence/flags/note cho trường này", style: "margin-left:6px" },
      compEntry.needs_review ? "⚑" : "…"
    );
    row.append(metaBtn);
    wrap.append(row);

    const metaBox = renderMetaBlock(compEntry, { cardEl: ctx.cardEl, onDirty: ctx.onDirty });
    metaBox.style.display = "none";
    wrap.append(metaBox);
    metaBtn.addEventListener("click", () => {
      metaBox.style.display = metaBox.style.display === "none" ? "" : "none";
    });
  }
  return wrap;
}

function renderMatrixEditor(question, entry, ctx) {
  if (!entry.rows) entry.rows = {};
  const nCols = (question.columns || []).length;
  const table = h("table", { class: "matrix" });
  const headRow = h("tr", {}, [h("th", { style: "text-align:left;min-width:160px" }, "Dòng")]);
  for (const col of question.columns) headRow.append(h("th", {}, col.label));
  headRow.append(h("th", { style: "width:36px" }, ""));
  table.append(h("thead", {}, [headRow]));

  const tbody = h("tbody", {});
  for (const row of question.rows || []) {
    if (row.group_header !== undefined) {
      tbody.append(h("tr", { class: "group-header" }, [h("td", { colspan: String(nCols + 2) }, row.group_header)]));
      continue;
    }
    if (!entry.rows[row.code] || typeof entry.rows[row.code] !== "object") {
      entry.rows[row.code] = { value: null };
    }
    const rowEntry = entry.rows[row.code];
    const tr = h("tr", {}, [h("td", { class: "row-label" }, row.label)]);
    for (const col of question.columns) {
      const cb = h("input", { type: "checkbox" });
      cb.checked = getCodesFromValue(rowEntry.value).includes(col.code);
      cb.addEventListener("change", () => {
        const set = new Set(getCodesFromValue(rowEntry.value));
        if (cb.checked) set.add(col.code);
        else set.delete(col.code);
        applySingleSelectCodes(rowEntry, Array.from(set));
        ctx.onDirty();
        metaBtn.textContent = rowEntry.needs_review ? "⚑" : "…";
      });
      tr.append(h("td", {}, [cb]));
    }
    const metaBtn = h(
      "button",
      { type: "button", class: "btn btn-sm btn-ghost", title: "confidence/flags/note cho dòng này" },
      rowEntry.needs_review ? "⚑" : "…"
    );
    tr.append(h("td", {}, [metaBtn]));
    tbody.append(tr);

    const metaTd = h("td", { colspan: String(nCols + 2) });
    if (row.other_text) metaTd.append(renderOtherTextBox(rowEntry, ctx.onDirty));
    metaTd.append(renderMetaBlock(rowEntry, { cardEl: ctx.cardEl, onDirty: ctx.onDirty }));
    const metaTr = h("tr", {}, [metaTd]);
    metaTr.style.display = "none";
    tbody.append(metaTr);
    metaBtn.addEventListener("click", () => {
      metaTr.style.display = metaTr.style.display === "none" ? "" : "none";
    });
  }
  table.append(tbody);

  const wrap = h("div", {});
  if (question.row_content_column && question.row_content_column.skip_extraction) {
    wrap.append(
      h(
        "div",
        { class: "muted small", style: "margin-bottom:6px" },
        `Cột "${question.row_content_column.label}" được schema đánh dấu skip_extraction — dữ liệu cũ trong JSON (nếu có) vẫn được giữ nguyên khi lưu.`
      )
    );
  }
  wrap.append(table);
  return wrap;
}

function renderDeviceGridEditor(question, entry, ctx) {
  if (!entry.rows) entry.rows = {};
  const extraCode = question.extra_option && question.extra_option.code;
  if (extraCode && typeof entry[extraCode] !== "boolean") entry[extraCode] = false;
  const nCols = (question.columns || []).length;
  const headRow = h("tr", {}, [h("th", { style: "text-align:left;min-width:160px" }, "Thiết bị")]);
  for (const col of question.columns) headRow.append(h("th", {}, col.label));
  headRow.append(h("th", { style: "width:36px" }, ""));
  const table = h("table", { class: "matrix" }, [h("thead", {}, [headRow])]);
  const tbody = h("tbody", {});

  for (const row of question.rows || []) {
    if (!entry.rows[row.code] || !Array.isArray(entry.rows[row.code].value)) {
      entry.rows[row.code] = { value: [] };
    }
    const rowEntry = entry.rows[row.code];
    const tr = h("tr", {}, [h("td", { class: "row-label" }, row.label)]);
    for (const col of question.columns) {
      const cb = h("input", { type: "checkbox" });
      cb.checked = rowEntry.value.includes(col.code);
      cb.addEventListener("change", () => {
        const set = new Set(rowEntry.value);
        if (cb.checked) set.add(col.code);
        else set.delete(col.code);
        rowEntry.value = Array.from(set);
        ctx.onDirty();
      });
      tr.append(h("td", {}, [cb]));
    }
    const metaBtn = h("button", { type: "button", class: "btn btn-sm btn-ghost" }, rowEntry.needs_review ? "⚑" : "…");
    tr.append(h("td", {}, [metaBtn]));
    tbody.append(tr);

    const metaTd = h("td", { colspan: String(nCols + 2) }, [renderMetaBlock(rowEntry, { cardEl: ctx.cardEl, onDirty: ctx.onDirty })]);
    const metaTr = h("tr", {}, [metaTd]);
    metaTr.style.display = "none";
    tbody.append(metaTr);
    metaBtn.addEventListener("click", () => {
      metaTr.style.display = metaTr.style.display === "none" ? "" : "none";
    });
  }
  table.append(tbody);

  const wrap = h("div", {}, [table]);
  if (question.extra_option) {
    const extra = h("label", { class: "chip-toggle", style: "margin-top:8px;display:inline-flex" });
    const cb = h("input", { type: "checkbox" });
    cb.checked = !!entry[extraCode];
    cb.addEventListener("change", () => {
      entry[extraCode] = cb.checked;
      ctx.onDirty();
    });
    extra.append(cb, document.createTextNode(" " + question.extra_option.label));
    wrap.append(extra);
  }
  return wrap;
}

export function renderQuestionCard(question, record, { onDirty }) {
  const entry = ensureAnswerEntry(record, question);
  const card = h("div", { class: "q-card", "data-qid": question.id });

  const head = h("div", { class: "q-head" }, [
    h("span", { class: "q-id" }, question.id),
    h("span", { class: "q-text" }, question.text || ""),
  ]);
  const badges = h("div", { class: "q-badges" });
  if (question.pii) badges.append(h("span", { class: "badge badge-danger" }, "PII"));
  if (question.depends_on) {
    badges.append(h("span", { class: "badge badge-neutral", title: JSON.stringify(question.depends_on) }, "depends_on"));
  }
  head.append(badges);
  card.append(head);

  if (question.note) {
    card.append(h("div", { class: "muted small", style: "margin-bottom:6px" }, question.note));
  }

  const ctx = {
    cardEl: card,
    onDirty: () => {
      updateCardHighlight(card, entry);
      onDirty();
    },
  };

  let editor;
  switch (question.type) {
    case "single_select":
      editor = renderSingleSelectEditor(question, entry, ctx);
      break;
    case "multi_select":
      editor = renderMultiSelectEditor(question, entry, ctx);
      break;
    case "composite":
      editor = renderCompositeEditor(question, entry, ctx);
      break;
    case "matrix":
      editor = renderMatrixEditor(question, entry, ctx);
      break;
    case "device_grid":
      editor = renderDeviceGridEditor(question, entry, ctx);
      break;
    case "free_text":
      editor = renderTextEditor(question, entry, ctx, { multiline: true });
      break;
    default:
      editor = renderTextEditor(question, entry, ctx, { multiline: false });
  }
  card.append(editor);

  if (question.subfield) {
    for (const subDef of toArray(question.subfield)) card.append(renderSubfieldBox(subDef, entry, ctx.onDirty, card));
  }
  if (question.derived_subfield) {
    // derived_subfield có thể là một object hoặc mảng nhiều definitions.
    const dsDefs = toArray(question.derived_subfield);
    for (const dsDef of dsDefs) card.append(renderDerivedSubfieldBox(dsDef, entry, ctx.onDirty, card));
  }

  card.append(renderMetaBlock(entry, { cardEl: card, onDirty: ctx.onDirty }));
  updateCardHighlight(card, entry);
  return card;
}

export function renderPageNotesBox(record, pageNumber, onDirty) {
  if (!record.page_notes) record.page_notes = {};
  const key = String(pageNumber);
  const textarea = h("textarea", { rows: "2", placeholder: "(không có ghi chú lề)" });
  textarea.value = record.page_notes[key] ?? "";
  textarea.addEventListener("input", () => {
    record.page_notes[key] = textarea.value.trim() ? textarea.value : null;
    onDirty();
  });
  return h("div", {}, [
    h("div", { class: "muted small", style: "margin-bottom:4px" }, `page_notes["${key}"] — ghi chú viết tay ngoài vùng câu hỏi`),
    textarea,
  ]);
}
