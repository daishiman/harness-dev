/**
 * 配色の組み立て。ボードとまとめ HTML が読む _src/tokens.css は、次をこの順につないだもの。
 *
 *   1. ボードの言葉 (assets/css/board-tokens.css)
 *      ボードの部品が使う名前 (--bg-board、--text-2、--anno など)。キットにある役割へ var() でつなぎ、
 *      キットに無いもの (ボードの地、注記の番号、端末の枠、文字の束、角丸) だけ値を持つ。
 *   2. 標準カラー (assets/css/vendor/standard-color-system.css)
 *      aidd-agent-kit の jp-web-design の正本を 1 バイトも変えずに写したもの。出所とハッシュは vendor/SOURCE.json。
 *      どの案件でも必ず入る。役割の名前と、その役割にどの基本色を当てるかはここで決まる。
 *   3. 案件の上書き (briefing.json の palette が standard でないときだけ)
 *      キットの決まりどおり、基本色 (--p-brand-indigo など) だけを書き換えれば、役割はすべてそれに付いてくる。
 *      ボードの原色 (--p-board など) や役割を直接書いてもよい (後に置くので勝つ)。
 *
 * 同じ :root の中では後に書いたものが勝つ。var() は描画のときに解くので、1 が 2 より前にあってよい。
 * 色の値はキットから来るので、同じ版のキットと同じ上書きからは、毎回同じ見た目になる。
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

import { CSS_DIR, sha256 } from "./briefing-files.mjs";

export const VENDOR_DIR = path.join(CSS_DIR, "vendor");
export const PALETTE_SOURCE = path.join(VENDOR_DIR, "SOURCE.json");
export const BOARD_TOKENS = path.join(CSS_DIR, "board-tokens.css");

/** 既定の配色。vendor はこの plugin の中の写し、kit はキットのルートからの場所。 */
export const STANDARD_PALETTE = Object.freeze({
  name: "standard",
  vendor: path.join(VENDOR_DIR, "standard-color-system.css"),
  kit: "skills/jp-web-design/assets/standard/standard-color-system.css",
});

/** 配色の CSS に書かれた版 (@standard-meta の version)。無ければ undefined。 */
export function colorVersion(css) {
  const meta = css.match(/@standard-meta\s+(\{.*\})/);
  if (!meta) return undefined;
  try {
    return JSON.parse(meta[1]).version;
  } catch {
    return undefined;
  }
}

/** vendor の写しが SOURCE.json の記録どおりか (手で書き換えられていないか) を返す。 */
export function verifyVendor() {
  if (!existsSync(PALETTE_SOURCE)) return { ok: false, reason: "assets/css/vendor/SOURCE.json がありません" };
  const source = JSON.parse(readFileSync(PALETTE_SOURCE, "utf8"));
  if (!existsSync(STANDARD_PALETTE.vendor)) return { ok: false, reason: "assets/css/vendor/standard-color-system.css がありません", source };
  const actual = sha256(readFileSync(STANDARD_PALETTE.vendor));
  if (actual !== source.sha256) {
    return { ok: false, reason: `vendor の写しが記録と違います (記録 ${String(source.sha256).slice(0, 12)} / 実物 ${actual.slice(0, 12)})`, source };
  }
  return { ok: true, source };
}

/** 上書きの CSS を読み、冒頭の説明に出す名前を付ける。ファイル名とハッシュの頭で、どの版から作ったかを追える。 */
export function readOverlay(file) {
  const buf = readFileSync(file);
  return { css: buf.toString("utf8"), label: `${path.basename(file)} (sha256 ${sha256(buf).slice(0, 12)})` };
}

/**
 * _src/tokens.css の中身を組み立てる。overlay は readOverlay の戻り値で、standard のときは渡さない。
 * 同じ入力からは同じバイト列になる (日時や絶対パスを入れない)。
 */
export function composeTokens(overlay) {
  const board = readFileSync(BOARD_TOKENS, "utf8");
  const vendor = readFileSync(STANDARD_PALETTE.vendor);
  const header = [
    "/* _src/tokens.css は build-briefing-scaffold.mjs init が作る。手で直さない。",
    "   配色を変えるときは briefing.json の palette を変え、init --refresh-css で作り直す。",
    "   1. ボードの言葉: plugin の assets/css/board-tokens.css",
    `   2. 標準カラー: ${standardLabel(vendor)}`,
    `   3. 案件の上書き: ${overlay ? overlay.label : "なし (palette は standard)"}`,
    "   同じ名前は後に書いたものが勝つ。 */",
    "",
  ].join("\n");
  const sep = (text) => (text.endsWith("\n") ? text : `${text}\n`);
  const parts = [header + sep(board), sep(vendor.toString("utf8"))];
  if (overlay) parts.push(sep(overlay.css));
  return parts.join("\n");
}

/** 既定の配色 (standard) で組み立てた _src/tokens.css の中身。 */
export function composeStandardTokens() {
  return composeTokens();
}

/** 標準カラーの説明。版とハッシュの頭を出し、どの写しから作ったかを追えるようにする。 */
export function standardLabel(vendor = readFileSync(STANDARD_PALETTE.vendor)) {
  const version = colorVersion(vendor.toString("utf8"));
  return `jp-web-design の standard-color-system.css${version ? ` v${version}` : ""} (sha256 ${sha256(vendor).slice(0, 12)})`;
}

/**
 * 上書きの CSS が、標準カラーにもボードの言葉にも無い名前を定義していれば、その名前を返す。
 * 綴りの誤りで上書きが効かないことに気づけるようにする (止めはしない)。
 */
export function unknownOverlayNames(css) {
  const known = new Set([...definedNames(readFileSync(BOARD_TOKENS, "utf8")), ...definedNames(readFileSync(STANDARD_PALETTE.vendor, "utf8"))]);
  return [...new Set(definedNames(css))].filter((name) => !known.has(name));
}

/** CSS の中で定義しているカスタムプロパティの名前 (--xxx) を、出てきた順に返す。注釈の中は見ない。 */
export function definedNames(css) {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...body.matchAll(/(?:^|[;{\s])(--[A-Za-z0-9_-]+)\s*:/g)].map((m) => m[1]);
}
