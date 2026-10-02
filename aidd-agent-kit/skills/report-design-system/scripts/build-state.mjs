#!/usr/bin/env node
// build が検査した成果物を SHA-256 で記録し、done で同じ成果物かを再確認する。
// 描画をやり直さずに「この HTML は実描画まで合格済み」を確かめるための内部コンポーネント。
//
//   node scripts/build-state.mjs clear  <report-dir>
//   node scripts/build-state.mjs record <report-dir> <report-name>
//   node scripts/build-state.mjs verify <report-dir> <report-name>
//
// 終了コード: 0=成功/合格 1=証跡不一致 2=入力エラー
import {
  existsSync,
  lstatSync,
  readFileSync,
  readdirSync,
  rmSync,
} from "node:fs";
import { basename, join, resolve, sep } from "node:path";
import { pathToFileURL } from "node:url";
import { RENDER_WIDTHS, INPUT_MANIFEST_FILE, BG_RE, sha256, writeAtomic } from "./lib.mjs";

import { readInputManifest } from "./inputs.mjs";

export const BUILD_STATE_FILE = ".report-build.json";
export const BUILD_STATE_VERSION = 2;
export { RENDER_WIDTHS };

const BASE_ARTIFACTS = Object.freeze([
  "analysis.mjs",
  "profile.json",
  "brief.json",
  INPUT_MANIFEST_FILE,
  "results.json",
]);
const SHA256_RE = /^[0-9a-f]{64}$/;

function lexical(items) {
  return [...items].sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));
}

function relativePath(root, file) {
  return file.slice(root.length + 1).split(sep).join("/");
}

function validateInputs(reportDir, reportName) {
  const dir = resolve(reportDir || "");
  if (!reportDir || !existsSync(dir) || !lstatSync(dir).isDirectory()) {
    throw new TypeError(`レポートフォルダがありません: ${reportDir || "(未指定)"}`);
  }
  if (!reportName || basename(reportName) !== reportName || reportName === "." || reportName === "..") {
    throw new TypeError(`レポート名が不正です: ${reportName || "(未指定)"}`);
  }
  return dir;
}

function hashEntry(root, relative) {
  const file = join(root, relative);
  if (!existsSync(file) || !lstatSync(file).isFile()) {
    throw new Error(`証跡対象ファイルがありません: ${relative}`);
  }
  return {
    path: relative.split(sep).join("/"),
    sha256: sha256(readFileSync(file)),
  };
}

function inputEntries(dir) {
  return readInputManifest(dir).files.map(({ path, sha256 }) => ({ path, sha256 }))
    .sort((a, b) => (a.path < b.path ? -1 : a.path > b.path ? 1 : 0));
}

function artifactPaths(dir, reportName) {
  const backgrounds = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && BG_RE.test(entry.name))
    .map((entry) => entry.name);
  return lexical([
    ...BASE_ARTIFACTS,
    ...backgrounds,
    `${reportName}.src.html`,
    `${reportName}.html`,
  ]);
}

function screenshotPaths(dir, reportName) {
  const screenDir = join(dir, "screens");
  if (!existsSync(screenDir) || !lstatSync(screenDir).isDirectory()) {
    throw new Error("描画検証の screens フォルダがありません");
  }
  const paths = readdirSync(screenDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".png"))
    .map((entry) => relativePath(dir, join(screenDir, entry.name)));
  const expected = RENDER_WIDTHS.map((width) => `screens/${reportName}-${width}.png`);
  const missing = expected.filter((path) => !paths.includes(path));
  if (missing.length) throw new Error(`描画検証のスクリーンショットが不足しています: ${missing.join(", ")}`);
  return lexical(paths);
}

function makeState(dir, reportName) {
  return {
    version: BUILD_STATE_VERSION,
    report: reportName,
    inputs: inputEntries(dir),
    artifacts: artifactPaths(dir, reportName).map((path) => hashEntry(dir, path)),
    screenshots: screenshotPaths(dir, reportName).map((path) => hashEntry(dir, path)),
  };
}

function canonicalState(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

/** 実描画まで合格した直後に呼び、対象ファイルの決定論的な証跡を原子的に保存する。 */
export function recordBuildState(reportDir, reportName) {
  const dir = validateInputs(reportDir, reportName);
  const state = makeState(dir, reportName);
  writeAtomic(join(dir, BUILD_STATE_FILE), canonicalState(state), { mode: 0o600 });
  return state;
}

/** build / verify 開始時に古い厳格検証の証跡を無効化する。失敗した生成を done へ進めない。 */
export function clearBuildState(reportDir) {
  const dir = resolve(reportDir || "");
  if (!reportDir || !existsSync(dir) || !lstatSync(dir).isDirectory()) {
    throw new TypeError(`レポートフォルダがありません: ${reportDir || "(未指定)"}`);
  }
  rmSync(join(dir, BUILD_STATE_FILE), { force: true });
}

function entryErrors(label, recorded, actual) {
  const errors = [];
  if (!Array.isArray(recorded)) return [`${label} の証跡が配列ではありません`];
  const paths = recorded.map((entry) => entry?.path);
  if (paths.some((path) => typeof path !== "string") || new Set(paths).size !== paths.length) {
    errors.push(`${label} の証跡パスが不正または重複しています`);
  }
  if (JSON.stringify(paths) !== JSON.stringify(lexical(paths.filter((path) => typeof path === "string")))) {
    errors.push(`${label} の証跡パスが安定順ではありません`);
  }
  const actualPaths = actual.map((entry) => entry.path);
  const recordedPaths = paths.filter((path) => typeof path === "string");
  for (const path of actualPaths.filter((path) => !recordedPaths.includes(path))) errors.push(`${label} が証跡にありません: ${path}`);
  for (const path of recordedPaths.filter((path) => !actualPaths.includes(path))) errors.push(`${label} が削除または対象外になりました: ${path}`);
  const byPath = new Map(actual.map((entry) => [entry.path, entry.sha256]));
  for (const entry of recorded) {
    if (!entry || typeof entry.path !== "string" || !SHA256_RE.test(entry.sha256 || "")) {
      errors.push(`${label} の SHA-256 証跡が不正です: ${entry?.path || "(パスなし)"}`);
    } else if (byPath.has(entry.path) && byPath.get(entry.path) !== entry.sha256) {
      errors.push(`${label} が build 後に変更されました: ${entry.path}`);
    }
  }
  return errors;
}

/** 現在の対象ファイルと保存済み証跡を比較する。描画は実行しない。 */
export function verifyBuildState(reportDir, reportName) {
  const dir = validateInputs(reportDir, reportName);
  const stateFile = join(dir, BUILD_STATE_FILE);
  if (!existsSync(stateFile) || !lstatSync(stateFile).isFile()) {
    return { ok: false, errors: [`厳格検証の証跡 ${BUILD_STATE_FILE} がありません。report.mjs verify を実行してください`] };
  }
  let recorded;
  try {
    recorded = JSON.parse(readFileSync(stateFile, "utf8"));
  } catch (error) {
    return { ok: false, errors: [`build 証跡を読めません: ${error.message}`] };
  }
  const errors = [];
  if (recorded?.version !== BUILD_STATE_VERSION) errors.push(`build 証跡の版が不正です: ${recorded?.version ?? "(なし)"}`);
  if (recorded?.report !== reportName) errors.push(`build 証跡のレポート名が不一致です: ${recorded?.report ?? "(なし)"}`);
  let current;
  try {
    current = makeState(dir, reportName);
  } catch (error) {
    errors.push(error.message);
  }
  if (current) {
    errors.push(...entryErrors("入力データ", recorded?.inputs, current.inputs));
    errors.push(...entryErrors("成果物", recorded?.artifacts, current.artifacts));
    errors.push(...entryErrors("スクリーンショット", recorded?.screenshots, current.screenshots));
  }
  return { ok: errors.length === 0, errors, state: recorded };
}

function usage() {
  console.error("使い方: node scripts/build-state.mjs <clear <report-dir> | record|verify <report-dir> <report-name>>");
}

function main([command, reportDir, reportName, ...extra]) {
  if (extra.length || !["clear", "record", "verify"].includes(command) || !reportDir || (command !== "clear" && !reportName)) {
    usage();
    return 2;
  }
  try {
    if (command === "clear") {
      if (reportName) return usage(), 2;
      clearBuildState(reportDir);
      return 0;
    }
    if (command === "record") {
      recordBuildState(reportDir, reportName);
      console.log(`build 証跡: 記録 ${join(resolve(reportDir), BUILD_STATE_FILE)}`);
      return 0;
    }
    const result = verifyBuildState(reportDir, reportName);
    for (const error of result.errors) console.error(`build 証跡: NG ${error}`);
    if (!result.ok) return 1;
    console.log("build 証跡: 合格 (build 後の成果物と描画結果に変更なし)");
    return 0;
  } catch (error) {
    console.error(`build 証跡: ${error.message}`);
    return error instanceof TypeError ? 2 : 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
