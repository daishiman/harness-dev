#!/usr/bin/env node
// 実行部隊向け資料 (<フォルダ名>-handout.html) を、了承済みのヒアリングシート (hearing.md) から決定的に組み立てる。
//
//   node scripts/build-handout.mjs <フォルダ> [out.html]
//
// 経営者向けレポートと同じ外枠 (lib.mjs の pageShell)・見出し帯・配色を使い、並びは「目的 → ゴール → やること (→ 困ったら)」に固定する。
// 数字の根拠・統計・要因分析は載せない。載せるのはヒアリングで確かめた文だけで、HTML を手で直さない (直すのは hearing.md)。
// 日時・乱数を出力に含めないので、同じシートからは常に同じHTMLになる。
// 終了コード: 0=成功 1=検査不合格/vendor改変 2=入力エラー 3=ヒアリング未完了 (直すこと・聞くことを表示)
import { existsSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { verifyVendor } from "./sync-kit.mjs";
import { PRINT_BUTTON, esc, isInsideSkill, pageShell, printResult, secHead, visibleText, writeAtomic } from "./lib.mjs";
import { HEARING_FILE, WAITING, hiddenWords, parseSheet, plainIssues, printIssues, sheetIssues } from "./hearing.mjs";

export const HANDOUT_SUFFIX = "-handout.html";
/** 資料のセクション。並び (最後の help だけ省ける) と見出し帯のチップ文言の正本。section の id もこの key */
export const HANDOUT_KINDS = Object.freeze({ purpose: "目的", goal: "ゴール", todo: "やること", help: "困ったら" });

const val = (item, field) => String(item?.[field] ?? "").trim();
const filledItems = (sheet, key) => (sheet.sections[key]?.items ?? []).filter((item) => Object.values(item).some((v) => String(v).trim()));

/** シート → 資料の中身。組み立てと検査の両方がこれを見る */
export function handoutModel(sheet) {
  const first = (key) => sheet.sections[key]?.items?.[0];
  return {
    reader: val(first("cover"), "相手"),
    title: val(first("cover"), "題名"),
    purpose: val(first("purpose"), "目的"),
    whyNow: val(first("purpose"), "なぜ今か"),
    goals: filledItems(sheet, "goals").map((g) => ({ text: val(g, "内容"), due: val(g, "期限") })),
    actions: filledItems(sheet, "actions").map((a) => ({ who: val(a, "誰が"), what: val(a, "何を"), due: val(a, "いつまでに"), done: val(a, "できたかの目安") })),
    help: val(first("help"), "相談先"),
    review: val(first("help"), "振り返り"),
    hidden: hiddenWords(sheet),
    date: val(sheet.meta, "作成日"),
  };
}

const section = (kind, h2, inner) =>
  [`<section id="${kind}" data-kind="${kind}">`, secHead(HANDOUT_KINDS[kind], `<h2>${h2}</h2>`), inner, "</section>"].filter(Boolean).join("\n");
/** .act-meta は div で包んだ dt/dd の組 (レポートの打ち手と同じ)、キットの .def-list は dt と dd を直に並べる2列の grid */
const pairs = (list, wrap) => list.filter(([, v]) => v).map(([dt, dd]) => wrap(`<dt>${dt}</dt><dd>${esc(dd)}</dd>`)).join("");

const DATE_RE = /^(\d{4})[-/.年](\d{1,2})(?:[-/.月](\d{1,2})日?|月?\s*(末|上旬|中旬|下旬))?$/;
/**
 * 期限を現場で読む形にする (2026-10-31 → 10月31日、2026-10末 → 10月末、2026-11 → 11月)。
 * 年は作成日と違うときだけ残す。読み替えるのは表記だけで、それ以外の書き方 (毎週月曜など) はそのまま出す
 */
export function plainDue(value, baseYear) {
  const m = String(value ?? "").trim().match(DATE_RE);
  if (!m) return String(value ?? "").trim();
  const [, y, mo, d, part] = m;
  return `${y === baseYear ? "" : `${y}年`}${Number(mo)}月${d ? `${Number(d)}日` : part ?? ""}`;
}

/** 資料の単一HTML。利用者の文はすべてエスケープする */
export function buildHandout(m) {
  const due = (value) => plainDue(value, m.date.slice(0, 4));
  const sections = [
    section("purpose", esc(m.purpose), m.whyNow ? `<p class="why-now"><b>なぜ今か</b>${esc(m.whyNow)}</p>` : ""),
    section("goal", "いつまでに、どうなっていれば成功か", `<ol class="goals">${m.goals.map((g, i) =>
      `\n<li class="goal card card-pad"><span class="goal-no">${i + 1}</span><p class="goal-text">${esc(g.text)}</p>` +
      `<p class="goal-due"><span class="goal-due-h">いつまでに</span>${esc(due(g.due))}</p></li>`).join("")}\n</ol>`),
    // 読み手は自分の担当を探して読むので、担当を番号の隣に出す (期限と目安は下の組)
    section("todo", "自分たちがやること", `<ol class="actions">${m.actions.map((a, i) =>
      `\n<li class="act card card-pad"><div class="act-head"><span class="act-no">${String(i + 1).padStart(2, "0")}</span>` +
      `<span class="act-who badge badge-tag">${esc(a.who)}</span><b class="act-title">${esc(a.what)}</b></div>\n` +
      `<dl class="act-meta">${pairs([["いつまでに", due(a.due)], ["できたかの目安", a.done]], (x) => `<div>${x}</div>`)}</dl></li>`).join("")}\n</ol>`),
  ];
  if (m.help || m.review) {
    sections.push(section("help", "迷ったとき・確かめるとき", `<dl class="def-list">${pairs([["相談先", m.help], ["振り返り", m.review]], (x) => x)}</dl>`));
  }
  const header = [
    '<header class="doc">',
    `<p class="crumb">実行プラン｜${esc(m.reader)} へ</p>`,
    `<h1 class="page-title">${esc(m.title)}</h1>`,
    m.date ? `<p class="sub">作成 ${esc(m.date)}</p>` : "",
    PRINT_BUTTON,
    "</header>",
  ].filter(Boolean).join("\n");
  return pageShell({ title: esc(m.title), mainClass: "wrap handout", body: [header, ...sections].join("\n") });
}

/**
 * 資料の検査。シートの検査 (hearing.mjs の sheetIssues) を通った後でも、組み立てた結果として守れているかを確かめる。
 * 件数・欄の有無・インラインの style のように生成器の形で決まることは、ここではなく selftest が確かめる
 */
export function checkHandout(html, model) {
  const errors = [];
  const main = html.match(/<main\b[\s\S]*<\/main>/)?.[0] ?? "";
  const kinds = [...main.matchAll(/<section\b[^>]*\bdata-kind="([^"]*)"/g)].map((x) => x[1]).join(" ");
  const order = Object.keys(HANDOUT_KINDS);
  if (![order, order.slice(0, -1)].some((o) => o.join(" ") === kinds)) {
    errors.push(`H01 セクションの並びが「${Object.values(HANDOUT_KINDS).join(" → ")} (最後は省ける)」ではありません (${kinds || "なし"})`);
  }
  const opens = main.match(/<section\b[^>]*>/g) ?? [];
  const heads = main.match(/<section\b[^>]*>\s*<div class="sec-head"><span class="secno">[^<]+<\/span><h2>/g) ?? [];
  if (heads.length !== opens.length) errors.push("H02 見出し帯 (.sec-head = チップ + h2) で始まらないセクションがあります");
  for (const issue of new Set(plainIssues(visibleText(main)))) errors.push(`H03 現場向けでない表現: ${issue}`);
  const whole = visibleText(html);
  for (const word of model.hidden) if (whole.includes(word)) errors.push(`H04 見せない情報「${word}」が資料に出ています`);
  return { errors, warnings: [] };
}

function main([dirArg, outArg]) {
  if (!dirArg) {
    console.error("使い方: node scripts/build-handout.mjs <フォルダ> [out.html]");
    return 2;
  }
  const dir = resolve(dirArg);
  const file = join(dir, HEARING_FILE);
  if (!existsSync(file)) {
    console.error(`入力エラー: ${file} がありません。先に node scripts/report.mjs hearing ${dirArg} でシートを作る`);
    return 2;
  }
  const outPath = resolve(outArg || join(dir, `${basename(dir)}${HANDOUT_SUFFIX}`));
  if (isInsideSkill(outPath)) {
    console.error(`入力エラー: 出力先 ${outPath} がスキルのフォルダの中です。第2引数で外の出力先を指定してください`);
    return 2;
  }
  const vendor = verifyVendor();
  if (!vendor.ok) {
    console.error(`NG: ${vendor.reason}`);
    return 1;
  }
  const sheet = parseSheet(readFileSync(file, "utf8"));
  const issues = sheetIssues(sheet);
  if (issues.length) {
    printIssues(file, issues);
    return WAITING;
  }
  const model = handoutModel(sheet);
  const html = buildHandout(model);
  const result = checkHandout(html, model);
  printResult(result);
  if (result.errors.length) return 1;
  writeAtomic(outPath, html);
  console.log(`生成: ${outPath}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
