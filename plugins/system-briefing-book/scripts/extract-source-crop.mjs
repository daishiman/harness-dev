#!/usr/bin/env node
/**
 * extract-source-crop — 素材の PDF・写真・スクリーンショットから一部を切り出して PNG にする。
 * ボードに素材の紙や画面を載せるときに使う。--info でページ数と大きさだけを調べる。
 *
 * 座標は 2 通り。
 * - --box x,y,w,h: 画素。PDF は --dpi で描いたときの画素、写真は向きを直したあとの画素。
 * - --rel x,y,w,h: 全体を 1 としたときの割合 (0〜1)。大きさが分からなくても使える。
 * 写真は撮ったときの向き (EXIF) を直してから切り出す。範囲が少しでも外にはみ出したら切り出さずに止める
 * (勝手に詰めると、別の場所を切り出したことに気づけないため)。
 *
 * 切り出しは Chrome / Edge の canvas で行う (画像は data: URL で渡すので、ブラウザは外へもファイルへも読みに行かない)。
 * PDF は poppler の pdftoppm で 1 ページを PNG にしてから同じように切り出す。pdfinfo があればページ数を確かめる。
 * --info はブラウザを使わない (画像はファイルの頭から大きさを読み、PDF は pdfinfo に聞く)。
 *
 * 使い方:
 *   node scripts/extract-source-crop.mjs --src <pdf|png|jpg|jpeg|webp> [--page N] [--dpi 200]
 *        (--box x,y,w,h | --rel x,y,w,h) --out <png> [--max-width 1600] [--browser <path>] [--quiet]
 *   node scripts/extract-source-crop.mjs --src <file> --info [--dpi 200] [--quiet]
 *
 * 書く場所: --out の PNG (一時ファイルに書いてから置き換える)、PDF のときは OS の一時フォルダ (終われば消す)。
 * stdout: JSON {status, src, kind, page, engine, dpi, source_size, box, out, out_size, scaled, warnings[]}
 *         (--info は {status, src, kind, engine, pages, sizes[]}。--quiet で 1 行)
 * exit: 0=切り出した (warn だけなら 0) / 2=使い方の誤り (範囲が画像の外、ページが無い、形式が違う など)
 *       / 3=Node が古い・Chrome / Edge が無い・PDF なのに pdftoppm が無い
 */
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

import { expandHome, isFile, toPosix, writeAtomic } from "./lib/briefing-files.mjs";
import { findBrowser, launchBrowser } from "./lib/browser-session.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";
import { imageSizeOfFile } from "./lib/image-size.mjs";

const USAGE = `
使い方:
  extract-source-crop.mjs --src <pdf|png|jpg|jpeg|webp> [--page N] [--dpi 200]
      (--box x,y,w,h | --rel x,y,w,h) --out <png> [--max-width 1600] [--browser <path>] [--quiet]
  extract-source-crop.mjs --src <file> --info [--dpi 200] [--quiet]
`;

const IMAGE_EXTS = new Set([".png", ".jpg", ".jpeg", ".webp"]);
const PDF_EXTS = new Set([".pdf"]);
const HINT_EXTS = Object.freeze({
  ".heic": "HEIC は読めません。写真アプリなどで JPEG に書き出してから渡してください",
  ".heif": "HEIF は読めません。JPEG に書き出してから渡してください",
  ".tif": "TIFF は対応していません。PNG か PDF に書き出してから渡してください",
  ".tiff": "TIFF は対応していません。PNG か PDF に書き出してから渡してください",
  ".xlsx": "Excel は切り出せません。PDF に書き出してから渡してください",
  ".xls": "Excel は切り出せません。PDF に書き出してから渡してください",
});
const MIME = Object.freeze({ png: "image/png", jpeg: "image/jpeg", webp: "image/webp" });
const DPI_MIN = 72;
const DPI_MAX = 600;
const SMALL_PX = 40;
const BLANK_STDDEV = 2.0;
const REL_EPS = 1e-6;
const TOOL_TIMEOUT_MS = 120_000;
const DECODE_TIMEOUT_MS = 120_000;
const NO_PDFTOPPM =
  "pdftoppm がありません。PDF のページを画像 (PNG) で保存して渡してください" +
  " (poppler を入れると PDF のまま使えます。Mac は `brew install poppler`、Windows は poppler を入れて PATH に足します)";

/** Python の round と同じ偶数への丸め (0.5 ちょうどは偶数の側)。 */
export function roundHalfEven(value) {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff > 0.5) return floor + 1;
  if (diff < 0.5) return floor;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Python の %g と同じ見た目 (有効 6 桁、余分な 0 を付けない)。 */
function fmtG(value) {
  return String(Number(value.toPrecision(6)));
}

function parseIntOption(text, name, fallback) {
  if (text === undefined) return fallback;
  if (!/^[+-]?\d+$/.test(text.trim())) throw new UsageError(`--${name} は整数で指定してください: ${text}`);
  return Number.parseInt(text, 10);
}

export function parseQuad(text, label) {
  const parts = text.trim().split(/[,\s，、]+/).filter(Boolean);
  if (parts.length !== 4) throw new UsageError(`${label} は x,y,w,h の 4 つの数で書いてください: ${JSON.stringify(text)}`);
  const nums = parts.map((p) => (/^[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(p) ? Number(p) : Number.NaN));
  if (nums.some((n) => !Number.isFinite(n))) throw new UsageError(`${label} に数でない値があります: ${JSON.stringify(text)}`);
  const [x, y, w, h] = nums;
  if (w <= 0 || h <= 0) throw new UsageError(`${label} の幅と高さは 0 より大きくしてください: ${JSON.stringify(text)}`);
  if (x < 0 || y < 0) throw new UsageError(`${label} の x と y は 0 以上にしてください: ${JSON.stringify(text)}`);
  return nums;
}

/** --box / --rel を画素の [x, y, w, h] にする。範囲の外にはみ出すなら UsageError。 */
export function toPixelBox({ box, rel }, [width, height]) {
  let left;
  let top;
  let right;
  let bottom;
  if (rel !== undefined) {
    const [x, y, w, h] = parseQuad(rel, "--rel");
    if (x + w > 1 + REL_EPS || y + h > 1 + REL_EPS) {
      throw new UsageError(`--rel が全体 (1) をはみ出しています: x+w=${fmtG(x + w)}, y+h=${fmtG(y + h)}`);
    }
    left = roundHalfEven(x * width);
    top = roundHalfEven(y * height);
    right = Math.min(width, roundHalfEven((x + w) * width));
    bottom = Math.min(height, roundHalfEven((y + h) * height));
  } else {
    const [x, y, w, h] = parseQuad(box, "--box");
    left = roundHalfEven(x);
    top = roundHalfEven(y);
    right = roundHalfEven(x + w);
    bottom = roundHalfEven(y + h);
    if (right > width || bottom > height) {
      throw new UsageError(
        `--box が画像の外にはみ出しています: 画像は ${width}x${height}、指定の右下は (${right}, ${bottom})。 大きさは --info で調べられます`,
      );
    }
  }
  if (right - left < 1 || bottom - top < 1) throw new UsageError("切り出す範囲が 1 画素より小さくなります。範囲を広げてください");
  return [left, top, right - left, bottom - top];
}

export function sourceKind(src) {
  const ext = path.extname(src).toLowerCase();
  if (PDF_EXTS.has(ext)) return "pdf";
  if (IMAGE_EXTS.has(ext)) return "image";
  throw new UsageError(HINT_EXTS[ext] ?? `この形式は対応していません (${ext || "拡張子なし"})。PDF・PNG・JPEG・WebP を渡してください`);
}

// ── 外の道具 (poppler) ───────────────────────────────

/** PATH から道具を探す (shell は使わない)。Windows は PATHEXT の拡張子も試す。無ければ null。 */
export function whichTool(name, env = process.env) {
  const dirs = (env.PATH ?? env.Path ?? "").split(path.delimiter).filter(Boolean);
  const exts = process.platform === "win32" ? ["", ...(env.PATHEXT ?? ".EXE;.CMD;.BAT;.COM").split(";").filter(Boolean)] : [""];
  for (const dir of dirs) {
    for (const ext of exts) {
      const file = path.join(dir, name + ext);
      if (isFile(file)) return file;
    }
  }
  return null;
}

function runTool(file, args) {
  const proc = spawnSync(file, args, {
    encoding: "utf8",
    shell: false,
    windowsHide: true,
    timeout: TOOL_TIMEOUT_MS,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (proc.error?.code === "ETIMEDOUT") {
    throw new UsageError(`${path.basename(file)} が ${TOOL_TIMEOUT_MS / 1000} 秒で終わりませんでした。PDF が壊れていないか確かめてください`);
  }
  if (proc.error) throw new ToolMissing(`${path.basename(file)} を動かせませんでした: ${proc.error.message}`);
  return proc;
}

const PDFINFO_PAGES = /^Pages:\s+(\d+)/m;
const PDFINFO_SIZE = /^Page\s+(\d+)\s+size:\s+([\d.]+)\s+x\s+([\d.]+)/gm;
const PDFINFO_ROT = /^Page\s+(\d+)\s+rot:\s+(\d+)/gm;

/** pdfinfo でページごとの大きさ (pt、回転を反映) を返す。pdfinfo が無ければ null。 */
export function pdfPages(src) {
  const pdfinfo = whichTool("pdfinfo");
  if (!pdfinfo) return null;
  const head = runTool(pdfinfo, [src]);
  if (head.status !== 0) throw new UsageError(`PDF を開けませんでした: ${head.stderr.trim() || "pdfinfo が失敗"}`);
  const count = Number(PDFINFO_PAGES.exec(head.stdout)?.[1] ?? 0);
  if (count === 0) return [];
  const detail = runTool(pdfinfo, ["-f", "1", "-l", String(count), src]);
  const rot = new Map([...detail.stdout.matchAll(PDFINFO_ROT)].map((m) => [Number(m[1]), Number(m[2])]));
  return [...detail.stdout.matchAll(PDFINFO_SIZE)].map((m) => {
    const [w, h] = [Number(m[2]), Number(m[3])];
    return (rot.get(Number(m[1])) ?? 0) % 180 === 90 ? [h, w] : [w, h];
  });
}

/** 描いたときの画素数。pdftoppm は端数を切り上げる。 */
function rasterPx(points, zoom) {
  return Math.ceil(points * zoom - 1e-6);
}

/** PDF の 1 ページを PNG に描いて、そのファイルと後片付けを返す。 */
function renderPdfPage(src, page, dpi) {
  const pdftoppm = whichTool("pdftoppm");
  if (!pdftoppm) throw new ToolMissing(NO_PDFTOPPM);
  const pages = pdfPages(src);
  if (pages !== null && !(page >= 1 && page <= pages.length)) {
    throw new UsageError(`ページ ${page} はありません (この PDF は ${pages.length} ページ)`);
  }
  const tmp = mkdtempSync(path.join(os.tmpdir(), "briefing-crop-"));
  const cleanup = () => rmSync(tmp, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  try {
    const prefix = path.join(tmp, "page");
    const proc = runTool(pdftoppm, ["-f", String(page), "-l", String(page), "-r", String(dpi), "-png", "-singlefile", src, prefix]);
    const png = `${prefix}.png`;
    if (proc.status !== 0 || !isFile(png)) {
      throw new UsageError(`ページ ${page} を描けませんでした: ${proc.stderr.trim() || "pdftoppm が画像を書きませんでした"}`);
    }
    return { file: png, cleanup };
  } catch (error) {
    cleanup();
    throw error;
  }
}

// ── ブラウザでの切り出し ───────────────────────────────

/** 画像を読み (EXIF の向きを直す)、大きさを返す。読んだ画像は次の式のために globalThis に置く。 */
function decodeExpression(dataUrl) {
  return `(async () => {
  const blob = await (await fetch(${JSON.stringify(dataUrl)})).blob();
  const bitmap = await createImageBitmap(blob, { imageOrientation: "from-image", premultiplyAlpha: "none", colorSpaceConversion: "none" });
  globalThis.__crop = bitmap;
  return [bitmap.width, bitmap.height];
})()`;
}

/** 切り出し、明るさのばらつき (PIL の L と同じ重み) を測り、必要なら縮めて PNG の data: URL を返す。 */
function cropExpression([x, y, w, h], maxWidth) {
  return `(() => {
  const bitmap = globalThis.__crop;
  const piece = document.createElement("canvas");
  piece.width = ${w};
  piece.height = ${h};
  const ctx = piece.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(bitmap, ${x}, ${y}, ${w}, ${h}, 0, 0, ${w}, ${h});
  const px = ctx.getImageData(0, 0, ${w}, ${h}).data;
  let sum = 0;
  let sum2 = 0;
  for (let i = 0; i < px.length; i += 4) {
    const l = Math.floor((px[i] * 299 + px[i + 1] * 587 + px[i + 2] * 114 + 500) / 1000);
    sum += l;
    sum2 += l * l;
  }
  const n = px.length / 4;
  const mean = sum / n;
  const stddev = Math.sqrt(Math.max(0, sum2 / n - mean * mean));
  let out = piece;
  const maxWidth = ${maxWidth};
  if (maxWidth && ${w} > maxWidth) {
    out = document.createElement("canvas");
    out.width = maxWidth;
    out.height = ${scaledHeight(w, h, maxWidth)};
    const small = out.getContext("2d");
    small.imageSmoothingEnabled = true;
    small.imageSmoothingQuality = "high";
    small.drawImage(piece, 0, 0, out.width, out.height);
  }
  bitmap.close();
  delete globalThis.__crop;
  return { stddev, width: out.width, height: out.height, png: out.toDataURL("image/png") };
})()`;
}

function scaledHeight(w, h, maxWidth) {
  return Math.max(1, roundHalfEven((h * maxWidth) / w));
}

function cropWarnings(w, h, stddev) {
  const warnings = [];
  if (w < SMALL_PX || h < SMALL_PX) {
    warnings.push({ code: "CROP-SMALL", message: `切り出した範囲が ${w}x${h} と小さいです。範囲か --dpi を見直してください` });
  }
  if (stddev < BLANK_STDDEV) {
    warnings.push({ code: "CROP-BLANK", message: "切り出した範囲がほぼ 1 色です。場所がずれていないか確かめてください" });
  }
  return warnings;
}

/** 画像ファイルの大きさ。読めない形式なら UsageError。 */
function headerSize(file, what) {
  const size = imageSizeOfFile(file);
  if (!size) throw new UsageError(`${what}を開けませんでした: PNG・JPEG・WebP として読めません`);
  return size;
}

// ── 本体 ───────────────────────────────

function checkArgs(options) {
  if (!options.src) throw new UsageError("--src で素材のファイルを指定してください");
  const src = expandHome(options.src);
  if (!isFile(src)) throw new UsageError(`--src のファイルがありません: ${options.src}`);
  const kind = sourceKind(src);
  const page = parseIntOption(options.page, "page", 1);
  const dpi = parseIntOption(options.dpi, "dpi", 200);
  const maxWidth = parseIntOption(options["max-width"], "max-width", 1600);
  if (!(dpi >= DPI_MIN && dpi <= DPI_MAX)) throw new UsageError(`--dpi は ${DPI_MIN}〜${DPI_MAX} にしてください: ${dpi}`);
  if (page < 1) throw new UsageError(`--page は 1 から数えます: ${page}`);
  if (maxWidth < 0) throw new UsageError(`--max-width は 0 以上にしてください: ${maxWidth}`);
  if (options.box !== undefined && options.rel !== undefined) throw new UsageError("--box と --rel はどちらか一方だけにしてください");
  if (!options.info) {
    if (options.box === undefined && options.rel === undefined) {
      throw new UsageError("--box か --rel で切り出す範囲を指定してください (大きさは --info で調べられます)");
    }
    if (!options.out) throw new UsageError("--out で書き出す PNG を指定してください");
  }
  return { src, kind, page, dpi, maxWidth };
}

export function info({ src, kind, dpi }) {
  if (kind === "image") {
    const size = headerSize(src, "画像");
    return { status: "ok", src: toPosix(src), kind, engine: "header", pages: 1, sizes: [{ page: 1, width: size.width, height: size.height }] };
  }
  const pts = pdfPages(src);
  if (pts === null) {
    return {
      status: "ok", src: toPosix(src), kind, engine: null, dpi, pages: null, sizes: [],
      warnings: [{ code: "PDFINFO-MISSING", message: "pdfinfo が無いので、ページ数と大きさを調べられません。poppler を入れるか、PDF のページを画像 (PNG) で保存して渡してください" }],
    };
  }
  const zoom = dpi / 72;
  const sizes = pts.map(([w, h], i) => ({
    page: i + 1,
    width_pt: Math.round(w * 100) / 100,
    height_pt: Math.round(h * 100) / 100,
    width: rasterPx(w, zoom),
    height: rasterPx(h, zoom),
  }));
  return { status: "ok", src: toPosix(src), kind, engine: "pdfinfo", dpi, pages: pts.length, sizes };
}

export async function crop(args, options) {
  const { src, kind, page, dpi, maxWidth } = args;
  const out = path.resolve(expandHome(options.out));
  if (path.extname(out).toLowerCase() !== ".png") throw new UsageError(`--out は .png にしてください: ${options.out}`);
  if (out === path.resolve(src)) throw new UsageError("--out に --src と同じファイルは指定できません");
  if (kind === "image" && page !== 1) throw new UsageError("画像は 1 ページだけです。--page を外してください");

  // ブラウザを起こす前に、読めるか・範囲が中に収まるかを確かめる
  const rendered = kind === "pdf" ? renderPdfPage(src, page, dpi) : null;
  try {
    const file = rendered ? rendered.file : src;
    const size = headerSize(file, rendered ? "描いたページの画像" : "画像");
    const area = { box: options.box, rel: options.rel };
    let box = toPixelBox(area, [size.width, size.height]);
    const executable = findBrowser(options.browser);
    const dataUrl = `data:${MIME[size.format]};base64,${readFileSync(file).toString("base64")}`;

    const session = await launchBrowser(executable);
    let sourceSize;
    let made;
    try {
      const tab = await session.newPage({ width: 800, height: 600 });
      let decoded;
      try {
        decoded = await tab.evaluate(decodeExpression(dataUrl), { timeoutMs: DECODE_TIMEOUT_MS });
      } catch (error) {
        throw new UsageError(`画像を開けませんでした: ${error.message}`);
      }
      sourceSize = decoded;
      // ファイルの頭から読んだ大きさと違えば (向きの読み違いなど)、ブラウザが読んだ大きさで決め直す
      if (decoded[0] !== size.width || decoded[1] !== size.height) box = toPixelBox(area, decoded);
      made = await tab.evaluate(cropExpression(box, maxWidth), { timeoutMs: DECODE_TIMEOUT_MS });
      await tab.close();
    } finally {
      await session.close();
    }
    const png = Buffer.from(made.png.slice(made.png.indexOf(",") + 1), "base64");
    writeAtomic(out, png);
    return {
      status: "ok",
      src: toPosix(src),
      kind,
      page,
      engine: "chrome",
      dpi: kind === "pdf" ? dpi : null,
      source_size: sourceSize,
      box,
      out: toPosix(out),
      out_size: [made.width, made.height],
      scaled: made.width !== box[2],
      warnings: cropWarnings(box[2], box[3], made.stddev),
    };
  } finally {
    rendered?.cleanup();
  }
}

function oneLine(result) {
  if ("sizes" in result) {
    const first = result.sizes[0] ?? {};
    return `crop-info: ${result.kind} ${result.pages ?? "-"} ページ (1 ページ目 ${first.width ?? "-"}x${first.height ?? "-"}) ${result.src}`;
  }
  const [x, y, w, h] = result.box;
  const [ow, oh] = result.out_size;
  const warn = result.warnings.length ? ` warn ${result.warnings.length}` : "";
  return `crop: ok p${result.page} (${x},${y},${w},${h}) → ${result.out} ${ow}x${oh}${warn}`;
}

export async function main(argv) {
  const { options } = parseOptions(argv, {
    src: "string",
    info: "boolean",
    page: "string",
    dpi: "string",
    box: "string",
    rel: "string",
    out: "string",
    "max-width": "string",
    browser: "string",
    quiet: "boolean",
  });
  const args = checkArgs(options);
  const result = options.info ? info(args) : await crop(args, options);
  const warnings = result.warnings ?? [];
  if (warnings.length) process.stderr.write(`${warnings.map((w) => `warn  ${w.code} ${w.message}`).join("\n")}\n`);
  emitResult(result, options.quiet ? oneLine(result) : null);
  return EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
