#!/usr/bin/env node
/**
 * compare-briefing-profile — 作った打ち合わせ資料を、基準点 (利用者が先に作った資料の数と形) と並べて差の表を出す。編集はしない。
 *
 * 表の行: ページの型の並び / 画面のボードの数 / 判断材料 5 つ / 型ごとの説明の字数 / いちばん小さい文字。
 * ボード HTML (_src/*.html) は文字として読む (ブラウザは使わない。注釈 <!-- --> の中は数えない)。
 *   facts      overview のボードに空でない可視の class="fact" が 1 つ以上
 *   paper      data-source の素材と表示画像のローカルファイルが存在する
 *   columns    data-map のボードに class="bar"
 *   reqs       phone / pc のボードのうち class="req" があるものの割合 (全部なら ○)
 *   mechanism  型 mechanism のページに可視の本文がある
 * ページの型の並びは、基準点の intended_additions にある型 (わざと足すページ) を両方から除いて比べる。
 * 説明の字数は現在の _check/boards.json の値だけ並べる。文字数そのものは合わせないので same は null にし、status に数えない。
 * いちばん小さい文字は、基準点より小さければ差。全ページの現在の計測が無ければ incomplete (差があれば diff)。
 * same は構造指標だけの一致。意味・参考版・範囲・視覚の高再現を保証しない。invalid は空/非表示/参照先不在、missing は材料の不一致。
 *
 * 使い方:
 *   node scripts/compare-briefing-profile.mjs --dir <打ち合わせ資料> [--profile <json>] [--quiet]
 *   --profile の既定は assets/data/target-profile.json。
 *
 * 書く場所: <dir>/_check/profile.json だけ (stdout と同じ中身)。
 * stdout: JSON {comparison, fidelity, status, profile, dir, rows, missing, invalid, measurements} (--quiet で要約 1 行)
 * exit: 0=比べた (差があっても 0。報告だけ) / 2=使い方の誤り (フォルダか briefing.json が無い) / 3=Node が古い・基準点のファイルが読めない
 */
import path from "node:path";
import { dependencyReceipt } from "./lib/resource-refs.mjs";
import { parseHtmlTree, iterNodes, classesOf } from "./lib/html-tokens.mjs";

import {
  DEVICE_TYPES,
  PAGE_TYPES,
  PLUGIN_ROOT,
  TYPE_LABEL,
  expandHome,
  isDir,
  isFile,
  loadJson,
  readText,
  realPath,
  toPosix,
  writeJson,
} from "./lib/briefing-files.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";

const USAGE = `
使い方:
  compare-briefing-profile.mjs --dir <打ち合わせ資料> [--profile <json>] [--quiet]
`;

export const PROFILE_PATH = path.join(PLUGIN_ROOT, "assets", "data", "target-profile.json");
const PROFILE_SCHEMA = "briefing-target-profile-v1";
/** 判断材料 5 つの並び。表示の言葉の正本は基準点のファイルの materials。 */
export const MATERIAL_KEYS = Object.freeze(["facts", "paper", "columns", "reqs", "mechanism"]);
const PRESENT = "○";
const ABSENT = "なし";

const isPlainObject = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const mark = (flag) => (flag ? PRESENT : ABSENT);
const listed = (page, key) => Array.isArray(page.materials) && page.materials.includes(key);
const sameList = (a, b) => a.length === b.length && a.every((value, i) => value === b[i]);

function push(map, key, value) {
  if (!map.has(key)) map.set(key, []);
  map.get(key).push(value);
}

/** 割合を表の値にする。全部なら ○、1 枚も無ければ なし、途中なら k/n。 */
function ratioMark(hit, total) {
  if (total > 0 && hit === total) return PRESENT;
  return hit > 0 ? `${hit}/${total}` : ABSENT;
}

/** 静的に分かる非表示だけを除く。CSS による可視性と意味は目視で照合する。 */
function hidden(node) {
  for (let n = node; n; n = n.parent) {
    if (["head", "script", "style", "template"].includes(n.tag) || Object.hasOwn(n.attrs, "hidden") || n.attrs["aria-hidden"] === "true" ||
        /(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*(?:hidden|collapse)|opacity\s*:\s*0(?:\.0*)?)(?:\s*!important)?\s*(?:;|$)/i.test(n.attrs.style ?? "")) return true;
  }
  return false;
}
function visibleText(node) {
  if (hidden(node)) return "";
  return node.children.map((child) => typeof child === "string" ? child : visibleText(child)).join("").trim();
}
function localFile(root, ref) {
  if (!root || !ref || /^(?:[a-z][a-z0-9+.-]*:|[\\/])/i.test(ref)) return null;
  try {
    const file = path.resolve(root, decodeURIComponent(ref.split(/[?#]/)[0]));
    const relative = path.relative(realPath(root), realPath(file));
    return relative && !relative.startsWith("..") && !path.isAbsolute(relative) && isFile(file) ? file : null;
  } catch { return null; }
}
export function boardTraits(html, { sourceDir, materialsDir } = {}) {
  const tree = parseHtmlTree(html);
  const classes = new Set();
  const invalid = [];
  let source = false;
  for (const node of iterNodes(tree)) {
    for (const name of classesOf(node)) {
      if (!hidden(node) && visibleText(node)) classes.add(name);
      else if (["fact", "req", "bar"].includes(name)) invalid.push({ key: name, reason: hidden(node) ? "hidden" : "empty" });
    }
    if (node.tag === "img" && !hidden(node) && !localFile(sourceDir, node.attrs.src) &&
        !/^data:image\/[a-z0-9.+-]+(?:;[^,]*)?,.+/is.test(node.attrs.src ?? "")) {
      invalid.push({ key: "image", reason: "image-missing", reference: node.attrs.src ?? "" });
    }
    if (!Object.hasOwn(node.attrs, "data-source")) continue;
    const images = [node, ...iterNodes(node)].filter((n) => n.tag === "img" && !hidden(n));
    let reason = null;
    if (hidden(node)) reason = "hidden";
    else if (!localFile(materialsDir, node.attrs["data-source"])) reason = "source-reference-missing";
    else if (!images.some((n) => localFile(sourceDir, n.attrs.src))) reason = "image-missing";
    if (reason) invalid.push({ key: "paper", reason, reference: node.attrs["data-source"] });
    else source = true;
  }
  return { classes, source, content: Boolean(visibleText(tree)), invalid };
}

/** 基準点のファイルを読む。形が違えば止める (exit 3)。 */
export function loadProfile(file) {
  const data = loadJson(file, null);
  if (!isPlainObject(data) || data.schema !== PROFILE_SCHEMA || !Array.isArray(data.pages)) {
    throw new ToolMissing(`基準点のファイルが読めません (schema ${PROFILE_SCHEMA} の JSON にする): ${file}`);
  }
  return { ...data, pages: data.pages.filter(isPlainObject) };
}

function readBriefing(base) {
  let data = null;
  try {
    data = JSON.parse(readText(path.join(base, "briefing.json")));
  } catch {
    data = null;
  }
  if (!isPlainObject(data)) throw new UsageError(`briefing.json が読めません (validate-briefing-docs.mjs で確かめる): ${base}`);
  return data;
}

/** pages の順にボード HTML を読む。ファイルが無い・読めないボードは中身が空として扱う。 */
function readBoards(base, pages, materials) {
  return pages.map((page) => {
    const name = typeof page.file === "string" ? path.basename(page.file) : "";
    const file = path.join(base, "_src", name);
    let html = "";
    if (name && isFile(file)) {
      try {
        html = readText(file);
      } catch {
        html = "";
      }
    }
    const traits = boardTraits(html, {
      sourceDir: path.join(base, "_src"),
      materialsDir: typeof materials === "string" ? path.resolve(base, materials) : null,
    });
    if (!html) traits.invalid.push({ key: "board", reason: "board-missing" });
    else if (page.type === "mechanism" && !traits.content) traits.invalid.push({ key: "mechanism", reason: "empty" });
    return { no: page.no, type: page.type, ...traits };
  });
}

/** _check/boards.json の説明の字数 (型ごと) といちばん小さい文字。無い・読めないときは null。今の pages にあるボードだけ使う。 */
function readMeasures(base, pages) {
  const data = loadJson(path.join(base, "_check", "boards.json"), null);
  const chars = new Map();
  const fonts = [];
  const unavailable = [];
  for (const page of pages) {
    const entries = (Array.isArray(data?.boards) ? data.boards : []).filter((e) => e && String(e.no) === String(page.no));
    const entry = entries.length === 1 ? entries[0] : null;
    const file = path.join(base, "_src", path.basename(page.file ?? ""));
    let reason = null;
    if (!entry || !Number.isFinite(entry.font_px_min) || entry.font_px_min <= 0) reason = "unmeasured";
    else if (!isPlainObject(entry.dependencies)) reason = "unverified-dependencies";
    else if (entry.status !== "ok" || entry.file !== page.file || entry.type !== page.type) reason = "invalid-measurement";
    else {
      // render/book と同じ参照解決と SHA receipt を使う。無関係な assets は読まない。
      const current = dependencyReceipt(file, base);
      const keys = new Set([...Object.keys(entry.dependencies), ...Object.keys(current)]);
      if ([...keys].some((key) => typeof current[key] !== "string" || current[key] !== entry.dependencies[key])) reason = "stale";
    }
    if (reason) { unavailable.push({ no: page.no, reason }); continue; }
    if (Number.isFinite(entry.text_chars)) push(chars, page.type, entry.text_chars);
    fonts.push(entry.font_px_min);
  }
  return { chars, font: !unavailable.length && fonts.length ? Math.min(...fonts) : null, unavailable };
}

function targetMaterials(pages) {
  const screens = pages.filter((page) => DEVICE_TYPES.includes(page.type));
  return {
    facts: mark(pages.some((page) => listed(page, "facts"))),
    paper: mark(pages.some((page) => listed(page, "paper"))),
    columns: mark(pages.some((page) => listed(page, "columns"))),
    reqs: ratioMark(screens.filter((page) => listed(page, "reqs")).length, screens.length),
    mechanism: mark(pages.some((page) => page.type === "mechanism")),
  };
}

function currentMaterials(boards) {
  const ofType = (types) => boards.filter((board) => types.includes(board.type));
  const screens = ofType(DEVICE_TYPES);
  return {
    facts: mark(ofType(["overview"]).some((board) => board.classes.has("fact"))),
    paper: mark(boards.some((board) => board.source)),
    columns: mark(ofType(["data-map"]).some((board) => board.classes.has("bar"))),
    reqs: ratioMark(screens.filter((board) => board.classes.has("req")).length, screens.length),
    mechanism: mark(boards.some((board) => board.type === "mechanism" && board.content)),
  };
}

export function compareProfile(base, profile, profileFile) {
  const briefing = readBriefing(base);
  const pages = (Array.isArray(briefing.pages) ? briefing.pages : []).filter(isPlainObject);
  const boards = readBoards(base, pages, briefing.materials);
  const rows = [];
  const row = (key, label, target, current, same) => rows.push({ key, label, target, current, same });

  const additions = Array.isArray(profile.intended_additions) ? profile.intended_additions : [];
  const added = PAGE_TYPES.filter((type) => additions.includes(type));
  const kept = (types) => types.filter((type) => !added.includes(type));
  const targetTypes = profile.pages.map((page) => page.type ?? null);
  const currentTypes = pages.map((page) => page.type ?? null);
  // 出す並びも除いたあとのもの (見出しと中身をそろえる)
  row("pages", added.length ? `ページの型の並び (${added.join("・")} はわざと足すので除いて比べる)` : "ページの型の並び",
    kept(targetTypes), kept(currentTypes), sameList(kept(targetTypes), kept(currentTypes)));

  const targetScreens = Number.isFinite(profile.screens)
    ? profile.screens
    : profile.pages.filter((page) => DEVICE_TYPES.includes(page.type)).length;
  const currentScreens = pages.filter((page) => DEVICE_TYPES.includes(page.type)).length;
  row("screens", "画面のボードの数 (phone・pc)", targetScreens, currentScreens, targetScreens === currentScreens);

  const labels = isPlainObject(profile.materials) ? profile.materials : {};
  const target = targetMaterials(profile.pages);
  const current = currentMaterials(boards);
  const missing = [];
  for (const key of MATERIAL_KEYS) {
    const same = target[key] === current[key];
    row(key, typeof labels[key] === "string" ? labels[key] : key, target[key], current[key], same);
    if (!same) missing.push(key);
  }

  const measures = readMeasures(base, pages);
  if (measures.chars.size) {
    const targetChars = new Map();
    for (const page of profile.pages) if (Number.isFinite(page.text_chars)) push(targetChars, page.type, page.text_chars);
    for (const type of PAGE_TYPES) {
      if (!targetChars.has(type) && !measures.chars.has(type)) continue;
      row(`text_chars.${type}`, `説明の字数: ${TYPE_LABEL[type]} (並べるだけ。字数は合わせない)`,
        targetChars.get(type) ?? [], measures.chars.get(type) ?? [], null);
    }
  }

  const targetFont = Number.isFinite(profile.font_px_min) ? profile.font_px_min : null;
  const currentFont = measures.font;
  row("font_px_min", "いちばん小さい文字 (px。基準点より小さければ差)", targetFont, currentFont,
    targetFont === null || currentFont === null ? null : currentFont >= targetFont);

  const invalid = boards.flatMap((board) => board.invalid.map((item) => ({ no: board.no, ...item })));
  return {
    comparison: "structure-only",
    fidelity: { status: "not-assessed", required: ["meaning", "reference-version", "scope", "visual"] },
    status: rows.some((r) => r.same === false) || invalid.length ? "diff" :
      measures.unavailable.length || currentFont === null ? "incomplete" : "same",
    invalid,
    measurements: { status: measures.unavailable.length || currentFont === null ? "incomplete" : "current", unavailable: measures.unavailable },
    profile: toPosix(realPath(profileFile)),
    dir: toPosix(realPath(base)),
    rows,
    missing,
  };
}

function show(value) {
  if (Array.isArray(value)) return value.length ? value.join(" ") : "-";
  return value === null || value === undefined ? "-" : String(value);
}

export async function main(argv) {
  const { options } = parseOptions(argv, { dir: "string", profile: "string", quiet: "boolean" });
  if (!options.dir) throw new UsageError("--dir を指定してください (打ち合わせ資料フォルダ)");
  const base = expandHome(options.dir);
  if (!isDir(base)) throw new UsageError(`フォルダがありません: ${base}`);
  if (!isFile(path.join(base, "briefing.json"))) {
    throw new UsageError(`briefing.json がありません (先に build-briefing-scaffold.mjs init): ${base}`);
  }
  const profileFile = path.resolve(options.profile ? expandHome(options.profile) : PROFILE_PATH);
  const result = compareProfile(base, loadProfile(profileFile), profileFile);
  writeJson(path.join(base, "_check", "profile.json"), result);
  const diffs = result.rows.filter((r) => r.same === false);
  if (diffs.length) {
    const lines = diffs.map((r) => `diff  ${r.key} ${r.label}: 基準点 ${show(r.target)} / 今回 ${show(r.current)}`);
    process.stderr.write(`${lines.join("\n")}\n`);
  }
  const quietLine = `profile: ${result.status} 差 ${diffs.length} 行 / そろっていない判断材料 ` +
    `${result.missing.length ? result.missing.join(", ") : "なし"} / 無効 ${result.invalid.length} / 未計測等 ${result.measurements.unavailable.length} (構造比較のみ)`;
  emitResult(result, options.quiet ? quietLine : null);
  return EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
