#!/usr/bin/env node
// =====================================================
//  manual-*.md から manual-*.html を生成する
//
//  なぜこのスクリプトが必要か:
//    以前は html を手書きで2系統(Mac / Windows)保守し、package-kit が
//    代表的な語句だけ md と一致するかを照合していた。語句以外は自由に
//    ずれるため、md を直しても html が古いまま配布される事故が起きる。
//    正本を md の1つにし、html は「ダブルクリックで読める表示形式」として
//    ここで機械的に生成する。依存パッケージは使わない (Node 22 の標準機能のみ)。
//
//  使い方:
//    node aidd-agent-kit/scripts/gen-manual-html.mjs             # kit 直下の html を更新
//    node aidd-agent-kit/scripts/gen-manual-html.mjs --check     # 生成結果とコミット済み html の一致を検査
//    node aidd-agent-kit/scripts/gen-manual-html.mjs --out-dir D # D/manual-*.html へ書き出す
//
//  対応する Markdown: 見出し(#〜###)・段落・箇条書き(入れ子)・番号付き・
//  fenced code・4桁インデント code・表・引用(>)・水平線・<details> の素通し・
//  インライン(**強調**・`code`・[リンク](url))。manual に無い構文は扱わない。
// =====================================================
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const KIT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TARGETS = [
  { os: "mac", badge: "Mac版" },
  { os: "windows", badge: "Windows版" },
];

// 旧 manual-*.html の見た目をそのまま引き継ぐ。
const CSS = `
  :root {
    --primary: #2456E5;
    --primary-tint: #EEF3FE;
    --ink: #1A1E27;
    --sub: #5A616E;
    --line: #E4E7EC;
    --warn-bg: #FFF7E8;
    --warn-line: #F0C36A;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Hiragino Kaku Gothic ProN", "Hiragino Sans", "Yu Gothic", "Meiryo", sans-serif;
    color: var(--ink);
    background: #fff;
    line-height: 1.9;
    font-size: 16px;
  }
  .wrap { max-width: 760px; margin: 0 auto; padding: 48px 24px 80px; }
  .os-badge {
    display: inline-block; background: var(--primary); color: #fff;
    font-weight: 700; font-size: 14px; padding: 4px 14px; border-radius: 999px;
    letter-spacing: 0.05em; margin-bottom: 16px;
  }
  h1 { font-size: 26px; line-height: 1.5; margin-bottom: 8px; }
  h2 {
    font-size: 20px; margin: 56px 0 16px; padding-left: 14px;
    border-left: 5px solid var(--primary); line-height: 1.5;
  }
  h3 { font-size: 16px; margin: 28px 0 8px; }
  h3.faq-q { color: var(--primary); }
  p { margin: 12px 0; }
  a { color: var(--primary); }
  hr { border: 0; border-top: 1px solid var(--line); margin: 40px 0; }
  .box {
    background: var(--primary-tint); border-radius: 12px;
    padding: 20px 24px; margin: 20px 0;
  }
  .box .big { font-size: 17px; font-weight: 700; margin: 0 0 8px; }
  .warn {
    background: var(--warn-bg); border: 1px solid var(--warn-line);
    border-radius: 12px; padding: 18px 22px; margin: 18px 0;
  }
  .warn p:first-child, .box p:first-child { margin-top: 0; }
  .warn p:last-child, .box p:last-child { margin-bottom: 0; }
  ol, ul { padding-left: 24px; margin: 10px 0; }
  li { margin: 6px 0; }
  code {
    font-family: "SF Mono", Menlo, Consolas, monospace;
    background: #F1F3F6; border-radius: 5px; padding: 2px 7px; font-size: 14px;
  }
  pre {
    background: #1A1E27; color: #E9EDF5; border-radius: 10px;
    padding: 16px 20px; margin: 14px 0; font-family: "SF Mono", Menlo, Consolas, monospace;
    font-size: 14px; line-height: 1.7; overflow-x: auto; white-space: pre-wrap;
  }
  pre code { background: none; color: inherit; padding: 0; font-size: inherit; }
  table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14.5px; }
  th, td { border: 1px solid var(--line); padding: 10px 14px; text-align: left; vertical-align: top; }
  th { background: #F7F8FA; white-space: nowrap; }
  td:first-child { white-space: nowrap; font-weight: 600; }
  details { margin: 16px 0; }
  summary { cursor: pointer; font-weight: 600; color: var(--primary); }
  .footer { margin-top: 72px; padding-top: 20px; border-top: 1px solid var(--line); color: var(--sub); font-size: 13px; }
  @media (max-width: 480px) {
    body { font-size: 15px; }
    .wrap { padding: 32px 16px 64px; }
    h1 { font-size: 22px; }
    td:first-child { white-space: normal; }
  }
`;

const escapeHtml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// インライン記法。code span を先に退避し、強調・リンクが code span をまたいでも
// (例: **`install-mac.command`**) 正しく閉じるようにする。
function inline(text) {
  const codes = [];
  let out = text.replace(/`([^`]*)`/g, (_, c) => {
    codes.push(`<code>${escapeHtml(c)}</code>`);
    return `\u0000${codes.length - 1}\u0000`;
  });
  out = escapeHtml(out);
  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => `<a href="${href}">${label}</a>`);
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  return out.replace(/\u0000(\d+)\u0000/g, (_, n) => codes[Number(n)]);
}

const isBlank = (line) => line.trim() === "";
const listMatch = (line) => /^(\s*)([-*]|\d+\.)\s+(.*)$/.exec(line);
const indentOf = (line) => /^\s*/.exec(line)[0].length;

// ブロック単位で Markdown を HTML に変換する。リスト項目や引用の中身は
// インデント/接頭辞を剥がして再帰的に同じ関数で処理する。
function renderBlocks(lines) {
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];

    if (isBlank(line)) { i += 1; continue; }

    // fenced code
    const fence = /^\s*```/.exec(line);
    if (fence) {
      const body = [];
      i += 1;
      while (i < lines.length && !/^\s*```/.test(lines[i])) { body.push(lines[i]); i += 1; }
      i += 1;
      const indent = Math.min(...body.filter((l) => !isBlank(l)).map(indentOf), fence[0].length - 3);
      out.push(`<pre><code>${escapeHtml(body.map((l) => l.slice(indent)).join("\n"))}</code></pre>`);
      continue;
    }

    // 4桁インデントのコード (リスト外)
    if (/^ {4,}\S/.test(line) && !listMatch(line)) {
      const body = [];
      while (i < lines.length && (/^ {4,}\S/.test(lines[i]) || isBlank(lines[i]))) { body.push(lines[i]); i += 1; }
      while (body.length && isBlank(body[body.length - 1])) body.pop();
      out.push(`<pre><code>${escapeHtml(body.map((l) => l.slice(4)).join("\n"))}</code></pre>`);
      continue;
    }

    // 生 HTML (details / summary) はそのまま通す
    if (/^\s*<\/?(details|summary)\b/.test(line)) {
      out.push(line.trim());
      i += 1;
      continue;
    }

    // 水平線
    if (/^\s*---+\s*$/.test(line)) { out.push("<hr>"); i += 1; continue; }

    // 見出し
    const heading = /^\s*(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const text = heading[2].trim();
      const cls = level === 3 && /^Q\d/.test(text) ? ' class="faq-q"' : "";
      out.push(`<h${level}${cls}>${inline(text)}</h${level}>`);
      i += 1;
      continue;
    }

    // 引用 (> ...)。中に見出しがあれば強調ボックス、無ければ注意ボックス。
    if (/^\s*>/.test(line)) {
      const body = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) {
        body.push(lines[i].replace(/^\s*>\s?/, ""));
        i += 1;
      }
      const hasHeading = body.some((l) => /^\s*#{1,3}\s/.test(l));
      const innerLines = hasHeading
        ? body.map((l) => l.replace(/^\s*#{1,3}\s+(.*)$/, (_, t) => `<p class="big">${inline(t)}</p>`))
        : body;
      const inner = hasHeading
        ? renderBlocksKeepingRaw(innerLines)
        : renderBlocks(innerLines);
      out.push(`<div class="${hasHeading ? "box" : "warn"}">\n${inner}\n</div>`);
      continue;
    }

    // 表
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|\s*-{3,}/.test(lines[i + 1])) {
      const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => inline(c.trim()));
      const head = cells(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { rows.push(cells(lines[i])); i += 1; }
      out.push(
        "<table>\n<thead><tr>" + head.map((c) => `<th>${c}</th>`).join("") + "</tr></thead>\n<tbody>\n" +
        rows.map((r) => "<tr>" + r.map((c) => `<td>${c}</td>`).join("") + "</tr>").join("\n") +
        "\n</tbody>\n</table>",
      );
      continue;
    }

    // リスト (入れ子・項目内のブロックに対応)
    const lm = listMatch(line);
    if (lm) {
      const baseIndent = lm[1].length;
      const ordered = /\d+\./.test(lm[2]);
      const items = [];
      while (i < lines.length) {
        // 空行を挟んで同じ階層の項目が続けば、同じリストとして扱う
        let k = i;
        while (k < lines.length && isBlank(lines[k])) k += 1;
        if (k > i && k < lines.length) {
          const peek = listMatch(lines[k]);
          if (peek && peek[1].length === baseIndent && /\d+\./.test(peek[2]) === ordered) i = k;
        }
        const m = listMatch(lines[i]);
        if (!m || m[1].length !== baseIndent || /\d+\./.test(m[2]) !== ordered) break;
        const contentIndent = m[1].length + m[2].length + 1;
        const itemLines = [m[3]];
        i += 1;
        while (i < lines.length) {
          const next = lines[i];
          if (isBlank(next)) {
            // 空行の後にさらに深いインデントが続けば同じ項目の続き
            let j = i + 1;
            while (j < lines.length && isBlank(lines[j])) j += 1;
            if (j < lines.length && indentOf(lines[j]) > baseIndent && !(listMatch(lines[j]) && indentOf(lines[j]) === baseIndent)) {
              itemLines.push("");
              i += 1;
              continue;
            }
            break;
          }
          if (indentOf(next) <= baseIndent) break;
          itemLines.push(next.slice(Math.min(contentIndent, indentOf(next))));
          i += 1;
        }
        items.push(itemLines);
      }
      const rendered = items.map((itemLines) => {
        const [first, ...rest] = itemLines;
        const restHtml = rest.length ? renderBlocks(rest) : "";
        return `<li>${inline(first)}${restHtml ? "\n" + restHtml : ""}</li>`;
      });
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>\n${rendered.join("\n")}\n</${tag}>`);
      continue;
    }

    // 段落 (次のブロック境界まで連結)
    const para = [];
    while (
      i < lines.length && !isBlank(lines[i]) && !listMatch(lines[i]) &&
      !/^\s*(#{1,3}\s|>|```|\||---+\s*$|<\/?(details|summary)\b)/.test(lines[i])
    ) {
      para.push(lines[i].trim());
      i += 1;
    }
    out.push(`<p>${inline(para.join("<br>"))}</p>`.replace(/&lt;br&gt;/g, "<br>"));
  }
  return out.join("\n");
}

// 引用ボックス内で既に HTML 化した行 (<p class="big">) を素通しするための版。
function renderBlocksKeepingRaw(lines) {
  const out = [];
  let buf = [];
  const flush = () => { if (buf.length) { out.push(renderBlocks(buf)); buf = []; } };
  for (const l of lines) {
    if (/^<p class="big">/.test(l)) { flush(); out.push(l); } else buf.push(l);
  }
  flush();
  return out.join("\n");
}

function renderPage(markdown, badge) {
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const titleLine = lines.find((l) => /^#\s+/.test(l)) ?? "# マニュアル";
  const title = titleLine.replace(/^#\s+/, "").trim();
  const bodyLines = lines.filter((l) => l !== titleLine);
  const body = renderBlocks(bodyLines);
  return `<!DOCTYPE html>
<!-- このファイルは manual-*.md から scripts/gen-manual-html.mjs で生成しています。直接編集せず md を直してください。 -->
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escapeHtml(title)}</title>
<style>${CSS}</style>
</head>
<body>
<div class="wrap">

  <div class="os-badge">${escapeHtml(badge)}</div>
  <h1>${inline(title)}</h1>

${body}

  <div class="footer">
    AI開発エージェントキット
  </div>

</div>
</body>
</html>
`;
}

function main(argv) {
  let outDir = KIT_DIR;
  let check = false;
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === "--check") check = true;
    else if (argv[i] === "--out-dir") { outDir = resolve(argv[i + 1]); i += 1; }
    else { console.error(`不明な引数: ${argv[i]}`); return 2; }
  }
  let stale = 0;
  for (const { os, badge } of TARGETS) {
    const src = join(KIT_DIR, `manual-${os}.md`);
    const dst = join(outDir, `manual-${os}.html`);
    if (!existsSync(src)) { console.error(`[NG] 正本が無い: ${src}`); return 1; }
    const html = renderPage(readFileSync(src, "utf8"), badge);
    if (check) {
      const current = existsSync(dst) ? readFileSync(dst, "utf8") : "";
      if (current === html) {
        console.log(`[OK] ${dst} は manual-${os}.md の生成結果と一致`);
      } else {
        console.error(`[NG] ${dst} が manual-${os}.md と一致しない (node scripts/gen-manual-html.mjs で再生成してコミット)`);
        stale += 1;
      }
    } else {
      writeFileSync(dst, html);
      console.log(`[OK] 生成: ${dst}`);
    }
  }
  return stale ? 1 : 0;
}

process.exit(main(process.argv.slice(2)));
