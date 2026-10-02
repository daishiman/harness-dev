#!/usr/bin/env node
/**
 * count-csv-columns — CSV の列ごとに、埋まっている行の数と値の種類の数を数え、列を 3 つに分ける。値そのものは出さない。
 * data-map のボードの「列の区分の棒」を作るときの下調べに使う。
 *
 *   blank  全行が空
 *   fixed  空でない値が 1 種類だけ
 *   value  それ以外
 * これより細かい区分 (紙から読む・しくみが入れる・決めること) は LLM が決め、data-map の棒 (data-kind) に写す。
 *
 * 1 行目を見出しとする。引用符つきの欄 (中のカンマ・改行・"") を正しく分ける。中身が空の行は数えない。空白だけの欄は空とみなす。
 * 文字コード: auto は UTF-8 (先頭の BOM は外す) で読めなければ Shift_JIS で読む。Excel のファイルは CSV に書き出してから渡す。
 *
 * 使い方:
 *   node scripts/count-csv-columns.mjs --src <csv> [--encoding auto|utf-8|shift_jis] [--quiet]
 *
 * 書く場所: なし (stdout だけ)。
 * stdout: JSON {status, src, encoding, rows, columns: [{no, name, kind, filled, distinct}], counts: {blank, fixed, value}}
 *         (--quiet で要約 1 行)
 * exit: 0=数えた / 2=使い方の誤り (ファイルが無い・読めない・決めた文字コードで読めない) / 3=Node が古い・この Node が Shift_JIS を読めない
 */
import { readFileSync } from "node:fs";

import { expandHome, isFile, realPath, toPosix } from "./lib/briefing-files.mjs";
import { EXIT, ToolMissing, UsageError, emitResult, isEntryPoint, parseOptions, runCli } from "./lib/cli-contract.mjs";

const USAGE = `
使い方:
  count-csv-columns.mjs --src <csv> [--encoding auto|utf-8|shift_jis] [--quiet]
`;

export const ENCODINGS = Object.freeze(["auto", "utf-8", "shift_jis"]);
export const KINDS = Object.freeze(["blank", "fixed", "value"]);

/** 決めた文字コードで読む。読めない並びがあれば null。この Node がその文字コードを知らなければ止める (exit 3)。 */
function decode(bytes, encoding) {
  let decoder;
  try {
    // UTF-8 の先頭の BOM は TextDecoder が外す (ignoreBOM の既定は false)
    decoder = new TextDecoder(encoding, { fatal: true });
  } catch {
    throw new ToolMissing(`この Node は ${encoding} を読めません (公式の配布の Node 22 以上を入れ直す)`);
  }
  try {
    return decoder.decode(bytes);
  } catch {
    return null;
  }
}

/** auto なら UTF-8 → Shift_JIS の順に試す。どれでも読めなければ使い方の誤り (exit 2)。 */
export function decodeCsv(bytes, encoding, src) {
  const order = encoding === "auto" ? ["utf-8", "shift_jis"] : [encoding];
  for (const name of order) {
    const text = decode(bytes, name);
    if (text !== null) return { text, encoding: name };
  }
  const names = order.map((name) => (name === "utf-8" ? "UTF-8" : "Shift_JIS"));
  const tried = names.length > 1 ? `${names.join(" でも ")} でも` : `${names[0]} で`;
  throw new UsageError(`${tried}読めません (--encoding を確かめる): ${src}`);
}

/**
 * CSV を行と欄に分ける (RFC 4180 の形)。引用符の中のカンマと改行は欄の中身、"" は " 1 文字。
 * 行の区切りは CRLF・LF・CR のどれでもよい。中身が空の行は数えない。引用符が閉じないまま終わったら、そこまでを 1 欄にする。
 */
export function parseCsv(text) {
  const records = [];
  let row = [];
  let field = "";
  let quoted = false;
  let atStart = true;
  const endField = () => {
    row.push(field);
    field = "";
    atStart = true;
  };
  const endRow = () => {
    endField();
    if (row.length > 1 || row[0] !== "") records.push(row);
    row = [];
  };
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (quoted) {
      if (ch !== '"') {
        field += ch;
      } else if (text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else {
        quoted = false;
      }
      continue;
    }
    if (ch === '"' && atStart) {
      quoted = true;
      atStart = false;
    } else if (ch === ",") {
      endField();
    } else if (ch === "\r" || ch === "\n") {
      if (ch === "\r" && text[i + 1] === "\n") i += 1;
      endRow();
    } else {
      field += ch;
      atStart = false;
    }
  }
  if (field !== "" || row.length || quoted) endRow();
  return records;
}

/** 1 行目を見出しにして、列ごとに埋まった行の数と値の種類の数を数える。値そのものは返さない。 */
export function countColumns(records) {
  const [header = [], ...data] = records;
  const width = data.reduce((n, record) => Math.max(n, record.length), header.length);
  const columns = [];
  for (let c = 0; c < width; c += 1) {
    const seen = new Set();
    let filled = 0;
    for (const record of data) {
      const value = (record[c] ?? "").trim();
      if (!value) continue;
      filled += 1;
      seen.add(value);
    }
    const kind = filled === 0 ? "blank" : seen.size === 1 ? "fixed" : "value";
    columns.push({ no: c + 1, name: (header[c] ?? "").trim(), kind, filled, distinct: seen.size });
  }
  const counts = Object.fromEntries(KINDS.map((kind) => [kind, columns.filter((col) => col.kind === kind).length]));
  return { rows: data.length, columns, counts };
}

export async function main(argv) {
  const { options } = parseOptions(argv, { src: "string", encoding: "string", quiet: "boolean" });
  if (!options.src) throw new UsageError("--src を指定してください (CSV のファイル)");
  const encoding = (options.encoding ?? "auto").toLowerCase();
  if (!ENCODINGS.includes(encoding)) {
    throw new UsageError(`--encoding は ${ENCODINGS.join(" / ")} のどれかです: ${options.encoding}`);
  }
  const src = expandHome(options.src);
  if (!isFile(src)) throw new UsageError(`ファイルがありません: ${src}`);
  let bytes;
  try {
    bytes = readFileSync(src);
  } catch (error) {
    throw new UsageError(`ファイルが読めません: ${src} (${error.message})`);
  }
  const decoded = decodeCsv(bytes, encoding, src);
  const { rows, columns, counts } = countColumns(parseCsv(decoded.text));
  const result = { status: "ok", src: toPosix(realPath(src)), encoding: decoded.encoding, rows, columns, counts };
  const quietLine = `csv: ok ${columns.length} 列 / ${rows} 行 (blank ${counts.blank} / fixed ${counts.fixed} / ` +
    `value ${counts.value}) ${decoded.encoding}`;
  emitResult(result, options.quiet ? quietLine : null);
  return EXIT.OK;
}

if (isEntryPoint(import.meta.url)) {
  runCli(main, USAGE);
}
