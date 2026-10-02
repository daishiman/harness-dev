#!/usr/bin/env node
/**
 * build-briefing-book — 打ち合わせ資料の文書 (Markdown) とボードの画像を、1 ファイルの HTML にまとめる。
 *
 * ページの順: 表紙 → 変更点 (中身があるとき) → ボード (briefing.json の pages 順) → 要件定義書 → 仕様書
 * → ヒアリング記録 (briefing.json の book.include_hearing が true のとき)。
 *
 * ボードの画像は render-board-png.mjs が書いた _src/book/NN_<slug>.webp を data: URI で埋め込む。
 * WebP が無い・古い・寸法不一致・render receipt と異なるときは PNG を埋め込み warn にする (exit は 0)。
 * Markdown のローカル画像と既存 data URI (PNG/JPEG/WebP) を保持し、読めないときは alt と DOC-IMAGE 警告を残す。
 * receipt のない画像と文書画像は IMAGE-UNVERIFIED 警告を残す。内部デコードはブラウザでの表示確認が必要。
 * render の品質警告は BOARD-CHECK-WARN と status=warn に引き継ぐ (既存の exit 0 / 書出し許容は維持)。
 * 画像の下にはボード HTML の注記 (できること / しくみ / 決めること) を文字で並べる。
 * 文書のページは lib/doc-report.mjs で、カードや区切りを使ったレポートの形に描く (Markdown は正本のまま。
 * 見分け方と部品はそのファイルの先頭の説明)。文の中の F01・S01・「02 のボード」などはリンクになり、
 * 行き先がまとめに無いものは文字に戻す。
 * JavaScript が動かなくても全ページが縦に並んで読める。JS は 1 ページずつの表示とキー操作を足すだけ。
 * ブラウザも npm の部品も使わない (Node だけで動く)。
 *
 * 止まる条件 (exit 1、まとめ HTML は書かない):
 * - 要件定義.md と 仕様書.md の「版:」が違う (VERSION-MISMATCH) / どちらかに無い (VERSION-MISSING)
 * - ボードの PNG が無い (PNG-MISSING)、ボード HTML・tokens.css・common.css・参照画像より古い (STALE-PNG、--allow-stale で warn)
 * - 直前の render-board-png.mjs の検査で、今と同じボード HTML が ng だった (BOARD-CHECK-NG)
 * - PNG の大きさが assets/data/quality-thresholds.json の board (width・height・scale) と合わない (PNG-SIZE)
 * - render が記録した PNG ハッシュと異なる (PNG-HASH)。旧 receipt のない画像は従来のヘッダ検査のみ
 * - 出来上がった HTML に外部参照 (http・https・//) やローカル参照が残った (EXTERNAL-REF / LOCAL-REF)
 *
 * 使い方:
 *   node scripts/build-briefing-book.mjs --dir <打ち合わせ資料> [--out <file.html>] [--allow-stale] [--quiet]
 *
 * 書く場所: <dir>/<タイトル>_打ち合わせ資料.html (または --out。error が 0 件のときだけ) と <dir>/_check/book.json。
 * stdout: JSON {schema, status, out, written, version, summary, errors[], warnings[], ...} (--quiet で要約 1 行)
 * exit: 0=できた (warn だけなら 0) / 1=検査で問題 / 2=使い方の誤り / 3=Node が古い・まとめの雛形が無い・しきい値のファイルが読めない
 */
import { readFileSync, statSync } from "node:fs";
import path from "node:path";

import {
  DATA_POLICIES,
  FILE_RE,
  TEMPLATES,
  TYPE_LABEL,
  escapeHtml as esc,
  expandHome,
  isDir,
  isFile,
  loadThresholds,
  readText,
  realPath,
  safeFilename,
  sha256,
  splitLines,
  threshold,
  toPosix,
  writeAtomic,
  writeJson,
} from "./lib/briefing-files.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";
import { classesOf, iterNodes, parseHtmlTree, textOf } from "./lib/html-tokens.mjs";
import { imageSize, imageSizeOfFile } from "./lib/image-size.mjs";
import { dependencyReceipt, htmlRefs, localRef, externalRef } from "./lib/resource-refs.mjs";
import { convertDoc, resolveRefs } from "./lib/doc-report.mjs";
import { composeStandardTokens } from "./lib/palette.mjs";

const USAGE = `
使い方:
  build-briefing-book.mjs --dir <打ち合わせ資料> [--out <file.html>] [--allow-stale] [--quiet]
`;

export const TEMPLATE = path.join(TEMPLATES, "book.html");
const REQ_MD = "要件定義.md";
const SPEC_MD = "仕様書.md";
const CHANGES_MD = "変更点.md";
const HEARING_MD = "ヒアリング.md";
export const BOOK_SUFFIX = "_打ち合わせ資料.html";
// PNG と WebP は同じ描画から続けて書くので、書く順によっては WebP が少しだけ古く見える。この幅までは同じ描画とみなす
const WEBP_SLACK_NS = 1_000_000_000n;

export const KIND_LABEL = Object.freeze({ can: "できること", how: "しくみ", ask: "決めること" });
// 表紙の 1 文 (briefing.json の data_policy ごと)。無い・不正なときは素材のままかもしれないので、source の文 (扱いの注意) を出す
const COVER_DATA_NOTE = Object.freeze({
  source: "素材の名前と数字をそのまま載せています。素材をくれた方と、作る側の中だけで扱ってください。",
  masked: "ボードの画面の中の名前と値は例です。",
});
const DOCS = [
  // [page id, 見出しの id の頭, ファイル, 目次での名前]
  ["p-req", "req", REQ_MD, "要件定義書"],
  ["p-spec", "spec", SPEC_MD, "仕様書"],
  ["p-hear", "hear", HEARING_MD, "ヒアリング記録"],
];

const VERSION_RE = /^版\s*[:：]\s*(v\d+\.\d+)\s*$/;
const DATE_RE = /^更新日\s*[:：]\s*(\d{4}-\d{2}-\d{2})\s*$/;
const CHANGES_VERSION_RE = /^##\s+v\d+\.\d+/m;
const QUESTION_ROW_RE = /^\|\s*Q\d{2,}\s*\|.*$/gm;
// 誰に聞くか (最後の列) が「決定 (v0.2)」の行は、もう決まったので数えない
const DECIDED_ROW_RE = /\|\s*決定\s*[(（][^|]*\|\s*$/;
const PLACEHOLDER_RE = /\{\{([A-Z_]+)\}\}/g;
const ID_ATTR_RE = /\sid="([^"]+)"/g;

class Report {
  errors = [];
  warnings = [];

  err(code, file, message) {
    this.errors.push({ code, file, message });
  }

  warn(code, file, message) {
    this.warnings.push({ code, file, message });
  }
}

/** Python の str(x or "") と同じ。null・空文字・0 は "" にする。 */
function show(value) {
  return value ? String(value) : "";
}

function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** 更新時刻 (ナノ秒、bigint)。無ければ null。mtimeMs の小数では続けて書いたファイルの前後が逆になることがある。 */
function mtimeNs(file) {
  try {
    return statSync(file, { bigint: true }).mtimeNs;
  } catch {
    return null;
  }
}

// ── ボード HTML の読み取り ───────────────────────────────

function firstBold(node) {
  for (const child of iterNodes(node)) if (child.tag === "b") return child;
  return null;
}

function subText(node) {
  return [...iterNodes(node)].filter((n) => classesOf(n).has("sub")).map(textOf).join(" ");
}

function childItems(node) {
  return node.children.filter((c) => typeof c !== "string" && c.tag === "li");
}

/** ボード HTML から、注記 (aside.notes ol.marks li) を取り出す。 */
export function extractBoardText(text) {
  const root = parseHtmlTree(text);
  const all = [...iterNodes(root)];
  const notes = [];
  for (const aside of all.filter((n) => n.tag === "aside" && classesOf(n).has("notes"))) {
    for (const ol of [...iterNodes(aside)].filter((n) => n.tag === "ol" && classesOf(n).has("marks"))) {
      for (const li of childItems(ol)) {
        const bold = firstBold(li);
        notes.push({
          mark: (li.attrs["data-mark"] || "").trim(),
          kind: (li.attrs["data-kind"] || "").trim(),
          title: textOf(bold ?? li),
          q: [...iterNodes(li)].filter((n) => classesOf(n).has("q")).map(textOf),
          sub: subText(li),
        });
      }
    }
  }
  return { notes };
}

/** Local resources in actual HTML attributes and CSS, excluding displayed examples. */
export function localRefs(text) {
  return [...new Set(htmlRefs(text).map(({ value }) => localRef(value)).filter(Boolean))].sort();
}

// ── 文書 ───────────────────────────────

export function docMeta(text) {
  const meta = { version: null, updated: null };
  for (const raw of splitLines(text).slice(0, 8)) {
    const line = raw.trim();
    const version = VERSION_RE.exec(line);
    if (version && !meta.version) meta.version = version[1];
    const date = DATE_RE.exec(line);
    if (date && !meta.updated) meta.updated = date[1];
  }
  return meta;
}

// ── ページを組む ───────────────────────────────

function pageNav(pages, i) {
  let prev = "";
  let next = "";
  if (i > 0) {
    const p = pages[i - 1];
    prev = `<a class="prev" href="#${p.id}" rel="prev">← ${esc(p.nav)}</a>`;
  }
  if (i < pages.length - 1) {
    const p = pages[i + 1];
    next = `<a class="next" href="#${p.id}" rel="next">${esc(p.nav)} →</a>`;
  }
  return `<nav class="pg-nav" aria-label="ページ送り">${prev}${next}</nav>`;
}

function renderNotes(notes) {
  if (!notes.length) return "";
  const parts = ['<div class="board-notes">', "<h3>ボードの注記</h3><ol>"];
  for (const note of notes) {
    const kind = Object.hasOwn(KIND_LABEL, note.kind) ? note.kind : "";
    const mark = note.mark ? `<span class="mark">${esc(note.mark)}</span>` : '<span class="mark none"></span>';
    const label = `<span class="kind ${kind}">${KIND_LABEL[kind] ?? "注記"}</span>`;
    const qs = note.q.map((q) => `<span class="q">${esc(q)}</span>`).join("");
    const sub = note.sub ? `<span class="sub">${esc(note.sub)}</span>` : "";
    parts.push(`<li>${mark}${label}<span class="txt"><b>${esc(note.title)}</b>${qs}${sub}</span></li>`);
  }
  parts.push("</ol></div>");
  return parts.join("");
}

function renderCover(ctx, pages, nav) {
  const boards = pages.filter((p) => p.kind === "board");
  const cards = ctx.readers.map((reader) => {
    const mine = boards.filter((p) => p.reader === reader);
    const items = mine.map((p) => `<li><a href="#${p.id}">${esc(p.no)} ${esc(p.title)}</a></li>`).join("") || "<li>ボードを順に見る</li>";
    return `<div class="reader-card"><h4>${esc(reader)}</h4><ul>${items}</ul></div>`;
  });
  const q = ctx.questions;
  // 行き先は要件定義書の「決めること」の節 (見つからなければ要件定義書の頭)
  const reqToc = pages.find((p) => p.id === "p-req")?.toc ?? [];
  const qLink = `<a href="#${(reqToc.find(([, label]) => label.includes("決めること")) ?? ["p-req"])[0]}">要件定義書の「決めること」</a>`;
  const qLine = q === 0
    ? `「決めること」は、すべて決まりました。答えは ${qLink}にあります。`
    : `「決めること」は ${q} 件あります。ボードの右の「決めること」と、${qLink}にまとめています。`;
  const chgLine = pages.some((p) => p.id === "p-chg") ? '<li>前の版からの違いは <a href="#p-chg">変更点</a> にあります。</li>' : "";
  const firstBoard = boards.length ? boards[0].id : "p-req";
  return `<section class="page cover" id="p-cover">
<div class="page-head"><span class="kind">打ち合わせ資料</span></div>
<h1>${esc(ctx.title)}</h1>
<p class="sub">要件定義書・仕様書・画面のボードをまとめた資料です。</p>
<div class="facts"><span>版 <b>${esc(ctx.version || "-")}</b></span><span>更新日 <b>${esc(ctx.updated || "-")}</b></span><span>ボード <b>${boards.length}</b> 枚</span><span>決めること <b>${q}</b> 件</span></div>
<h3>読み方</h3>
<ol class="howto">
<li><a href="#${firstBoard}">ボード</a>を順に見て、全体をつかむ。注記は「できること」「しくみ」「決めること」の 3 種類です。</li>
<li>ボードの画像を押すと大きく表示します。戻るときは「閉じる」を押します。</li>
<li>細かい決まりは <a href="#p-req">要件定義書</a> (何をするか) と <a href="#p-spec">仕様書</a> (どう動くか) にあります。</li>
<li>${qLine}</li>
${chgLine}
</ol>
<p class="sub">${COVER_DATA_NOTE[ctx.dataPolicy]}</p>
<h3>読む人ごとのおすすめ</h3>
<div class="readers">${cards.join("")}</div>
${nav}
</section>`;
}

function renderBoard(page, nav, [w, h]) {
  const no = page.no;
  const reader = page.reader ? `<span class="reader">主に読む人: ${esc(page.reader)}</span>` : "";
  const message = page.message ? `<p class="message">${esc(page.message)}</p>` : "";
  return `<section class="page board-page" id="b${no}">
<div class="page-head"><span class="kind">ボード ${esc(no)} ・ ${esc(TYPE_LABEL[page.type] ?? page.type)}</span><h2>${esc(page.title)}</h2>${reader}</div>
${message}
<figure class="shot" id="z${no}">
<a class="zoom" href="#z${no}"><img src="${page.dataUri}" alt="${esc(page.title)} のボード" width="${w}" height="${h}" decoding="async"></a>
<figcaption>画像を押すと大きく表示します</figcaption>
<a class="close" href="#b${no}">閉じる ×</a>
</figure>
${renderNotes(page.notes)}
${nav}
</section>`;
}

function renderDoc(page, nav) {
  return `<section class="page doc" id="${page.id}">
${page.body}
${nav}
</section>`;
}

function renderToc(pages) {
  const groups = [["はじめに", ["cover", "changes"]], ["ボード", ["board"]], ["文書", ["doc"]]];
  const parts = [];
  for (const [label, kinds] of groups) {
    const members = pages.filter((p) => kinds.includes(p.kind));
    if (!members.length) continue;
    parts.push(`<p class="grp">${label}</p><ol>`);
    for (const p of members) {
      const no = p.kind === "board" ? `<span class="no">${esc(p.no)}</span>` : "";
      const sub = p.toc?.length ? `<ol>${p.toc.map(([id, t]) => `<li><a href="#${id}">${esc(t)}</a></li>`).join("")}</ol>` : "";
      parts.push(`<li><a class="p" href="#${p.id}">${no}${esc(p.nav)}</a>${sub}</li>`);
    }
    parts.push("</ol>");
  }
  return parts.join("\n");
}

/** まとめ HTML に残った参照のうち、#・data:・mailto: 以外を拾う。where は参照のあるページの id。 */
export function scanRefs(doc) {
  return htmlRefs(doc).filter(({ value }) => value && !value.startsWith("#") && !/^(?:data|mailto):/i.test(value))
    .map(({ attr, value, where }) => ({ code: externalRef(value) ? "EXTERNAL-REF" : "LOCAL-REF", attr, value: value.slice(0, 200), where }));
}

function buildTime() {
  const epoch = process.env.SOURCE_DATE_EPOCH;
  if (epoch && /^\d+$/.test(epoch)) return new Date(Number(epoch) * 1000).toISOString().slice(0, 16).replace("T", " ");
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
}

// ── 画像 ───────────────────────────────

/**
 * 埋め込む画像を決める。まとめ用の WebP が使えればそれ、使えなければ PNG (理由を warn に足す)。
 * 返り値 {file, format, data} か、PNG も読めなければ null。
 */
function pickImage(rep, base, stem, pngPath, expected, receipt) {
  const webpPath = path.join(base, "_src", "book", `${stem}.webp`);
  const webpRel = `_src/book/${stem}.webp`;
  const redo = `render-board-png.mjs --only ${stem.slice(0, 2)} で描き直すと WebP もできます`;
  if (isFile(webpPath)) {
    const size = imageSizeOfFile(webpPath);
    const webpM = mtimeNs(webpPath);
    const pngM = mtimeNs(pngPath);
    if (!size || size.format !== "webp") {
      rep.warn("WEBP-BROKEN", webpRel, `WebP として読めないので PNG をそのまま埋め込みます。${redo}`);
    } else if (size.width !== expected[0] || size.height !== expected[1]) {
      rep.warn("WEBP-SIZE", webpRel, `WebP の寸法が ${size.width}x${size.height} のため PNG を使います。${redo}`);
    } else if (receipt?.webp_sha256 && receipt.webp_sha256 !== sha256(readFileSync(webpPath))) {
      rep.warn("WEBP-HASH", webpRel, `描画後に WebP が変わっているため PNG を使います。${redo}`);
    } else if (webpM !== null && pngM !== null && webpM + WEBP_SLACK_NS < pngM) {
      rep.warn("WEBP-OLD", webpRel, `WebP が PNG より古いので PNG をそのまま埋め込みます。${redo}`);
    } else {
      return { file: webpRel, format: "webp", mime: "image/webp", data: readFileSync(webpPath) };
    }
  } else {
    rep.warn("WEBP-MISSING", webpRel, `まとめ用の WebP が無いので PNG をそのまま埋め込みます (ファイルが大きくなります)。${redo}`);
  }
  return { file: path.basename(pngPath), format: "png", mime: "image/png", data: readFileSync(pngPath) };
}

// ── 本体 ───────────────────────────────

function readBriefing(file) {
  try {
    const data = JSON.parse(readText(file));
    if (!isPlainObject(data)) return [null, "JSON の一番外がオブジェクトではありません"];
    return [data, null];
  } catch (error) {
    return [null, error.message];
  }
}

function readBoardsJson(file) {
  try {
    const data = JSON.parse(readText(file));
    return isPlainObject(data) ? data : null;
  } catch {
    return null;
  }
}

/** 直前の検査で ng だったか。status が無い書き方なら errors の有無で決める。 */
function boardCheckFailed(entry) {
  if (entry.status !== undefined) return entry.status === "ng";
  return Array.isArray(entry.errors) && entry.errors.length > 0;
}

/** 打ち合わせ資料フォルダ base をまとめる。返り値は [終了コード, 結果]。 */
export function build(base, { out = null, allowStale = false } = {}) {
  if (!isFile(TEMPLATE)) throw new ToolMissing(`まとめの雛形がありません: ${TEMPLATE}`);
  const thresholds = loadThresholds();
  const viewSize = [threshold(thresholds, "board", "width"), threshold(thresholds, "board", "height")];
  const scale = threshold(thresholds, "board", "scale");
  const pngSize = viewSize.map((n) => Math.trunc(n * scale));
  const rep = new Report();
  const src = path.join(base, "_src");
  const checkDir = path.join(base, "_check");
  const result = { schema: "briefing-book-check-v1", dir: toPosix(base), out: null, written: false };

  const [briefing, problem] = readBriefing(path.join(base, "briefing.json"));
  if (problem !== null) {
    rep.err("BRIEFING-JSON", "briefing.json", `briefing.json を読めません: ${problem}`);
    return finish(checkDir, result, rep);
  }

  const title = show(briefing.title).trim() || path.basename(path.dirname(base)) || "打ち合わせ資料";
  const readers = (Array.isArray(briefing.readers) ? briefing.readers : []).map(show).filter((r) => r.trim());
  const pagesCfg = Array.isArray(briefing.pages) ? briefing.pages : [];
  const includeHearing = Boolean(isPlainObject(briefing.book) && briefing.book.include_hearing);
  const dataPolicy = DATA_POLICIES.includes(briefing.data_policy) ? briefing.data_policy : "source";
  if (!pagesCfg.length) rep.err("PAGES-EMPTY", "briefing.json", "pages が空です。ボードが 1 枚もありません");

  // 文書と版
  const texts = {};
  for (const name of [REQ_MD, SPEC_MD, CHANGES_MD, HEARING_MD]) {
    const file = path.join(base, name);
    if (isFile(file)) texts[name] = readText(file);
  }
  for (const name of [REQ_MD, SPEC_MD]) {
    if (!(name in texts)) rep.err("DOC-MISSING", name, `${name} がありません`);
  }
  if (includeHearing && !(HEARING_MD in texts)) {
    rep.err("DOC-MISSING", HEARING_MD, "book.include_hearing が true ですが ヒアリング.md がありません");
  }
  const reqMeta = docMeta(texts[REQ_MD] ?? "");
  const specMeta = docMeta(texts[SPEC_MD] ?? "");
  const version = reqMeta.version;
  for (const [name, meta] of [[REQ_MD, reqMeta], [SPEC_MD, specMeta]]) {
    if (name in texts && !meta.version) rep.err("VERSION-MISSING", name, "「版: vX.Y」の行がありません");
  }
  if (reqMeta.version && specMeta.version && reqMeta.version !== specMeta.version) {
    rep.err("VERSION-MISMATCH", SPEC_MD, `版がずれています: 要件定義.md は ${reqMeta.version}、仕様書.md は ${specMeta.version}`);
  }
  const updated = [reqMeta.updated, specMeta.updated].filter(Boolean).sort().at(-1) ?? null;
  result.version = version;
  result.versions = { requirements: reqMeta.version, spec: specMeta.version };

  // ボード
  const boardsJson = readBoardsJson(path.join(checkDir, "boards.json"));
  if (boardsJson === null) {
    rep.warn("BOARD-CHECK-MISSING", "_check/boards.json", "ボードの検査結果がありません。render-board-png.mjs を通したか確かめてください");
  }
  const checked = new Map();
  for (const entry of Array.isArray(boardsJson?.boards) ? boardsJson.boards : []) {
    if (isPlainObject(entry)) checked.set(String(entry.no), entry);
  }

  const boardPages = [];
  const boardStatus = [];
  const stale = [];
  const formats = new Set();
  let imageBytes = 0;
  for (const cfg of pagesCfg) {
    if (!isPlainObject(cfg)) {
      rep.err("PAGE-FORMAT", "briefing.json", "pages の要素がオブジェクトではありません");
      continue;
    }
    const no = show(cfg.no);
    const file = show(cfg.file);
    if (!/^\d{2}$/.test(no) || !FILE_RE.test(file)) {
      rep.err("PAGE-FORMAT", "briefing.json", `pages の no / file の形が違います: no=${JSON.stringify(no)} file=${JSON.stringify(file)}`);
      continue;
    }
    const stem = file.slice(0, -5);
    const htmlPath = path.join(src, file);
    const pngPath = path.join(base, `${stem}.png`);
    const status = { no, file, png: `${stem}.png`, status: "ok" };
    boardStatus.push(status);
    if (!isFile(htmlPath)) {
      rep.err("BOARD-MISSING", `_src/${file}`, "ボード HTML がありません");
      status.status = "missing";
      continue;
    }
    const htmlBytes = readFileSync(htmlPath);
    const boardHtml = htmlBytes.toString("utf8");
    if (!isFile(pngPath)) {
      rep.err("PNG-MISSING", status.png, "ボードの PNG がありません。render-board-png.mjs で作ってください");
      status.status = "missing";
      continue;
    }

    // 鮮度: PNG は、ボード HTML・CSS・ボードが読む画像のどれよりも新しいこと
    const pngM = mtimeNs(pngPath) ?? 0n;
    const dependencies = dependencyReceipt(htmlPath, base);
    const entry = checked.get(no);
    const newer = Object.keys(dependencies).filter((name) => {
      const m = mtimeNs(path.resolve(base, name));
      return m !== null && m > pngM;
    });
    if (isPlainObject(entry?.dependencies)) {
      for (const name of new Set([...Object.keys(entry.dependencies), ...Object.keys(dependencies)])) {
        if (entry.dependencies[name] !== dependencies[name] && !newer.includes(name)) newer.push(name);
      }
    }
    if (newer.length) {
      stale.push({ no, png: status.png, newer });
      status.status = "stale";
      const message = `PNG がこれより古い: ${newer.join(", ")}。render-board-png.mjs --only ${no} で描き直してください`;
      if (allowStale) rep.warn("STALE-PNG", status.png, message);
      else rep.err("STALE-PNG", status.png, message);
    }

    // 直前の検査結果
    if (boardsJson !== null) {
      if (entry === undefined) {
        rep.warn("BOARD-CHECK-MISSING", `_src/${file}`, "このボードの検査結果が boards.json にありません");
      } else if (entry.html_sha256 && entry.html_sha256 !== sha256(htmlBytes)) {
        rep.warn("BOARD-CHECK-OLD", `_src/${file}`, "検査のあとでボード HTML が変わっています。render-board-png.mjs をもう一度通してください");
      } else if (boardCheckFailed(entry)) {
        const count = Array.isArray(entry.errors) ? entry.errors.length : 0;
        rep.err("BOARD-CHECK-NG", `_src/${file}`, `直前の検査で問題が残っています (error ${count} 件)。_check/boards.json を見てください`);
      }
      // Retain the permissive missing/old-check contract, but never hide recorded quality warnings.
      if (entry?.status === "warn" || entry?.warnings?.length) {
        const warnings = Array.isArray(entry.warnings) ? entry.warnings : [];
        if (status.status === "ok") status.status = "warn";
        rep.warn("BOARD-CHECK-WARN", `_src/${file}`, `ボードの品質警告が残っています: ${warnings.map((w) => `${w?.code ?? "WARN"}: ${w?.message ?? ""}`).join("; ") || "boards.json を確認してください"}`);
      }
    }

    if (entry?.png_sha256 && entry.png_sha256 !== sha256(readFileSync(pngPath))) {
      rep.err("PNG-HASH", status.png, "描画後に PNG が変わっています。render-board-png.mjs で作り直してください");
      status.status = "broken";
      continue;
    }
    const size = imageSizeOfFile(pngPath);
    if (!size || size.format !== "png") {
      rep.err("PNG-READ", status.png, "PNG として読めません。render-board-png.mjs で作り直してください");
      status.status = "broken";
      continue;
    }
    if (size.width !== pngSize[0] || size.height !== pngSize[1]) {
      rep.err("PNG-SIZE", status.png, `大きさが ${size.width}x${size.height} です (決まりは ${pngSize[0]}x${pngSize[1]})。render-board-png.mjs で作り直してください`);
    }
    const image = pickImage(rep, base, stem, pngPath, pngSize, entry);
    if (!entry?.[`${image.format}_sha256`]) {
      rep.warn("IMAGE-UNVERIFIED", image.file, "render receipt が無いため、画像内部のデコードは未検証です。ブラウザで表示を確認するか再描画してください");
    }
    formats.add(image.format);
    imageBytes += image.data.length;
    Object.assign(status, { image: image.file, image_format: image.format, image_bytes: image.data.length });
    const extracted = extractBoardText(boardHtml);
    const pageTitle = show(cfg.title) || stem;
    boardPages.push({
      id: `b${no}`, kind: "board", no, type: show(cfg.type), title: pageTitle, nav: pageTitle,
      reader: show(cfg.reader), message: show(cfg.message),
      dataUri: `data:${image.mime};base64,${image.data.toString("base64")}`,
      notes: extracted.notes,
    });
  }

  // 文書を HTML に
  const imageHooks = (name) => ({
    imageReferenceMissing: (alt, id) => rep.warn("DOC-IMAGE", name, `画像「${alt}」の参照定義 [${id}] がありません`),
    image: (alt, url) => {
      const isData = /^data:/i.test(url);
      const ref = localRef(url);
      if (!isData && !ref) return null; // External images retain the existing alt-only behavior.
      try {
        let data, size, uri;
        if (isData) {
          const match = /^data:(image\/(?:png|jpeg|webp));base64,([a-z0-9+/]+={0,2})$/i.exec(url);
          if (!match || match[2].length % 4 !== 0) throw new Error("data URI は PNG / JPEG / WebP の base64 形式にしてください");
          data = Buffer.from(match[2], "base64");
          if (data.toString("base64") !== match[2]) throw new Error("base64 の内容が不正です");
          size = imageSize(data);
          if (!size || `image/${size.format}` !== match[1].toLowerCase()) throw new Error("data URI の画像形式と内容が一致しません");
          uri = url;
        } else {
          const file = path.resolve(base, ref);
          data = readFileSync(file);
          size = imageSize(data);
          if (!size) throw new Error("対応形式の画像として読めません (PNG / JPEG / WebP)");
          uri = `data:image/${size.format};base64,${data.toString("base64")}`;
        }
        if (size.width <= 0 || size.height <= 0) throw new Error("画像の寸法が不正です");
        imageBytes += data.length;
        rep.warn("IMAGE-UNVERIFIED", name, `文書画像「${alt}」はヘッダ検査のみです。内部のデコードはブラウザで表示を確認してください`);
        return `<img src="${esc(uri)}" alt="${esc(alt)}" width="${size.width}" height="${size.height}" style="max-width:100%;height:auto" decoding="async">`;
      } catch (error) {
        rep.warn("DOC-IMAGE", name, `画像 ${isData ? "data URI" : url} を埋め込めません: ${error.message}`);
        return null;
      }
    },
  });
  const usedIds = new Set();
  const docPages = [];
  let changesPage = null;
  if (CHANGES_MD in texts && CHANGES_VERSION_RE.test(texts[CHANGES_MD])) {
    const { body, toc } = convertDoc(texts[CHANGES_MD], "chg", usedIds, imageHooks(CHANGES_MD));
    changesPage = { id: "p-chg", kind: "changes", nav: "変更点", toc, body, no: "" };
  }
  for (const [id, prefix, name, nav] of DOCS) {
    if (!(name in texts) || (name === HEARING_MD && !includeHearing)) continue;
    const { body, toc } = convertDoc(texts[name], prefix, usedIds, imageHooks(name));
    docPages.push({ id, kind: "doc", nav, toc, body, no: "" });
  }

  const pages = [{ id: "p-cover", kind: "cover", nav: "表紙と読み方", no: "" }];
  if (changesPage) pages.push(changesPage);
  pages.push(...boardPages, ...docPages);

  const ctx = { title, version, updated, readers, dataPolicy, questions: ((texts[REQ_MD] ?? "").match(QUESTION_ROW_RE) ?? []).filter((row) => !DECIDED_ROW_RE.test(row)).length };
  const drafts = pages.map((page, i) => {
    const nav = pageNav(pages, i);
    if (page.kind === "cover") return renderCover(ctx, pages, nav);
    if (page.kind === "board") return renderBoard(page, nav, viewSize);
    return renderDoc(page, nav);
  });
  // 文の中の番号のリンクは、行き先がまとめにあるものだけ残す (無いものは文字に戻す)
  const ids = new Set(drafts.flatMap((html) => [...html.matchAll(ID_ATTR_RE)].map((m) => m[1])));
  const rendered = drafts.map((html) => resolveRefs(html, ids));

  let tokensCss;
  const tokensPath = path.join(src, "tokens.css");
  if (isFile(tokensPath)) {
    tokensCss = readText(tokensPath);
  } else {
    rep.warn("TOKENS-MISSING", "_src/tokens.css", "tokens.css が無いため、まとめは既定の配色 (standard) で表示します");
    tokensCss = composeStandardTokens();
  }
  if (/<\/style/i.test(tokensCss)) {
    rep.warn("TOKENS-CSS", "_src/tokens.css", "tokens.css に </style が含まれていたので取り除きました");
    tokensCss = tokensCss.replace(/<\/style/gi, "");
  }

  const built = buildTime();
  const values = {
    TITLE: esc(`${title} 打ち合わせ資料 ${version ?? ""}`.trim()),
    PROJECT: esc(title),
    VERSION: esc(version || "-"),
    UPDATED: esc(updated || "-"),
    BUILT: esc(built),
    TOKENS_CSS: tokensCss,
    NAV: renderToc(pages),
    PAGES: rendered.join("\n"),
    PAGE_COUNT: String(pages.length),
  };
  const template = readText(TEMPLATE);
  const unknown = [...new Set([...template.matchAll(PLACEHOLDER_RE)].map((m) => m[1]))].filter((k) => !Object.hasOwn(values, k)).sort();
  if (unknown.length) rep.err("TEMPLATE-PLACEHOLDER", "assets/templates/book.html", `知らない置換子があります: ${unknown.join(", ")}`);
  // 1 回だけ置き換える (差し込んだ文書の中の {{..}} はそのまま残す)
  const doc = template.replace(PLACEHOLDER_RE, (whole, key) => (Object.hasOwn(values, key) ? values[key] : whole));

  const refs = scanRefs(doc);
  for (const ref of refs) {
    const what = ref.code === "EXTERNAL-REF" ? "外部参照" : "ファイルへの参照";
    rep.err(ref.code, ref.where, `${what}が残っています: ${ref.attr}=${ref.value}`);
  }

  const outFile = out ?? path.join(base, `${safeFilename(title)}${BOOK_SUFFIX}`);
  Object.assign(result, {
    out: toPosix(outFile),
    title,
    updated_doc: updated,
    pages: pages.map((p) => ({ id: p.id, kind: p.kind, title: p.nav, ...(p.no ? { no: p.no } : {}) })),
    boards: boardStatus,
    stale,
    external: refs,
    bytes: Buffer.byteLength(doc, "utf8"),
    image_bytes: imageBytes,
    image_format: formats.size > 1 ? "mixed" : ([...formats][0] ?? null),
  });
  if (!rep.errors.length) {
    writeAtomic(outFile, doc);
    result.written = true;
  }
  return finish(checkDir, result, rep, built);
}

function finish(checkDir, result, rep, built = buildTime()) {
  const pages = result.pages ?? [];
  Object.assign(result, {
    status: rep.errors.length ? "ng" : rep.warnings.some((w) => w.code === "BOARD-CHECK-WARN" || w.code === "DOC-IMAGE" || w.code === "IMAGE-UNVERIFIED") ? "warn" : "ok",
    built,
    summary: {
      errors: rep.errors.length,
      warnings: rep.warnings.length,
      pages: pages.length,
      boards: pages.filter((p) => p.kind === "board").length,
      stale: (result.stale ?? []).length,
      external: (result.external ?? []).filter((r) => r.code === "EXTERNAL-REF").length,
    },
    errors: rep.errors,
    warnings: rep.warnings,
  });
  writeJson(path.join(checkDir, "book.json"), result);
  const lines = [];
  for (const item of rep.errors) lines.push(`error ${item.code} ${item.file} ${item.message}`);
  for (const item of rep.warnings) lines.push(`warn  ${item.code} ${item.file} ${item.message}`);
  if (!result.written) lines.push("問題があるため、まとめ HTML は書き出していません。");
  if (lines.length) process.stderr.write(`${lines.join("\n")}\n`);
  return [rep.errors.length ? EXIT.FOUND : EXIT.OK, result];
}

export async function main(argv) {
  const { options } = parseOptions(argv, { dir: "string", out: "string", "allow-stale": "boolean", quiet: "boolean" });
  if (!options.dir) throw new UsageError("--dir を指定してください (打ち合わせ資料フォルダ)");
  const dir = path.resolve(expandHome(options.dir));
  if (!isDir(dir)) throw new UsageError(`打ち合わせ資料フォルダが見つかりません: ${dir}`);
  const base = realPath(dir);
  if (!isFile(path.join(base, "briefing.json"))) throw new UsageError(`briefing.json がありません: ${path.join(base, "briefing.json")}`);
  let out = null;
  if (options.out !== undefined) {
    const file = path.resolve(expandHome(options.out));
    if (path.extname(file).toLowerCase() !== ".html") throw new UsageError(`--out は .html で指定してください: ${file}`);
    out = path.join(realPath(path.dirname(file)), path.basename(file));
  }
  const [code, result] = build(base, { out, allowStale: Boolean(options["allow-stale"]) });
  const s = result.summary;
  const where = result.written ? result.out : "書き出しなし";
  const quietLine = `book: ${result.status} 版 ${result.version || "-"} ページ ${s.pages} (ボード ${s.boards}) error ${s.errors} / warn ${s.warnings} → ${where}`;
  emitResult(result, options.quiet ? quietLine : null);
  return code;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
