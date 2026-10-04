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
 * 再 init の配色は既存 briefing.json を使う。配色の変更は briefing.json を直してから --refresh-css を実行する。
 *
 * 配色: _src/tokens.css は、ボードの言葉 (assets/css/board-tokens.css)、標準カラー (jp-web-design の写し
 *       assets/css/vendor/standard-color-system.css)、案件の上書きの順につないで作る (scripts/lib/palette.mjs)。
 *       --palette standard (既定) なら上書きは無い。--palette <css> の CSS は標準カラーへの上書きで、
 *       基本色 (--p-*) だけを書けば役割はすべてそれに付いてくる。標準カラーにもボードにも無い名前があれば注意を出す。
 *       配色の正は briefing.json の palette。既にあれば --palette を省いてもその値で作り、--palette と違えば止める (exit 2)。
 *       配色を変えるときは briefing.json の palette を直し、--refresh-css を付けて回し直す。palette は materials と同じく
 *       出力フォルダからの相対で書く。作り直さなかった CSS がいまの palette と plugin から作るものと違えば stale_css に並べる。
 *       tokens.css を作る・作り直すときは、何かを書く前に scripts/lib/design-tokens.mjs で確かめ、だめなら何も書かずに止める (exit 2)。
 *       palette が指す CSS が無くなっていても、--refresh-css を付けず tokens.css もあれば、tokens.css はそのまま残す (skipped)。
 *
 * 使い方:
 *   node scripts/build-briefing-scaffold.mjs init --materials <素材フォルダ> --title <タイトル>
 *        [--out <dir>] [--palette standard|<css>] [--data-policy source|masked] [--date YYYY-MM-DD] [--refresh-css] [--quiet]
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
import { BOARD_TOKENS, STANDARD_PALETTE, composeTokens, readOverlay, unknownOverlayNames } from "./lib/palette.mjs";
import { hearingTemplateValues } from "./lib/hearing-catalog.mjs";
import { validateDesignTokens } from "./lib/design-tokens.mjs";

const USAGE = `
使い方:
  build-briefing-scaffold.mjs init --materials <素材フォルダ> --title <タイトル> [--out <dir>] [--palette standard|<css>] [--data-policy source|masked] [--date YYYY-MM-DD] [--refresh-css] [--quiet]
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

/**
 * 配色を決める。briefing.json が既にあれば、その palette を正とする。init は briefing.json を書き換えないので、
 * 別の値で tokens.css を作ると記録と実物がずれる。--palette は初めて作るときの値で、記録と違えば止める。
 * 返り値の value は briefing.json に書く値、overlay は上書きの CSS の実パス (standard なら null)。
 * 記録した CSS が見つからなければ lost に記録の値が入る (overlay は null)。
 */
function resolvePalette(options, out) {
  const recorded = recordedPalette(out);
  const given = options.palette === undefined ? undefined : normalizePalette(options.palette, process.cwd());
  if (recorded && given && recorded.value !== given.value) {
    throw new UsageError(
      `briefing.json の palette (${recorded.value}) と --palette (${given.value}) が違います。配色を変えるときは briefing.json の palette を直し、--refresh-css を付けて init を回し直してください`,
    );
  }
  if (recorded || given) return recorded || given;
  const fallback = loadThresholds().palette_default;
  if (!fallback) throw new ToolMissing(`しきい値 palette_default がありません: ${THRESHOLDS_PATH}`);
  return normalizePalette(fallback, process.cwd());
}

/** palette の値を、briefing.json に書く形にそろえる。standard ならキットの標準カラーだけ。それ以外は上書きの CSS の場所 (base からの相対も可)。 */
function normalizePalette(palette, base) {
  if (palette === STANDARD_PALETTE.name) return { value: STANDARD_PALETTE.name, overlay: null };
  const file = path.resolve(base, expandHome(palette));
  if (!isFile(file)) throw new UsageError(`配色の CSS がありません: ${palette}`);
  const overlay = realPath(file);
  return { value: toPosix(overlay), overlay };
}

/** 出力フォルダに既にある briefing.json の palette。briefing.json が無いか palette が書かれていなければ undefined。 */
function recordedPalette(out) {
  const file = path.join(out, "briefing.json");
  if (!isFile(file)) return undefined;
  let briefing;
  try {
    briefing = JSON.parse(readText(file));
  } catch (error) {
    throw new UsageError(`briefing.json が JSON として読めません: ${error.message}`);
  }
  if (!briefing || typeof briefing !== "object" || Array.isArray(briefing)) {
    throw new UsageError("briefing.json は案件の設定を持つオブジェクトにします");
  }
  const { palette } = briefing;
  if (typeof palette !== "string" || !palette) return undefined;
  try {
    return normalizePalette(palette, out);
  } catch (error) {
    if (!(error instanceof UsageError)) throw error;
    // 指す CSS が無い。既存の tokens.css を残すか止めるかは、作り直すかどうかで cmdInit が決める
    return { value: toPosix(path.resolve(out, expandHome(palette))), overlay: null, lost: palette };
  }
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
  const palette = resolvePalette(options, out);
  const overlaySrc = palette.overlay;
  const refreshCss = Boolean(options["refresh-css"]);
  const tokensDest = path.join(out, "_src", "tokens.css");
  // 元の配色 CSS が動いていても、配った資料を再 init するだけなら既存の tokens.css を守る。作り直すときだけ止める
  const keepTokens = Boolean(palette.lost) && !refreshCss && existsSync(tokensDest);
  if (palette.lost && !keepTokens) {
    throw new UsageError(`briefing.json の palette が指す配色の CSS がありません: ${palette.lost} (相対の場所は briefing.json のあるフォルダから数えます)`);
  }
  // tokens.css を書くなら、何かを書く前に確かめる。不正な上書きで既存の資料を変えない
  const tokensNeeds = [BOARD_TOKENS, STANDARD_PALETTE.vendor];
  const tokensText = keepTokens || !tokensNeeds.every(isFile) ? undefined : composeTokens(overlaySrc ? readOverlay(overlaySrc) : undefined);
  if (tokensText !== undefined && (refreshCss || !existsSync(tokensDest))) {
    const errors = validateDesignTokens(tokensText);
    if (errors.length) throw new UsageError(`配色の CSS を確認してください: ${errors.join("; ")}`);
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
    palette: overlaySrc ? relPosix(overlaySrc, outResolved) : STANDARD_PALETTE.name,
    materials: relPosix(realPath(materials), outResolved),
    data_policy: dataPolicy,
    book: { include_hearing: false },
    pages: [],
  };
  writeNew(path.join(out, "briefing.json"), `${JSON.stringify(briefing, null, 2)}\n`, created, skipped, out);

  const values = { TITLE: title, DATE: date, VERSION: FIRST_VERSION, ...hearingTemplateValues() };
  for (const [tmplName, docName] of DOC_TEMPLATES) {
    const tmpl = path.join(TEMPLATES, tmplName);
    if (!isFile(tmpl)) {
      missing.push(pluginRelative(tmpl));
      continue;
    }
    const text = readText(tmpl).replace(PLACEHOLDER, (whole, key) => values[key] ?? whole);
    writeNew(path.join(out, docName), text, created, skipped, out);
  }

  // tokens.css はボードの言葉・標準カラー・案件の上書きをつないで作り (scripts/lib/palette.mjs)、common.css はそのまま写す
  const commonCss = path.join(CSS_DIR, "common.css");
  const cssOutputs = [
    { needs: tokensNeeds, dest: tokensDest, text: () => tokensText, keep: keepTokens },
    { needs: [commonCss], dest: path.join(out, "_src", "common.css"), text: () => readText(commonCss) },
  ];
  // 作り直さなかった CSS が、いまの palette と plugin から作るものと違えば知らせる (同じ入力からは同じバイト列になる)
  const staleCss = [];
  for (const { needs, dest, text, keep } of cssOutputs) {
    if (keep) {
      skipped.push(relPosix(dest, out));
      continue;
    }
    const lacking = needs.filter((file) => !isFile(file));
    if (lacking.length) {
      missing.push(...lacking.map(pluginRelative));
      continue;
    }
    const expected = text();
    if (!refreshCss && isFile(dest) && readText(dest) !== expected) staleCss.push(relPosix(dest, out));
    writeNew(dest, expected, created, skipped, out, refreshCss);
  }
  if (staleCss.length) process.stderr.write(`注意: ${staleCss.join(" と ")} が、いまの palette と plugin から作るものと違います。--refresh-css を付けて回し直してください\n`);
  const unknownNames = overlaySrc ? unknownOverlayNames(readText(overlaySrc)) : [];
  if (unknownNames.length) process.stderr.write(`注意: 配色の CSS に、標準カラーにもボードにも無い名前があります (綴りを確かめてください): ${unknownNames.join(" ")}\n`);

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
    stale_css: staleCss,
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
