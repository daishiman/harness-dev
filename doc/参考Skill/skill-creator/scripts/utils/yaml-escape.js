// scripts/utils/yaml-escape.js
// YAML safe escape ヘルパー。description は double-quoted scalar に統一する方針のため、
// 改行・Tab・連続空白を正規化し、ダブルクォート / バックスラッシュをエスケープする。

/**
 * 改行 (\r\n, \n)、Tab、連続空白を半角空白 1 個に正規化する。
 *
 * @param {string} str
 * @returns {string}
 */
export function normalizeWhitespace(str) {
  return String(str)
    .replace(/\r\n/g, "\n")
    .replace(/\t/g, " ")
    .replace(/\n+/g, " ")
    .replace(/ {2,}/g, " ")
    .trim();
}

/**
 * double-quoted scalar 内で安全な文字列に変換する。
 * バックスラッシュとダブルクォートをエスケープし、改行は空白に置換する。
 *
 * @param {string} str
 * @returns {string}
 */
export function escapeForScalar(str) {
  return String(str)
    .replace(/\\/g, "\\\\")
    .replace(/"/g, '\\"')
    .replace(/\r?\n/g, " ");
}

/**
 * 文字列を YAML double-quoted scalar として出力する。
 * 改行や危険文字を正規化・エスケープしてから double-quote で囲む。
 *
 * @param {string} str
 * @returns {string}
 */
export function toDoubleQuotedScalar(str) {
  return `"${escapeForScalar(normalizeWhitespace(str))}"`;
}
