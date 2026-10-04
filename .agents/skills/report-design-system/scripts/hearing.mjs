#!/usr/bin/env node
// 実行部隊向け資料のヒアリングシート (hearing.md)。AI が下書きを書き、ユーザーには決めてほしいことだけを聞く往復の正本。
//
//   node scripts/hearing.mjs <フォルダ>   シートが無ければ作る (レポートの打ち手と、前の月のシートを下書きに使う)。
//                                        あれば読み、「AI が直すこと」と「ユーザーに聞くこと」に分けて出す
//
// シートは人が編集する Markdown。機械が読むのは次の行だけで、「>」で始まる案内・空行は読み飛ばす。
//   ## <番号>. <題>〔…〕           まとまり (QUESTIONS の title と一致させる。〔〕の中は読まない)
//   ### <名前>                     繰り返す項目 (ゴール・やること) の1件の始まり
//   - <欄>: <回答>                 記入欄
//   - [x] この内容で資料にする     ユーザーが全体を了承した印 (シートに1つだけ)。AI はユーザーの明示の了承なしに付けない
// 終了コード: 0=全項目がそろい了承済み 2=入力エラー 3=回答待ち (AI が直すこと・ユーザーに聞くことを表示)
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { ASK_LIMIT, NAME_RE, OVERVIEW_JARGON, TECHNICAL_STAT, decodeEntities, isFilled } from "./lib.mjs";

export const HEARING_FILE = "hearing.md";
/** 終了コード: 回答待ち。不合格 (1)・入力エラー (2) と区別し、AI が「直す・聞く番」だと分かるようにする */
export const WAITING = 3;

/**
 * ヒアリングのまとまり。シートはこの順に並び、資料は「目的 → ゴール → やること (→ 困ったら)」で並ぶ。
 *   fields   = 1件の記入欄。optional に挙げた欄は空でもよい (全欄が optional のまとまりは、空なら資料に出さない)
 *   decide   = ユーザーが決める欄。空なら聞く。ほかの欄は AI が下書きし、最後の了承でまとめて見てもらう
 *   repeat   = 「### 名前 n」で区切って min〜max 件書ける
 */
export const QUESTIONS = Object.freeze([
  { key: "cover", title: "表紙", fields: ["相手", "題名"],
    ask: "渡す相手 (役割) と、現場の人が「自分に関係がある」と分かる題名" },
  { key: "purpose", title: "目的", fields: ["目的", "なぜ今か"], optional: ["なぜ今か"],
    ask: "なぜ取り組むのかを、現場の人が納得できる1文で (数字や分析の言葉は使わない)" },
  { key: "goals", title: "ゴール", fields: ["内容", "期限"], decide: ["内容", "期限"], repeat: { label: "ゴール", min: 1, max: 3 },
    ask: "いつまでに、どうなっていれば成功か (1〜3個。現場の人が自分で「できた」と分かる形で)" },
  { key: "actions", title: "やること", fields: ["誰が", "何を", "いつまでに", "できたかの目安"], decide: ["誰が", "何を", "いつまでに"],
    repeat: { label: "やること", min: 1, max: 5 },
    ask: "誰が、何を、いつまでにやるか (1件に担当は1人か1つの役割)" },
  { key: "help", title: "困ったら", fields: ["相談先", "振り返り"], optional: ["相談先", "振り返り"],
    ask: "迷ったときの相談先と、進み具合を確かめる日" },
  { key: "hidden", title: "見せない情報", fields: ["語句"], decide: ["語句"],
    ask: "現場に見せない名前や数字 (荷主の社名、車両ごとの赤字額など) を「、」で区切って。無ければ「なし」" },
]);
const isOptional = (q) => (q.optional ?? []).length === q.fields.length;
const whoFills = (q, field) => (q.decide ?? []).includes(field) ? "ask" : "fix";
const tagOf = (q) => (q.decide ? "あなたが決める" : isOptional(q) ? "任意" : "AI が下書き");

/** 1件の一部だけ空の欄に添える、欄ごとの書き方 (まとまりごと空なら ask を出す) */
const FIELD_HINTS = Object.freeze({
  誰が: "人の名前か役割を1つ",
  何を: "「〜する」で終わる1文",
  いつまでに: "「10月末」「毎週月曜」のように",
  期限: "「10月末」「2026-12-31」のように",
  できたかの目安: "終わったと誰が見ても分かる形で (例: 一覧を社長に渡した、週1回続けられた)",
  内容: "終わったときの状態を1文で",
});
const CONFIRM_TITLE = "確認";
const CONFIRM_TEXT = "この内容で資料にする";
const NOTES_TITLE = "メモ（自由記入）";
const DUE_FIELDS = ["期限", "いつまでに", "振り返り"];
const DUE = /\d{4}[-/.年]\d{1,2}|\d{1,2}\s*月|\d{1,2}\s*日|毎(?:日|週|月|朝)|今週|来週|今月|来月|月末|週末|[月火水木金土日]曜/;
const ASK_AGAIN = /^(?:わからない|分からない|わかりません|分かりません|未定|不明|要確認|\?|？)$/;
const NONE = /^(?:なし|無し|ない|特になし|特に無し)$/;
/** 前の月のシートから引き継ぐ欄。毎月の資料で変わりにくいものだけ (題名・目的・ゴール・やることは月ごとに決める) */
const CARRY_OVER = Object.freeze({ cover: ["相手"], help: ["相談先", "振り返り"], hidden: ["語句"] });
/** 1欄と題名の字数の上限。prompts/handout.md の転記は selftest が照合する */
export const TEXT_MAX = 60;
export const TITLE_MAX = 40;

/** 統計・分析の言葉 (lib.mjs の文章契約に無い分)。実行部隊向けの資料では使わない */
const ANALYSIS_WORDS = /仮説|反証|指標|区間|サンプル|母集団|外れ値|分布|四分位|パーセンタイル|寄与度|感応度|比較群|[上中下]位群|中位|KPI|KGI|\d\s*pt\b/i;
/**
 * 「確かめ、未反映なら請求する」のように、前の動作の結果しだいで次の動作をする書き方。やること1件に動作は1つ (prompts/handout.md)。
 * 「赤字にならない」「当たらず」の打ち消しは条件ではないので数えない
 */
const TWO_STEPS = /、[^、]*(?:(?:なら|たら)(?![なずぬ])|れば|場合は)/;

/**
 * 現場の言葉への言い換え表。[使わない言葉, 言い換えの例]。
 * 統計の言葉は上の正規表現が止める。ここには、社内の分析資料 (reports/2026-05-vehicle-pl の打ち手など) では普通に使うが、
 * 配車担当・ドライバーには伝わりにくい業務の言葉を置く。表に無い言葉も AI が prompts/handout.md の規律で言い換える。
 */
export const FRONTLINE_WORDS = Object.freeze([
  ["tW", "トンウイング車 (10tW → 10トンウイング車)"],
  ["km単価", "走った距離のわりの運賃"],
  ["損益ゼロ", "赤字にも黒字にもならない"],
  ["損益分岐", "赤字にならない境目"],
  ["燃料サーチャージ", "軽油代の上乗せ分"],
  ["変動費", "走った分だけかかるお金"],
  ["固定費", "走らなくてもかかるお金"],
  ["割賦", "分割払い"],
  ["実車率", "荷物を積んで走った割合"],
]);

/**
 * 実行部隊向けの文として直すべき点を返す (空なら問題なし)。
 * 返す文は「何をどう直すか」。AI はこれを材料に言い換える。
 */
export function plainIssues(text) {
  const s = String(text ?? "");
  const out = [];
  const stat = [OVERVIEW_JARGON, TECHNICAL_STAT, ANALYSIS_WORDS].map((re) => s.match(re)?.[0]).filter(Boolean);
  for (const word of new Set(stat)) out.push(`「${word}」は統計・分析の言葉。削るか「差が大きい」「よく起きる」のように言う`);
  for (const [word, plain] of FRONTLINE_WORDS) if (s.includes(word)) out.push(`「${word}」は「${plain}」のように言い換える`);
  if (s.includes("▲")) out.push("「▲」は使わず「赤字」「減った」と書く");
  // 「2026.10.31」のような日付は小数と数えない
  if (/\d\.\d/.test(s.replace(/\d{4}\.\d{1,2}(?:\.\d{1,2})?/g, ""))) out.push("小数は使わず、丸めた数か言葉にする");
  if (/\p{Extended_Pictographic}/u.test(s)) out.push("絵文字は使わない");
  return out;
}

// ---- シートの組み立てと読み取り ----

const GUIDE = [
  "AI が下書きを書き、決めてほしいことだけをチャットで聞きます。答えはチャットでも、この「:」の右に書いてもかまいません。",
  "分からないところは「わからない」と書けば、AI が選べる案を出します。",
  `全体を読んでよければ、下の「- [ ] ${CONFIRM_TEXT}」を「- [x]」にしてください。`,
];

/**
 * シートの Markdown を作る。draft = { meta, sections: {key: {items: [{欄: 値}]}}, refs: {key: [参考の文]}, confirmed }
 * 空の欄も「- 欄: 」として出し、どこに書けばよいかを見せる
 */
export function renderSheet(draft = {}) {
  const { meta = {}, sections = {}, refs = {}, confirmed = false } = draft;
  const lines = ["# ヒアリングシート（実行部隊向け資料）", "", ...GUIDE.map((g) => `> ${g}`), ""];
  for (const [label, value] of Object.entries(meta)) lines.push(`- ${label}: ${value ?? ""}`);
  QUESTIONS.forEach((q, n) => {
    lines.push("", `## ${n + 1}. ${q.title}〔${tagOf(q)}〕`, `> ${q.ask}`);
    for (const ref of refs[q.key] ?? []) lines.push(`> 参考: ${ref}`);
    const items = sections[q.key]?.items?.length ? sections[q.key].items : [{}];
    items.forEach((item, i) => {
      if (q.repeat) lines.push("", `### ${q.repeat.label} ${i + 1}`);
      for (const field of q.fields) lines.push(`- ${field}: ${item[field] ?? ""}`);
    });
  });
  lines.push("", `## ${CONFIRM_TITLE}`, `- [${confirmed ? "x" : " "}] ${CONFIRM_TEXT}`);
  lines.push("", `## ${NOTES_TITLE}`, "> 資料に入れてほしいことなどを自由に書いてください。", "");
  return lines.join("\n");
}

/**
 * シートを読む。形の崩れ (知らない見出し・欄・チェック) は problems に集め、止めずに「AI が直すこと」へ回す
 * @returns {{meta: object, sections: object, confirmed: boolean, notes: string[], problems: string[]}}
 */
export function parseSheet(md) {
  const sheet = { meta: {}, sections: {}, confirmed: false, notes: [], problems: [] };
  let area = "meta";   // meta | question | confirm | notes | unknown
  let q = null;        // 今のまとまり
  let item = null;     // 今の1件
  let last = null;     // 直前の欄 (続きの行をつなげる先)
  for (const raw of String(md).split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith(">") || /^#\s/.test(line)) continue;
    let m;
    if ((m = line.match(/^##\s+(?:\d+\.\s*)?(.+?)\s*(?:〔[^〕]*〕)?$/))) {
      q = QUESTIONS.find((x) => x.title === m[1]) ?? null;
      area = q ? "question" : m[1] === CONFIRM_TITLE ? "confirm" : m[1].startsWith("メモ") ? "notes" : "unknown";
      if (area === "unknown") sheet.problems.push(`知らない見出し「${m[1]}」。見出しの文言は変えない (${[...QUESTIONS.map((x) => x.title), CONFIRM_TITLE].join("・")})`);
      if (q) sheet.sections[q.key] = { items: [] };
      item = q && !q.repeat ? newItem(sheet.sections[q.key]) : null;
      last = null;
      continue;
    }
    if (area === "notes") {
      sheet.notes.push(line);
      continue;
    }
    if ((m = line.match(/^-\s*\[([ xX])\]\s*(.*)$/))) {
      if (m[2].startsWith(CONFIRM_TEXT)) sheet.confirmed = m[1] !== " ";
      else sheet.problems.push(`知らないチェック「${m[2]}」。チェックは「${CONFIRM_TEXT}」の1つだけ`);
      last = null;
      continue;
    }
    if (area === "unknown" || area === "confirm") continue;
    if ((m = line.match(/^###\s+(.+)$/))) {
      if (q?.repeat) item = newItem(sheet.sections[q.key]);
      else sheet.problems.push(`「### ${m[1]}」は、ゴール・やることの中でだけ使える`);
      last = null;
      continue;
    }
    if ((m = line.match(/^-\s*([^:：]+?)\s*[:：]\s*(.*)$/))) {
      const [, label, value] = m;
      if (area === "meta") {
        sheet.meta[label] = value.trim();
        continue;
      }
      if (!q.fields.includes(label)) {
        sheet.problems.push(`${q.title} に知らない欄「${label}」。欄の名前は ${q.fields.join("・")} のどれか`);
        last = null;
        continue;
      }
      item ??= newItem(sheet.sections[q.key]);
      item[label] = value.trim();
      last = { item, label };
      continue;
    }
    // 欄の続きの行 (長い回答を改行して書いた場合) は、直前の欄へつなげる
    if (last) last.item[last.label] = `${last.item[last.label]} ${line}`.trim();
    else if (q) sheet.problems.push(`${q.title} の「${line.slice(0, 20)}」は、どの欄の回答か分からない。「- 欄: 回答」の形で書く`);
  }
  return sheet;
}
const newItem = (sec) => {
  const item = {};
  sec.items.push(item);
  return item;
};

/** 見せない情報に書かれた語句 (「、」「,」空白で区切る)。「なし」「わからない」は語句に数えない */
export const hiddenWords = (sheet) =>
  String(sheet.sections.hidden?.items?.[0]?.語句 ?? "").split(/[、,，\s]+/).map((w) => w.trim())
    .filter((w) => w.length > 0 && !ASK_AGAIN.test(w) && !NONE.test(w));

/**
 * 残っていること。空ならヒアリング完了。who = "fix" は AI が聞かずにシートを直すこと、"ask" はユーザーに聞くこと。
 * 「未確認」(全体の了承) は、AI が直すことが無くなってから1回だけ聞く (直す途中の内容を了承させない)
 * @returns {{section: string, where: string, kind: string, who: "ask"|"fix", text: string}[]}
 */
export function sheetIssues(sheet) {
  const out = [];
  const hidden = hiddenWords(sheet);
  for (const q of QUESTIONS) {
    const add = (where, kind, who, text) => out.push({ section: q.title, where, kind, who, text });
    // 丸ごと空の件 (消し忘れた「### やること 4」など) は数えない
    const items = (sheet.sections[q.key]?.items ?? []).filter((item) => q.fields.some((f) => isFilled(item[f])));
    if (!items.length) {
      if (!isOptional(q)) add(q.title, "未記入", q.decide ? "ask" : "fix", q.ask);
      continue;
    }
    if (q.repeat && items.length > q.repeat.max) add(q.title, "多すぎ", "fix", `${q.repeat.label}は ${q.repeat.max} 件までに絞る (今 ${items.length} 件)。外したものは了承のときに伝える`);
    items.forEach((item, i) => {
      const at = q.repeat ? `${q.repeat.label} ${i + 1}` : q.title;
      for (const field of q.fields) {
        const where = `${at} › ${field}`;
        const who = whoFills(q, field);
        const value = String(item[field] ?? "").trim();
        if (!value) {
          if (!(q.optional ?? []).includes(field)) add(where, "未記入", who, FIELD_HINTS[field] ?? q.ask);
          continue;
        }
        if (ASK_AGAIN.test(value)) {
          add(where, "聞き直し", who, who === "ask" ? "聞き方を変え、選べる案を2〜3個添えてもう一度聞く" : "AI が案を書く");
          continue;
        }
        if (q.key === "hidden") continue;
        for (const text of plainIssues(value)) add(where, "言い換え", "fix", text);
        const max = field === "題名" ? TITLE_MAX : TEXT_MAX;
        if (value.length > max) add(where, "長すぎ", "fix", `${max}字以内にする (今 ${value.length}字)`);
        if (DUE_FIELDS.includes(field) && !DUE.test(value)) add(where, "期限", who, "「2026-10-31」「10月末」「毎週月曜」のように、いつかが分かる形にする");
        if (field === "何を" && TWO_STEPS.test(value)) add(where, "分ける", "fix", "動作が2つ入っている。2件に分け、後の件の担当・期限・目安も案を書く (了承のときに見せる)");
        for (const word of hidden) if (value.includes(word)) add(where, "見せない情報", "fix", `「${word}」は見せない情報。削るか言い換える`);
      }
    });
  }
  for (const text of sheet.problems) out.push({ section: "シートの形", where: "シートの形", kind: "形式", who: "fix", text });
  if (!sheet.confirmed && !out.some((x) => x.who === "fix")) {
    out.push({ section: CONFIRM_TITLE, where: "全体", kind: "未確認", who: "ask", text: `下書き全体を見せ、この内容で資料にしてよいかを聞く。了承をもらったら「- [x] ${CONFIRM_TEXT}」にする` });
  }
  return out;
}

/** 聞くことを、まとまりごとに1問へ束ねる (同じまとまりの欄は、表にして1回で聞く)。シートの上から順 */
export function askGroups(issues) {
  const groups = new Map();
  for (const x of issues.filter((x) => x.who === "ask")) groups.set(x.section, [...(groups.get(x.section) ?? []), x]);
  return [...groups].map(([section, items]) => ({ section, items }));
}

// ---- 下書き (レポートの打ち手と、前の月のシート) ----

const plain = (html) => decodeEntities(String(html ?? "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim());
const today = () => new Date().toLocaleDateString("sv-SE");

/** compose.mjs の actions() が書く打ち手 (<li class="act">) を読む。形の約束は selftest が compose と往復して確かめる */
export function readActs(html) {
  return [...String(html).matchAll(/<li class="act"[^>]*>([\s\S]*?)<\/li>/g)].map(([, body]) => {
    const dd = (dt) => plain(body.match(new RegExp(`<dt>${dt}</dt>\\s*<dd>([\\s\\S]*?)</dd>`))?.[1]);
    return { title: plain(body.match(/<b class="act-title">([\s\S]*?)<\/b>/)?.[1]), owner: dd("担当"), due: dd("期限") };
  });
}

/** 同じ slug で、この月より前の月のうち最新のフォルダのシート (例: 2026-06-vehicle-pl → 2026-05-vehicle-pl/hearing.md) */
function previousSheet(dir) {
  const [, month, slug] = basename(dir).match(/^(\d{4}-\d{2})-(.+)$/) ?? [];
  if (!slug || !existsSync(dirname(dir))) return null;
  const prev = readdirSync(dirname(dir))
    .filter((d) => d.slice(8) === slug && NAME_RE.test(d) && d.slice(0, 7) < month && existsSync(join(dirname(dir), d, HEARING_FILE)))
    .sort().pop();
  return prev ? { name: prev, sheet: parseSheet(readFileSync(join(dirname(dir), prev, HEARING_FILE), "utf8")) } : null;
}

/**
 * フォルダから下書きを作る。レポート (<name>/<name>.src.html) があれば、結論と打ち手の方針を参考に、打ち手を「やること」に写す。
 * 前の月のシートがあれば、相手・相談先・見せない情報を引き継ぐ。どちらも無ければ空のシート
 */
export function draftFromReport(dir) {
  const name = basename(dir);
  const draft = { meta: { 元のレポート: "", 作成日: today() }, sections: {}, refs: {} };
  const prev = previousSheet(dir);
  for (const [key, fields] of Object.entries(prev ? CARRY_OVER : {})) {
    const old = prev.sheet.sections[key]?.items?.[0] ?? {};
    if (!fields.some((f) => isFilled(old[f]))) continue;
    draft.sections[key] = { items: [Object.fromEntries(fields.map((f) => [f, old[f] ?? ""]))] };
    draft.refs[key] = [`前回 (${prev.name}) のシートから写した。変わっていれば直す`];
  }
  const srcPath = join(dir, `${name}.src.html`);
  if (!existsSync(srcPath)) return draft;
  const src = readFileSync(srcPath, "utf8");
  draft.meta.元のレポート = name;
  const conclusion = src.match(/<section\b[^>]*data-kind="conclusion"[^>]*>[\s\S]*?<h2\b[^>]*>([\s\S]*?)<\/h2>/);
  if (conclusion) draft.refs.purpose = [`レポートの結論「${plain(conclusion[1])}」`];
  const plan = src.match(/<section\b[^>]*data-kind="action"[^>]*>[\s\S]*?<h2\b[^>]*>([\s\S]*?)<\/h2>/);
  if (plan) draft.refs.goals = [`レポートの打ち手の方針「${plain(plan[1])}」`];
  const acts = readActs(src).map((a) => ({ 誰が: a.owner, 何を: a.title, いつまでに: a.due, できたかの目安: "" }));
  if (acts.length) {
    draft.sections.actions = { items: acts };
    draft.refs.actions = ["レポートの打ち手から写した。言葉は現場向けに直す"];
  }
  return draft;
}

// ---- CLI ----

export function printIssues(file, issues) {
  if (!issues.length) {
    console.log(`ヒアリング完了: ${file} の全項目がそろい、了承済みです。次: node scripts/report.mjs handout <フォルダ>`);
    return;
  }
  const fixes = issues.filter((x) => x.who === "fix");
  const groups = askGroups(issues);
  console.log(`回答待ち (${file})`);
  if (fixes.length) {
    console.log(`AI が直す ${fixes.length} 件 (ユーザーに聞かずにシートを直し、了承のときにまとめて見せる):`);
    for (const x of fixes) console.log(`  - [${x.kind}] ${x.where}: ${x.text}`);
  }
  if (groups.length) {
    console.log(`ユーザーに聞く ${Math.min(groups.length, ASK_LIMIT)} 問 (1回に ${ASK_LIMIT} 問まで。まとまりごとに1問):`);
    groups.slice(0, ASK_LIMIT).forEach((g, i) => {
      console.log(`  ${i + 1}. ${g.section}`);
      for (const x of g.items) console.log(`     - [${x.kind}] ${x.where}: ${x.text}`);
    });
    if (groups.length > ASK_LIMIT) console.log(`  ほか ${groups.length - ASK_LIMIT} 問は次の往復で聞く`);
  }
}

function main([dirArg]) {
  if (!dirArg) {
    console.error("使い方: node scripts/hearing.mjs <フォルダ>");
    return 2;
  }
  const dir = resolve(dirArg);
  if (!existsSync(dir)) {
    // 打ち間違いで知らないフォルダを作らない。新しく作るのは、既存の親フォルダの下の <YYYY-MM>-<slug> だけ
    if (!existsSync(dirname(dir)) || !NAME_RE.test(basename(dir))) {
      console.error(`入力エラー: フォルダ ${dir} がありません。レポートのフォルダか、既存のフォルダの下に <YYYY-MM>-<slug> の名前で指定する`);
      return 2;
    }
    mkdirSync(dir);
  }
  const file = join(dir, HEARING_FILE);
  if (!existsSync(file)) {
    writeFileSync(file, renderSheet(draftFromReport(dir)), { encoding: "utf8", flag: "wx" });
    console.log(`作成: ${file}`);
  }
  const issues = sheetIssues(parseSheet(readFileSync(file, "utf8")));
  printIssues(file, issues);
  return issues.length ? WAITING : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
