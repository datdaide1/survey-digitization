import * as fsAccess from "./fsAccess.js";
import * as idb from "./idb.js";
import * as schemaEngine from "./schemaEngine.js";
import { parseCSV } from "./csv.js";

// ---------------------------------------------------------------------------
// DOM helper (bản riêng, tối giản — main.js không cần toàn bộ API của
// schemaEngine.js nên không import dùng chung để 2 module độc lập nhau).
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
// State
// ---------------------------------------------------------------------------

const state = {
  root: null,
  project: null,
  schema: null,
  questionsByPage: null,
  progressRows: [],
  recordMetaCache: new Map(),
  currentRecordId: null,
  currentRecord: null,
  isNewRecord: false,
  currentPage: 1,
  dirty: false,
  autosaveTimer: null,
  imageCache: new Map(),
  assembly: null,
  validateBannerEl: null,
};

function toast(message, kind = "info") {
  const root = document.getElementById("toast-root");
  const el = h("div", { class: "toast" + (kind !== "info" ? " " + kind : "") }, message);
  root.append(el);
  setTimeout(() => el.remove(), 4500);
}

function showGateError(message) {
  const el = document.getElementById("gate-error");
  el.hidden = false;
  el.textContent = message;
}

// ---------------------------------------------------------------------------
// Boot / chọn thư mục gốc
// ---------------------------------------------------------------------------

async function boot() {
  const pickBtn = document.getElementById("btn-pick-root");
  if (!fsAccess.isSupported()) {
    showGateError("Trình duyệt này chưa hỗ trợ File System Access API — mở bằng Chrome hoặc Edge bản mới nhất.");
    pickBtn.disabled = true;
    return;
  }
  if (location.protocol === "file:") {
    showGateError(
      "Trang đang được mở trực tiếp từ file (file://) — trình duyệt sẽ chặn không cho chạy. Chạy lệnh trong docs/review-ui-guide.md (python -m http.server ... --directory scripts/review_ui) rồi mở bằng http://localhost:8765, không mở trực tiếp index.html."
    );
    pickBtn.disabled = true;
    return;
  }

  // Luôn gán sẵn hành động "chọn thư mục mới" cho nút này TRƯỚC, bất kể có
  // handle đã lưu hay không — bootWithRoot() ẩn màn hình gate khi thành công,
  // nên việc gán này chỉ có tác dụng khi vẫn còn kẹt ở màn hình gate (kể cả
  // khi handle đã lưu bị hỏng/đổi chỗ và cần chọn lại). Tránh lặp lại lỗi cũ:
  // trước đây nhánh "đã lưu + còn quyền" không gán onclick nào cả, nên nếu
  // bootWithRoot thất bại (thư mục đã lưu không còn hợp lệ), nút chọn thư
  // mục trở thành nút chết vĩnh viễn — không bấm được nữa dù còn hiện trên
  // màn hình.
  function wirePickNewFolder() {
    pickBtn.textContent = "Chọn thư mục project.json";
    pickBtn.onclick = async () => {
      try {
        const handle = await fsAccess.pickRoot();
        const ok = await bootWithRoot(handle);
        // Chỉ lưu lại handle sau khi đã xác nhận đọc được schema — tránh lưu
        // nhầm 1 thư mục sai khiến lần mở sau bị kẹt lại đúng lỗi này.
        if (ok) await idb.saveRootHandle(handle).catch(() => {});
      } catch (err) {
        if (err && err.name !== "AbortError") showGateError(err.message || String(err));
      }
    };
  }
  wirePickNewFolder();

  const saved = await idb.loadRootHandle().catch(() => null);
  if (!saved) return;

  const granted = await fsAccess.verifyPermission(saved, "readwrite").catch(() => false);
  if (granted) {
    const ok = await bootWithRoot(saved);
    if (!ok) toast("Thư mục đã lưu trước đó không dùng được nữa — hãy chọn lại thư mục dự án.", "error");
    return;
  }

  pickBtn.textContent = "Cấp lại quyền cho thư mục đã chọn trước đó";
  toast("Trình duyệt cần xác nhận lại quyền truy cập thư mục đã chọn trước đó — bấm nút để tiếp tục.");
  pickBtn.onclick = async () => {
    const ok = await fsAccess.verifyPermission(saved, "readwrite").catch(() => false);
    if (!ok) {
      showGateError("Chưa được cấp quyền truy cập thư mục.");
      return;
    }
    const success = await bootWithRoot(saved);
    if (!success) wirePickNewFolder();
  };
}

async function bootWithRoot(handle) {
  state.root = handle;
  try {
    state.project = await fsAccess.readJSON(state.root, "project.json");
    state.schema = await fsAccess.readJSON(state.root, projectPath("schema", "schema.json"));
  } catch (err) {
    showGateError(
      "Không đọc được project.json hoặc schema — hãy chọn đúng thư mục project. Lỗi: " +
        (err.message || err)
    );
    return false;
  }
  state.questionsByPage = schemaEngine.groupQuestionsByPage(state.schema);

  try {
    const csvText = await fsAccess.readText(state.root, projectPath("manifest", "data/manifest.csv"));
    state.progressRows = parseCSV(csvText);
  } catch (err) {
    state.progressRows = [];
    toast("Không đọc được manifest — sidebar sẽ trống nhưng UI vẫn dùng được.", "error");
  }

  document.getElementById("gate").hidden = true;
  const mainEl = document.getElementById("main");
  mainEl.hidden = false;

  const rootNameEl = document.getElementById("root-name");
  rootNameEl.textContent = handle.name;
  rootNameEl.title = "Bấm để đổi sang thư mục khác";
  rootNameEl.style.cursor = "pointer";
  rootNameEl.onclick = async () => {
    if (state.dirty) await saveNow();
    try {
      const newHandle = await fsAccess.pickRoot();
      await idb.saveRootHandle(newHandle);
      location.reload();
    } catch (err) {
      /* người dùng huỷ hộp thoại chọn thư mục — bỏ qua */
    }
  };

  wireGlobalControls();
  await buildSidebar();
  return true;
}

function projectPath(key, fallback) {
  const value = state.project && state.project.paths && state.project.paths[key];
  return value || fallback;
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

async function scanRecordMeta(recordId) {
  const relPath = `${projectPath("full", "work/full")}/${recordId}.json`;
  const exists = await fsAccess.fileExists(state.root, relPath);
  if (!exists) return { hasFile: false };
  try {
    const record = await fsAccess.readJSON(state.root, relPath);
    return {
      hasFile: true,
      broken: false,
      needsReview: schemaEngine.countNeedsReview(state.schema, record),
      errorCount: schemaEngine.validateRecord(state.schema, record).length,
    };
  } catch (err) {
    return { hasFile: true, broken: true, error: String(err && err.message ? err.message : err) };
  }
}

async function buildSidebar() {
  await Promise.all(
    state.progressRows.map(async (row) => {
      const meta = await scanRecordMeta(row.record_id);
      state.recordMetaCache.set(row.record_id, meta);
    })
  );
  renderSidebarList();
}

function renderSidebarList() {
  const list = document.getElementById("record-list");
  list.innerHTML = "";
  const search = (document.getElementById("search-record").value || "").trim().toLowerCase();
  const showDone = document.getElementById("filter-done").checked;
  const showPending = document.getElementById("filter-pending").checked;
  const onlyFlagged = document.getElementById("filter-flagged").checked;

  let shown = 0;
  for (const row of state.progressRows) {
    const meta = state.recordMetaCache.get(row.record_id) || { hasFile: false };
    if (search && !row.record_id.toLowerCase().includes(search)) continue;
    if (meta.hasFile && !showDone) continue;
    if (!meta.hasFile && !showPending) continue;
    if (onlyFlagged && !(meta.broken || meta.needsReview > 0)) continue;

    shown += 1;
    const item = h("div", {
      class: "record-item" + (row.record_id === state.currentRecordId ? " active" : ""),
      role: "option",
    });
    let dotClass = "pending";
    if (meta.broken) dotClass = "broken";
    else if (meta.hasFile && meta.needsReview > 0) dotClass = "flagged";
    else if (meta.hasFile) dotClass = "clean";
    item.append(h("span", { class: "dot " + dotClass }));
    item.append(h("span", { class: "rid" }, row.record_id));
    if (meta.broken) item.append(h("span", { class: "count" }, "lỗi JSON"));
    else if (meta.hasFile && meta.needsReview > 0) item.append(h("span", { class: "count" }, String(meta.needsReview)));
    const manifestContext = Object.entries(row)
      .filter(([key, value]) => !["record_id", "source_path"].includes(key) && value)
      .map(([key, value]) => `${key}: ${value}`);
    item.title = [...manifestContext, meta.broken ? meta.error : ""].filter(Boolean).join(" — ");
    item.addEventListener("click", () => selectRecord(row.record_id));
    list.append(item);
  }
  document.getElementById("record-count").textContent = `${shown}/${state.progressRows.length} phiếu`;
}

async function refreshSidebarItem(recordId) {
  const meta = await scanRecordMeta(recordId);
  state.recordMetaCache.set(recordId, meta);
  renderSidebarList();
}

// ---------------------------------------------------------------------------
// Chọn / nạp 1 phiếu
// ---------------------------------------------------------------------------

async function selectRecord(recordId) {
  if (state.dirty) await saveNow();

  state.currentRecordId = recordId;
  state.imageCache.forEach((url) => {});
  document.getElementById("current-record").textContent = recordId;

  const relPath = `${projectPath("full", "work/full")}/${recordId}.json`;
  const exists = await fsAccess.fileExists(state.root, relPath);
  let record = null;
  if (exists) {
    try {
      record = await fsAccess.readJSON(state.root, relPath);
    } catch (err) {
      toast(`Không đọc được ${relPath}: ${err.message}. File JSON có thể bị lỗi cú pháp — sửa thủ công rồi chọn lại phiếu.`, "error");
      state.currentRecord = null;
      state.isNewRecord = false;
      renderSidebarList();
      const container = document.getElementById("record-view");
      container.innerHTML = "";
      container.append(
        h("div", { class: "empty-state" }, [
          h("div", { style: "text-align:center;max-width:480px" }, [
            h("p", {}, `${relPath} bị lỗi cú pháp JSON, không đọc được:`),
            h("pre", { class: "mono small", style: "white-space:pre-wrap;text-align:left" }, String(err.message || err)),
            h("p", { class: "muted small" }, "Sửa file này thủ công (VS Code / editor bất kỳ) rồi bấm lại vào phiếu trong danh sách để tải lại."),
          ]),
        ])
      );
      return;
    }
  }
  state.currentRecord = record;
  state.isNewRecord = !exists;
  state.dirty = false;
  updateSaveStatus("saved");

  try {
    state.assembly = await fsAccess.readJSON(state.root, `${projectPath("assembly", "work/assembly")}/${recordId}.json`);
  } catch (err) {
    state.assembly = null;
  }

  if (record) {
    const hits = schemaEngine.walkNeedsReview(state.schema, record);
    state.currentPage = hits.length ? hits[0].page : 1;
  } else {
    state.currentPage = 1;
  }

  renderSidebarList();
  renderRecordView();
}

// ---------------------------------------------------------------------------
// Lưu / trạng thái lưu
// ---------------------------------------------------------------------------

function updateSaveStatus(kind) {
  const el = document.getElementById("save-status");
  el.className = "save-status " + kind;
  if (kind === "dirty") el.textContent = "Có thay đổi chưa lưu…";
  else if (kind === "saved") el.textContent = "Đã lưu";
  else if (kind === "error") el.textContent = "Lỗi khi lưu!";
  else el.textContent = "—";
}

function markDirty() {
  state.dirty = true;
  updateSaveStatus("dirty");
  if (state.autosaveTimer) clearTimeout(state.autosaveTimer);
  state.autosaveTimer = setTimeout(saveNow, 900);
  if (state.currentRecord) refreshValidateBanner(state.currentRecord);
}

async function saveNow() {
  if (state.autosaveTimer) {
    clearTimeout(state.autosaveTimer);
    state.autosaveTimer = null;
  }
  if (!state.dirty || !state.currentRecord || !state.currentRecordId) return;
  try {
    await fsAccess.writeJSON(state.root, `${projectPath("full", "work/full")}/${state.currentRecordId}.json`, state.currentRecord);
    state.dirty = false;
    state.isNewRecord = false;
    const now = new Date();
    updateSaveStatus("saved");
    document.getElementById("save-status").textContent = "Đã lưu lúc " + now.toLocaleTimeString("vi-VN");
    await refreshSidebarItem(state.currentRecordId);
  } catch (err) {
    updateSaveStatus("error");
    toast("Lưu thất bại: " + (err.message || err), "error");
  }
}

// ---------------------------------------------------------------------------
// Validate banner
// ---------------------------------------------------------------------------

function refreshValidateBanner(record) {
  if (!state.validateBannerEl) return;
  const errors = schemaEngine.validateRecord(state.schema, record);
  const badge = document.getElementById("validate-badge");
  state.validateBannerEl.innerHTML = "";
  if (errors.length) {
    state.validateBannerEl.className = "validate-panel";
    state.validateBannerEl.append(h("div", {}, `❌ ${errors.length} lỗi cấu trúc (thiếu trường theo schema):`));
    const ul = h("ul", {});
    errors.slice(0, 20).forEach((e) => ul.append(h("li", {}, e)));
    state.validateBannerEl.append(ul);
    if (errors.length > 20) state.validateBannerEl.append(h("div", { class: "small" }, `… và ${errors.length - 20} lỗi khác`));
    badge.hidden = false;
    badge.className = "badge badge-danger";
    badge.textContent = `${errors.length} lỗi cấu trúc`;
  } else {
    state.validateBannerEl.className = "validate-panel ok";
    state.validateBannerEl.textContent =
      "✅ Cấu trúc hợp lệ — đủ trường theo schema (chỉ kiểm tra thiếu trường, không kiểm tra nội dung đúng/sai).";
    badge.hidden = false;
    badge.className = "badge badge-success";
    badge.textContent = "Cấu trúc OK";
  }
}

// ---------------------------------------------------------------------------
// Image viewer (zoom / pan)
// ---------------------------------------------------------------------------

function attachZoomPan(canvasEl, img, zoomWrapEl) {
  const view = { scale: 1, tx: 0, ty: 0 };
  const zoomValueEl = h("span", { class: "zoom-value" }, "100%");

  function apply() {
    img.style.transform = `translate(${view.tx}px, ${view.ty}px) scale(${view.scale})`;
    zoomValueEl.textContent = Math.round(view.scale * 100) + "%";
  }

  function fit() {
    const rect = canvasEl.getBoundingClientRect();
    if (!img.naturalWidth || !img.naturalHeight) return;
    view.scale = Math.min(rect.width / img.naturalWidth, rect.height / img.naturalHeight) || 1;
    view.tx = Math.max(0, (rect.width - img.naturalWidth * view.scale) / 2);
    view.ty = 0;
    apply();
  }

  img.addEventListener("load", fit);
  if (img.complete && img.naturalWidth) fit();

  canvasEl.addEventListener(
    "wheel",
    (e) => {
      e.preventDefault();
      const rect = canvasEl.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const newScale = Math.min(10, Math.max(0.1, view.scale * factor));
      view.tx = mx - (mx - view.tx) * (newScale / view.scale);
      view.ty = my - (my - view.ty) * (newScale / view.scale);
      view.scale = newScale;
      apply();
    },
    { passive: false }
  );

  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  canvasEl.addEventListener("pointerdown", (e) => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    canvasEl.classList.add("dragging");
    canvasEl.setPointerCapture(e.pointerId);
  });
  canvasEl.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    view.tx += e.clientX - lastX;
    view.ty += e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    apply();
  });
  const stopDrag = () => {
    dragging = false;
    canvasEl.classList.remove("dragging");
  };
  canvasEl.addEventListener("pointerup", stopDrag);
  canvasEl.addEventListener("pointercancel", stopDrag);
  canvasEl.addEventListener("dblclick", fit);

  zoomWrapEl.innerHTML = "";
  zoomWrapEl.append(
    h("button", { type: "button", class: "btn btn-sm btn-icon", title: "Thu nhỏ", onClick: () => { view.scale = Math.max(0.1, view.scale / 1.2); apply(); } }, "−"),
    zoomValueEl,
    h("button", { type: "button", class: "btn btn-sm btn-icon", title: "Phóng to", onClick: () => { view.scale = Math.min(10, view.scale * 1.2); apply(); } }, "+"),
    h("button", { type: "button", class: "btn btn-sm", title: "Vừa khung (hoặc double-click ảnh)", onClick: fit }, "Vừa khung")
  );
  apply();
}

async function mountPageImage(canvasEl, pageNumber, zoomWrapEl) {
  canvasEl.innerHTML = "";
  let relPath = null;
  if (state.assembly && Array.isArray(state.assembly.pages)) {
    const p = state.assembly.pages.find((pg) => pg.tentative_page === pageNumber);
    if (p) relPath = p.image_path;
  }
  if (!relPath) {
    relPath = `${projectPath("assembly", "work/assembly")}/_render/${state.currentRecordId}/${state.currentRecordId}__p${pageNumber}.png`;
  }

  let url;
  try {
    if (state.imageCache.has(relPath)) {
      url = state.imageCache.get(relPath);
    } else {
      const file = await fsAccess.readBlob(state.root, relPath);
      url = URL.createObjectURL(file);
      state.imageCache.set(relPath, url);
    }
  } catch (err) {
    canvasEl.append(h("div", { class: "muted", style: "padding:24px" }, `Không tìm thấy ảnh: ${relPath}`));
    return;
  }

  const img = new Image();
  img.alt = `${state.currentRecordId} — trang ${pageNumber}`;
  img.src = url;
  canvasEl.append(img);
  attachZoomPan(canvasEl, img, zoomWrapEl);
}

// ---------------------------------------------------------------------------
// Dựng giao diện phiếu (ảnh + form)
// ---------------------------------------------------------------------------

function buildImagePane(record) {
  const pane = h("div", { class: "image-pane" });
  const toolbar = h("div", { class: "image-toolbar" });

  const tabs = h("div", { class: "page-tabs" });
  const totalPages = Number(state.schema.total_pages);
  const flaggedPages = new Set(schemaEngine.walkNeedsReview(state.schema, record).map((x) => x.page));
  for (let p = 1; p <= totalPages; p++) {
    const tab = h("button", { type: "button", class: "page-tab" + (p === state.currentPage ? " active" : "") }, `Tr.${p}`);
    if (flaggedPages.has(p)) tab.append(h("span", { class: "flag-dot" }));
    tab.addEventListener("click", () => {
      state.currentPage = p;
      renderRecordView();
    });
    tabs.append(tab);
  }
  toolbar.append(tabs);

  const zoomWrap = h("div", { class: "zoom-controls" });
  toolbar.append(zoomWrap);
  pane.append(toolbar);

  const canvas = h("div", { class: "image-canvas" });
  pane.append(canvas);

  const noteBar = h("div", { class: "page-note-bar" });
  noteBar.append(schemaEngine.renderPageNotesBox(record, state.currentPage, markDirty));
  pane.append(noteBar);

  mountPageImage(canvas, state.currentPage, zoomWrap);
  return pane;
}

function jumpToNextFlagged() {
  if (!state.currentRecord) return;
  const hits = schemaEngine.walkNeedsReview(state.schema, state.currentRecord);
  if (!hits.length) {
    toast("Không còn câu nào cần review trong phiếu này.", "success");
    return;
  }
  const pages = Array.from(new Set(hits.map((x) => x.page))).sort((a, b) => a - b);
  let next = pages.find((p) => p > state.currentPage);
  if (next === undefined) next = pages[0];
  state.currentPage = next;
  renderRecordView();
  toast(`Trang ${next} — còn ${hits.length} chỗ needs_review trong phiếu này.`);
}

function buildFormPane(record) {
  const pane = h("div", { class: "form-pane" });

  const toolbar = h("div", { class: "form-toolbar" });
  const pageLabel = h("span", { class: "muted small" }, `Trang ${state.currentPage}/${state.schema.total_pages}`);
  const onlyFlaggedLabel = h("label", { class: "chip-toggle" });
  const onlyFlaggedCb = h("input", { type: "checkbox" });
  onlyFlaggedLabel.append(onlyFlaggedCb, document.createTextNode(" chỉ hiện câu cần review"));
  const jumpBtn = h("button", { type: "button", class: "btn btn-sm", onClick: jumpToNextFlagged }, "Câu review tiếp theo →");
  toolbar.append(pageLabel, onlyFlaggedLabel, jumpBtn);
  pane.append(toolbar);

  const validateBanner = h("div", { class: "validate-panel" });
  state.validateBannerEl = validateBanner;
  pane.append(validateBanner);
  refreshValidateBanner(record);

  const list = h("div", { class: "form-list" });
  const questions = (state.questionsByPage.get(state.currentPage) || []);
  for (const q of questions) {
    const card = schemaEngine.renderQuestionCard(q, record, { onDirty: markDirty });
    list.append(card);
  }
  if (!questions.length) {
    list.append(h("div", { class: "muted" }, "Trang này không có câu hỏi nào trong schema."));
  }
  pane.append(list);

  onlyFlaggedCb.addEventListener("change", () => {
    list.querySelectorAll(".q-card").forEach((card) => {
      const show = !onlyFlaggedCb.checked || card.classList.contains("needs-review");
      card.style.display = show ? "" : "none";
    });
  });

  const rawWrap = h("div", { class: "raw-json" });
  const rawPre = h("pre");
  rawPre.style.display = "none";
  const rawToggle = h(
    "button",
    {
      type: "button",
      class: "btn btn-sm btn-ghost",
      onClick: () => {
        const showing = rawPre.style.display !== "none";
        rawPre.style.display = showing ? "none" : "block";
        rawToggle.textContent = (showing ? "▸" : "▾") + " Xem JSON thô (chỉ đọc)";
        if (!showing) rawPre.textContent = JSON.stringify(record, null, 2);
      },
    },
    "▸ Xem JSON thô (chỉ đọc)"
  );
  rawWrap.append(rawToggle, rawPre);
  pane.append(rawWrap);

  return pane;
}

function setupSplitter(splitEl, splitterEl) {
  let dragging = false;
  splitterEl.addEventListener("pointerdown", (e) => {
    dragging = true;
    splitterEl.classList.add("dragging");
    splitterEl.setPointerCapture(e.pointerId);
  });
  splitterEl.addEventListener("pointermove", (e) => {
    if (!dragging) return;
    const rect = splitEl.getBoundingClientRect();
    let pct = ((e.clientX - rect.left) / rect.width) * 100;
    pct = Math.min(80, Math.max(25, pct));
    splitEl.style.setProperty("--split-left", pct + "%");
  });
  const stop = () => {
    dragging = false;
    splitterEl.classList.remove("dragging");
  };
  splitterEl.addEventListener("pointerup", stop);
  splitterEl.addEventListener("pointercancel", stop);
}

function renderRecordView() {
  const container = document.getElementById("record-view");
  container.innerHTML = "";
  const record = state.currentRecord;

  if (!record) {
    const box = h("div", { class: "empty-state" });
    const inner = h("div", { style: "text-align:center" });
    inner.append(h("p", {}, `Phiếu ${state.currentRecordId} chưa có bản ghi extraction.`));
    const btn = h(
      "button",
      {
        class: "btn btn-primary",
        type: "button",
        onClick: () => {
          state.currentRecord = schemaEngine.createEmptyRecord(state.schema, state.currentRecordId);
          state.isNewRecord = true;
          markDirty();
          renderRecordView();
        },
      },
      "Tạo file mới (trống) để bắt đầu nhập"
    );
    inner.append(btn);
    box.append(inner);
    container.append(box);
    return;
  }

  const split = h("div", { class: "split" });
  const imagePane = buildImagePane(record);
  const splitter = h("div", { class: "splitter" });
  const formPane = buildFormPane(record);
  split.append(imagePane, splitter, formPane);
  container.append(split);
  setupSplitter(split, splitter);
}

function changePage(delta) {
  if (!state.currentRecord) return;
  const total = Number(state.schema.total_pages);
  let p = state.currentPage + delta;
  if (p < 1) p = total;
  if (p > total) p = 1;
  state.currentPage = p;
  renderRecordView();
}

// ---------------------------------------------------------------------------
// Điều khiển chung (toolbar, phím tắt, theme)
// ---------------------------------------------------------------------------

function initTheme() {
  const saved = localStorage.getItem("review-ui-theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
  document.getElementById("btn-toggle-theme").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("review-ui-theme", next);
  });
}

let globalControlsWired = false;
function wireGlobalControls() {
  if (globalControlsWired) return;
  globalControlsWired = true;

  document.getElementById("btn-save").addEventListener("click", saveNow);
  document.getElementById("search-record").addEventListener("input", renderSidebarList);
  document.getElementById("filter-done").addEventListener("change", renderSidebarList);
  document.getElementById("filter-pending").addEventListener("change", renderSidebarList);
  document.getElementById("filter-flagged").addEventListener("change", renderSidebarList);

  document.addEventListener("keydown", (e) => {
    const tag = (document.activeElement && document.activeElement.tagName) || "";
    const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveNow();
      return;
    }
    if (typing) return;
    if (!state.currentRecord) return;
    if (e.key === "ArrowLeft") changePage(-1);
    else if (e.key === "ArrowRight") changePage(1);
    else if (e.key.toLowerCase() === "j") jumpToNextFlagged();
  });

  window.addEventListener("beforeunload", (e) => {
    if (state.dirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  });
}

initTheme();
boot();
