#!/usr/bin/env node
// 生成済みレポートHTMLの検収。build-report.mjs が毎回自動で呼ぶ。単体でも実行できる。
//
//   node scripts/check-report.mjs <report.html>
//
// エラー(E)=不合格。警告(W)=目視で判断。
// 終了コード: 0=合格 1=不合格 2=入力エラー
import { existsSync, readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { verifyVendor, VENDOR_FILES, vendorPath } from "./sync-kit.mjs";
import {
  embeddedCss, embeddedJs, REPORT_CSS, ORDER, ACT_SOURCES, ACT_FIELDS,
  DEFAULT_REPORT_DETAIL, REPORT_DETAILS, REPORT_DETAIL_BY_TOKEN,
  OVERVIEW_JARGON, TECHNICAL_STAT, OVERVIEW_ITEMS, LIMITS, textOf, printResult,
} from "./lib.mjs";

// 文章量の上限 (LIMITS) と検査結果の表示 (printResult) の正本は lib.mjs。ここから import している呼び出し元のために再 export する
export { LIMITS, printResult };
const COLOR_LITERAL = /#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(/;
const INFERENCE_IN_FACT = /原因|主因|と考え|とみられ|示唆|可能性|\bbecause\b|ために|によって|したがって/;
// 観察データだけのレポートで禁止する、限定的な強い因果断定。
// 明示的な留保がある文は先に除外し、「関連」「整合」のみの表現も断定とは扱わない。
const CAUSAL_HEDGE = /可能性(?:が|も)ある|かもしれない|と考えられる|とみられる|示唆される|因果(?:関係)?は未確認|原因とは限らない|断定できない/;
const STRONG_CAUSAL_ASSERTION = /(?:主因|原因)(?:である|だ(?:[。！？]|$)|となった|になった|[。！？]|$)|引き起こした|もたらした|生んだ|招いた|悪化させた|押し下げた|押し上げた|(?:により|によって|(?<!比)で)[^。！？]{0,24}(?:増えた|減った|増加した|減少した)/;
const hasUnsupportedCausalAssertion = (text) => {
  const clauses = String(text || "").split(/[。！？]/).filter(Boolean);
  return clauses.some((clause) => STRONG_CAUSAL_ASSERTION.test(clause) && !CAUSAL_HEDGE.test(clause));
};
/** 角丸・文字サイズの px 直書き (キットのトークンを使う。999px の丸は可。:root のトークン定義は対象外) */
const PX_LITERAL = /(?<![-\w])(border-radius|font-size)\s*:\s*([^;}]*)/g;
/** 旧版の手書き部品と、置き換え先のキットの部品 (部品の正本は assets/vendor/standard-components.css。references/maintenance.md「正本と責務」) */
const LEGACY = [
  [/class="[^"]*\bpill\b/, ".pill → キットの .badge .badge-*"],
  [/class="[^"]*\btblwrap\b/, ".tblwrap → キットの .table-scroll .card"],
  [/<td\b[^>]*class="[^"]*(?<![-\w])r\b/, "td.r → キットの td.col-num"],
  [/class="[^"]*\bbasis\b/, "dl.basis → キットの details.disclosure + dl.def-list"],
  [/<div class="actions">/, "div.actions → ol.actions > li.act"],
  [/class="[^"]*(?<![-\w])(cell|v)\b[^"]*"/, ".hero .cell/.v → キットの .hero-number / .kpi-strip"],
];

const all = (s, re) => [...s.matchAll(re)];
const count = (s, re) => all(s, re).length;
/** figure と表の中身を除いた本文 (図の注記やセルは文章量の対象外) */
const prose = (html) => html.replace(/<figure\b[\s\S]*?<\/figure>/g, "").replace(/<table\b[\s\S]*?<\/table>/g, "");

/** report.css のうち、トークン規律 (色・角丸・文字サイズ) に反する記述を返す */
export function cssViolations(css) {
  const bare = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const out = [];
  if (COLOR_LITERAL.test(bare)) out.push("report.css に色の直書き (HEX/rgb/hsl) があります。役割トークンを使ってください");
  for (const m of bare.matchAll(PX_LITERAL)) {
    const v = m[2].replace(/\b999px\b/g, "");
    if (/\d(\.\d+)?px\b/.test(v)) out.push(`report.css の ${m[1]} に px の直書きがあります (${m[0].trim()})。--radius-glass* / --font-size-* を使ってください`);
  }
  return out;
}

/** 文字色・白文字の地として使う基本色。白地とのコントラスト比 4.5 以上を要求する (WCAG 2.2 AA) */
export const PALETTE_TEXT = [
  "--p-brand-indigo", "--p-brand-accent", "--p-ink", "--p-ink-secondary", "--p-ink-muted",
  "--p-info", "--p-success", "--p-warning", "--p-danger",
];
const relLuminance = (hex) => {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
/** 白地とのコントラスト比 */
export const contrastOnWhite = (hex) => 1.05 / (relLuminance(hex) + 0.05);
const declsOf = (block) =>
  new Map(block.split(";").map((d) => d.trim()).filter(Boolean).map((d) => {
    const i = d.indexOf(":");
    return [d.slice(0, i).trim(), d.slice(i + 1).trim()];
  }));

/**
 * vendor 標準カラー (キット正本) の基本色の規律違反を返す。
 * 色の値はキット正本だけが持つので、検査もその1ファイルに対して行う。値を変えるときはキット側を直し、
 * sync-kit.mjs で取り込み直す (レポート側に上書き層は置かない)。
 * キット側の check-standard-contrast.mjs が役割トークン50ペアを見るのに対し、ここは
 * 「レポートが文字に使う基本色が白地で読めるか」だけを、取り込んだ現物に対して独立に見る。
 */
export function colorBaseViolations(colorCss) {
  const base = declsOf((colorCss.replace(/\/\*[\s\S]*?\*\//g, "").match(/:root\s*\{([^{}]*)\}/) || [, ""])[1]);
  const out = [];
  for (const name of PALETTE_TEXT) {
    const value = base.get(name);
    if (value === undefined) {
      out.push(`vendor 標準カラーに ${name} がありません。キット正本の基本色が変わった可能性があります (sync-kit.mjs で取り込み直してください)`);
      continue;
    }
    if (!/^#[0-9A-Fa-f]{6}$/.test(value)) out.push(`vendor 標準カラーの ${name} が #RRGGBB ではありません (${value})`);
    else if (contrastOnWhite(value) < 4.5) {
      out.push(`vendor 標準カラーの ${name} (${value}) は白地とのコントラスト比 ${contrastOnWhite(value).toFixed(2)} で、文字色に使えません (4.5 以上)`);
    }
  }
  return out;
}

export function checkReport(html) {
  const errors = [];
  const warnings = [];
  const E = (code, msg) => errors.push(`${code} ${msg}`);
  const W = (code, msg) => warnings.push(`${code} ${msg}`);

  // E01 文書の枠
  if (!/^<!doctype html>/i.test(html)) E("E01", "<!doctype html> で始まっていません");
  if (!/<html lang="ja">/.test(html)) E("E01", '<html lang="ja"> がありません');
  if (!/<title>[^<]+<\/title>/.test(html)) E("E01", "<title> が空です");

  // E02 外部参照ゼロ
  if (/\b(?:src|href)\s*=\s*"(?:https?:)?\/\//i.test(html)) E("E02", "外部URLへの src/href があります");
  if (/@import\b|url\(\s*["']?(?:https?:)?\/\//i.test(html)) E("E02", "@import または外部 url() があります");

  // E03/E04 CSS・JS が正本と完全一致 (手で似せた CSS / 古いビルドを検出する)
  const vendor = verifyVendor();
  if (!vendor.ok) E("E03", vendor.reason);
  const styles = all(html, /<style>\n?([\s\S]*?)\n?<\/style>/g);
  if (styles.length !== 1) E("E03", `<style> は1つだけにしてください (${styles.length} 個)`);
  else if (styles[0][1] !== embeddedCss()) E("E03", "埋め込みCSSが正本 (vendor + report.css) と一致しません。build-report.mjs で再生成してください");
  const scripts = all(html, /<script>\n?([\s\S]*?)\n?<\/script>/g);
  if (scripts.length !== 1) E("E04", `<script> は1つだけにしてください (${scripts.length} 個)`);
  else if (scripts[0][1] !== embeddedJs()) E("E04", "埋め込みJSが正本 (vendor用語UI → report.js) と一致しません。build-report.mjs で再生成してください");
  for (const v of cssViolations(readFileSync(REPORT_CSS, "utf8"))) E("E03", v);
  for (const v of colorBaseViolations(readFileSync(vendorPath(VENDOR_FILES[0]), "utf8"))) E("E03", v);

  const body = html.slice(html.indexOf("</head>"));
  const main = (body.match(/<main\b[^>]*>([\s\S]*)<\/main>/) || [, ""])[1];
  const headerMatch = main.match(/<header class="doc"([^>]*)>([\s\S]*?)<\/header>/);
  const detailToken = headerMatch?.[1].match(/\bdata-detail="([^"]+)"/)?.[1];
  const detail = REPORT_DETAIL_BY_TOKEN[detailToken] || { label: DEFAULT_REPORT_DETAIL, ...REPORT_DETAILS[DEFAULT_REPORT_DETAIL] };
  if (!REPORT_DETAIL_BY_TOKEN[detailToken]) E("E18", `header.doc の data-detail は ${Object.values(REPORT_DETAILS).map((x) => x.token).join(" / ")} のどれかにしてください (${detailToken || "なし"})`);

  // E06 id の重複
  const ids = all(body, /\bid="([^"]+)"/g).map((m) => m[1]);
  const dup = [...new Set(ids.filter((x, i) => ids.indexOf(x) !== i))];
  if (dup.length) E("E06", `id が重複しています: ${dup.join(", ")}`);

  // E05 目次と本文内リンク: 全リンクが実在の見出しへ飛び、目次はセクションと同じ数・同じ順で並ぶ
  const nav = body.match(/<nav class="toc side-nav"[^>]*>([\s\S]*?)<\/nav>/);
  const sections = all(main, /<section\b([^>]*)>([\s\S]*?)<\/section>/g).map((m) => ({
    attrs: m[1],
    id: (m[1].match(/\bid="([^"]+)"/) || [, null])[1],
    kind: (m[1].match(/\bdata-kind="([^"]+)"/) || [, null])[1],
    inner: m[2],
  }));
  const hasAction = sections.some((s) => s.kind === "action");
  if (!nav) E("E05", "サイドバー目次 (nav.toc.side-nav) がありません");
  else {
    const hrefs = all(nav[1], /href="#([^"]+)"/g).map((m) => m[1]);
    for (const h of hrefs) if (!ids.includes(h)) E("E05", `目次のリンク先 #${h} が本文にありません`);
    const top = hrefs.filter((h) => sections.some((s) => s.id === h));
    if (top.join() !== sections.map((s) => s.id).join()) E("E05", "目次の第1階層がセクションの並びと一致しません");
    // 目次の番号チップはセクションと同じ種類の色で塗るので、li の data-kind もセクションと揃える
    const tocKinds = all(nav[1], /<li data-kind="([^"]+)"><a href="#([^"]+)"/g).map((m) => `${m[2]}:${m[1]}`);
    if (tocKinds.join() !== sections.map((s) => `${s.id}:${s.kind}`).join()) E("E05", "目次の data-kind がセクションの種類と一致しません (build-report.mjs で再生成してください)");
    for (const m of all(nav[1], /data-label="([^"]*)"/g)) {
      if (m[1].length > LIMITS.tocLabel) W("W02", `目次ラベルが ${LIMITS.tocLabel} 字を超えています: 「${m[1]}」 (section に data-toc で短い名前を付ける)`);
    }
  }
  for (const m of all(main, /href="#([^"]+)"/g)) if (!ids.includes(m[1])) E("E05", `本文のリンク先 #${m[1]} がありません`);

  // E07 並び: 結論 → 要因 1つ以上 → 必要な場合だけ打ち手 1つ。各セクションの上端に見出し帯 (番号チップ + 見出し)
  const order = sections.map((s) => s.kind).join(" ");
  if (!ORDER.test(order)) E("E07", `セクションの並びが 結論 → 要因 → 必要な場合だけ打ち手 になっていません (${order || "なし"})`);
  if (!/<header class="doc"[^>]*>[\s\S]*?<h1 class="page-title">/.test(main)) E("E07", '文書ヘッダーの題名は <h1 class="page-title"> にしてください (キットのページ見出し)');

  // E18 ヘッダー・フッターの必須情報 (毎回同じ位置に同じ情報が出るように)
  const header = headerMatch?.[2] || "";
  if (!/<p class="crumb">[^<]*\S[^<]*<\/p>/.test(header)) E("E18", "文書ヘッダーに所属 (p.crumb。例: サンプル運送｜車両別収支 月次レポート) がありません");
  const sub = textOf((header.match(/<p class="sub">([\s\S]*?)<\/p>/) || [, ""])[1]);
  if (!/対象/.test(sub) || !/\d{4}-\d{2}-\d{2}/.test(sub)) E("E18", `文書ヘッダーの p.sub に「対象: 範囲・件数」と作成日 (YYYY-MM-DD) を書いてください: 「${sub}」`);
  if (!sub.includes(`情報量: ${detail.label}`)) E("E18", `文書ヘッダーの表示「情報量: ${detail.label}」と data-detail を一致させてください`);
  const footer = textOf((main.match(/<footer>([\s\S]*?)<\/footer>/) || [, ""])[1]);
  if (footer && !/データ[:：]/.test(footer)) E("E18", "footer に「データ: 出所のファイル名・期間」を書いてください");
  sections.forEach((s, i) => {
    const where = `${i + 1} 番目のセクション`;
    const h2 = s.inner.match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/);
    if (!/^\s*(?:<!--[\s\S]*?-->\s*)*<div class="sec-head"><span class="secno">[^<]+<\/span><h2\b/.test(s.inner)) {
      E("E07", `${where} の先頭に見出し帯 (div.sec-head = span.secno + h2) がありません (build-report.mjs で生成してください)`);
    }
    if (!h2) E("E07", `${where} に <h2> がありません`);
    else {
      const t = textOf(h2[1]);
      if (t.length > LIMITS.h2) E("E15", `${where} の見出しが ${t.length} 字あります (${LIMITS.h2} 字まで。結論だけを1文で): 「${t}」`);
      else if (t.length < 8) W("W03", `${where} の見出しが短すぎます (体言止めでなく結論を文で書く): 「${t}」`);
      if (s.kind !== "action" && hasUnsupportedCausalAssertion(t)) E("E21", `${where} (${s.kind === "conclusion" ? "結論" : "要因"}) の見出しが、未確認の因果を断定しています: 「${t}」`);
    }

    // E15 文章量: 段落は1つまで・1項目60字まで。補足説明は書かない
    const text = prose(s.inner);
    const ps = all(text, /<p\b[^>]*>([\s\S]*?)<\/p>/g);
    if (ps.length > LIMITS.pPerSection) E("E15", `${where} に段落が ${ps.length} 個あります (${LIMITS.pPerSection} 個まで。根拠は ul.facts の箇条書きにする)`);
    for (const m of [...ps, ...all(text, /<li\b(?![^>]*class="act\b)[^>]*>([\s\S]*?)<\/li>/g)]) {
      const t = textOf(m[1]);
      if (t.length > LIMITS.line) E("E15", `${where} に ${t.length} 字の文があります (${LIMITS.line} 字まで。分けるか削る): 「${t.slice(0, 30)}…」`);
    }

    // E16 結論: 主数字1つ + 前提ストリップ1〜3個を1枚のカードに。要因ランキングと CTA がある
    if (s.kind === "conclusion") {
      const hero = s.inner.match(/<div class="hero card">([\s\S]*?)<\/div>\s*(?=<div class="overview card">|<div class="why card">|<div class="caution-panel">|<figure\b)/);
      if (!hero) E("E16", '結論に <div class="hero card"> (主数字と前提ストリップ) がありません');
      else {
        if (count(hero[1], /<div class="hero-number">/g) !== 1 || !/<div class="hn-value\b/.test(hero[1])) E("E16", "結論の主数字 (.hero-number > .hn-value) は1つだけ書いてください");
        const kpis = count(hero[1], /<div class="kpi">/g);
        if (kpis < LIMITS.kpiMin || kpis > LIMITS.kpiMax) E("E16", `結論の前提ストリップ (.kpi-strip > .kpi) は ${LIMITS.kpiMin}〜${LIMITS.kpiMax} 個にしてください (${kpis} 個)`);
      }
      if (h2 && !/\d/.test(textOf(h2[1]))) E("E18", "結論の見出しに数字がありません (何がどれだけかを1文で)");
      if (hero && !/\d/.test(textOf((hero[1].match(/<div class="hn-value\b[^>]*>([\s\S]*?)<\/div>/) || [, ""])[1]))) E("E18", "結論の主数字 (.hn-value) に数字がありません");
      if (hero) for (const m of all(hero[1], /<div class="kpi-value\b[^>]*>([\s\S]*?)<\/div>/g)) if (!/\d/.test(textOf(m[1]))) E("E18", `結論の前提ストリップに数字の無い値があります: 「${textOf(m[1])}」`);
      // E20 初心者向け概要: 固定4項目だけで、対象・結果・読み方・限界を平易に示す
      const overview = s.inner.match(/<div class="overview card">([\s\S]*?)<\/div>\s*(?=<div class="why card">|<div class="caution-panel">|<figure\b)/);
      if (!overview || !/<div class="overview-title">分析結果の概要<\/div>/.test(overview[1])) E("E20", "結論に初心者向けの「分析結果の概要」(.overview.card) がありません");
      else {
        const items = all(overview[1], /<li><span class="overview-label">([^<]+)<\/span><span class="overview-text">([\s\S]*?)<\/span><\/li>/g)
          .map((m) => [textOf(m[1]), textOf(m[2])]);
        const expected = OVERVIEW_ITEMS.map(([, label]) => label);
        if (items.length !== expected.length || items.some(([label], i) => label !== expected[i])) E("E20", `分析結果の概要は「${expected.join("／")}」の4項目をこの順で置いてください`);
        for (const [label, value] of items) {
          if (!value) E("E20", `分析結果の概要「${label}」が空です`);
          if (value.length > LIMITS.overview) E("E20", `分析結果の概要「${label}」は${LIMITS.overview}字までです (${value.length}字)`);
          if (OVERVIEW_JARGON.test(value)) E("E20", `分析結果の概要「${label}」の専門用語を平易に言い換えてください: 「${value}」`);
        }
        if (items[1] && !/\d/.test(items[1][1])) E("E20", "分析結果の概要「数字で分かったこと」に最重要の数字がありません");
      }
      if (!/<div class="why card">/.test(s.inner)) E("E16", "結論に要因ランキング (.why) がありません (build-report.mjs で生成してください)");
      const hasCta = /<div class="cta-row"><a class="btn btn-primary"/.test(s.inner);
      if (hasAction && !hasCta) E("E16", "打ち手があるのに、結論に CTA がありません (build-report.mjs で生成してください)");
      if (!hasAction && hasCta) E("E16", "打ち手が無いのに、結論に CTA があります");
      const vals = all(s.inner, /<span class="why-bar[^"]*"[^>]*><i class="[^"]*" style="width:([\d.]+)%"/g).map((m) => Number(m[1]));
      if (vals.some((v, j) => j > 0 && v > vals[j - 1])) E("E16", "要因の並びが影響の大きい順になっていません (factor セクションを |data-impact| の大きい順に並べる)");
      if (vals.length > detail.factorsMax) W("W07", `情報量「${detail.label}」の要因は ${detail.factorsMax} つまでです (${vals.length}個)。増やすなら plan.情報量 を変更する`);
    }

    // E08 要因: 図か表で根拠を見せ、根拠の数字を事実カード (ul.facts) で並べ、データと計算を開閉に入れる
    if (s.kind === "factor") {
      if (!/<figure\b/.test(s.inner)) E("E08", `${where} (要因) に図 (figure) がありません。根拠は図で見せる (表は図の補助。charts.mjs で作る)`);
      if (!/<div class="facts-h">統計的事実<\/div>/.test(s.inner)) E("E08", `${where} (要因) に「統計的事実」の表示ラベルがありません`);
      const facts = s.inner.match(/<ul class="facts">([\s\S]*?)<\/ul>/);
      const n = facts ? count(facts[1], /<li\b/g) : 0;
      if (n < detail.factsMin || n > detail.factsMax) E("E08", `${where} (要因) の統計的事実は、情報量「${detail.label}」では ${detail.factsMin}〜${detail.factsMax} 項目にしてください (${n}項目)`);
      if (facts && !/\d/.test(textOf(facts[1]))) E("E08", `${where} (要因) の根拠に数字がありません`);
      if (facts) for (const item of all(facts[1], /<li\b[^>]*>([\s\S]*?)<\/li>/g)) {
        const fact = textOf(item[1]);
        if (INFERENCE_IN_FACT.test(fact)) E("E08", `${where} (要因) の統計的事実に解釈・因果が混ざっています: 「${fact}」`);
      }
      const interpretation = s.inner.match(/<div class="statement interpretation">[\s\S]*?<span class="statement-text">([\s\S]*?)<\/span><\/div>/);
      if (!interpretation || !textOf(interpretation[1])) E("E08", `${where} (要因) に、統計的事実と分けた「解釈」がありません`);
      else {
        if (textOf(interpretation[1]).length > LIMITS.interpretation) E("E15", `${where} (要因) の解釈は${LIMITS.interpretation}字までです (${textOf(interpretation[1]).length}字)`);
        if (hasUnsupportedCausalAssertion(textOf(interpretation[1]))) E("E21", `${where} (要因) の解釈が、未確認の因果を断定しています: 「${textOf(interpretation[1])}」`);
      }
      const claim = s.inner.match(/<div class="statement claim"[^>]*data-hypothesis-id="([^"]+)"[^>]*data-verdict="([^"]+)"[^>]*>[\s\S]*?<span class="statement-text">([\s\S]*?)<\/span><\/div>/);
      const hypothesisIds = (s.attrs.match(/\bdata-hypotheses="([^"]*)"/)?.[1] || "").split(",").map((id) => id.trim()).filter(Boolean);
      if (hypothesisIds.length && (!claim || !textOf(claim[3]))) E("E08", `${where} (要因) の仮説 ID に対応する「仮説・主張」がありません`);
      else if (!hypothesisIds.length && claim) E("E08", `${where} (要因) に仮説 ID が無いのに「仮説・主張」があります`);
      else if (claim && claim[2] !== "採用") E("E08", `${where} (要因) の仮説・主張は採用済みにしてください (${claim[1]}: ${claim[2]})`);
      if (claim && hasUnsupportedCausalAssertion(textOf(claim[3]))) E("E21", `${where} (要因) の仮説・主張が、未確認の因果を断定しています: 「${textOf(claim[3])}」`);
      for (const cause of all(s.inner, /<span class="cause-text">([\s\S]*?)<\/span>/g).map((m) => textOf(m[1]))) {
        if (hasUnsupportedCausalAssertion(cause)) E("E21", `${where} (要因) の背景の説明仮説が、未確認の因果を断定しています: 「${cause}」`);
      }
      // 判断への意味: 図の説明で終わらせず、読み手が何を前提に・何を変えるかを1文で (compose.mjs の factor({ meaning }))
      const meaning = s.inner.match(/<div class="meaning">[\s\S]*?<span class="meaning-text">([\s\S]*?)<\/span>/);
      if (!meaning || !textOf(meaning[1]).trim()) E("E08", `${where} (要因) に判断への意味 (div.meaning) がありません。図の説明ではなく、読み手が何を前提に・何を変えるかを1文で書く`);
      else if (textOf(meaning[1]).length > LIMITS.line) E("E15", `${where} (要因) の判断への意味は${LIMITS.line}字までです (${textOf(meaning[1]).length}字)`);
      // W08 図の言い換え: 根拠の項目の数字がすべて図に描いた数字なら、図を読めば分かることを繰り返している
      const figText = all(s.inner, /<figure\b[\s\S]*?<\/figure>/g).map((m) => textOf(m[0].replace(/<text\b[^>]*>/g, " ").replace(/<\/text>/g, " "))).join(" ");
      const figNums = new Set(all(figText, /(\d[\d,]*(?:\.\d+)?)/g).map((m) => m[1].replace(/,/g, "")));
      if (facts) for (const m of all(facts[1], /<li\b[^>]*>([\s\S]*?)<\/li>/g)) {
        const ns = all(textOf(m[1]), /(\d[\d,]*(?:\.\d+)?)/g).map((x) => x[1].replace(/,/g, "")).filter((x) => x.length > 1 && !/^(?:19|20)\d\d$/.test(x));
        if (ns.length && ns.every((x) => figNums.has(x))) W("W08", `${where} (要因) の根拠「${textOf(m[1]).slice(0, 30)}」は図の数字の言い換えです。図に無い比較・内訳・前提に替えるか削る`);
      }
      const disc = s.inner.match(/<details class="disclosure">\s*<summary>[\s\S]*?<dl class="def-list">([\s\S]*?)<\/dl>/);
      if (!disc) E("E08", `${where} (要因) に データと計算 の開閉 (details.disclosure > dl.def-list) がありません`);
      else {
        const dts = all(disc[1], /<dt>([\s\S]*?)<\/dt>/g).map((m) => textOf(m[1]));
        for (const need of ["データ", "計算"]) if (!dts.includes(need)) E("E08", `${where} (要因) のデータと計算に <dt>${need}</dt> がありません`);
      }

      // E19 統計の要約: 要因ごとに1枚。n (件数) と、ばらつき・比較・関係などの指標を数字で (references/statistics.md §4)
      const stats = s.inner.match(/<div class="stats card">([\s\S]*?)(?=<ul class="facts">|<details\b|<figure\b|<div class="(?:stats|table-scroll) card">|$)/);
      if (!stats) E("E19", `${where} (要因) に統計の要約 (div.stats.card。charts.mjs の statStrip) がありません`);
      else {
        const items = all(stats[1], /<div class="kpi-label">([\s\S]*?)<\/div><div class="kpi-value\b[^>]*>([\s\S]*?)<\/div>(?:<div class="kpi-sub">([\s\S]*?)<\/div>)?/g)
          .map((m) => [textOf(m[1]), textOf(m[2]), textOf(m[3] || "")]);
        if (items.length < detail.statsMin || items.length > detail.statsMax) E("E19", `${where} (要因) の統計の要約は、情報量「${detail.label}」では ${detail.statsMin}〜${detail.statsMax} 項目にしてください (${items.length}項目)`);
        for (const [k, v, sub] of items) {
          if (!/\d/.test(v)) E("E19", `${where} (要因) の統計の要約「${k}」に数字がありません`);
          if (TECHNICAL_STAT.test(`${k} ${v}`) && !sub) E("E19", `${where} (要因) の専門指標「${k}」に初心者向けの読み方 (kpi-sub) がありません`);
          if (sub.length > LIMITS.statSub) E("E19", `${where} (要因) の統計補足「${k}」は${LIMITS.statSub}字までです (${sub.length}字)`);
        }
        const n = items.find(([k]) => k === "n");
        if (!n) E("E19", `${where} (要因) の統計の要約に n (標本の件数) がありません。何件から出した数字かを必ず示す`);
        else if (Number(n[1].replace(/[^\d.]/g, "")) < LIMITS.smallN) W("W05", `${where} (要因) の n が ${n[1]} です (${LIMITS.smallN} 未満。結論を断定せず、傾向として書く)`);
      }
    }

    // E08 打ち手: 1〜5件。各件に 動詞で始まる指示・効果の数字・担当・期限・出所
    if (s.kind === "action") {
      const acts = all(s.inner, /<li class="act card card-pad"([^>]*)>([\s\S]*?)<\/li>/g);
      if (!/<ol class="actions">/.test(s.inner) || !acts.length) E("E08", "打ち手セクションに ol.actions > li.act がありません");
      if (acts.length > LIMITS.actsMax) E("E08", `打ち手が ${acts.length} 件あります (${LIMITS.actsMax} 件まで。効果の大きいものに絞る)`);
      acts.forEach(([, attrs, inner], j) => {
        const at = `打ち手 ${j + 1} 件目`;
        const source = (attrs.match(/data-source="([^"]*)"/) || [, ""])[1];
        const title = textOf((inner.match(/<b class="act-title">([\s\S]*?)<\/b>/) || [, ""])[1]);
        if (!title) E("E08", `${at} に指示 (b.act-title) がありません`);
        else if (title.length > LIMITS.line) E("E15", `${at} の指示が ${title.length} 字あります (${LIMITS.line} 字まで)`);
        const dd = Object.fromEntries(all(inner, /<dt>([\s\S]*?)<\/dt>\s*<dd>([\s\S]*?)<\/dd>/g).map((m) => [textOf(m[1]), textOf(m[2])]));
        for (const f of ACT_FIELDS) if (!dd[f]) E("E08", `${at} の ${f} が空です`);
        if (dd["効果"] && !/\d/.test(dd["効果"])) E("E08", `${at} の効果に数字がありません (何がどれだけ変わるかを数字で書く): 「${dd["効果"]}」`);
        const unsure = ACT_FIELDS.filter((f) => /要確認|未定/.test(dd[f] || ""));
        if (!ACT_SOURCES[source]) E("E08", `${at} の data-source が data / hearing / pending のどれでもありません`);
        else if (source !== "pending" && unsure.length) E("E08", `${at} の ${unsure.join("・")} が未確定なのに data-source="${source}" です (ヒアリングで確定するか pending にする)`);
        else if (source === "pending") W("W04", `${at} に未確定の項目があります (${unsure.join("・") || "出所"})。ユーザーにヒアリングして確定する (prompts/analyst.md「C. 解釈」の「打ち手（必要時だけ）」)`);
        if (!/<div class="act-links"><a class="btn btn-tertiary"/.test(inner)) E("E08", `${at} に根拠の要因へのボタンがありません (build-report.mjs で生成してください)`);
      });
    }
  });

  // E09 主数字は文書で1つ、主操作 (btn-primary) も1つ (マゼンタは1画面1つ)
  const hn = count(main, /class="hn-value\b/g);
  if (hn !== 1) E("E09", `主数字 (.hn-value) が ${hn} 個あります (結論に1つだけ)`);
  const primary = count(body, /class="btn btn-primary"/g), expectedPrimary = hasAction ? 1 : 0;
  if (primary !== expectedPrimary) E("E09", `主操作 (.btn-primary) が ${primary} 個あります (打ち手があるときだけ結論 CTA を1個。ソースに書かない)`);

  // E10 本文への色の直書き禁止 (SVG は .c-* / .s-* クラスで塗る)
  for (const m of all(main, /\b(fill|stroke|style|color|bgcolor|stop-color)="([^"]*)"/g)) {
    if (COLOR_LITERAL.test(m[2])) E("E10", `色の直書きがあります: ${m[0].slice(0, 60)} (SVGは .c-main 等のクラス、HTMLは部品クラスを使う)`);
  }
  if (/style="[^"]*border(-left|-radius)?\s*:/.test(main)) E("E10", "style 属性での枠線・角丸は禁止です (左端の色帯を含む。部品クラスを使う)");

  // E11/W01 チャート: figure はキットのカード
  for (const f of all(main, /<figure\b([^>]*)>([\s\S]*?)<\/figure>/g)) {
    if (!/class="card card-pad"/.test(f[1])) E("E11", '<figure> は class="card card-pad" (キットのカード) にしてください');
    if (!/<figcaption>/.test(f[2])) E("E11", "<figure> に <figcaption> (題名と凡例) がありません");
    const legend = f[2].match(/<figcaption>[\s\S]*?<small>([\s\S]*?)<\/small>/);
    if (legend && textOf(legend[1]).length > LIMITS.line) E("E15", `図の凡例が ${LIMITS.line} 字を超えています: 「${textOf(legend[1]).slice(0, 30)}…」`);
    for (const s of all(f[2], /<svg\b([^>]*)>([\s\S]*?)<\/svg>/g)) {
      if (!/role="img"/.test(s[1]) || !/aria-label="[^"]+"/.test(s[1])) E("E11", 'svg に role="img" と aria-label がありません');
      if (!/data-tip="/.test(s[2])) E("E11", `data-tip の無いチャートがあります (${(s[1].match(/aria-label="([^"]*)"/) || [, "?"])[1]})`);
    }
    // E22 図の読み方: 閉じた状態で置き、押したときだけ出す (常時表示にすると本文が読みにくくなる)
    const title = textOf((f[2].match(/<figcaption>([\s\S]*?)(?:<small>|<\/figcaption>)/) || [, "?"])[1]);
    const howto = f[2].match(/<details class="howto">([\s\S]*?)<\/details>/);
    if (!howto) E("E22", `図「${title}」に「この図の読み方」(details.howto) がありません (charts.mjs の figure で作る)`);
    else {
      if (/<details class="howto"\s+open/.test(f[2])) E("E22", `図「${title}」の読み方が開いたままです (説明は常時表示にしない)`);
      if (!/<summary>この図の読み方<\/summary>/.test(howto[1])) E("E22", `図「${title}」の読み方の見出しは「この図の読み方」にしてください`);
      const text = textOf((howto[1].match(/<p>([\s\S]*?)<\/p>/) || [, ""])[1]);
      if (!text) E("E22", `図「${title}」の読み方の説明文が空です`);
      else if (text.length > LIMITS.howto) E("E22", `図「${title}」の読み方が ${text.length} 字あります (${LIMITS.howto} 字まで): 「${text.slice(0, 30)}…」`);
    }
  }
  if (/<svg\b(?![^>]*class="chart")[^>]*viewBox/.test(main)) W("W01", 'class="chart" の付いていない svg があります');

  // E22 用語の説明: 本文の点線の語 (.term) と末尾の用語集 (aside.glossary) が1対1で対応する
  const glossary = main.match(/<aside class="glossary card card-pad">([\s\S]*?)<\/aside>/);
  const terms = all(main, /<a class="term" href="#([^"]+)"([^>]*)>([\s\S]*?)<\/a>/g);
  if (terms.length && !glossary) E("E22", "本文に用語マーク (.term) があるのに、末尾の用語集 (aside.glossary) がありません");
  if (glossary) {
    if (!/<details>\s*\n?\s*<summary>用語の説明/.test(glossary[1])) E("E22", "用語集は閉じた開閉 (details > summary「用語の説明」) にしてください (説明は常時表示にしない)");
    const dts = all(glossary[1], /<dt id="([^"]+)">([\s\S]*?)<\/dt>\s*<dd>([\s\S]*?)<\/dd>/g);
    if (!dts.length) E("E22", "用語集に <dt>/<dd> の組がありません");
    const ids = dts.map((m) => m[1]);
    const used = new Set(terms.map((m) => m[1]));
    for (const id of new Set(terms.map((m) => m[1]))) if (!ids.includes(id)) E("E22", `用語マークのリンク先 #${id} が用語集にありません`);
    for (const [, id, label] of dts) if (!used.has(id)) E("E22", `用語集の「${textOf(label)}」が本文で使われていません (使った用語だけ載せる)`);
    for (const [, , , dd] of dts) {
      const t = textOf(dd);
      if (!t) E("E22", "用語集に説明の無い項目があります");
      else if (t.length > LIMITS.glossary) E("E22", `用語集の説明が ${t.length} 字あります (${LIMITS.glossary} 字まで): 「${t.slice(0, 30)}…」`);
    }
  }
  for (const [, , attrs, inner] of terms) {
    if (!/data-term="[^"]+"/.test(attrs)) E("E22", `用語マークに data-term (用語名) がありません: 「${textOf(inner)}」`);
    if (!/<span class="term-q" aria-hidden="true">\?<\/span>/.test(inner)) E("E22", `用語マークに ? の印がありません: 「${textOf(inner)}」`);
  }

  // E12 数値セルは右揃え (キットの .col-num)
  for (const m of all(main, /<td(?![^>]*class="[^"]*\bcol-num\b)[^>]*>([^<]*)<\/td>/g)) {
    if (/^[▲△+\-−]?[\d,]+(\.\d+)?%?$/.test(m[1].trim())) E("E12", `数値セルが右揃え (td.col-num) になっていません: ${m[1].trim()}`);
  }

  // E13 出所
  if (!/<footer>[\s\S]*?\S[\s\S]*?<\/footer>/.test(main)) E("E13", "<footer> (データの出所・手法) がありません");

  // E14 絵文字
  if (/\p{Extended_Pictographic}/u.test(textOf(main))) E("E14", "絵文字があります");

  // E17 旧版の手書き部品 (キットの部品で書く)
  for (const [re, hint] of LEGACY) if (re.test(main)) E("E17", `旧部品が使われています: ${hint}`);

  return { errors, warnings };
}

function main(argv) {
  const [file] = argv;
  if (!file || !existsSync(file)) {
    console.error("使い方: node scripts/check-report.mjs <report.html>");
    return 2;
  }
  const result = checkReport(readFileSync(file, "utf8"));
  printResult(result);
  return result.errors.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
