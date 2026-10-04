/**
 * 打ち合わせ資料フォルダの決まりごとと、ファイルの読み書き。
 *
 * ページの型・ファイル名・画面番号の決まりは schemas/briefing.schema.json と同じものをここ 1 か所に置き、
 * スクリプトはここから読む (tests/test_briefing_schema.py がスキーマと突き合わせる)。
 * 型の表示名 TYPE_LABEL の正本もここ。references/page-patterns.md の型の見出しは写し (tests/test_single_source.py が突き合わせる)。
 * しきい値の正本は assets/data/quality-thresholds.json だけ。ここに既定値は置かない。
 */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, renameSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { ToolMissing } from "./cli-contract.mjs";

export const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
export const TEMPLATES = path.join(PLUGIN_ROOT, "assets", "templates");
export const CSS_DIR = path.join(PLUGIN_ROOT, "assets", "css");
export const THRESHOLDS_PATH = path.join(PLUGIN_ROOT, "assets", "data", "quality-thresholds.json");
export const PLAIN_LANGUAGE_PATH = path.join(PLUGIN_ROOT, "assets", "data", "plain-language.json");

export const OUT_DIR_NAME = "打ち合わせ資料";
export const PAGE_TYPES = Object.freeze([
  "overview", "screen-map", "phone", "pc", "data-map", "mechanism", "future",
]);
/** 型の表示名。本の見出しに出す。 */
export const TYPE_LABEL = Object.freeze({
  overview: "全体図",
  "screen-map": "画面の一覧と流れ",
  phone: "画面 (スマホ)",
  pc: "画面 (PC)",
  "data-map": "データの対応",
  mechanism: "しくみ",
  future: "将来の広げ方",
});
export const DEVICE_TYPES = Object.freeze(["phone", "pc"]);
/** 資料に素材の名前・値・画像をそのまま載せるか (briefing.json の data_policy)。source = 素材のまま (素材をくれた先方と、作る側だけで見る)、masked = 伏せる (それ以外の人にも見せる)。 */
export const DATA_POLICIES = Object.freeze(["source", "masked"]);
export const FILE_RE = /^(\d{2})_[a-z0-9]+(?:-[a-z0-9]+)*\.html$/;
export const SCREEN_ID = /^S\d{2,}$/;

/** JSON を読む。読めなければ fallback。 */
export function loadJson(file, fallback) {
  try {
    return JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return fallback;
  }
}

/** しきい値のファイルを読む。読めなければ止める (exit 3)。 */
export function loadThresholds() {
  const data = loadJson(THRESHOLDS_PATH, null);
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    throw new ToolMissing(`しきい値のファイルが読めません: ${THRESHOLDS_PATH}`);
  }
  return data;
}

/** しきい値を 1 つ取り出す。数が無ければ止める (exit 3)。 */
export function threshold(thresholds, group, key) {
  const value = thresholds?.[group]?.[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ToolMissing(`しきい値 ${group}.${key} がありません: ${THRESHOLDS_PATH}`);
  }
  return value;
}

/** 型ごとのしきい値の表を取り出す ({ 型: 数 })。足りない型や数でない値があれば止める (exit 3)。 */
export function thresholdTable(thresholds, group, key, names) {
  const table = thresholds?.[group]?.[key];
  if (!table || typeof table !== "object" || Array.isArray(table)) {
    throw new ToolMissing(`しきい値 ${group}.${key} がありません: ${THRESHOLDS_PATH}`);
  }
  const out = {};
  for (const name of names) {
    const value = table[name];
    if (typeof value !== "number" || !Number.isFinite(value)) {
      throw new ToolMissing(`しきい値 ${group}.${key}.${name} がありません: ${THRESHOLDS_PATH}`);
    }
    out[name] = value;
  }
  return out;
}

/** UTF-8 で読む。先頭の BOM は外す (Windows のメモ帳で保存した文書のため)。 */
export function readText(file) {
  const text = readFileSync(file, "utf8");
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/** 行に分ける。最後の改行のあとに空の行を作らない (Python の splitlines と同じ数え方)。 */
export function splitLines(text) {
  const lines = text.split(/\r\n|\r|\n/);
  if (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines;
}

export function isFile(file) {
  try {
    return statSync(file).isFile();
  } catch {
    return false;
  }
}

export function isDir(dir) {
  try {
    return statSync(dir).isDirectory();
  } catch {
    return false;
  }
}

export function mtimeMs(file) {
  try {
    return statSync(file).mtimeMs;
  } catch {
    return null;
  }
}

export function toPosix(file) {
  return file.split(path.sep).join("/");
}

/** start から見た target の相対パス (区切りは /)。Windows で別ドライブなら target をそのまま返す。 */
export function relPosix(target, start) {
  const rel = path.relative(start, target);
  if (path.isAbsolute(rel)) return toPosix(target);
  return toPosix(rel) || ".";
}

/** 実在するパスは実体のパス (シンボリックリンクと /tmp → /private/tmp をほどく) にする。無ければ絶対パスのまま。 */
export function realPath(file) {
  try {
    return realpathSync(file);
  } catch {
    return path.resolve(file);
  }
}

/** 一時ファイルに書いてから置き換える。途中で止まっても半端なファイルを残さない。 */
export function writeAtomic(file, data) {
  mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.tmp`;
  try {
    writeFileSync(tmp, data);
    renameSync(tmp, file);
  } catch (error) {
    if (existsSync(tmp)) rmSync(tmp, { force: true });
    throw error;
  }
}

/** 字下げ 2 の JSON と最後の改行で書く。 */
export function writeJson(file, value) {
  writeAtomic(file, `${JSON.stringify(value, null, 2)}\n`);
}

export function sha256(data) {
  return createHash("sha256").update(data).digest("hex");
}

export function sha256File(file) {
  return sha256(readFileSync(file));
}

/** HTML として逃がす。quote なら " と ' も逃がす。 */
export function escapeHtml(text, quote = true) {
  let out = String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  if (quote) out = out.replace(/"/g, "&quot;").replace(/'/g, "&#x27;");
  return out;
}

/** ファイル名に使えない文字を _ にし、後ろの . と空白を落とす (Windows で作れない名前を避ける)。空なら fallback。 */
export function safeFilename(name, fallback = "資料") {
  // eslint-disable-next-line no-control-regex
  const cleaned = String(name).replace(/[\\/:*?"<>|\x00-\x1f]/g, "_").trim().replace(/[. ]+$/, "");
  return cleaned || fallback;
}

/** 今日の日付 YYYY-MM-DD (その場所の時刻で)。 */
export function todayIso() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** ~ で始まるパスを家のフォルダに広げる。 */
export function expandHome(file) {
  if (file === "~" || file.startsWith("~/") || file.startsWith("~\\")) {
    return path.join(process.env.HOME || process.env.USERPROFILE || "", file.slice(1));
  }
  return file;
}

// ── 素材フォルダ ───────────────────────────────

export const MATERIAL_TYPES = Object.freeze({
  ".pdf": "pdf",
  ".png": "image", ".jpg": "image", ".jpeg": "image", ".webp": "image", ".gif": "image",
  ".heic": "image", ".heif": "image", ".bmp": "image", ".tif": "image", ".tiff": "image", ".svg": "image",
  ".csv": "csv", ".tsv": "csv",
  ".xlsx": "excel", ".xlsm": "excel", ".xls": "excel", ".ods": "excel", ".numbers": "excel",
  ".txt": "text", ".md": "text", ".markdown": "text", ".text": "text",
});
const MAX_MATERIALS = 2000;

/** 素材フォルダを上から順に歩く (隠しファイル・Office の一時ファイル・出力フォルダ自身は飛ばす)。 */
export function scanMaterials(materials, outDir) {
  const items = [];
  const outResolved = realPath(outDir);
  let truncated = false;

  const walk = (dir) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }
    const files = [];
    const dirs = [];
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      let kind = entry.isDirectory() ? "dir" : entry.isFile() ? "file" : null;
      if (entry.isSymbolicLink()) {
        try {
          kind = statSync(full).isFile() ? "file" : null; // リンク先のフォルダには入らない
        } catch {
          kind = null;
        }
      }
      if (kind === "dir") dirs.push(entry.name);
      else if (kind === "file") files.push(entry.name);
    }
    for (const name of files.sort()) {
      if (name.startsWith(".") || name.startsWith("~$")) continue;
      const full = path.join(dir, name);
      const kind = MATERIAL_TYPES[path.extname(name).toLowerCase()] || "other";
      const item = { path: relPosix(full, materials), type: kind, size: statSync(full).size };
      if (kind === "excel") item.needs_csv = true;
      items.push(item);
      if (items.length >= MAX_MATERIALS) {
        truncated = true;
        return;
      }
    }
    for (const name of dirs.sort()) {
      if (name.startsWith(".") || name === "__pycache__") continue;
      const full = path.join(dir, name);
      if (realPath(full) === outResolved) continue;
      walk(full);
      if (truncated) return;
    }
  };
  walk(materials);

  const counts = {};
  for (const item of items) counts[item.type] = (counts[item.type] || 0) + 1;
  return {
    schema: "briefing-materials-v1",
    materials: toPosix(realPath(materials)),
    counts,
    needs_csv: items.filter((i) => i.needs_csv).map((i) => i.path),
    truncated,
    items,
  };
}
