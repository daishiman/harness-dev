/** Resource references shared by rendering and book assembly. No text/code-example scanning. */
import path from "node:path";
import { readFileSync } from "node:fs";
import { tokenizeHtml } from "./html-tokens.mjs";
import { isFile, sha256, toPosix } from "./briefing-files.mjs";

const REF_ATTRS = new Set(["src", "href", "poster", "action", "formaction", "xlink:href"]);
export const externalRef = (value) => /^(?:https?:)?\/\//i.test(value.trim());
const cssUnescape = (s) => s.replace(/\\([\da-f]{1,6})\s?|\\([^\r\n])/gi, (_, hex, ch) => hex ? String.fromCodePoint(Math.min(parseInt(hex, 16) || 65533, 0x10ffff)) : ch);

/** CSS tokens: skip comments and ordinary strings; collect url(), imports and image-set string candidates. */
export function cssRefs(css) {
  const out = [];
  const tokens = css.match(/\/\*[\s\S]*?\*\/|"(?:\\[\s\S]|[^"\\])*"|'(?:\\[\s\S]|[^'\\])*'|(?:\\[\da-f]{1,6}\s?|\\.|[-\w])+|[^\s]/gi) ?? [];
  const stack = [];
  let importing = false;
  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.startsWith("/*")) continue;
    const word = cssUnescape(t).toLowerCase();
    if (t === "@" && tokens[i + 1]?.toLowerCase() === "import") { importing = true; i++; continue; }
    if (t === ";") importing = false;
    if (tokens[i + 1] === "(") {
      i++;
      if (word === "url") {
        let value = "";
        while (++i < tokens.length && tokens[i] !== ")") if (!tokens[i].startsWith("/*")) value += tokens[i];
        if (/^["']/.test(value)) value = value.slice(1, -1);
        out.push({ attr: importing ? "@import" : "url()", value: cssUnescape(value) });
        importing = false;
      } else stack.push(word);
      continue;
    }
    if (t === "(") stack.push("");
    if (t === ")") stack.pop();
    if (/^["']/.test(t) && (importing || /^(?:-webkit-)?image-set$/.test(stack.at(-1) ?? ""))) {
      out.push({ attr: importing ? "@import" : "image-set()", value: cssUnescape(t.slice(1, -1)) });
      importing = false;
    }
  }
  return out;
}

/** srcset URLs may contain commas (notably data URIs); descriptors end at the next comma. */
export function srcsetRefs(value) {
  const urls = [];
  let rest = value.trim();
  while (rest) {
    rest = rest.replace(/^[\s,]+/, "");
    const m = /^\S+/.exec(rest);
    if (!m) break;
    const url = m[0];
    urls.push(url.replace(/,+$/, ""));
    rest = rest.slice(url.length);
    if (!url.endsWith(",")) {
      const comma = rest.indexOf(",");
      rest = comma < 0 ? "" : rest.slice(comma + 1);
    }
  }
  return urls;
}

export function htmlRefs(html) {
  const refs = [];
  let where = "head";
  for (const token of tokenizeHtml(html)) {
    if (token.type === "raw" && token.tag === "style") refs.push(...cssRefs(token.text).map((r) => ({ ...r, where })));
    if (token.type !== "start") continue;
    const attrs = token.attrs;
    if (token.tag === "section" && (attrs.class ?? "").split(/\s+/).includes("page") && attrs.id) where = attrs.id;
    for (const [attr, raw] of Object.entries(attrs)) {
      const value = (raw ?? "").trim();
      if (REF_ATTRS.has(attr) || (attr === "data" && token.tag === "object")) refs.push({ attr, value, where });
      if (attr === "srcset" || attr === "imagesrcset") refs.push(...srcsetRefs(value).map((v) => ({ attr, value: v, where })));
      if (["style", "fill", "stroke", "filter", "clip-path", "mask"].includes(attr)) refs.push(...cssRefs(value).map((r) => ({ ...r, where })));
    }
  }
  return refs;
}

export function localRef(value) {
  const ref = value.trim().split(/[?#]/, 1)[0];
  if (!ref || /^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(ref)) return null;
  try { return decodeURIComponent(ref); } catch { return ref; }
}

/** Follow CSS imports/backgrounds recursively; missing files stay in the receipt as null hashes. */
export function dependencyReceipt(htmlFile, base) {
  const found = new Map();
  const visit = (file, kind) => {
    file = path.resolve(file);
    const key = toPosix(path.relative(base, file));
    if (found.has(key)) return;
    found.set(key, null);
    if (!isFile(file)) return;
    const bytes = readFileSync(file);
    found.set(key, sha256(bytes));
    if (!kind) return;
    const refs = kind === "html" ? htmlRefs(bytes.toString("utf8")) : cssRefs(bytes.toString("utf8"));
    for (const { value, attr } of refs) {
      const ref = localRef(value);
      if (!ref) continue;
      const target = path.resolve(path.dirname(file), ref);
      visit(target, attr === "@import" || path.extname(target).toLowerCase() === ".css" ? "css" : null);
    }
  };
  visit(htmlFile, "html");
  for (const css of ["tokens.css", "common.css"]) visit(path.join(path.dirname(htmlFile), css), "css");
  return Object.fromEntries([...found].sort(([a], [b]) => a.localeCompare(b)));
}
