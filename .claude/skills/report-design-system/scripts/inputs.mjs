// 入力データの読み取りと、init/analysis/厳格証跡で共用する入力manifest契約。
// 同じschemaの分割入力はreadInputRowsで連結する。異種入力はreadInputManifestで検証して個別に読む。
import { existsSync, readFileSync, statSync } from "node:fs";
import { isAbsolute, join, resolve } from "node:path";
import { INPUT_MANIFEST_FILE, INPUT_MANIFEST_VERSION, parseCsv, sha256, writeAtomic } from "./lib.mjs";

const SHA256_RE = /^[0-9a-f]{64}$/;

/** CSV・オブジェクト配列JSON・D1 --jsonを、文字列セルの行配列として読む。 */
export function readRows(file) {
  const text = readFileSync(file, "utf8");
  if (!/\.json$/i.test(file)) return parseCsv(text);
  const data = JSON.parse(text);
  const rows = Array.isArray(data?.[0]?.results) ? data[0].results
    : Array.isArray(data) ? data : Array.isArray(data?.results) ? data.results : null;
  if (!rows || rows.some((row) => !row || typeof row !== "object" || Array.isArray(row))) {
    throw new Error(`${file}: オブジェクトの配列ではありません`);
  }
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value == null ? "" : String(value)])));
}

/** 受領した入力の絶対パスとhashを記録する。入力なしはnew-report単体の雛形作成時だけ許す。 */
export function inputManifest(files, { allowEmpty = false } = {}) {
  if (!Array.isArray(files) || (!files.length && !allowEmpty)) throw new TypeError("入力データを1つ以上指定してください");
  const paths = files.map((file) => resolve(file));
  if (new Set(paths).size !== paths.length) throw new TypeError("入力データのパスが重複しています");
  return {
    version: INPUT_MANIFEST_VERSION,
    files: paths.map((path) => ({ path, sha256: sha256(readFileSync(path)) })),
  };
}

/** 既存reportの移行にも使う。analysisが読む全入力を明示して初回だけ保存する。 */
export function writeInputManifest(reportDir, files) {
  const manifest = inputManifest(files);
  writeAtomic(join(reportDir, INPUT_MANIFEST_FILE), `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest;
}

/** 必須形・絶対パス・重複・現在のhashを確認する。入力の宣言順は維持する。 */
export function readInputManifest(reportDir) {
  const path = join(reportDir, INPUT_MANIFEST_FILE);
  if (!existsSync(path) || !statSync(path).isFile()) throw new Error(`入力マニフェストがありません: ${INPUT_MANIFEST_FILE}`);
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`入力マニフェストを読めません: ${error.message}`);
  }
  if (manifest?.version !== INPUT_MANIFEST_VERSION || !Array.isArray(manifest?.files) || !manifest.files.length) {
    throw new Error(`入力マニフェストの形式が不正です: ${INPUT_MANIFEST_FILE}`);
  }
  const seen = new Set();
  for (const [index, entry] of manifest.files.entries()) {
    const file = entry?.path;
    if (typeof file !== "string" || !isAbsolute(file) || resolve(file) !== file || !SHA256_RE.test(entry?.sha256 || "")) {
      throw new Error(`入力マニフェストの files[${index}] が不正です`);
    }
    if (seen.has(file)) throw new Error(`入力マニフェストのパスが重複しています: ${file}`);
    seen.add(file);
    if (!existsSync(file) || !statSync(file).isFile()) throw new Error(`入力データがありません: ${file}`);
    if (sha256(readFileSync(file)) !== entry.sha256) throw new Error(`入力データが init 後に変更されました: ${file}`);
  }
  return manifest;
}

/** initで受け取る、同じschemaの分割入力を検証して読み込む。 */
export const readInputRows = (reportDir) => readInputManifest(reportDir).files.flatMap((entry) => readRows(entry.path));
