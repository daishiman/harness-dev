#!/usr/bin/env node
// データの概要 (profile.json) を作る。LLM の分析者は生データではなくこれを読んで問いと仮説を立てる
// (列の名前・型・件数・欠損・範囲・期間を推測で語らないため。prompts/analyst.md)。
//
//   node scripts/profile-data.mjs <出力先 profile.json> <データ...>   (CSV か、オブジェクトの配列の JSON)
// 複数入力は同じ schema の分割ファイルとして縦に連結する。異種データの join は扱わない。
//
// 列の型: number (8割以上が数値) / period (YYYY-MM か YYYY-MM-DD) / category (種類が件数の半分以下) / text
// 終了コード: 0=作成 2=入力エラー
import { writeFileSync, existsSync } from "node:fs";
import { basename } from "node:path";
import { pathToFileURL } from "node:url";
import { readRows } from "./inputs.mjs";
export { readRows };
import { describe } from "./stats.mjs";

const PERIOD = /^\d{4}[-/](0[1-9]|1[0-2])([-/](0[1-9]|[12]\d|3[01]))?$/;
const r3 = (v) => Math.round(v * 1000) / 1000;

export function profile(rows) {
  const names = [...new Set(rows.flatMap((r) => Object.keys(r)))];
  const columns = names.map((name) => {
    const vals = rows.map((r) => (r[name] ?? "").trim());
    const filled = vals.filter((v) => v !== "");
    const col = { name, n: filled.length, missing: vals.length - filled.length };
    const parsed = filled.map((raw) => ({ raw, value: Number(raw.replace(/,/g, "")) }));
    const nums = parsed.filter(({ value }) => Number.isFinite(value)).map(({ value }) => value);
    const invalidNumeric = parsed.filter(({ value }) => !Number.isFinite(value)).map(({ raw }) => raw);
    const distinct = new Set(filled);
    if (filled.length && filled.every((v) => PERIOD.test(v))) {
      const s = [...distinct].map((v) => v.replace(/\//g, "-")).sort();
      Object.assign(col, { type: "period", min: s[0], max: s.at(-1), distinct: s.length });
    } else if (filled.length && nums.length >= filled.length * 0.8) {
      const d = describe(nums);
      Object.assign(col, {
        type: "number",
        valid_numeric_n: nums.length,
        invalid_numeric_n: invalidNumeric.length,
        invalid_samples: [...new Set(invalidNumeric)].slice(0, 5),
        min: r3(d.min),
        q1: r3(d.q1),
        median: r3(d.median),
        q3: r3(d.q3),
        max: r3(d.max),
        mean: r3(d.mean),
        sd: r3(d.sd),
        negatives: nums.filter((v) => v < 0).length,
        zeros: nums.filter((v) => v === 0).length,
      });
    } else if (distinct.size <= Math.max(1, filled.length / 2)) {
      const counts = new Map();
      for (const v of filled) counts.set(v, (counts.get(v) || 0) + 1);
      Object.assign(col, { type: "category", distinct: distinct.size, top: [...counts].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))).slice(0, 8) });
    } else Object.assign(col, { type: "text", distinct: distinct.size });
    return col;
  });
  return { rows: rows.length, columns, sample: rows.slice(0, 3) };
}

// category と text は値の重複率で入れ替わるため、ともに文字列として schema を比較する。
const schemaType = (column) => column.n === 0 ? "unknown" : ["category", "text"].includes(column.type) ? "string" : column.type;

export function schemaErrors(parts) {
  if (parts.length < 2) return [];
  const base = parts[0];
  const expected = new Map(base.columns.map((column) => [column.name, schemaType(column)]));
  const expectedFile = new Map(base.columns.map((column) => [column.name, base.file]));
  const errors = [];
  for (const part of parts.slice(1)) {
    const actual = new Map(part.columns.map((column) => [column.name, schemaType(column)]));
    const missing = [...expected.keys()].filter((name) => !actual.has(name));
    const extra = [...actual.keys()].filter((name) => !expected.has(name));
    if (missing.length || extra.length) {
      errors.push(`${part.file}: 列集合が ${base.file} と異なります${missing.length ? ` (不足: ${missing.join("・")})` : ""}${extra.length ? ` (余分: ${extra.join("・")})` : ""}`);
      continue;
    }
    for (const [name, expectedType] of expected) {
      const actualType = actual.get(name);
      if (expectedType === "unknown" && actualType !== "unknown") {
        expected.set(name, actualType);
        expectedFile.set(name, part.file);
      } else if (expectedType !== "unknown" && actualType !== "unknown" && actualType !== expectedType) {
        errors.push(`${part.file}: 列「${name}」の型が ${expectedFile.get(name)} と異なります (${actualType} / ${expectedType})`);
      }
    }
  }
  return errors;
}

function main(argv) {
  const [out, ...files] = argv;
  if (!out || !/\.json$/.test(out) || !files.length || !files.every(existsSync)) {
    console.error("使い方: node scripts/profile-data.mjs <出力先 profile.json> <同一schemaの分割データ.csv|.json ...>");
    return 2;
  }
  let parts;
  try {
    parts = files.map((f) => ({ file: basename(f), ...profile(readRows(f)) }));
  } catch (error) {
    console.error(`入力エラー: ${error.message}`);
    return 2;
  }
  const errors = schemaErrors(parts);
  if (errors.length) {
    console.error(`入力エラー: 複数入力は同一schemaの分割ファイルだけ指定できます (joinは未対応)\n${errors.join("\n")}`);
    return 2;
  }
  writeFileSync(out, JSON.stringify({ files: parts }, null, 2) + "\n");
  for (const p of parts) console.log(`${p.file}: ${p.rows}行・${p.columns.length}列 (${p.columns.map((c) => `${c.name}:${c.type}`).join(" ")})`);
  console.log(`書き出し: ${out}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
