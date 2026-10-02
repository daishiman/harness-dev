/**
 * 配色の共通契約。_src/tokens.css (ボードの言葉 + 標準カラー + 案件の上書き) のうち、
 * トップレベルの :root にある宣言だけを配色とみなす。クラスの規則と @media などの条件付きのブロックは読み飛ばす
 * (標準カラーの写しが持つ部品クラスや印刷・高コントラスト向けの差し替えは、既定の見た目を決めないため)。
 * 必須の役割名は、標準の組み立て (scripts/lib/palette.mjs の composeStandardTokens) から得る。原色名・値は案件で変更できる。
 * CSS一般の構文検査ではなく、空値・不足・var参照切れ・循環を生成前に止める。
 */
import { composeStandardTokens } from "./palette.mjs";

// Strings/comments are kept whole so quoted punctuation is not a declaration boundary.
const PARTS = /\/\*[\s\S]*?\*\/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^]/g;
function parts(text) { return [...text.matchAll(PARTS)].map(([p]) => p.startsWith("/*") ? " " : p); }

function declarations(css) {
  const tokens = parts(css);
  const values = new Map();
  const priorities = new Map();
  let prelude = "", body = "", inRoot = false, skipDepth = 0;
  function add(text) {
    if (!text.trim()) return;
    const match = /^\s*(--[\w-]+|color-scheme)\s*:\s*([\s\S]*)$/.exec(text);
    if (!match) throw new Error("配色は :root のカスタムプロパティ宣言で定義してください");
    const important = /\s*!\s*important\s*$/i.test(match[2]);
    if (match[1] !== "color-scheme" && (important || !priorities.get(match[1]))) {
      values.set(match[1], match[2].trim().replace(/\s*!\s*important\s*$/i, ""));
      priorities.set(match[1], important);
    }
  }
  for (const token of tokens) {
    if (skipDepth) {
      // :root 以外のブロックは、対応する } まで中身を見ない
      if (token === "{") skipDepth++;
      else if (token === "}") skipDepth--;
    } else if (inRoot) {
      if (token === "{") throw new Error("配色の :root に入れ子は使えません");
      if (token === ";" || token === "}") {
        add(body); body = "";
        if (token === "}") inRoot = false;
      } else body += token;
    } else if (token === "{") {
      if (prelude.trim() === ":root") inRoot = true;
      else skipDepth = 1;
      prelude = "";
    } else if (token === ";" || token === "}") {
      throw new Error("配色に宣言以外の文 (@import など) は使えません");
    } else prelude += token;
  }
  if (inRoot || skipDepth || prelude.trim()) throw new Error("配色の :root 宣言が閉じていないか、宣言以外の文字があります");
  return values;
}

let required;
/** 必須の役割名。標準の組み立てが定義する名前のうち、基本色 (--p-*) を除いたもの。 */
export function requiredDesignTokens() {
  required ??= Object.freeze([...declarations(composeStandardTokens()).keys()].filter((key) => !key.startsWith("--p-")));
  return required;
}

/** Return error messages; an empty array means the supported token contract is complete. */
export function validateDesignTokens(css) {
  let values;
  let names;
  try { names = requiredDesignTokens(); } catch (error) { return [`標準カラーを読めません: ${error.message}`]; }
  try { values = declarations(css); } catch (error) { return [error.message]; }
  const errors = new Set();
  const resolved = new Map();
  const active = new Set();
  const checked = new Set();
  // CSS cycles include references in fallback branches, even if the first branch exists.
  function checkCycles(name, trail = new Set()) {
    if (trail.has(name)) throw new Error(`トークン参照が循環しています: ${name}`);
    if (checked.has(name) || !values.has(name)) return;
    trail.add(name);
    const unquoted = parts(values.get(name)).map((p) => /^["']/.test(p) ? " " : p).join("");
    for (const [, dependency] of unquoted.matchAll(/\bvar\(\s*(--[\w-]+)/g)) checkCycles(dependency, trail);
    trail.delete(name);
    checked.add(name);
  }
  function resolve(name) {
    if (active.has(name)) throw new Error(`トークン参照が循環しています: ${name}`);
    if (!values.has(name)) throw new Error(`トークンがありません: ${name}`);
    if (resolved.has(name)) return resolved.get(name);
    active.add(name);
    try {
      const value = expand(values.get(name));
      if (!value.trim() || /^(initial|inherit|unset|revert|revert-layer)$/i.test(value.trim())) throw new Error(`トークンの値が空か未確定です: ${name}`);
      resolved.set(name, value);
      return value;
    } finally { active.delete(name); }
  }
  function expand(value) {
    const tokens = parts(value);
    let result = "";
    for (let i = 0; i < tokens.length; i++) {
      if (tokens.slice(i, i + 4).join("") !== "var(") { result += tokens[i]; continue; }
      let depth = 1, argument = "", fallback = null;
      i += 4;
      for (; i < tokens.length; i++) {
        const t = tokens[i];
        if (t === "(") depth++;
        if (t === ")" && --depth === 0) break;
        if (t === "," && depth === 1 && fallback === null) fallback = "";
        else if (fallback === null) argument += t;
        else fallback += t;
      }
      if (depth !== 0) throw new Error("var() が閉じていません");
      const name = argument.trim();
      if (!/^--[\w-]+$/.test(name)) throw new Error(`var() の参照名が不正です: ${name}`);
      result += values.has(name) ? resolve(name) : fallback !== null ? expand(fallback) : resolve(name);
    }
    return result;
  }
  for (const name of names) {
    try { checkCycles(name); resolve(name); } catch (error) { errors.add(error.message); }
  }
  return [...errors];
}
