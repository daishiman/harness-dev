/**
 * 文書 (要件定義.md・仕様書.md・ヒアリング.md・変更点.md) を、まとめ HTML の中で「レポートの形」に描く。
 * Markdown は正本のまま (validate と /build-app は Markdown を読む)。ここで変えるのは見せ方だけ。
 *
 * 見分け方 (どれにも当たらなければ、今までどおりの表・箇条書きで描く):
 *   - # の行は文書の題、すぐ下の「版:」「更新日:」は題の下の小さな札。
 *   - ## の章は 1 枚の区画カード。### が 2 つで中身が箇条書きだけなら左右の対比、3 つ以上なら小カードの格子。
 *   - 表は見出しの行 (列の並び) で部品を選ぶ (TABLES)。列の並びは document-structure.md と validate の決まりと同じ。
 *   - 箇条書きは形で選ぶ: 「名前: 文」だけ → 2 列の定義 / 番号つき → 段の流れ / 字下げの「名前: 文」を持つ → 候補のカード。
 *   - 文の中の番号 (F01・Q01・S01・D01・R01・H01) と「NN のボード」は、その場所へのリンクにする。
 *     行き先がまとめに無いリンクは resolveRefs が文字に戻す。
 * 同じ文書からは、いつも同じ HTML が出る。JS は使わない。外への参照も作らない。
 */
import { escapeHtml } from "./briefing-files.mjs";
import { renderInline, renderMarkdown, splitTableRow, readList, isTableStart, prepareMarkdown } from "./markdown-lite.mjs";

const HEADING_RE = /^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$/;
const FENCE_RE = /^ {0,3}(`{3,}|~{3,})/;
const ITEM_RE = /^([ \t]*)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*))?$/;
const META_RE = /^(版|更新日)\s*[:：]\s*(.+)$/;
// 名前は 24 字まで (8 章の候補の名前が収まる長さ)。長い文の途中の「:」では分けない
const LABEL_RE = /^([^:：。\n]{1,24}?)\s*[:：]\s*([\s\S]+)$/;
const CODE_ONLY_RE = /^[A-Z]\d{2,}$/;
const UNIT_RE = /^1\s*件\s*[=＝]/;
// Python の \b と同じく、日本語の文字も語の一部として扱う ("S01画面" は S01 で切らない)
const WORD_END = "(?![\\p{L}\\p{N}_])";
const HEAD_NUMBER_RE = /^(\d+(?:\.\d+)*)\.?(?:[ \t]+([\s\S]*))?$/u;
const HEAD_VERSION_RE = new RegExp(`^(v\\d+(?:\\.\\d+)*)${WORD_END}[ \\t]*([\\s\\S]*)$`, "u");
const HEAD_CODE_RE = new RegExp(`^([A-Za-z]\\d+)${WORD_END}[ \\t]*([\\s\\S]*)$`, "u");
// 文の中の参照: 番号 (F01 など) / 「02 のボード」 / 「ボード: 02, 03」。1 回の走査で拾う (置きかえた結果を二度読まない)
const REF_RE = new RegExp([
  `(?<![\\p{L}\\p{N}_#-])([FQSDRH])(\\d{2,})${WORD_END}`,
  // 「02 のボード」「04・09・10 のボード」。前が英字や数字のとき (X04 など) は拾わない
  "(?<![\\p{Lu}\\p{Ll}\\p{N}_#.-])(\\d{2}(?:\\s*[・,、，]\\s*\\d{2})*\\s*のボード)",
  "(ボード\\s*[:：]\\s*)(\\d{2}(?:\\s*[,、，]\\s*\\d{2})*)",
].join("|"), "gu");
// 文の中の番号の行き先 (id の頭)。頭は build-briefing-book.mjs の DOCS と同じ
const CODE_TARGET = { F: "req-f", Q: "req-q", S: "spec-s", D: "spec-d", R: "spec-r", H: "hear-h" };
const NO_WORDS = /やらない|入れない|しない/;
const DEVICE_TONE = { スマホ: "t-phone", PC: "t-pc" };

// ── 文字 ─────────────────────────────────────

const esc = (s) => escapeHtml(String(s ?? ""), false);

/** タグの外の文字だけを置きかえる。 */
function mapText(html, fn) {
  return html.split(/(<[^>]*>)/).map((part, i) => (i % 2 ? part : fn(part))).join("");
}

/** 文の中の番号・「NN のボード」・「ボード: NN, NN」をリンクにする。 */
function linkCodes(html) {
  return mapText(html, (text) => text.replace(REF_RE, (all, letter, num, no, head, nos) => {
    if (letter) return `<a class="ref" href="#${CODE_TARGET[letter]}${num}">${all}</a>`;
    if (no) return no.replace(/(\d{2})(\s*のボード)?/g, (m, n) => `<a class="ref" href="#b${n}">${m}</a>`);
    return head + nos.replace(/\d{2}/g, (n) => `<a class="ref" href="#b${n}">${n}</a>`);
  }));
}

/** セルや項目の文字を HTML にする (書式・逃がし・番号のリンク・改行)。 */
function inl(text, hooks = {}) {
  return linkCodes(renderInline(String(text ?? "").trim(), hooks)).replace(/\n/g, "<br />");
}

function formatters(hooks) {
  return {
    inl: (text) => inl(text, hooks),
    sourceChips: (text) => sourceChips(text, hooks),
    screenChips: (text) => screenChips(text, hooks),
    boardLinks: (text) => boardLinks(text, hooks),
  };
}

/** 行き先がまとめの中に無いリンクを文字に戻す。ids はまとめ全体の id。 */
export function resolveRefs(html, ids) {
  return html.replace(/<a class="ref([^"]*)" href="#([^"]+)">([\s\S]*?)<\/a>/g,
    (all, cls, id, inner) => (ids.has(id) ? all : `<span class="ref${cls}">${inner}</span>`));
}

function chip(text, tone = "", href = "") {
  const cls = `d-chip${tone ? ` ${tone}` : ""}`;
  return href ? `<a class="ref ${cls}" href="#${href}">${esc(text)}</a>` : `<span class="${cls}">${esc(text)}</span>`;
}

/** 根拠・出どころの値を札にする: 素材:x / 聞き取り:H03 / 例 / 決めること:Q02 / 既定案 / 未定 / 要望。 */
function sourceChips(value, hooks = {}) {
  const fmt = formatters(hooks);
  const parts = String(value ?? "").split(/、|,\s*/).map((p) => p.trim()).filter(Boolean);
  return parts.map((part) => {
    const [head, ...rest] = part.split(/[:：]/);
    const tail = rest.join(":").trim();
    const code = /^[A-Z]\d{2,}$/.test(tail) ? tail : "";
    switch (head.trim()) {
      case "素材": return `<span class="d-src">${chip("素材", "t-src")}${tail ? `<span class="d-src-at">${esc(tail)}</span>` : ""}</span>`;
      case "聞き取り": return code ? chip(`聞き取り ${code}`, "t-heard", `hear-h${code.slice(1)}`) : chip(part, "t-heard");
      case "決めること": return code ? chip(`決めること ${code}`, "t-ask", `req-q${code.slice(1)}`) : chip(part, "t-ask");
      case "未定": return chip(part, "t-ask");
      case "要望": return chip(part, "t-want");
      case "例": case "既定案": return chip(part);
      default: return `<span class="d-src-at">${fmt.inl(part)}</span>`;
    }
  }).join(" ");
}

/** 「S01, S02」「なし」を画面の札にする。 */
function screenChips(value, hooks = {}) {
  const fmt = formatters(hooks);
  return fmt.inl(value).replace(/class="ref" href="#spec-s/g, 'class="ref d-chip t-screen" href="#spec-s');
}

function deviceChip(value) {
  const v = String(value ?? "").trim();
  return v ? chip(v, DEVICE_TONE[v.replace(/\s/g, "")] ?? "t-pc") : "";
}

// ── 組み立て (行 → 章 → かたまり) ──────────────────────

function outline(text) {
  const lines = String(text).replace(/^﻿/, "").replace(/\r\n?/g, "\n").split("\n");
  const doc = { title: null, lines: [], sections: [] };
  let sec = null;
  let sub = null;
  let fence = null;
  for (const line of lines) {
    const target = sub ?? sec ?? doc;
    const f = FENCE_RE.exec(line);
    if (fence) {
      if (f && f[1][0] === fence[0] && f[1].length >= fence.length && !line.trim().slice(f[1].length)) fence = null;
      target.lines.push(line);
      continue;
    }
    if (f) {
      fence = f[1];
      target.lines.push(line);
      continue;
    }
    const h = HEADING_RE.exec(line);
    if (h && h[1].length === 1 && doc.title === null && !sec) {
      doc.title = h[2];
    } else if (h && h[1].length === 2) {
      sec = { head: h[2], lines: [], subs: [] };
      sub = null;
      doc.sections.push(sec);
    } else if (h && h[1].length === 3 && sec) {
      sub = { head: h[2], lines: [] };
      sec.subs.push(sub);
    } else {
      target.lines.push(line);
    }
  }
  return doc;
}

const blank = (line) => /^[ \t]*$/.test(line);
const startsOther = (line) => FENCE_RE.test(line) || HEADING_RE.test(line) || /^ {0,3}>/.test(line);

/** 行の並びを かたまり (table / list / para / other) に分ける。 */
function blocks(lines, depth = 0) {
  if (depth >= 20) return [{ type: "other", raw: lines }];
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (blank(line)) {
      i += 1;
      continue;
    }
    if (isTableStart(lines, i)) {
      const start = i;
      const header = splitTableRow(lines[i]);
      const rows = [];
      i += 2;
      while (i < lines.length && !blank(lines[i]) && lines[i].includes("|")) {
        rows.push(splitTableRow(lines[i]));
        i += 1;
      }
      out.push({ type: "table", header, rows, raw: lines.slice(start, i) });
      continue;
    }
    if (ITEM_RE.test(line)) {
      const list = readList(lines, i);
      const raw = lines.slice(i, list.next);
      const items = list.items.map((body) => {
        const parsed = blocks(body, depth + 1);
        // A decorated item must begin with ordinary prose; otherwise keep raw Markdown.
        const first = parsed[0];
        const simple = !blank(body[0]) && first?.type === "para";
        const text = simple ? first.text : "";
        const children = simple ? body.slice(text.split("\n").length) : body;
        return { text, children };
      });
      out.push({ type: "list", ...list, items, raw });
      i = list.next;
      continue;
    }
    if (startsOther(line) || /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/.test(line)) {
      const raw = [];
      let fence = null;
      while (i < lines.length && (fence || !blank(lines[i]))) {
        const f = FENCE_RE.exec(lines[i]);
        if (f && !fence) fence = f[1];
        else if (f && f[1][0] === fence[0] && f[1].length >= fence.length && !lines[i].trim().slice(f[1].length)) fence = null;
        raw.push(lines[i]);
        i += 1;
        if (raw.length > 1 && !fence && f) break;
      }
      out.push({ type: "other", raw });
      continue;
    }
    const para = [lines[i++].trim()];
    while (i < lines.length && !blank(lines[i]) && !isTableStart(lines, i) && !ITEM_RE.test(lines[i]) && !startsOther(lines[i])) {
      para.push(lines[i].trim());
      i += 1;
    }
    out.push({ type: "para", text: para.join("\n") });
  }
  return out;
}

/** 見出しの文字を 番号と名前に分ける: "3.1 範囲" → {no:"3.1", name:"範囲"}、"S01 送る" → {no:"S01", name:"送る"}。 */
function splitHead(raw) {
  const text = String(raw).trim();
  for (const re of [HEAD_NUMBER_RE, HEAD_VERSION_RE, HEAD_CODE_RE]) {
    const m = re.exec(text);
    if (m) return { no: m[1], name: (m[2] ?? "").trim().replace(/^[(（](.*)[)）]$/, "$1") };
  }
  return { no: "", name: text };
}

/** 見出しの文字から id を作る: "3.1 範囲" → req-3-1、"v0.2 (..)" → chg-v0-2、"S01 写真" → spec-s01。 */
export function headingId(plain, prefix) {
  const { no } = splitHead(plain);
  if (!no) return null;
  return `${prefix}-${no.toLowerCase().replaceAll(".", "-")}`;
}

const plainOf = (raw) => renderInline(String(raw).trim()).replace(/<[^>]+>/g, "")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");

// ── 部品 ─────────────────────────────────────

const label = (key, value) => `<span class="d-label">${esc(key)}</span>${value}`;
const pick = (header, row) => Object.fromEntries(header.map((h, i) => [h, row[i] ?? ""]));

/** 表の部品。cols は document-structure.md の列の並び (validate と同じ)。 */
const TABLES = [
  {
    cols: ["使う人", "人数", "端末", "主にすること"],
    render(rows, ctx) {
      const { inl } = formatters(ctx.hooks);
      let sum = 0;
      const cards = rows.map((r) => {
        const raw = r["人数"].trim();
        const n = /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) ? Number(raw) : Number.NaN;
        sum = Number.isSafeInteger(sum + n) ? sum + n : Number.NaN;
        const count = inl(r["人数"]);
        return `<article class="d-card d-person"><div class="d-card-top"><b class="d-name">${inl(r["使う人"])}</b>${deviceChip(r["端末"])}</div>`
          + `<p class="d-count">${count}</p><p>${inl(r["主にすること"])}</p></article>`;
      });
      ctx.stat("使う人", Number.isFinite(sum) ? sum : rows.length, Number.isFinite(sum) ? "人" : "役割");
      return `<div class="d-cards">${cards.join("")}</div>`;
    },
  },
  {
    cols: ["番号", "できること", "画面", "最初の版"],
    render(rows, ctx) {
      const { inl, screenChips } = formatters(ctx.hooks);
      const groups = new Map();
      for (const r of rows) {
        const key = r["最初の版"].trim() || "-";
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(r);
      }
      const parts = [...groups].map(([key, list]) => {
        const first = key === "○";
        ctx.stat(first ? "最初の版でできること" : key === "あとで" ? "あとでにしたこと" : key, list.length, "件");
        const items = list.map((r) => {
          const tags = [...r["できること"].matchAll(/[(（]\s*要望\s*[:：]\s*(H\d{2,})\s*[)）]/g)].map((m) => m[1]);
          const text = r["できること"].replace(/\s*[(（]\s*要望\s*[:：]\s*H\d{2,}\s*[)）]/g, "");
          const want = tags.map((h) => chip(`要望 ${h}`, "t-want", `hear-h${h.slice(1)}`)).join(" ");
          return `<li${ctx.rowId(r["番号"])}><span class="d-id">${esc(r["番号"])}</span><span class="d-text">${inl(text)}</span>`
            + `<span class="d-tags">${screenChips(r["画面"])}${want ? ` ${want}` : ""}</span></li>`;
        });
        const title = first ? "最初の版でやる" : key === "あとで" ? "あとで (次の版から相談)" : `最初の版: ${key}`;
        return `<div class="d-group ${first ? "t-yes" : "t-later"}"><p class="d-group-h">${esc(title)}<span class="d-n">${list.length} 件</span></p>`
          + `<ol class="d-items">${items.join("")}</ol></div>`;
      });
      return `<div class="d-groups">${parts.join("")}</div>`;
    },
  },
  {
    cols: ["用語", "意味"],
    render: (rows, ctx) => `<dl class="d-terms">${rows.map((r) => `<div><dt>${inl(r["用語"], ctx.hooks)}</dt><dd>${inl(r["意味"], ctx.hooks)}</dd></div>`).join("")}</dl>`,
  },
  {
    cols: ["番号", "決めること", "案", "誰に聞くか"],
    render(rows, ctx) {
      const { inl } = formatters(ctx.hooks);
      let open = 0;
      const cards = rows.map((r) => {
        const done = /^決定/.test(r["誰に聞くか"].trim());
        if (!done) open += 1;
        const state = done ? chip(r["誰に聞くか"].trim(), "t-yes") : chip("未決", "t-ask");
        return `<article class="d-card d-q ${done ? "is-done" : "is-open"}"${ctx.rowId(r["番号"])}>`
          + `<div class="d-card-top"><span class="d-id t-ask">${esc(r["番号"])}</span>${state}</div>`
          + `<p class="d-name">${inl(r["決めること"])}</p>`
          + `<p class="d-line">${label(done ? "答え" : "案", inl(r["案"]))}</p>`
          + (done ? "" : `<p class="d-line">${label("誰に聞くか", inl(r["誰に聞くか"]))}</p>`) + "</article>";
      });
      ctx.stat("まだ決めていないこと", open, "件");
      return `<div class="d-cards d-wide">${cards.join("")}</div>`;
    },
  },
  {
    cols: ["番号", "質問", "回答", "出どころ"],
    render(rows, ctx) {
      const { inl, sourceChips } = formatters(ctx.hooks);
      ctx.stat("聞いたこと", rows.length, "件");
      const pending = rows.filter((r) => r["出どころ"].trim() === "未定").length;
      if (pending) ctx.stat("未定", pending, "件");
      const items = rows.map((r) => `<li${ctx.rowId(r["番号"])}><span class="d-id">${esc(r["番号"])}</span>`
        + `<div><p class="d-qa-q">${inl(r["質問"])}</p><p class="d-qa-a">${inl(r["回答"])}</p></div>`
        + `<span class="d-tags">${sourceChips(r["出どころ"])}</span></li>`);
      return `<ol class="d-qa">${items.join("")}</ol>`;
    },
  },
  {
    cols: ["画面番号", "画面名", "使う人", "端末", "ひとことで"],
    render(rows, ctx) {
      const { inl } = formatters(ctx.hooks);
      ctx.stat("画面", rows.length, "枚");
      const cards = rows.map((r) => {
        const code = r["画面番号"].trim();
        const name = /^S\d{2,}$/.test(code) ? `<a class="ref" href="#spec-s${code.slice(1)}">${inl(r["画面名"])}</a>` : inl(r["画面名"]);
        return `<article class="d-card d-screen"><div class="d-card-top"><span class="d-id">${esc(code)}</span>${deviceChip(r["端末"])}</div>`
          + `<p class="d-name">${name}</p><p class="d-meta">${inl(r["使う人"])}</p><p>${inl(r["ひとことで"])}</p></article>`;
      });
      return `<div class="d-cards">${cards.join("")}</div>`;
    },
  },
  { cols: ["項目", "種類", "必須", "初期値", "説明", "根拠"], render: (rows, ctx) => fieldTable("入力と表示の項目", ctx.header, rows, ctx.hooks) },
  { cols: ["項目", "型", "必須", "例", "根拠"], render: (rows, ctx) => fieldTable("覚えておく項目", ctx.header, rows, ctx.hooks) },
  {
    cols: ["操作", "動き", "次の画面"],
    render(rows, ctx) {
      const { inl } = formatters(ctx.hooks);
      const items = rows.map((r) => {
        const next = r["次の画面"].trim();
        const to = /^S\d{2,}$/.test(next) ? chip(`→ ${next}`, "t-screen", `spec-s${next.slice(1)}`) : `<span class="d-muted">${esc(next)}</span>`;
        return `<li><span class="d-btn">${inl(r["操作"])}</span><span class="d-text">${inl(r["動き"])}</span><span class="d-to">${to}</span></li>`;
      });
      return `<p class="d-cap">操作と動き</p><ol class="d-ops">${items.join("")}</ol>`;
    },
  },
  {
    cols: ["番号", "ルール", "いつ", "根拠"],
    render(rows, ctx) {
      const { inl, sourceChips } = formatters(ctx.hooks);
      ctx.stat("処理のルール", rows.length, "個");
      const items = rows.map((r) => `<li${ctx.rowId(r["番号"])}><span class="d-id">${esc(r["番号"])}</span><span class="d-text">${inl(r["ルール"])}</span>`
        + `<span class="d-tags">${chip(r["いつ"].trim(), "t-when")} ${sourceChips(r["根拠"])}</span></li>`);
      return `<ol class="d-rows">${items.join("")}</ol>`;
    },
  },
  {
    cols: ["項目", "方式", "理由"],
    render: (rows, ctx) => `<dl class="d-dl">${rows.map((r) => `<div><dt>${inl(r["項目"], ctx.hooks)}</dt><dd><b>${inl(r["方式"], ctx.hooks)}</b>`
      + `<span class="d-why">${inl(r["理由"], ctx.hooks)}</span></dd></div>`).join("")}</dl>`,
  },
  { cols: ["役割", "できること", "できないこと", "見える範囲"], render: (rows, ctx) => roleCards(rows, ctx.hooks) },
  { cols: ["役割", "できること", "できないこと"], render: (rows, ctx) => roleCards(rows, ctx.hooks) },
  {
    cols: ["番号", "変更", "場所", "きっかけ"],
    render(rows, ctx) {
      const { inl } = formatters(ctx.hooks);
      ctx.stat("変えたこと", rows.length, "件");
      const items = rows.map((r) => `<li><span class="d-id">${esc(r["番号"])}</span><span class="d-text">${inl(r["変更"])}</span>`
        + `<span class="d-sub-lines"><span class="d-line">${label("場所", inl(r["場所"]))}</span>`
        + `<span class="d-line">${label("きっかけ", inl(r["きっかけ"]))}</span></span></li>`);
      return `<ol class="d-rows">${items.join("")}</ol>`;
    },
  },
];
/** 部品にする表の列の並び。validate の表の決まりがどれもここにあることを tests/test_doc_report.py が確かめる。 */
export const TABLE_SHAPES = TABLES.map((t) => t.cols);

function fieldTable(caption, header, rows, hooks = {}) {
  const fmt = formatters(hooks);
  const cell = (h, v) => {
    if (h === "必須") return v.trim() === "○" ? '<span class="d-must">必須</span>' : `<span class="d-muted">${esc(v.trim() === "-" ? "任意" : v)}</span>`;
    if (h === "根拠") return fmt.sourceChips(v);
    if (h === "項目") return `<b>${fmt.inl(v)}</b>`;
    return fmt.inl(v);
  };
  const head = header.map((h) => `<th>${esc(h)}</th>`).join("");
  // data-k は、スマホ幅で行を縦に積むときの小さな見出し (CSS の attr(data-k))
  const body = rows.map((r) => `<tr>${header.map((h) => `<td data-k="${esc(h)}">${cell(h, r[h])}</td>`).join("")}</tr>`).join("\n");
  return `<p class="d-cap">${esc(caption)}</p><div class="tw d-fields"><table>\n<thead><tr>${head}</tr></thead>\n<tbody>\n${body}\n</tbody>\n</table></div>`;
}

function roleCards(rows, hooks = {}) {
  const fmt = formatters(hooks);
  const cards = rows.map((r) => `<article class="d-card d-role"><p class="d-name">${fmt.inl(r["役割"])}</p>`
    + `<p class="d-line t-can">${label("できること", fmt.inl(r["できること"]))}</p>`
    + `<p class="d-line t-cannot">${label("できないこと", fmt.inl(r["できないこと"]))}</p>`
    + (r["見える範囲"] !== undefined ? `<p class="d-line t-scope">${label("見える範囲", fmt.inl(r["見える範囲"]))}</p>` : "") + "</article>");
  return `<div class="d-cards d-wide">${cards.join("")}</div>`;
}

function renderTable(block, ctx) {
  const kind = TABLES.find((t) => t.cols.length === block.header.length && t.cols.every((c, i) => c === block.header[i]));
  if (!kind || block.rows.some((r) => r.length > block.header.length)) return linkCodes(renderMarkdown(block.raw.join("\n"), ctx.hooks));
  return kind.render(block.rows.map((r) => pick(block.header, r)), { ...ctx, header: block.header });
}

/** 項目を「名前: 文」に分ける。分けられなければ null。 */
function labelOf(text) {
  const m = LABEL_RE.exec(String(text).trim());
  return m ? { key: m[1].trim(), value: m[2].trim() } : null;
}

function childItems(children) {
  const parsed = blocks(children);
  return parsed.length === 1 && parsed[0].type === "list" && !parsed[0].ordered ? parsed[0].items : null;
}

function renderList(block, ctx) {
  const { inl, boardLinks } = formatters(ctx.hooks);
  const { items } = block;
  const labels = items.map((it) => labelOf(it.text));
  const allLabeled = labels.every(Boolean);
  const noChildren = items.every((it) => !it.children.some((c) => !blank(c)));
  // 候補のカード: 「名前: 文」の下に、字下げの「名前: 文」を持つ (仕様書 8 章)
  const childLists = items.map((it) => childItems(it.children));
  if (!block.ordered && allLabeled && childLists.every((children) => children?.length && children.every((c) => labelOf(c.text) && c.children.every(blank)))) {
    ctx.stat("次に広げる候補", items.length, "個");
    const cards = items.map((it, k) => {
      const subs = childLists[k].map((c) => labelOf(c.text));
      const when = subs.find((s) => s.key === "時期");
      const rest = subs.filter((s) => s !== when);
      return `<article class="d-card d-future"><div class="d-card-top"><p class="d-name">${inl(labels[k].key)}</p>${when ? chip(when.value, "t-when") : ""}</div>`
        + `<p>${inl(labels[k].value)}</p>${rest.map((s) => `<p class="d-line">${label(s.key, inl(s.value))}</p>`).join("")}</article>`;
    });
    return `<div class="d-cards d-wide">${cards.join("")}</div>`;
  }
  // 番号つきの行: 「H17: 〜」だけの並び (ヒアリング 5 章)
  if (!block.ordered && allLabeled && noChildren && labels.every((l) => CODE_ONLY_RE.test(l.key))) {
    return `<ol class="d-rows">${labels.map((l) => `<li><span class="d-id">${esc(l.key)}</span><span class="d-text">${inl(l.value)}</span></li>`).join("")}</ol>`;
  }
  // 2 列の定義: 「名前: 文」だけの並び
  if (allLabeled && noChildren && !block.ordered) {
    const value = (l) => (l.key === "ボード" ? boardLinks(l.value) : l.key === "端末" && ctx.facts ? deviceChip(l.value) : inl(l.value));
    // 画面やデータのカードの中では、短い値を横に並べる小さな札の格子にする
    if (ctx.facts) {
      return `<dl class="d-facts">${labels.map((l) => `<div${plainOf(l.value).length > 12 ? ' class="is-wide"' : ""}><dt>${inl(l.key)}</dt><dd>${value(l)}</dd></div>`).join("")}</dl>`;
    }
    return `<dl class="d-dl">${labels.map((l) => `<div><dt>${inl(l.key)}</dt><dd>${value(l)}</dd></div>`).join("")}</dl>`;
  }
  // Render the original list through the shared renderer: keep nested blocks and numbering.
  return linkCodes(renderMarkdown(block.raw.join("\n"), ctx.hooks))
    .replace(/^<ul>/, '<ul class="d-list">')
    .replace(/^<ol(?=[ >])/, `<ol class="d-steps"${block.start !== 1 ? ` style="counter-reset: st ${block.start - 1}"` : ""}`);
}

/** 「ボード: 02, 03」の値をボードへのリンクにする。 */
function boardLinks(value, hooks = {}) {
  const fmt = formatters(hooks);
  return String(value).split(/\s*[,、，]\s*/).map((no) => (/^\d{2}$/.test(no) ? `<a class="ref" href="#b${no}">${no}</a>` : fmt.inl(no))).join("、");
}

function renderFlow(list, ctx, { lead = false } = {}) {
  const { inl } = formatters(ctx.hooks);
  if (lead && list.length && list.every((b) => b.type === "para")) {
    return `<div class="d-lead">${list.map((b) => `<p>${inl(b.text)}</p>`).join("")}</div>`;
  }
  return list.map((b) => {
    if (b.type === "table") return renderTable(b, ctx);
    if (b.type === "list") return renderList(b, ctx);
    if (b.type === "para") return UNIT_RE.test(b.text) ? `<p class="d-unit">${inl(b.text)}</p>` : `<p>${inl(b.text)}</p>`;
    return renderMarkdown(b.raw.join("\n"), ctx.hooks);
  }).join("\n");
}

const onlyList = (sub) => {
  const b = blocks(sub.lines);
  return b.length === 1 && b[0].type === "list" ? b[0] : null;
};

function renderSubs(subs, ctx) {
  const heads = subs.map((s) => {
    const { no, name } = splitHead(plainOf(s.head));
    const id = ctx.makeId(plainOf(s.head));
    return { id, no, name };
  });
  const h4 = (k) => `<h4 id="${heads[k].id}">${heads[k].no ? `<span class="d-subno">${esc(heads[k].no)}</span>` : ""}${esc(heads[k].name)}</h4>`;
  const lists = subs.map(onlyList);
  // 左右の対比: ### が 2 つで、中身が箇条書きだけ (範囲のやる / やらない、業務の流れの今 / これから)
  if (subs.length === 2 && lists.every(Boolean)) {
    const ordered = lists.every((l) => l.ordered);
    const tones = ordered ? ["t-before", "t-after"] : heads.map((h) => (NO_WORDS.test(h.name) ? "t-no" : "t-yes"));
    const panes = subs.map((s, k) => `<div class="d-pane ${tones[k]}">${h4(k)}${renderList(lists[k], ctx)}</div>`);
    return `<div class="d-pair${ordered ? " is-flow" : ""}">${panes.join(ordered ? '<span class="d-arrow" aria-hidden="true">→</span>' : "")}</div>`;
  }
  // 小カードの格子: ### が 3 つ以上で、どれも箇条書きだけ (画面の共通ルール)
  if (subs.length >= 3 && lists.every(Boolean)) {
    return `<div class="d-grid">${subs.map((s, k) => `<div class="d-mini">${h4(k)}${renderList(lists[k], ctx)}</div>`).join("")}</div>`;
  }
  return subs.map((s, k) => {
    const card = /^[A-Za-z]\d/.test(heads[k].no);
    const flow = renderFlow(blocks(s.lines), card ? { ...ctx, facts: true } : ctx);
    return `<div class="d-sub${card ? " d-item-card" : ""}">${h4(k)}${flow}</div>`;
  }).join("\n");
}

function renderKpis(stats) {
  if (stats.size < 2) return "";
  const cells = [...stats].map(([key, { value, unit }]) => `<div class="d-kpi"><span>${esc(key)}</span><b>${value}</b><small>${esc(unit)}</small></div>`);
  return `<div class="d-kpis">${cells.join("")}</div>`;
}

/**
 * 文書 1 つを HTML にする。## を目次に集める。used は文書をまたいで id がぶつからないように共有する。
 * 戻り値は { body, toc, title }。hooks.image(alt, src) は検証済み画像の HTML を返す省略可能な同期フック。
 */
export function convertDoc(text, prefix, used, hooks = {}) {
  const prepared = prepareMarkdown(text, hooks);
  hooks = prepared.hooks;
  const doc = outline(prepared.text);
  const toc = [];
  const stats = new Map();
  let count = 0;
  const claim = (base) => {
    let id = base;
    for (let n = 2; used.has(id); n += 1) id = `${base}-${n}`;
    used.add(id);
    return id;
  };
  const makeId = (plain) => {
    count += 1;
    return claim(headingId(plain, prefix) ?? `${prefix}-h${count}`);
  };
  const ctx = {
    makeId,
    stat(key, value, unit) {
      const prev = stats.get(key);
      stats.set(key, { value: (prev?.value ?? 0) + value, unit });
    },
    rowId(code) {
      const c = String(code ?? "").trim();
      if (!/^[A-Z]\d{2,}$/.test(c) || !CODE_TARGET[c[0]]) return "";
      const id = `${CODE_TARGET[c[0]]}${c.slice(1)}`;
      if (used.has(id)) return "";
      used.add(id);
      return ` id="${id}"`;
    },
    hooks: {
      ...hooks,
      heading: (level, inline, plain) => {
        const id = makeId(plain);
        const out = Math.min(level + 1, 6);
        return `<h${out} id="${id}">${inline}</h${out}>\n`;
      },
      table: (html) => `<div class="tw">${html.replace(/\n$/, "")}</div>\n`,
    },
  };

  const titlePlain = doc.title === null ? "" : plainOf(doc.title);
  const separator = titlePlain.search(/[:：]/);
  const [kind, name] = separator < 0 ? ["", titlePlain] : [titlePlain.slice(0, separator), titlePlain.slice(separator + 1).trimStart()];
  const meta = [];
  const leadLines = [];
  for (const line of doc.lines) {
    const m = META_RE.exec(line.trim());
    if (m && leadLines.every(blank)) meta.push(`<span>${esc(m[1])} <b>${esc(m[2])}</b></span>`);
    else leadLines.push(line);
  }

  const sections = doc.sections.map((sec) => {
    const plain = plainOf(sec.head);
    const { no, name: secName } = splitHead(plain);
    const id = makeId(plain);
    toc.push([id, plain]);
    const flowBlocks = blocks(sec.lines);
    const parts = [];
    if (flowBlocks.length) parts.push(renderFlow(flowBlocks, ctx, { lead: !sec.subs.length }));
    if (sec.subs.length) parts.push(renderSubs(sec.subs, ctx));
    const badge = no ? `<span class="d-no">${esc(no)}</span>` : "";
    return `<section class="d-sec" aria-labelledby="${id}">\n<header class="d-head">${badge}<h3 id="${id}">${esc(secName || plain)}</h3></header>\n`
      + `<div class="d-body">\n${parts.join("\n")}\n</div>\n</section>`;
  });

  const lead = renderFlow(blocks(leadLines), ctx);
  const hero = `<header class="d-hero">\n${kind ? `<p class="d-kind">${esc(kind)}</p>` : ""}<h2 class="doc-title">${esc(name || titlePlain)}</h2>\n`
    + `${meta.length ? `<p class="d-meta-line">${meta.join("")}</p>` : ""}${renderKpis(stats)}${lead ? `\n${lead}` : ""}\n</header>`;
  return { body: `${hero}\n${sections.join("\n")}\n`, toc, title: titlePlain };
}
