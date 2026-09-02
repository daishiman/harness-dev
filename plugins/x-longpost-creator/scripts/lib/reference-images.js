"use strict";
/**
 * reference-images.js - 画風の見本画像の宣言解決（決定論的処理）
 *
 * assets/reference-images/manifest.json が宣言する見本を kind ごとに解決し、
 * codex exec -i へ渡せる絶対パスの一覧と、宣言されたのに実体が無いものの一覧を返す。
 *
 * 「無ければ落とす」にはしていない。画風の正本は文章の canon であり、見本は精度を
 * 上げる補助だからである。ただし missing を黙って握り潰すと「見本があるつもりで
 * 書かれた canon」と「見本なしで生成された絵」の差が記録から消えるため、必ず
 * 呼び出し側へ返して出力と meta.json に載せる。FAIL へ昇格するかは呼び出し側の
 * --require-reference-images が決める（validate-visual-assets.js の --strict と同じ思想）。
 */

const fs = require("fs");
const path = require("path");

const DEFAULT_REFERENCE_DIR = path.join(__dirname, "..", "..", "assets", "reference-images");

/**
 * 見本の置き場。既定は plugin 同梱の assets/reference-images/。
 * 画風の見本は規範の一部なので plugin と一緒に配るのが基本だが、利用者固有の
 * 見本へ差し替えたいときのために XLP_REFERENCE_IMAGE_DIR で外から指せる。
 */
function referenceDir() {
  const configured = process.env.XLP_REFERENCE_IMAGE_DIR;
  return configured && configured.trim()
    ? path.resolve(configured.trim())
    : DEFAULT_REFERENCE_DIR;
}

function manifestPath() {
  return path.join(referenceDir(), "manifest.json");
}

/** manifest を読む。壊れている・無いときは空宣言として扱わず、理由を持って返す。 */
function loadManifest() {
  const file = manifestPath();
  if (!fs.existsSync(file)) {
    return { ok: false, reason: `manifest-missing: ${file}`, images: [] };
  }
  let parsed;
  try {
    parsed = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (err) {
    return { ok: false, reason: `manifest-unparsable: ${err.message}`, images: [] };
  }
  if (!Array.isArray(parsed.images)) {
    return { ok: false, reason: "manifest-has-no-images-array", images: [] };
  }
  return { ok: true, reason: null, images: parsed.images };
}

/**
 * kind に対応する見本を解決する。
 *
 * @param {string} kind          visual-spec.json の kind 名
 * @param {string[]} validKinds  spec が定義する kind の全集合。未知の kind 宣言を弾く
 * @returns {{ok:boolean, attached:string[], missing:string[], declared:number, error:(string|null)}}
 */
function resolveForKind(kind, validKinds) {
  const manifest = loadManifest();
  if (!manifest.ok) {
    return { ok: false, attached: [], missing: [], declared: 0, error: manifest.reason };
  }

  const attached = [];
  const missing = [];
  let declared = 0;

  for (const entry of manifest.images) {
    const kinds = Array.isArray(entry.kinds) ? entry.kinds : [];
    // 宣言側の kind 名が spec と食い違っていると、見本が黙って1枚も渡らない状態が
    // 誰にも気付かれずに続く。綴り違いはここで止める。
    for (const declaredKind of kinds) {
      if (!validKinds.includes(declaredKind)) {
        return {
          ok: false,
          attached: [],
          missing: [],
          declared: 0,
          error: `manifest の未知の kind: ${declaredKind}（有効: ${validKinds.join(", ")}）`,
        };
      }
    }
    if (!kinds.includes(kind)) continue;

    declared++;
    const file = String(entry.file || "");
    // manifest はディレクトリ直下のファイル名だけを宣言できる。相対脱出を許すと
    // 任意のファイルが生成系へ送信されうる。
    if (file === "" || file.includes("/") || file.includes("\\") || file.includes("..")) {
      return {
        ok: false,
        attached: [],
        missing: [],
        declared: 0,
        error: `manifest の file はディレクトリ直下のファイル名のみ許可: "${file}"`,
      };
    }
    const abs = path.join(referenceDir(), file);
    if (fs.existsSync(abs)) attached.push(abs);
    else missing.push(file);
  }

  return { ok: true, attached, missing, declared, error: null };
}

module.exports = { resolveForKind, referenceDir, manifestPath, DEFAULT_REFERENCE_DIR };
