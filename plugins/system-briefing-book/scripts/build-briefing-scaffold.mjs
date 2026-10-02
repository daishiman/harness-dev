#!/usr/bin/env node
/**
 * build-briefing-scaffold — 打ち合わせ資料の雛形を作る。
 *
 * init   : 出力フォルダ、briefing.json (pages は空、data_policy は --data-policy)、ヒアリング.md・要件定義.md・仕様書.md・変更点.md、
 *          _src/tokens.css・_src/common.css・_src/assets/・_check/ を作り、素材フォルダを走査して
 *          _check/materials.json に種類別の一覧を書く。
 * boards : briefing.json の pages のうち _src/<file> が無いものを assets/templates/board-<type>.html から作る。
 *          data_policy が masked なら meta に「例です」の札 (.sample-flag) を置き、source なら置かない。
 *
 * どちらも既存ファイルは上書きしない (skipped に並べる)。init の --refresh-css だけは CSS 2 つを上書きする。
 *
 * 使い方:
 *   node scripts/build-briefing-scaffold.mjs init --materials <素材フォルダ> --title <タイトル>
 *        [--out <dir>] [--palette hiraga|<css>] [--data-policy source|masked] [--date YYYY-MM-DD] [--refresh-css] [--quiet]
 *   node scripts/build-briefing-scaffold.mjs boards --dir <打ち合わせ資料> [--quiet]
 *
 * 書く場所: init は --out (既定 <素材フォルダ>/打ち合わせ資料) の配下、boards は --dir/_src の配下だけ。
 * stdout: JSON {status, command, out, created[], skipped[], ...} (--quiet で要約 1 行)
 * exit: 0=成功 / 1=雛形が足りないなど作れないものがある / 2=使い方の誤り / 3=Node が古い・しきい値のファイルが読めない
 */
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

import {
  CSS_DIR,
  DATA_POLICIES,
  FILE_RE,
  OUT_DIR_NAME,
  PAGE_TYPES,
  PLUGIN_ROOT,
  TEMPLATES,
  THRESHOLDS_PATH,
  escapeHtml,
  expandHome,
  isDir,
  isFile,
  loadThresholds,
  readText,
  realPath,
  relPosix,
  scanMaterials,
  toPosix,
  todayIso,
  writeJson,
} from "./lib/briefing-files.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";

const USAGE = `
使い方:
  build-briefing-scaffold.mjs init --materials <素材フォルダ> --title <タイトル> [--out <dir>] [--palette hiraga|<css>] [--data-policy source|masked] [--date YYYY-MM-DD] [--refresh-css] [--quiet]
  build-briefing-scaffold.mjs boards --dir <打ち合わせ資料> [--quiet]
`;

export const DEFAULT_READERS = Object.freeze(["現場の担当者", "発注側の責任者", "開発する人"]);
export const DOC_TEMPLATES = Object.freeze([
  ["hearing.md.tmpl", "ヒアリング.md"],
  ["requirements.md.tmpl", "要件定義.md"],
  ["spec.md.tmpl", "仕様書.md"],
  ["changes.md.tmpl", "変更点.md"],
]);
export const FIRST_VERSION = "v0.1";
// kicker は「区分 ・ 順番」。h1 (ページの題) と同じ言葉にしない (render-board-png の KICKER-SAME)
export const KICKERS = Object.freeze({
  overview: "はじめに",
  "screen-map": "画面 ・ 全体",
  future: "これから",
});
const DEVICE_LABEL = { phone: "スマホ", pc: "PC" };
const HIDDEN_TYPES = Object.freeze(["data-map", "mechanism"]);

const PLACEHOLDER = /\{\{([A-Z_]+)\}\}/g;
/** data_policy が masked のときに meta の {{SAMPLE_FLAG}} に入れる札 (HTML のまま入れる) */
const SAMPLE_FLAG_HTML = '<br><span class="sample-flag">画面の中の名前と値は例です</span>';

function writeNew(file, text, created, skipped, base, overwrite = false) {
  const rel = relPosix(file, base);
  if (existsSync(file) && !overwrite) {
    skipped.push(rel);
    return;
  }
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, text, "utf8");
  created.push(rel);
}

function pluginRelative(file) {
  const rel = path.relative(PLUGIN_ROOT, file);
  return rel && !rel.startsWith("..") && !path.isAbsolute(rel) ? toPosix(rel) : toPosix(file);
}

function cmdInit(options) {
  for (const name of ["materials", "title"]) {
    if (options[name] === undefined) throw new UsageError(`--${name} を指定してください`);
  }
  const materials = expandHome(options.materials);
  if (!isDir(materials)) throw new UsageError(`素材フォルダがありません: ${materials}`);
  const title = (options.title || "").trim();
  if (!title) throw new UsageError("--title が空です");
  const date = options.date || todayIso();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new UsageError(`--date は YYYY-MM-DD で指定します: ${date}`);
  const dataPolicy = options["data-policy"] ?? "source";
  if (!DATA_POLICIES.includes(dataPolicy)) throw new UsageError(`--data-policy は source か masked で指定します: ${dataPolicy}`);
  const out = options.out ? expandHome(options.out) : path.join(materials, OUT_DIR_NAME);
  const palette = options.palette || loadThresholds().palette_default;
  if (!palette) throw new ToolMissing(`しきい値 palette_default がありません: ${THRESHOLDS_PATH}`);
  let paletteSrc;
  let paletteValue;
  if (palette === "hiraga") {
    paletteSrc = path.join(CSS_DIR, "tokens-hiraga.css");
    paletteValue = "hiraga";
  } else {
    paletteSrc = realPath(expandHome(palette));
    if (!isFile(paletteSrc)) throw new UsageError(`配色の CSS がありません: ${palette}`);
    paletteValue = toPosix(paletteSrc);
  }

  const created = [];
  const skipped = [];
  const missing = [];
  for (const sub of ["_src", "_src/assets", "_check"]) mkdirSync(path.join(out, sub), { recursive: true });
  const outResolved = realPath(out);

  const briefing = {
    schema: "briefing-v1",
    title,
    readers: [...DEFAULT_READERS],
    palette: paletteValue,
    materials: relPosix(realPath(materials), outResolved),
    data_policy: dataPolicy,
    book: { include_hearing: false },
    pages: [],
  };
  writeNew(path.join(out, "briefing.json"), `${JSON.stringify(briefing, null, 2)}\n`, created, skipped, out);

  const values = { TITLE: title, DATE: date, VERSION: FIRST_VERSION };
  for (const [tmplName, docName] of DOC_TEMPLATES) {
    const tmpl = path.join(TEMPLATES, tmplName);
    if (!isFile(tmpl)) {
      missing.push(pluginRelative(tmpl));
      continue;
    }
    const text = readText(tmpl).replace(PLACEHOLDER, (whole, key) => values[key] ?? whole);
    writeNew(path.join(out, docName), text, created, skipped, out);
  }

  const cssPairs = [
    [paletteSrc, path.join(out, "_src", "tokens.css")],
    [path.join(CSS_DIR, "common.css"), path.join(out, "_src", "common.css")],
  ];
  for (const [src, dest] of cssPairs) {
    if (!isFile(src)) {
      missing.push(pluginRelative(src));
      continue;
    }
    writeNew(dest, readText(src), created, skipped, out, Boolean(options["refresh-css"]));
  }

  const report = scanMaterials(materials, out);
  writeJson(path.join(out, "_check", "materials.json"), report);
  for (const name of report.needs_csv) process.stderr.write(`注意: Excel などは CSV に書き出してから読みます: ${name}\n`);
  for (const name of missing) process.stderr.write(`雛形がありません: ${name}\n`);
  const result = {
    status: missing.length ? "ng" : "ok",
    command: "init",
    out: toPosix(outResolved),
    created,
    skipped,
    missing_templates: missing,
    materials: { counts: report.counts, needs_csv: report.needs_csv, truncated: report.truncated },
  };
  return [missing.length ? EXIT.FOUND : EXIT.OK, result];
}

/**
 * ボード上の小見出し (区分 ・ 順番)。
 * phone/pc は「画面 i / n ・ スマホ」、見えない部分 (data-map・mechanism) は「見えない部分 i / n」
 * (1 枚だけなら番号なし)、それ以外は型ごとの決まり文句。
 */
export function kickerFor(page, pages) {
  const kind = page.type;
  if (Object.hasOwn(DEVICE_LABEL, kind)) {
    const devicePages = pages.filter((p) => Object.hasOwn(DEVICE_LABEL, p.type)).map((p) => p.no);
    return `画面 ${devicePages.indexOf(page.no) + 1} / ${devicePages.length} ・ ${DEVICE_LABEL[kind]}`;
  }
  if (HIDDEN_TYPES.includes(kind)) {
    const hiddenPages = pages.filter((p) => HIDDEN_TYPES.includes(p.type)).map((p) => p.no);
    if (hiddenPages.length < 2) return "見えない部分";
    return `見えない部分 ${hiddenPages.indexOf(page.no) + 1} / ${hiddenPages.length}`;
  }
  return KICKERS[kind] ?? "";
}

function cmdBoards(options) {
  if (options.dir === undefined) throw new UsageError("--dir を指定してください");
  const out = expandHome(options.dir);
  const briefingPath = path.join(out, "briefing.json");
  if (!isFile(briefingPath)) throw new UsageError(`briefing.json がありません (先に init を実行): ${briefingPath}`);
  let briefing;
  try {
    briefing = JSON.parse(readText(briefingPath));
  } catch (error) {
    return [EXIT.FOUND, { status: "ng", command: "boards", errors: [`briefing.json が JSON として読めません: ${error.message}`] }];
  }
  const pages = (Array.isArray(briefing?.pages) ? briefing.pages : []).filter((p) => p && typeof p === "object");
  const title = String(briefing?.title ?? "");
  // 札は HTML のまま入れる (エスケープしない)。data_policy が不正なら置換子を残す (unreplaced に出る)
  const policy = briefing?.data_policy;
  const rawValues = DATA_POLICIES.includes(policy) ? { SAMPLE_FLAG: policy === "masked" ? SAMPLE_FLAG_HTML : "" } : {};

  const created = [];
  const skipped = [];
  const errors = [];
  const leftovers = [];
  for (const page of pages) {
    const no = String(page.no ?? "");
    const file = String(page.file ?? "");
    const kind = page.type;
    const match = FILE_RE.exec(file);
    if (!match || match[1] !== no) {
      errors.push(`pages の file は '<no>_<slug>.html' (slug は英小文字と数字と -) にします: no=${no} file=${file}`);
      continue;
    }
    if (!PAGE_TYPES.includes(kind)) {
      errors.push(`pages の type が不明です: ${file} type=${kind}`);
      continue;
    }
    const dest = path.join(out, "_src", file);
    if (existsSync(dest)) {
      skipped.push(`_src/${file}`);
      continue;
    }
    const tmpl = path.join(TEMPLATES, `board-${kind}.html`);
    if (!isFile(tmpl)) {
      errors.push(`ボードの雛形がありません: ${pluginRelative(tmpl)}`);
      continue;
    }
    const values = {
      NO: no,
      TITLE: String(page.title ?? ""),
      LEAD: String(page.message ?? ""),
      PROJECT: title,
      SCREENS: (Array.isArray(page.screens) ? page.screens : []).join(" "),
      KICKER: kickerFor(page, pages),
    };
    const text = readText(tmpl).replace(PLACEHOLDER, (whole, key) => {
      if (Object.hasOwn(values, key)) return escapeHtml(values[key]);
      return Object.hasOwn(rawValues, key) ? rawValues[key] : whole;
    });
    mkdirSync(path.dirname(dest), { recursive: true });
    writeFileSync(dest, text, "utf8");
    created.push(`_src/${file}`);
    const rest = [...new Set(text.match(PLACEHOLDER) || [])].sort();
    if (rest.length) leftovers.push(`_src/${file}: ${rest.join(" ")}`);
  }
  for (const message of errors) process.stderr.write(`${message}\n`);
  const result = {
    status: errors.length ? "ng" : "ok",
    command: "boards",
    out: toPosix(realPath(out)),
    created,
    skipped,
    errors,
    unreplaced: leftovers,
  };
  return [errors.length ? EXIT.FOUND : EXIT.OK, result];
}

export async function main(argv) {
  const [command, ...rest] = argv;
  let code;
  let result;
  if (command === "init") {
    const { options } = parseOptions(rest, {
      materials: "string", title: "string", out: "string", palette: "string", "data-policy": "string", date: "string",
      "refresh-css": "boolean", quiet: "boolean",
    });
    [code, result] = cmdInit(options);
    emitQuiet(result, options.quiet);
  } else if (command === "boards") {
    const { options } = parseOptions(rest, { dir: "string", quiet: "boolean" });
    [code, result] = cmdBoards(options);
    emitQuiet(result, options.quiet);
  } else {
    throw new UsageError(`最初の引数は init か boards です${command ? `: ${command}` : ""}`);
  }
  return code;
}

function emitQuiet(result, quiet) {
  const line = `${result.command}: ${result.status} 作成 ${(result.created || []).length} 件 / 既存 ${(result.skipped || []).length} 件`;
  emitResult(result, quiet ? line : null);
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
