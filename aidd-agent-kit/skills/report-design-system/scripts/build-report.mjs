#!/usr/bin/env node
// レポートのソース(本文だけのHTML)から、配布用の単一HTMLを決定的に組み立てる。
//
//   node scripts/build-report.mjs <source.src.html> [out.html]
//
// ソースに書くのは <title> / <header class="doc"> / <section data-kind=…>… / <footer> だけ。
// <style> <script> 目次 .sec-head .secno .why .cta-row .doc-tools .act-head .act-links は書かない (書くと入力エラー)。
// ここで次を機械的に付与する:
//   1. vendor (標準カラー) → vendor (キット部品CSS) → report.css を <style> に埋め込む
//      (vendor はハッシュ検証済みのものだけ)
//   2. セクションの並び (結論 → 要因 1..n → 必要な場合だけ打ち手) を検証し、見出し帯 (.sec-head = 番号チップ .secno + h2) を付ける
//   3. 要因セクションの data-impact から、結論セクションの「要因ランキング」(.why) と、打ち手がある場合だけ CTA を生成する
//   4. 打ち手 (li.act) をカードにし、番号・出所バッジ (data-source)・根拠の要因へのボタン (data-from) を付ける
//   5. section / h3 に id を振り、左サイドバー目次 (狭い画面では上部の折りたたみ) を生成する
//   6. 文書ヘッダーに印刷ボタン、body 末尾に report.js とツールチップ要素を埋め込む
//   7. 出力を check-report.mjs で検査する (不合格なら終了コード 1)
// 日時・乱数を出力に含めないので、同じソースからは常にバイト単位で同じHTMLになる。
// 終了コード: 0=成功 1=検査不合格/vendor改変 2=入力エラー
import { readFileSync, existsSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { basename, dirname, join, resolve } from "node:path";
import { verifyVendor } from "./sync-kit.mjs";
import {
  KINDS, ORDER, ACT_SOURCES, ACT_FIELDS, parseImpact, textOf, NAME_RE,
  pageShell, secHead, PRINT_BUTTON, printResult, writeAtomic, isInsideSkill,
} from "./lib.mjs";
import { checkReport } from "./check-report.mjs";
import { fmt } from "./charts.mjs";
import { markTerms, glossaryBlock } from "./glossary.mjs";

export class InputError extends Error {}

export { KINDS, ORDER, ACT_SOURCES, ACT_FIELDS, parseImpact, textOf };
const attr = (attrs, name) => {
  const m = attrs.match(new RegExp(`\\b${name}\\s*=\\s*"([^"]*)"`));
  return m ? m[1] : null;
};
const escAttr = (s) => s.replace(/&(?![a-zA-Z#][a-zA-Z0-9]*;)/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

/**
 * 要因ランキングに出す影響値の表示を決める。
 * impact は「結論の指標への影響」で、悪化方向をマイナスとして書く約束。
 * @param {{value: number, digits: string}} impact parseImpact の戻り値
 * @returns {{text: string, tone: "loss"|"profit"|"flat"}} text=表示文字列, tone=色の意味
 */
export function formatImpact(impact) {
  // data-impact は常に「結論の指標への影響」。マイナス=悪化 (▲・赤)、プラス=改善 (+・緑)、ゼロ=中立。
  // 費用のように増えると悪い指標も、ソース側で悪化をマイナスとして書く (prompts/analyst.md「C. 解釈」の「要因を選ぶ」)。
  // data-impact は results.json と照合するため計算値のまま書かれる。表示だけを有効数字3桁 (整数部はすべて) に丸め、
  // 桁区切りを付ける (3752.92… → 3,753 / 12.46 → 12.5)。ソースに無い小数桁は足さない。
  const abs = Math.abs(impact.value);
  const given = (impact.digits.split(".")[1] || "").length;
  // 表示は小数20桁までに丸める。有限の極小値でもIntlへ数百桁を渡さず、data-impactの計算値は保つ。
  const digits = abs ? Math.min(20, given, Math.max(0, 2 - Math.floor(Math.log10(abs)))) : 0;
  const shown = fmt(abs, digits);
  if (!/[1-9]/.test(shown)) return { text: shown, tone: "flat" };
  return impact.value < 0 ? { text: `▲${shown}`, tone: "loss" } : { text: `+${shown}`, tone: "profit" };
}

/** 要因ランキング (.why)。並びはソース順 (|影響| の大きい順に書く。check が検証する) */
function whyBlock(factors, unit) {
  const max = Math.max(...factors.map((f) => Math.abs(f.impact.value))) || 1;
  const rows = factors.map((f, i) => {
    const { text, tone } = formatImpact(f.impact);
    const width = Math.max(2, Math.round((Math.abs(f.impact.value) / max) * 1000) / 10);
    const badge = { loss: "badge-danger", profit: "badge-success", flat: "badge-tag" }[tone];
    const fill = f.impact.value < 0 ? "is-loss" : "is-brand";
    return (
      `\n<li><a href="#${f.id}"><span class="why-no">${i + 1}</span>` +
      `<span class="why-text">${f.h2Text}</span>` +
      `<span class="why-val badge ${badge}">${text}</span>` +
      `<span class="why-bar bar-track" aria-hidden="true"><i class="bar-fill ${fill}" style="width:${width}%"></i></span></a></li>`
    );
  });
  return (
    `\n<div class="why card">\n<div class="why-head"><span>結論に至った要因</span><span>影響（${unit}）</span></div>\n` +
    `<ol>${rows.join("")}\n</ol>\n</div>\n`
  );
}

/** 結論の CTA。文書で唯一の主操作 (btn-primary) として打ち手セクションへ移動する */
const ctaBlock = (actionId, n) => `<div class="cta-row"><a class="btn btn-primary" href="#${actionId}">打ち手 ${n} 件を見る</a></div>\n`;

/**
 * 打ち手セクションの li.act をカードに組み立てる。
 * ソースに書くのは <li class="act" data-from="要因[,…]" data-source="data|hearing|pending"> と、
 * data-from は要因番号 ("1") か要因の data-toc の名前 ("燃料費")。名前なら並べ替え後の番号に直す (要因の順はデータで変わるため)。
 * その中の <b class="act-title"> と <dl class="act-meta"> (効果・担当・期限の順) だけ。
 */
function buildActions(inner, factors) {
  let n = 0;
  const out = inner.replace(/<li class="act"([^>]*)>([\s\S]*?)<\/li>/g, (_all, attrs, body) => {
    n += 1;
    const where = `打ち手 ${n} 件目`;
    const from = (attr(attrs, "data-from") || "").split(",").map((x) => x.trim()).filter(Boolean);
    if (!from.length) throw new InputError(`${where} に data-from (根拠の要因。番号か data-toc の名前。例: "1" / "1,3" / "燃料費") がありません`);
    const nos = from.map((x) => {
      const i = /^\d+$/.test(x) ? Number(x) - 1 : factors.findIndex((f) => f.toc === x);
      if (!factors[i]) throw new InputError(`${where} の data-from="${x}" に対応する要因がありません (要因は 1〜${factors.length}、名前は ${factors.map((f) => f.toc).filter(Boolean).join("・") || "なし"})`);
      return i + 1;
    });
    const links = nos.map((no) => `<a class="btn btn-tertiary" href="#${factors[no - 1].id}">要因 ${no} の根拠を見る</a>`);
    attrs = attrs.replace(/\bdata-from="[^"]*"/, `data-from="${nos.join(",")}"`);
    const source = ACT_SOURCES[attr(attrs, "data-source")];
    if (!source) throw new InputError(`${where} の data-source は data / hearing / pending のどれかにしてください (現在: ${attr(attrs, "data-source") ?? "なし"})`);
    const title = body.match(/<b class="act-title">[\s\S]*?<\/b>/);
    if (!title) throw new InputError(`${where} に <b class="act-title"> (動詞で始まる指示) がありません`);
    const meta = body.match(/<dl class="act-meta">[\s\S]*?<\/dl>/);
    const dts = meta ? [...meta[0].matchAll(/<dt>([\s\S]*?)<\/dt>/g)].map((m) => textOf(m[1])) : [];
    if (dts.join() !== ACT_FIELDS.join()) throw new InputError(`${where} の dl.act-meta は ${ACT_FIELDS.join("・")} の順に dt を書いてください (現在: ${dts.join("・") || "なし"})`);
    const no = String(n).padStart(2, "0");
    return (
      `<li class="act card card-pad"${attrs}>\n` +
      `<div class="act-head"><span class="act-no">${no}</span>${title[0]}<span class="badge ${source[0]}">${source[1]}</span></div>\n` +
      `${meta[0]}\n<div class="act-links">${links.join("")}</div>\n</li>`
    );
  });
  if (!n) throw new InputError('打ち手セクションに <li class="act"> が1つもありません (<ol class="actions"> の中に書く)');
  return { html: out, count: n };
}

export function buildReport(src) {
  for (const [re, what] of [
    [/<style\b/i, "<style>"],
    [/<script\b/i, "<script>"],
    [/<(html|head|body)\b/i, "<html>/<head>/<body>"],
    [/class="[^"]*\btoc\b/i, "目次"],
    [/class="[^"]*\b(secno|sec-head)\b/i, "セクションの見出し帯・番号 (.sec-head / .secno)"],
    [/class="[^"]*\bwhy\b/i, "要因ランキング (.why)"],
    [/class="[^"]*\b(cta-row|doc-tools|act-head|act-links|act-no)\b/i, "CTA・印刷ボタン・打ち手の番号やボタン"],
    [/id="tip"/i, "ツールチップ要素"],
    [/class="[^"]*\bterm\b/i, "用語マーク (.term)"],
    [/class="[^"]*\bglossary\b/i, "用語集 (aside.glossary)"],
  ]) {
    if (re.test(src)) throw new InputError(`ソースに ${what} を書かないでください (ビルドが付与します)`);
  }
  const title = src.match(/<title>([\s\S]*?)<\/title>/i);
  if (!title) throw new InputError("<title> がありません");
  let body = src.replace(title[0], "").trim();

  // 1回目の走査: 種別と並びの検証、要因の影響値の読み取り
  const raw = [...body.matchAll(/<section\b([^>]*)>([\s\S]*?)<\/section>/g)];
  if (!raw.length) throw new InputError("<section> が1つもありません");
  const kinds = raw.map((m, i) => {
    const k = attr(m[1], "data-kind");
    if (!KINDS[k]) throw new InputError(`${i + 1} 番目の <section> の data-kind は conclusion / factor / action のどれかにしてください (現在: ${k ?? "なし"})`);
    return k;
  });
  const order = kinds.join(" ");
  if (!ORDER.test(order)) {
    throw new InputError(`セクションの並びは 結論(conclusion) → 要因(factor) 1つ以上 → 必要な場合だけ打ち手(action) 1つ にしてください (現在: ${order})`);
  }
  if (!/<header class="doc"[^>]*>[\s\S]*?<\/header>/.test(body)) throw new InputError('<header class="doc"> (題名・対象データ・作成日・情報量) がありません');
  const unit = attr(raw[0][1], "data-unit");
  if (!unit) throw new InputError('結論セクションに data-unit (要因の影響の単位。例: "万円/月") がありません');

  const usedIds = new Set([...body.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
  const autoId = (x) => {
    if (usedIds.has(x)) throw new InputError(`自動採番した id "${x}" がソース内の既存 id と衝突しています`);
    return x;
  };

  // 2回目の走査: id・番号チップ・目次項目を付与する
  const entries = [];
  const factors = [];
  let actionInfo = null;
  let n = 0;
  body = body.replace(/<section\b([^>]*)>([\s\S]*?)<\/section>/g, (_all, attrs, inner) => {
    const kind = kinds[n];
    n += 1;
    const h2 = inner.match(/<h2\b[^>]*>([\s\S]*?)<\/h2>/);
    if (!h2) throw new InputError(`${n} 番目の <section> に <h2> がありません`);
    const h2Text = textOf(h2[1]);
    const id = attr(attrs, "id") || autoId(`sec-${n}`);
    let secno = KINDS[kind];
    if (kind === "factor") {
      const impactRaw = attr(attrs, "data-impact");
      const impact = parseImpact(impactRaw);
      if (!impact) throw new InputError(`${n} 番目の要因セクションの data-impact が数値ではありません (例: "-120" / "+30"。現在: ${impactRaw ?? "なし"})`);
      factors.push({ id, h2Text, impact, toc: attr(attrs, "data-toc") });
      secno = `要因 ${factors.length}`;
    }
    if (kind === "action") {
      const built = buildActions(inner, factors);
      inner = built.html;
      actionInfo = { id, count: built.count };
    }
    const children = [];
    let m = 0;
    inner = inner.replace(/<h3\b([^>]*)>([\s\S]*?)<\/h3>/g, (_h3, h3attrs, h3inner) => {
      m += 1;
      const hid = attr(h3attrs, "id") || autoId(`${id}-${m}`);
      children.push({ id: hid, label: attr(h3attrs, "data-toc") || textOf(h3inner) });
      const rest = h3attrs.replace(/\s*\bid="[^"]*"/, "");
      return `<h3 id="${hid}"${rest}>${h3inner}</h3>`;
    });
    entries.push({ id, kind, secno, label: attr(attrs, "data-toc") || h2Text, children });
    const rest = attrs.replace(/\s*\bid="[^"]*"/, "");
    // 見出し帯: 番号チップと h2 を1つの帯にまとめ、セクションの囲みの上端に置く (種類ごとの色は report.css の --kind)
    const head = inner.match(/<h2\b[^>]*>[\s\S]*?<\/h2>/)[0];
    inner = inner.replace(head, secHead(secno, head));
    return `<section id="${id}"${rest}>${inner}</section>`;
  });

  // 結論セクションに要因ランキングと打ち手への CTA を差し込む。結論に図 (内訳の waterfall など) があればその前、無ければ末尾
  // (ランキングを最初の画面に入れるため)
  const firstEnd = body.indexOf("</section>");
  const firstFig = body.slice(0, firstEnd).indexOf("<figure"); // 最初のセクション (結論) の中の図
  const at = firstFig >= 0 ? firstFig : firstEnd;
  body = body.slice(0, at) + whyBlock(factors, unit) + (actionInfo ? ctaBlock(actionInfo.id, actionInfo.count) : "") + body.slice(at);
  // 文書ヘッダーに印刷ボタン (副操作)
  body = body.replace(/<\/header>/, `${PRINT_BUTTON}\n</header>`);

  // 専門用語に用語集へのリンク (.term) を付け、使われた用語だけの用語集を本文の末尾 (フッターの前) へ置く。
  // 説明は常時表示せず、ホバー・フォーカス・クリックで出す (assets/report.js)
  const marked = markTerms(body);
  body = marked.html;
  const glossary = glossaryBlock(marked.used);
  if (glossary) body = body.includes("<footer>") ? body.replace("<footer>", `${glossary}<footer>`) : body + glossary;

  const li = (e) => {
    const sub = e.children.length
      ? `\n<ol>${e.children.map((c) => `\n<li><a href="#${c.id}" data-label="${escAttr(c.label)}"><span class="toc-label">${c.label}</span></a></li>`).join("")}\n</ol>`
      : "";
    return `\n<li data-kind="${e.kind}"><a href="#${e.id}" data-label="${escAttr(e.label)}"><span class="toc-no">${e.secno}</span><span class="toc-label">${e.label}</span></a>${sub}</li>`;
  };
  const toc =
    `<nav class="toc side-nav" aria-label="目次">\n<details open>\n<summary>目次<span class="toc-current"></span></summary>\n` +
    `<p class="toc-title">目次</p>\n<ol>${entries.map(li).join("")}\n</ol>\n</details>\n</nav>`;

  return pageShell({ title: title[1].trim(), nav: toc, body });
}

/** 出力先とファイル名の規則 (new-report.mjs が作る形): <YYYY-MM>-<slug>/<YYYY-MM>-<slug>.src.html と analysis.mjs */
export function layoutWarnings(srcPath) {
  const out = [];
  const name = basename(srcPath).replace(/\.src\.html$/, "");
  const dir = dirname(resolve(srcPath));
  if (!NAME_RE.test(name)) out.push(`W06 ファイル名が <YYYY-MM>-<slug>.src.html ではありません (${basename(srcPath)})。new-report.mjs でフォルダを作る`);
  else if (basename(dir) !== name) out.push(`W06 ソースが同名のフォルダ ${name}/ に入っていません (${dir})`);
  if (!existsSync(join(dir, "analysis.mjs"))) out.push("W06 同じフォルダに analysis.mjs がありません。数字と図は analysis.mjs で計算して書き出す (手で書かない)");
  return out;
}

function main(argv) {
  const [srcPath, outArg] = argv;
  if (!srcPath || !existsSync(srcPath)) {
    console.error("使い方: node scripts/build-report.mjs <source.src.html> [out.html]");
    return 2;
  }
  const vendor = verifyVendor();
  if (!vendor.ok) {
    console.error(`NG: ${vendor.reason}`);
    return 1;
  }
  const outPath = outArg || srcPath.replace(/\.src\.html$/, ".html");
  // スキルの中 (見本の template.src.html など) に成果物を書かない。見本を確かめるときは出力先を scratchpad などに指定する
  if (isInsideSkill(outPath)) {
    console.error(`入力エラー: 出力先 ${outPath} がスキルのフォルダの中です。第2引数で外の出力先を指定してください (例: <scratchpad>/template.html)`);
    return 2;
  }
  if (outPath === srcPath) {
    console.error("入力エラー: ソースは *.src.html と命名するか、出力先を指定してください");
    return 2;
  }
  let html;
  try {
    html = buildReport(readFileSync(srcPath, "utf8"));
  } catch (e) {
    if (e instanceof InputError) {
      console.error(`入力エラー: ${e.message}`);
      return 2;
    }
    throw e;
  }
  const result = checkReport(html);
  result.warnings.push(...layoutWarnings(srcPath));
  printResult(result);
  if (result.errors.length) return 1;

  writeAtomic(outPath, html);
  console.log(`生成: ${outPath}`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
