/**
 * 打ち合わせ資料の文書 (要件定義.md など) を HTML にする小さな Markdown 変換 (npm 依存なし)。
 *
 * 扱うもの: 見出し (#)、段落 (中の改行はそのまま改行 <br />)、箇条書き (- * +)、番号つき (1.)、入れ子 (字下げ)、
 *          GFM の表 (\| で縦棒を書ける、:--- の寄せ)、コードブロック (``` と ~~~)、引用 (>)、区切り線、
 *          太字 (**x** と __x__)、インラインコード (`x`)、バックスラッシュでの記号の打ち消し。
 * 文字はすべて HTML として逃がす (文書に書いた <tag> は文字のまま出る)。
 * リンク [文字](URL) と画像 ![説明](URL) は文字だけ残す (まとめ HTML に外の URL を持ち込まないため)。
 *
 * 呼び出し側のフック:
 *   heading(level, inlineHtml, plain) → 見出しの HTML (省略時は <hN>)
 *   image(alt, src) → trusted HTML; null/undefined falls back to escaped alt
 *   imageReferenceMissing(alt, id) → optional notification for an unresolved image reference
 *   table(tableHtml)                  → 表の HTML (横にはみ出す表を包むときなどに使う)
 */
import { escapeHtml } from "./briefing-files.mjs";
import { decodeEntities } from "./html-tokens.mjs";

const FENCE_RE = /^ {0,3}(`{3,}|~{3,})[ \t]*([^\s`]*)[^`]*$/;
const HEADING_RE = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
const HR_RE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE_RE = /^ {0,3}> ?/;
const LIST_RE = /^([ \t]*)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
const TABLE_DELIM_RE = /^ {0,3}\|?[ \t]*:?-+:?[ \t]*(?:\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$/;
const ASCII_PUNCT = /[!-/:-@[-`{-~]/;

function isBlank(line) {
  return /^[ \t]*$/.test(line);
}

function indentOf(line) {
  const expanded = line.replace(/\t/g, "    ");
  return expanded.length - expanded.trimStart().length;
}

/** 表の 1 行をセルに分ける。\| は縦棒の文字として残す。 */
export function splitTableRow(line) {
  let inner = line.trim();
  if (inner.startsWith("|")) inner = inner.slice(1);
  if (inner.endsWith("|") && !inner.endsWith("\\|")) inner = inner.slice(0, -1);
  return inner.split(/(?<!\\)\|/).map((cell) => cell.replace(/\\\|/g, "|").trim());
}

export function isTableStart(lines, i) {
  if (i + 1 >= lines.length || !lines[i].includes("|") || !TABLE_DELIM_RE.test(lines[i + 1])) return false;
  return splitTableRow(lines[i]).length === splitTableRow(lines[i + 1]).length;
}

function startsBlock(lines, i) {
  const line = lines[i];
  return FENCE_RE.test(line) || HEADING_RE.test(line) || HR_RE.test(line) || QUOTE_RE.test(line)
    || LIST_RE.test(line) || isTableStart(lines, i);
}

// ---------------------------------------------------------------- 行の中

/** 行の中の書式を HTML にする。 */
export function renderInline(text, hooks = {}) {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const ch = text[i];
    if (ch === "\\" && i + 1 < text.length && ASCII_PUNCT.test(text[i + 1])) {
      out += escapeHtml(text[i + 1], false);
      i += 2;
      continue;
    }
    if (ch === "`") {
      const run = /^`+/.exec(text.slice(i))[0];
      const close = text.indexOf(run, i + run.length);
      if (close !== -1 && text[close + run.length] !== "`") {
        let code = text.slice(i + run.length, close).replace(/\n/g, " ");
        if (/^ .* $/.test(code) && code.trim()) code = code.slice(1, -1);
        out += `<code>${escapeHtml(code, false)}</code>`;
        i = close + run.length;
        continue;
      }
      out += escapeHtml(run, false);
      i += run.length;
      continue;
    }
    if (ch === "!" && text[i + 1] === "[") {
      const link = readLink(text, i + 1, hooks, true);
      if (link) {
        if (link.reference !== undefined && link.src === undefined) hooks.imageReferenceMissing?.(link.label, link.reference);
        out += (link.src === undefined ? null : hooks.image?.(link.label, link.src)) ?? escapeHtml(link.label, false);
        i = link.end;
        continue;
      }
    }
    if (ch === "[") {
      const link = readLink(text, i, hooks);
      if (link) {
        out += renderInline(link.label, hooks); // リンクは文字だけ
        i = link.end;
        continue;
      }
    }
    if (ch === "<") {
      const auto = /^<((?:https?|mailto):[^\s<>]+)>/i.exec(text.slice(i));
      if (auto) {
        out += escapeHtml(auto[1], false);
        i += auto[0].length;
        continue;
      }
    }
    if ((ch === "*" || ch === "_") && text[i + 1] === ch) {
      const mark = ch + ch;
      const close = findStrongClose(text, i + 2, mark);
      const before = text[i - 1] ?? " ";
      const intraword = ch === "_" && /[\p{L}\p{N}]/u.test(before);
      if (close !== -1 && !/\s/.test(text[i + 2] ?? " ") && !intraword) {
        out += `<strong>${renderInline(text.slice(i + 2, close), hooks)}</strong>`;
        i = close + 2;
        continue;
      }
    }
    out += escapeHtml(ch, false);
    i += 1;
  }
  return out;
}

function findStrongClose(text, from, mark) {
  let at = text.indexOf(mark, from);
  while (at !== -1) {
    const inCode = (text.slice(from, at).match(/`/g) || []).length % 2 === 1;
    if (at > from && !/\s/.test(text[at - 1]) && !inCode) return at;
    at = text.indexOf(mark, at + 1);
  }
  return -1;
}

/** [文字](URL) か [文字][名前] を読む。読めなければ null。 */
function readLink(text, open, hooks = {}, image = false) {
  let depth = 0;
  let close = -1;
  for (let i = open; i < text.length; i += 1) {
    if (text[i] === "\\") {
      i += 1;
    } else if (text[i] === "[") {
      depth += 1;
    } else if (text[i] === "]") {
      depth -= 1;
      if (depth === 0) {
        close = i;
        break;
      }
    }
  }
  if (close === -1) return null;
  const label = text.slice(open + 1, close);
  if (text[close + 1] === "(") {
    let paren = 0;
    for (let i = close + 1; i < text.length; i += 1) {
      if (text[i] === "(") paren += 1;
      else if (text[i] === ")" && (paren -= 1) === 0) {
        const destination = text.slice(close + 2, i).trim();
        const match = /^(?:<([^<>]*)>|([^\s]+?))(?:\s+["'].*["'])?$/.exec(destination);
        return { label, src: match ? (match[1] ?? match[2]) : destination, end: i + 1 };
      }
    }
    return null;
  }
  if (text[close + 1] === "[") {
    const end = text.indexOf("]", close + 2);
    if (end === -1) return null;
    const reference = text.slice(close + 2, end) || label;
    return { label, reference, src: hooks.references?.get(referenceKey(reference)), end: end + 1 };
  }
  const src = hooks.references?.get(referenceKey(label));
  return image || src !== undefined ? { label, reference: label, src, end: close + 1 } : null;
}

const referenceKey = (label) => label.replace(/\\([!-/:-@[-`{-~])/g, "$1").trim().replace(/\s+/g, " ").toLowerCase();

/** Collect document-wide definitions before splitting into sections; first definition wins.
 * Fenced and indented code are never definitions. Invalid definition syntax stays visible.
 */
export function prepareMarkdown(text, hooks = {}) {
  const lines = String(text).replace(/^﻿/, "").replace(/\r\n?/g, "\n").split("\n");
  const references = new Map(hooks.references ?? []);
  let fence = null;
  const source = lines.map((line) => {
    if (fence) {
      const closing = new RegExp(`^ {0,3}${fence[0]}{${fence.length},}[ \t]*$`);
      if (closing.test(line)) fence = null;
      return line;
    }
    const start = FENCE_RE.exec(line);
    if (start) { fence = start[1]; return line; }
    const definition = /^ {0,3}\[((?:\\.|[^\]\\])+)\]:[ \t]*(?:<([^<>\n]*)>|(\S+?))(?:[ \t]+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*$/.exec(line);
    if (!definition) return line;
    const key = referenceKey(definition[1]);
    if (!key) return line;
    if (!references.has(key)) references.set(key, definition[2] ?? definition[3]);
    return "";
  }).join("\n");
  return { text: source, hooks: { ...hooks, references } };
}

// ---------------------------------------------------------------- かたまり

function paragraphHtml(lines, hardWrap, hooks) {
  const joined = lines.map((l) => l.trim()).join("\n");
  const inline = renderInline(joined, hooks);
  return hardWrap ? inline.replace(/\n/g, "<br />\n") : inline;
}

function renderTable(lines, start, hooks) {
  const header = splitTableRow(lines[start]);
  const aligns = splitTableRow(lines[start + 1]).map((cell) => {
    const left = cell.startsWith(":");
    const right = cell.endsWith(":");
    return left && right ? "center" : right ? "right" : left ? "left" : null;
  });
  let i = start + 2;
  const rows = [];
  while (i < lines.length && !isBlank(lines[i]) && lines[i].includes("|") && !FENCE_RE.test(lines[i])) {
    rows.push(splitTableRow(lines[i]));
    i += 1;
  }
  const cellHtml = (tag, text, col) => {
    const align = aligns[col] ? ` style="text-align:${aligns[col]}"` : "";
    return `  <${tag}${align}>${renderInline(text, hooks)}</${tag}>\n`;
  };
  let html = "<table>\n<thead>\n<tr>\n";
  header.forEach((text, col) => {
    html += cellHtml("th", text, col);
  });
  html += "</tr>\n</thead>\n";
  if (rows.length) {
    html += "<tbody>\n";
    for (const row of rows) {
      html += "<tr>\n";
      header.forEach((_, col) => {
        html += cellHtml("td", row[col] ?? "", col);
      });
      html += "</tr>\n";
    }
    html += "</tbody>\n";
  }
  html += "</table>\n";
  return { html: hooks.table ? hooks.table(html) : html, next: i };
}

/** Shared list reader; body lines retain paragraphs, fences and nested lists. */
export function readList(lines, start) {
  const first = LIST_RE.exec(lines[start]);
  const baseIndent = indentOf(first[1]);
  const ordered = /\d/.test(first[2]);
  const items = [];
  let i = start;
  while (i < lines.length) {
    const m = LIST_RE.exec(lines[i]);
    if (!m || indentOf(m[1]) !== baseIndent || /\d/.test(m[2]) !== ordered) break;
    const contentIndent = baseIndent + m[2].length + 1;
    const body = [m[3] ?? ""];
    i += 1;
    while (i < lines.length) {
      const line = lines[i];
      if (isBlank(line)) {
        let j = i;
        while (j < lines.length && isBlank(lines[j])) j += 1;
        if (j < lines.length && indentOf(lines[j]) > baseIndent) {
          body.push("");
          i += 1;
          continue;
        }
        break;
      }
      const indent = indentOf(line);
      if (indent > baseIndent) {
        const expanded = line.replace(/\t/g, "    ");
        body.push(expanded.slice(Math.min(indent, contentIndent)));
        i += 1;
        continue;
      }
      if (LIST_RE.test(line) || startsBlock(lines, i)) break;
      body.push(line.trim()); // 字下げなしの続きの行は同じ項目の続き
      i += 1;
    }
    items.push(body);
  }
  const startNo = ordered ? Number.parseInt(first[2], 10) : 1;
  return { ordered, start: startNo, items, next: i };
}

function renderList(lines, start, hooks, depth) {
  const { ordered, start: startNo, items, next } = readList(lines, start);
  const tag = ordered ? "ol" : "ul";
  const open = ordered && startNo !== 1 ? `<ol start="${startNo}">` : `<${tag}>`;
  const inner = items.map((body) => `<li>${renderBlocks(body, hooks, { tight: true, depth: depth + 1 }).trim()}</li>\n`).join("");
  return { html: `${open}\n${inner}</${tag}>\n`, next };
}

/** 行の並びをかたまりごとに HTML にする。tight は箇条書きの中 (段落を <p> で包まない)。 */
function renderBlocks(lines, hooks, { tight = false, depth = 0 } = {}) {
  let html = "";
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (isBlank(line)) {
      i += 1;
      continue;
    }
    const fence = FENCE_RE.exec(line);
    if (fence) {
      const marker = fence[1];
      const body = [];
      i += 1;
      while (i < lines.length) {
        const closing = new RegExp(`^ {0,3}${marker[0] === "`" ? "`" : "~"}{${marker.length},}[ \\t]*$`);
        if (closing.test(lines[i])) {
          i += 1;
          break;
        }
        body.push(lines[i]);
        i += 1;
      }
      const lang = fence[2] ? ` class="language-${escapeHtml(decodeEntities(fence[2]))}"` : "";
      const code = body.length ? `${body.join("\n")}\n` : "";
      html += `<pre><code${lang}>${escapeHtml(code, false)}</code></pre>\n`;
      continue;
    }
    const heading = HEADING_RE.exec(line);
    if (heading) {
      const level = heading[1].length;
      const inline = renderInline((heading[2] ?? "").trim(), hooks);
      const plain = decodeEntities(inline.replace(/<[^>]+>/g, "")).trim();
      html += hooks.heading ? hooks.heading(level, inline, plain) : `<h${level}>${inline}</h${level}>\n`;
      i += 1;
      continue;
    }
    if (HR_RE.test(line)) {
      html += "<hr />\n";
      i += 1;
      continue;
    }
    if (isTableStart(lines, i)) {
      const table = renderTable(lines, i, hooks);
      html += table.html;
      i = table.next;
      continue;
    }
    if (QUOTE_RE.test(line)) {
      const body = [];
      while (i < lines.length && QUOTE_RE.test(lines[i])) {
        body.push(lines[i].replace(QUOTE_RE, ""));
        i += 1;
      }
      html += `<blockquote>\n${renderBlocks(body, hooks, { depth })}</blockquote>\n`;
      continue;
    }
    if (LIST_RE.test(line) && depth < 20) {
      const list = renderList(lines, i, hooks, depth);
      html += list.html;
      i = list.next;
      continue;
    }
    const para = [line];
    i += 1;
    while (i < lines.length && !isBlank(lines[i]) && !startsBlock(lines, i)) {
      para.push(lines[i]);
      i += 1;
    }
    const inline = paragraphHtml(para, hooks.hardWrap !== false, hooks);
    html += tight ? `${inline}\n` : `<p>${inline}</p>\n`;
  }
  return html;
}

/** Markdown の文字列を HTML にする。 */
export function renderMarkdown(text, hooks = {}) {
  const prepared = prepareMarkdown(text, hooks);
  return renderBlocks(prepared.text.split("\n"), prepared.hooks);
}
