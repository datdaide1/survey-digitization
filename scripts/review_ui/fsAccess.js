// Wrapper mỏng quanh File System Access API — mọi đọc/ghi đều tương đối so
// với thư mục project mà người dùng chọn.

export function isSupported() {
  return typeof window.showDirectoryPicker === "function";
}

export async function pickRoot() {
  const handle = await window.showDirectoryPicker({ id: "startup-root", mode: "readwrite" });
  return handle;
}

export async function verifyPermission(handle, mode = "readwrite") {
  const opts = { mode };
  if ((await handle.queryPermission(opts)) === "granted") return true;
  if ((await handle.requestPermission(opts)) === "granted") return true;
  return false;
}

function splitPath(relPath) {
  if (typeof relPath !== "string" || !relPath || /^[A-Za-z]:/.test(relPath) || relPath.startsWith("/")) {
    throw new Error(`Đường dẫn project không hợp lệ: ${relPath}`);
  }
  const parts = relPath.replaceAll("\\", "/").split("/").filter(Boolean);
  if (parts.some((part) => part === "." || part === "..")) {
    throw new Error(`Đường dẫn project vượt ra ngoài thư mục đã chọn: ${relPath}`);
  }
  return parts;
}

async function walkToDir(root, parts, { create = false } = {}) {
  let dir = root;
  for (const part of parts) {
    dir = await dir.getDirectoryHandle(part, { create });
  }
  return dir;
}

export async function getFileHandle(root, relPath, { create = false } = {}) {
  const parts = splitPath(relPath);
  const fileName = parts.pop();
  const dir = await walkToDir(root, parts, { create });
  return dir.getFileHandle(fileName, { create });
}

export async function fileExists(root, relPath) {
  try {
    await getFileHandle(root, relPath, { create: false });
    return true;
  } catch (err) {
    return false;
  }
}

export async function dirExists(root, relPath) {
  try {
    await walkToDir(root, splitPath(relPath), { create: false });
    return true;
  } catch (err) {
    return false;
  }
}

export async function listDir(root, relPath) {
  const dir = await walkToDir(root, splitPath(relPath), { create: false });
  const names = [];
  for await (const [name, handle] of dir.entries()) {
    names.push({ name, kind: handle.kind });
  }
  return names;
}

export async function readText(root, relPath) {
  const fh = await getFileHandle(root, relPath, { create: false });
  const file = await fh.getFile();
  return await file.text();
}

export async function readJSON(root, relPath) {
  const text = await readText(root, relPath);
  return JSON.parse(text);
}

export async function readBlob(root, relPath) {
  const fh = await getFileHandle(root, relPath, { create: false });
  const file = await fh.getFile();
  return file;
}

// Ghi JSON đúng quy ước của project (2-space indent, UTF-8 nguyên văn dấu
// tiếng Việt, xuống dòng cuối file) — khớp _atomic_write_json trong
// scripts/extract_mc.py. Trước khi ghi đè, sao lưu bản cũ sang "<path>.bak"
// (ghi đè lần trước) để có 1 bước hoàn tác nếu sửa nhầm.
export async function writeJSON(root, relPath, value, { backup = true } = {}) {
  if (backup) {
    try {
      const oldText = await readText(root, relPath);
      const bakHandle = await getFileHandle(root, `${relPath}.bak`, { create: true });
      const writable = await bakHandle.createWritable();
      await writable.write(oldText);
      await writable.close();
    } catch (err) {
      // Chưa có file cũ (lần đầu tạo) — không cần backup, bỏ qua lỗi.
    }
  }
  const text = JSON.stringify(value, null, 2) + "\n";
  const fh = await getFileHandle(root, relPath, { create: true });
  const writable = await fh.createWritable();
  await writable.write(text);
  await writable.close();
}

export async function writeText(root, relPath, text) {
  const fh = await getFileHandle(root, relPath, { create: true });
  const writable = await fh.createWritable();
  await writable.write(text);
  await writable.close();
}
