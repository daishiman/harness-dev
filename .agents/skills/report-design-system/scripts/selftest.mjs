#!/usr/bin/env node
// スキル自身の全回帰テスト。検査器・統計・図・生成器・vendor 同期の変更時、または明示されたときに実行する。
//
//   node .claude/skills/report-design-system/scripts/selftest.mjs
//
// 1. vendor CSS が SOURCE.json と一致すること
// 2. 同じソースから2回ビルドしてバイト一致すること (再現性)
// 3. テンプレートが検査をエラー0・警告0で通ること
// 4. 規律違反を入れたソース/出力を、検査・ビルドが確実に不合格にすること (検査の感度)
// 5. report.css の mirror 区間 (キットの宣言を写した箇所) が vendor の部品CSSと食い違っていないこと
// 6. stats.mjs が既知の値 (scipy・Excel で照合済み) を返すこと
// 7. charts.mjs + compose.mjs で組んだソースが検査をエラー0・警告0で通ること (analysis.mjs の経路)
// 8. new-report.mjs の雛形が構文として正しく、build が出力先の規則違反を W06 で知らせること
// 9. 図がデータの端 (負の値・全部0・1項目・長いラベル・密集した折れ線) でも壊れた SVG を出さないこと
// 10. profile-data が列の型を正しく判定し、check-llm が brief / results / review の欠陥を検出すること (LLM の出力の検査)
// 11. thinking.md の混入防止と review prompt の人間向け転記が機械正本と同期していること
// 12. build 証跡が成果物・背景データ集合・実描画結果の変更を検出すること
// 13. ヒアリングシートの往復 (下書き→AI が直す・ユーザーに聞く→了承) と、実行部隊向け資料の生成・検査が崩れないこと
// 終了コード: 0=合格 1=不合格
import { readFileSync, writeFileSync, mkdtempSync, mkdirSync, rmSync, existsSync, cpSync, realpathSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { verifyVendor, VENDOR_FILES, vendorPath } from "./sync-kit.mjs";
import {
  SKILL_DIR, REPORT_CSS, REFERENCE_MAX_LINE_LENGTH, REVIEW_CONDITIONS,
  REVIEW_FINDING_FIELDS, REVIEW_SEVERITIES, REVIEW_STATUSES, REVIEW_VERDICTS,
  OVERVIEW_JARGON, TECHNICAL_STAT, RENDER_WIDTHS, ASK_LIMIT, parseImpact, serializeImpact, sha256, LIMITS, REPORT_DETAILS, esc, textOf, embeddedCss, embeddedJs,
} from "./lib.mjs";
import { buildReport, InputError, layoutWarnings } from "./build-report.mjs";
import * as st from "./stats.mjs";
import { figure, hbar, columns, line, waterfall, histogram, boxplot, scatter, paretoChart, table, sfmt, multiline, stacked, dumbbell, forest, butterfly, heatmap, flow } from "./charts.mjs";
import { header, conclusion, factor as composeFactor, actions, footer, source, num, parseCsv, hypothesisClaim } from "./compose.mjs";
import { checkReport, colorBaseViolations, cssViolations, PALETTE_TEXT } from "./check-report.mjs";
import { profile as profileRows } from "./profile-data.mjs";
import { checkBrief, checkResults, checkReview, checkImpacts, checkCauses, checkStrictCompletion, mergeBackgroundFiles, unfixedMusts } from "./check-llm.mjs";
import { pipelineSteps, USAGE } from "./report.mjs";
import { FRONTLINE_WORDS, QUESTIONS, TEXT_MAX, TITLE_MAX, askGroups, draftFromReport, parseSheet, plainIssues, readActs, renderSheet, sheetIssues } from "./hearing.mjs";
import { HANDOUT_KINDS, buildHandout, checkHandout, handoutModel, plainDue } from "./build-handout.mjs";
import { INPUT_MANIFEST_FILE, INPUT_MANIFEST_VERSION } from "./new-report.mjs";
import { BUILD_STATE_FILE, clearBuildState, recordBuildState, verifyBuildState } from "./build-state.mjs";
import { inputManifest, readInputManifest, readInputRows, readRows, writeInputManifest, parseNumericCell } from "./inputs.mjs";
import { runContentChecks } from "./content-selftest.mjs";

const src = readFileSync(join(SKILL_DIR, "assets/template.src.html"), "utf8");
const failures = [];
const ok = (cond, msg) => { if (!cond) failures.push(msg); };
runContentChecks(ok);
const long = "あ".repeat(61);
const factor = (impact) =>
  `<section data-kind="factor" data-impact="${impact}"><h2>追加した要因の見出しを一文で書く</h2>` +
  `<div class="meaning"><span class="meaning-h">判断への意味</span><span class="meaning-text">意味</span></div>` +
  `<figure class="card card-pad"><figcaption>図</figcaption><div class="chartbox"><svg viewBox="0 0 10 10" class="chart" role="img" aria-label="図"><rect class="c-main" data-tip="a: 1"/></svg></div></figure>` +
  `<div class="stats card"><div class="stats-title">統計の要約</div><div class="kpi-strip"><div class="kpi"><div class="kpi-label">n</div><div class="kpi-value num">20台</div></div><div class="kpi"><div class="kpi-label">中央値</div><div class="kpi-value num">1</div><div class="kpi-sub">半数は1以下</div></div></div></div>` +
  `<div class="facts-h">統計的事実</div><ul class="facts"><li>根拠 <b class="num">1</b></li><li>根拠 <b class="num">2</b></li></ul>` +
  `<div class="statement interpretation"><span class="statement-text">差がある</span></div>` +
  `<div class="statement claim" data-hypothesis-id="H1" data-verdict="採用"><span class="statement-text">仮説</span></div>` +
  `<details class="disclosure"><summary>データと計算</summary><div class="disclosure-body"><dl class="def-list"><dt>データ</dt><dd>x</dd><dt>計算</dt><dd>y</dd></dl></div></details></section>`;
const beforeAction = '<!-- 打ち手:';

ok(verifyVendor().ok, "vendor CSS が SOURCE.json と一致しない");

// 共通参照へ別用途のプロンプトを連結する編集事故を、内容と異常な行長の両方で止める。
const thinking = readFileSync(join(SKILL_DIR, "references/thinking.md"), "utf8");
for (const marker of ["プロジェクトID: elegant-review", "Layer 1:", "UserInput"]) {
  ok(!thinking.includes(marker), `references/thinking.md に別用途の指示 (${marker}) が混入している`);
}
const longestThinkingLine = Math.max(0, ...thinking.split(/\r?\n/).map((line) => line.length));
ok(longestThinkingLine <= REFERENCE_MAX_LINE_LENGTH, `references/thinking.md に異常な長行がある (${longestThinkingLine}文字)`);
for (const condition of REVIEW_CONDITIONS) ok(thinking.includes(condition), `references/thinking.md に4条件「${condition}」がない`);

// 通常 build は最短経路としてブラウザと独立reviewの証跡を起動せず、verify だけが重い検証を追加する。
{
  const steps = (mode) => pipelineSteps(mode, "/tmp/2026-05-sample", "2026-05-sample");
  const fast = steps("build"), strict = steps("verify");
  ok(fast.length === 3 && !fast.some(([script]) => script === "verify-render.mjs") && !fast.some(([script, action]) => script === "build-state.mjs" && action === "record"), "通常 build に最短生成以外の段が混入している");
  ok(strict.some(([script]) => script === "verify-render.mjs") && strict.some(([script, action]) => script === "build-state.mjs" && action === "record"), "verify に実描画と証跡記録が揃っていない");
}
// review prompt は LLM への操作契約なので、lib.mjs の機械正本からの必要な転記を照合する。
const reviewPrompt = readFileSync(join(SKILL_DIR, "prompts/review.md"), "utf8");
for (const [name, values] of Object.entries({ REVIEW_CONDITIONS, REVIEW_VERDICTS, REVIEW_SEVERITIES, REVIEW_STATUSES, REVIEW_FINDING_FIELDS })) {
  for (const value of values) ok(reviewPrompt.includes(value), `prompts/review.md に ${name} の値「${value}」がない`);
}
ok(reviewPrompt.includes("仮説を使う要因だけ") && reviewPrompt.includes("単純な記述では仮説と claim の省略を許す"), "review が単純記述にも採用仮説を一律要求している");
ok(readFileSync(join(SKILL_DIR, "references/statistics.md"), "utf8").includes("仮説を使う場合は複数の仮説を競わせる"), "statistics の手順が仮説使用を一律要求している");
ok(OVERVIEW_JARGON.test("p値") && TECHNICAL_STAT.test("中央値"), "共有した文章契約の語彙が欠けている");
ok(parseImpact("−12.5")?.value === -12.5 && parseImpact("▲3")?.value === -3 && parseImpact("+2")?.value === 2, "data-impact の共有正規化が Unicode 符号を扱えない");

// 有限impactはNumberの指数表記になっても同じ値と表示精度へ戻る。
for (const value of [1e-7, -1e-7, 1e21, Number.MIN_VALUE, Number.MAX_VALUE, 0]) {
  const encoded = serializeImpact(value);
  ok(parseImpact(encoded)?.value === value && parseImpact(String(value))?.value === value, `impactの有限数が往復できない (${value})`);
}
ok(parseImpact("1e309") === null && parseImpact("Infinity") === null, "非有限impactを受理した");

const a = buildReport(src);
ok(a === buildReport(src), "同じソースからのビルド結果が一致しない (非決定的)");

const base = checkReport(a);
ok(base.errors.length === 0, `テンプレートが不合格: ${base.errors.join(" / ")}`);
ok(base.warnings.length === 0, `テンプレートに警告: ${base.warnings.join(" / ")}`);

// 共通用語UIはvendor JSとして1つのscriptへ埋め込む。CSSには混入せず、キットを置かない単独コピーでもbuildできる。
{
  const jsFiles = VENDOR_FILES.filter((file) => file.kind === "js");
  ok(jsFiles.length > 0, "共通用語UIのvendor JSが配布契約にない");
  for (const file of jsFiles) {
    const javascript = readFileSync(vendorPath(file), "utf8").trimEnd();
    ok(embeddedJs().includes(javascript) && a.includes(javascript), `${file.vendor} が単一HTMLへ埋め込まれていない`);
    ok(!embeddedCss().includes(javascript), `${file.vendor} がCSSへ混入している`);
  }
  // macOSのtmpdirは/var→/private/varのsymlinkを含む。CLIのimport.meta guardと同じ実パスで起動する。
  const tmp = realpathSync(mkdtempSync(join(tmpdir(), "rds-standalone-")));
  try {
    const copy = join(tmp, "report-design-system"), output = join(tmp, "report.html");
    cpSync(SKILL_DIR, copy, { recursive: true });
    const build = spawnSync(process.execPath, [join(copy, "scripts/build-report.mjs"), join(copy, "assets/template.src.html"), output], { cwd: tmp, env: { ...process.env, AIDD_KIT_DIR: "" }, encoding: "utf8" });
    ok(build.status === 0 && existsSync(output), `キットを置かない単独コピーでbuildできない (${build.error?.message || build.stderr || build.stdout || `status=${build.status}, signal=${build.signal}`})`);
    if (existsSync(output)) ok(checkReport(readFileSync(output, "utf8")).errors.length === 0, "単独コピーから生成したHTMLが正本と一致しない");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

// escで増えた実体参照の文字を、表示字数へ戻す。生成が許す48字は最終検査も許し、49字は拒否する。
for (const symbol of ["&", "<", ">", '"']) {
  const value = symbol + "あ".repeat(LIMITS.overview - 1);
  ok(textOf(esc(value)) === value, `表示字数へ戻すときに ${symbol} を復号できない`);
  const replaceOverview = (text) => src.replace(/(<span class="overview-text">)[^<]*(<\/span>)/, (_all, open, close) => open + esc(text) + close);
  ok(!checkReport(buildReport(replaceOverview(value))).errors.some((e) => e.startsWith("E20")), `実体参照を含む${LIMITS.overview}字の概要を拒否した (${symbol})`);
  ok(checkReport(buildReport(replaceOverview(value + "あ"))).errors.some((e) => e.startsWith("E20")), `実体参照を含む${LIMITS.overview + 1}字の概要を受理した (${symbol})`);
}
ok(textOf('<b>A&amp;B</b><span class="term-q" aria-hidden="true">?</span>') === "A&B", "用語マークの飾りを表示字数に数えた");
{
  const label = '<img src=x>の差は10万円', literalEntity = "A&amp;Bの差は10万円";
  const withHeading = (text) => src.replace(/(<section data-kind="factor"[^>]*>\s*<h2>)[\s\S]*?(<\/h2>)/, (_all, start, end) => start.replace(/ data-toc="[^"]*"/, "") + esc(text) + end);
  for (const value of [label, literalEntity]) {
    const html = buildReport(withHeading(value));
    ok(html.includes(`<span class="why-text">${esc(value)}</span>`) && html.includes(`<span class="toc-label">${esc(value)}</span>`), "復号した見出しを要因ランキングか目次へ再挿入するときにエスケープしていない");
    ok(!html.includes(`<span class="why-text">${label}</span>`) && checkReport(html).errors.length === 0, "文字数用の復号が見出しをHTMLタグへ変えた");
  }
  const brief = { hypotheses: [{ id: "H1", 主張: literalEntity }] };
  const results = { steps: [{ label: "売上", value: 10 }], hypotheses: [{ id: "H1", 判定: "採用" }] };
  const html = `<section data-kind="factor" data-toc="売上" data-impact="10" data-hypotheses="H1"><div class="statement claim" data-hypothesis-id="H1" data-verdict="採用"><span class="statement-text">${esc(literalEntity)}</span></div></section>`;
  ok(checkImpacts(results, brief, html).length === 0, "表示用claimの実体参照を二重復号した");
}
ok((a.match(/<li class="act card card-pad"/g) || []).length === 3 && (a.match(/class="btn btn-primary"/g) || []).length === 1, "打ち手カードと CTA が生成されていない");
const templateFactors = [...src.matchAll(/<section\b[^>]*data-kind="factor"[^>]*>/g)].map((m) => m[0]);
ok(templateFactors.length > 0 && templateFactors.every((tag) => /data-hypotheses="[^"]+"/.test(tag)), "テンプレートの要因に仮説 trace がない");

// mirror 区間: キットの .side-nav [aria-current="page"] の宣言を写したもの。キット更新で値がずれたら落とす
const decls = (block) => block.replace(/\/\*[\s\S]*?\*\//g, "").split(";").map((d) => d.replace(/\s+/g, " ").trim()).filter((d) => d.includes(":"));
const vendorCss = readFileSync(join(SKILL_DIR, "assets/vendor/standard-components.css"), "utf8");
const kitDecls = new Set(
  [...vendorCss.matchAll(/([^{}]*\.side-nav[^{}]*\[aria-current="page"\][^{}]*)\{([^{}]*)\}/g)].flatMap((m) => decls(m[2])),
);
const reportCss = readFileSync(REPORT_CSS, "utf8");
const mirror = reportCss.match(/\/\* mirror:side-nav-current[\s\S]*?\*\/([\s\S]*?)\/\* \/mirror \*\//);
ok(mirror, "report.css に mirror:side-nav-current 区間がない");
if (mirror) {
  const body = [...mirror[1].matchAll(/\{([^{}]*)\}/g)].map((m) => m[1]).join(";");
  const first = [...mirror[1].matchAll(/\{([^{}]*)\}/g)][0];
  for (const d of decls(first ? first[1] : body)) ok(kitDecls.has(d), `mirror 区間の宣言がキットに無い (キット側が変わった可能性): ${d}`);
}
ok(cssViolations(reportCss).length === 0, `report.css がトークン規律に反する: ${cssViolations(reportCss).join(" / ")}`);
// 配色: 値はキット正本 (vendor) だけが持つ。レポート側に上書き層は無い
const colorCss = readFileSync(join(SKILL_DIR, "assets/vendor/standard-color-system.css"), "utf8");
ok(colorBaseViolations(colorCss).length === 0, `vendor 標準カラーの基本色が規律に反する: ${colorBaseViolations(colorCss).join(" / ")}`);
ok(
  colorBaseViolations(":root{--p-ink:#AAAAAA}").length > 0 &&
  colorBaseViolations(":root{--p-ink:rgb(0,0,0)}").length > 0 &&
  colorBaseViolations(":root{}").length === PALETTE_TEXT.length,
  "基本色の規律違反 (コントラスト不足・値の形式・トークン欠落) を検出できない",
);
{
  // 埋め込み順: vendor 配色 → キット部品 → report.css。値はHEXを固定せず正本から取り、正本の色が動いても壊れないようにする
  const indigo = colorCss.match(/--p-brand-indigo:\s*(#[0-9A-Fa-f]{6});/)[1];
  const colorAt = a.indexOf(`--p-brand-indigo: ${indigo}`), kitAt = a.indexOf("--radius-glass: 22px");
  ok(colorAt >= 0 && colorAt < kitAt, "vendor 配色がキット部品より前に埋め込まれていない");
  ok(a.split(`--p-brand-indigo: ${indigo}`).length - 1 === 1, "基本色が2回以上宣言されている (上書き層が復活している)");
}
ok(cssViolations(".x{border-radius:12px}").length === 1 && cssViolations(".x{border-radius:999px;font-size:var(--font-size-body)}").length === 0, "角丸・文字サイズの px 直書き検出が機能しない");
ok(/<div class="why card">/.test(a) && (a.match(/<li><a href="#sec-\d+"><span class="why-no">/g) || []).length === 3, "要因ランキングが要因セクションの数だけ生成されていない");

// 違反ごとに、期待するエラーコードが出ることを確かめる
const cases = [
  ["E15", "長い見出し", (s) => s.replace("<h2>小型の空車", "<h2>" + "長".repeat(30) + "小型の空車"), "src"],
  ["E15", "段落の羅列", (s) => s.replace("<ul class=\"facts\">", "<p>補足1</p><p>補足2</p><ul class=\"facts\">"), "src"],
  ["E15", "60字を超える箇条書き", (s) => s.replace("<li>全体 ", `<li>${long}`), "src"],
  ["E15", "長い凡例", (s) => s.replace("<small>赤=目標", `<small>${long}`), "src"],
  ["E15", "長い打ち手の指示", (s) => s.replace("<b class=\"act-title\">小型車", `<b class="act-title">${long}`), "src"],
  ["E08", "要因に図が無い (表だけでは不可)", (s) => s.replace(/<figure class="card card-pad">[\s\S]*?<\/figure>/, '<div class="table-scroll card"><table><tbody><tr><td>行</td><td class="col-num">1</td></tr></tbody></table></div>'), "src"],
  ["E08", "データと計算に計算が無い", (s) => s.replace("<dt>計算</dt><dd>実車距離 ÷ 総走行距離</dd>", ""), "src"],
  ["E11", "チャートに data-tip が無い", (s) => s.replace(/(aria-label="車種別[\s\S]*?<\/svg>)/, (m) => m.replace(/ data-tip="[^"]*"/g, "")), "src"],
  ["E18", "ヘッダーに所属が無い", (s) => s.replace(/<p class="crumb">[^<]*<\/p>/, ""), "src"],
  ["E18", "ヘッダーに作成日が無い", (s) => s.replace("｜作成 2026-10-05", ""), "src"],
  ["E18", "ヘッダーに対象が無い", (s) => s.replace("対象: 48台・6ヶ月｜", ""), "src"],
  ["E18", "情報量の表示と属性が不一致", (s) => s.replace("情報量: 標準", "情報量: 詳細"), "src"],
  ["E18", "フッターにデータの出所が無い", (s) => s.replace("データ: 運行日報", "運行日報"), "src"],
  ["E18", "結論の見出しに数字が無い", (s) => s.replace("<h2>営業利益は目標を月280万円下回り", "<h2>営業利益は目標を大きく下回り"), "src"],
  ["E18", "前提ストリップに数字が無い", (s) => s.replace('<div class="kpi-value num">67<span class="unit">%</span></div>', '<div class="kpi-value num">低い</div>'), "src"],
  ["E20", "初心者向け概要が無い", (s) => s.replace(/\s*<div class="overview card">[\s\S]*?<\/div>\s*(?=<\/section>)/, ""), "src"],
  ["E20", "初心者向け概要が3項目", (s) => s.replace(/\s*<li><span class="overview-label">言えないこと<\/span>[\s\S]*?<\/li>/, ""), "src"],
  ["E20", "概要の結果に数字が無い", (s) => s.replace("営業利益は目標を月280万円下回った", "営業利益は目標を大きく下回った"), "src"],
  ["E20", "概要に専門用語", (s) => s.replace("関連は確認したが、原因の確定には追加確認が必要", "p値は0.01だが、原因の確定には追加確認が必要"), "src"],
  ["E19", "要因に統計の要約が無い", (s) => s.replace(/<div class="stats card">[\s\S]*?<\/div>\s*<\/div>\s*<\/div>/, ""), "src"],
  ["E19", "統計の要約に n が無い", (s) => s.replace('<div class="kpi"><div class="kpi-label">n</div><div class="kpi-value num">48台</div></div>', ""), "src"],
  ["E19", "統計の要約が1項目", (s) => s.replace(/(<div class="stats card">[\s\S]*?<div class="kpi-strip">\s*<div class="kpi">[\s\S]*?<\/div><\/div>)[\s\S]*?(\s*<\/div>\s*<\/div>\s*<div class="facts-h">)/, "$1$2"), "src"],
  ["E19", "統計の値に数字が無い", (s) => s.replace('<div class="kpi-value num">7.2pt</div>', '<div class="kpi-value num">大きい</div>'), "src"],
  ["E19", "専門指標の平易な読み方が無い", (s) => s.replace('<div class="kpi-sub">車両ごとの差は平均から約7pt</div>', ""), "src"],
  ["E08", "要因に判断への意味が無い", (s) => s.replace(/<div class="meaning">[\s\S]*?<\/div>/, ""), "src"],
  ["E08", "要因に統計的事実の表示ラベルが無い", (s) => s.replace('<div class="facts-h">統計的事実</div>', ""), "src"],
  ["E08", "根拠の箇条書きが無い", (s) => s.replace(/<ul class="facts">[\s\S]*?<\/ul>/, ""), "src"],
  ["E08", "統計的事実に因果解釈が混在", (s) => s.replace("<li>全体 ", "<li>原因は全体 "), "src"],
  ["E08", "要因に解釈が無い", (s) => s.replace(/<div class="statement interpretation">[\s\S]*?<\/div>/, ""), "src"],
  ["E08", "要因に仮説・主張が無い", (s) => s.replace(/<div class="statement claim"[\s\S]*?<\/div>/, ""), "src"],
  ["E21", "見出しの因果断定", (s) => s.replace("小型の空車42便と実車率58%が対応し、影響は月150万円", "小型の帰り荷不足が実車率低下の主因である"), "src"],
  ["E21", "結論見出しの因果断定", (s) => s.replace("営業利益は目標を月280万円下回り、半分が実車率の低さと対応", "燃料高が月280万円の利益低下を引き起こした"), "src"],
  ["E21", "結論見出しの因果断定と別文留保の矛盾", (s) => s.replace("営業利益は目標を月280万円下回り、半分が実車率の低さと対応", "燃料高が月280万円の利益低下を生んだ。因果は未確認"), "src"],
  ["E21", "解釈の因果断定", (s) => s.replace("小型車の空車増加が、全体の実車率低下に最も強く関係している", "小型車の空車が全体の低下を引き起こした"), "src"],
  ["E21", "仮説・主張の因果断定", (s) => s.replace("小型の帰り荷不足が実車率低下の説明と最も整合する", "小型の帰り荷不足が実車率低下の原因である"), "src"],
  ["E21", "背景の説明仮説の因果断定", (s) => s.replace("給油単価の上昇と支出増が同時に観測され、使用量は前年並み", "補助金の縮小により給油単価が増加した"), "src"],
  ["E21", "因果断定と別文の留保の矛盾", (s) => s.replace("小型の帰り荷不足が実車率低下の説明と最も整合する", "小型の帰り荷不足が原因である。因果は未確認"), "src"],
  ["E21", "仮説・主張の「生んだ」断定", (s) => s.replace("小型の帰り荷不足が実車率低下の説明と最も整合する", "小型の帰り荷不足が実車率低下を生んだ"), "src"],
  ["E21", "背景の説明仮説の「招いた」断定", (s) => s.replace("給油単価の上昇と支出増が同時に観測され、使用量は前年並み", "補助金の縮小が給油単価の上昇を招いた"), "src"],
  ["E08", "データと計算の開閉が無い", (s) => s.replace(/<details class="disclosure">[\s\S]*?<\/details>/, ""), "src"],
  ["E08", "打ち手の効果に数字が無い", (s) => s.replace("<dd>空車 42→20便/月で +80万円/月</dd>", "<dd>空車が減る</dd>"), "src"],
  ["E08", "打ち手の担当が空", (s) => s.replace("<dd>配車</dd>", "<dd></dd>"), "src"],
  ["E08", "未確定なのに出所が data", (s) => s.replace("<dd>2026年11月の配車から</dd>", "<dd>要確認</dd>"), "src"],
  ["E08", "打ち手が6件", (s) => s.replace(/(<li class="act" data-from="1"[\s\S]*?<\/li>)/, "$1$1$1$1"), "src"],
  ["E16", "要因が影響の大きい順でない", (s) => s.replace(beforeAction, factor("-200") + "\n" + beforeAction), "src"],
  ["E16", "前提ストリップが4個", (s) => s.replace(/(<div class="kpi">[\s\S]*?<\/div><\/div>)/, "$1$1"), "src"],
  ["E16", "主数字が無い", (s) => s.replace(/<div class="hero-number">[\s\S]*?<\/div>\s*<\/div>\s*(?=<div class="kpi-strip">)/, ""), "src"],
  ["E09", "主操作を手書きで追加", (s) => s.replace("<footer>", '<footer><a class="btn btn-primary" href="#main">上へ</a>'), "src"],
  ["E10", "SVGの色の直書き", (s) => s.replace('class="c-main" data-tip="大型', 'fill="#1d63be" data-tip="大型'), "src"],
  ["E10", "左端の色帯", (s) => s.replace('<ol class="actions">', '<ol class="actions" style="border-left:3px solid var(--link)">'), "src"],
  ["E11", "図がカードでない", (s) => s.replace('<figure class="card card-pad">', "<figure>"), "src"],
  ["E11", "チャートの aria-label 欠落", (s) => s.replace(/ aria-label="車種別[^"]*"/, ""), "src"],
  ["E12", "数値セルの左揃え", (s) => s.replace('<td class="col-num">40</td>', "<td>40</td>"), "src"],
  ["E13", "footer の欠落", (s) => s.replace(/<footer>[\s\S]*<\/footer>/, ""), "src"],
  ["E14", "絵文字", (s) => s.replace("<li>全体 ", "<li>\u{1F680}全体 "), "src"],
  ["E17", "旧部品 (.pill)", (s) => s.replace("<li>全体 ", '<li><span class="pill bad">悪化</span>全体 '), "src"],
  ["E17", "旧部品 (td.r)", (s) => s.replace('<td class="col-num">40</td>', '<td class="r">40</td>'), "src"],
  ["E02", "外部参照", (s) => s.replace("<footer>", '<footer><img src="https://example.com/a.png" alt="">'), "src"],
  // 配色の値を書き換える変異は「埋め込みCSSの手直し」と同じ経路 (embeddedCss 不一致) で捕まるので置かない。
  // vendor 自体の改変は SOURCE.json との照合 (冒頭の verifyVendor) が別経路で見ている
  ["E03", "埋め込みCSSの手直し", (h) => h.replace("--toc-width:240px", "--toc-width:200px"), "out"],
  ["E03", "キット部品CSSの手直し", (h) => h.replace("--radius-glass: 22px", "--radius-glass: 8px"), "out"],
  ["E04", "埋め込みJSの手直し", (h) => h.replace('"use strict";', ""), "out"],
  ["E05", "目次のリンク切れ", (h) => h.replace('href="#sec-2" data-label', 'href="#nowhere" data-label'), "out"],
  ["E05", "打ち手の根拠ボタンのリンク切れ", (h) => h.replace('class="btn btn-tertiary" href="#sec-2"', 'class="btn btn-tertiary" href="#nowhere"'), "out"],
  ["E07", "番号チップの欠落", (h) => h.replace('<span class="secno">要因 1</span>', ""), "out"],
  ["E07", "見出し帯の欠落", (h) => h.replace(/<div class="sec-head">(<span class="secno">要因 1<\/span><h2>[\s\S]*?<\/h2>)<\/div>/, "$1"), "out"],
  ["E07", "見出し帯がセクションの先頭にない", (h) => h.replace('<div class="sec-head"><span class="secno">要因 1</span>', '<p>前置き</p><div class="sec-head"><span class="secno">要因 1</span>'), "out"],
  ["E05", "目次の種類がセクションと不一致", (h) => h.replace('<li data-kind="action">', '<li data-kind="factor">'), "out"],
  ["E07", "題名が page-title でない", (s) => s.replace('<h1 class="page-title">', "<h1>"), "src"],
  // 説明の仕掛け (E22): 図の読み方と用語集は「閉じて置き、押したら出る」形でだけ通す
  ["E22", "図の読み方が無い", (s) => s.replace(/\s*<details class="howto">[\s\S]*?<\/details>/, ""), "src"],
  ["E22", "図の読み方が開いたまま", (h) => h.replace('<details class="howto">', '<details class="howto" open>'), "out"],
  ["E22", "図の読み方の説明が空", (h) => h.replace(/<details class="howto">\s*<summary>この図の読み方<\/summary>\s*<p>[^<]*<\/p>/, '<details class="howto">\n    <summary>この図の読み方</summary>\n    <p></p>'), "out"],
  ["E22", "用語集が無いのに本文に用語マーク", (h) => h.replace(/<aside class="glossary card card-pad">[\s\S]*?<\/aside>/, ""), "out"],
  ["E22", "用語マークのリンク切れ", (h) => h.replace('class="term" href="#gl-median"', 'class="term" href="#gl-nowhere"'), "out"],
  ["E22", "本文で使わない用語が用語集にある", (h) => h.replace('<dt id="gl-median">', '<dt id="gl-unused">つかわない</dt><dd><span>説明</span></dd>\n<dt id="gl-median">'), "out"],
  ["E22", "用語集が常時表示", (h) => h.replace("<summary>用語の説明", "<div>用語の説明"), "out"],
  ["E22", "用語マークに ? の印が無い", (h) => h.replace(/(<a class="term" href="#gl-median"[^>]*>[^<]*)<span class="term-q" aria-hidden="true">\?<\/span>/, "$1"), "out"],
];
// n が少なければ、エラーにせず警告 (W05) で断定を避けさせる
{
  const small = checkReport(buildReport(src.replace('<div class="kpi-label">n</div><div class="kpi-value num">48台</div>', '<div class="kpi-label">n</div><div class="kpi-value num">6台</div>')));
  ok(small.errors.length === 0 && small.warnings.some((w) => w.startsWith("W05")), `n が少ないのに W05 にならない (${[...small.errors, ...small.warnings].join(" / ")})`);
}
// 根拠が図の数字の言い換えなら、警告 (W08) で図に無い比較・理由に替えさせる
{
  const base = checkReport(buildReport(src));
  ok(!base.warnings.some((w) => w.startsWith("W08")), `図に無い数字の根拠を W08 にした (${base.warnings.join(" / ")})`);
  const echo = checkReport(buildReport(src.replace('<li>全体 <b class="num">67%</b> は前年 <b class="num">71%</b> から <b class="num loss">▲4pt</b></li>', '<li>大型 <b class="num">72%</b>、中型 <b class="num">68%</b></li>')));
  ok(echo.errors.length === 0 && echo.warnings.some((w) => w.startsWith("W08")), `図の値を並べただけの根拠が W08 にならない (${[...echo.errors, ...echo.warnings].join(" / ")})`);
}

// 6. 統計の既知値 (scipy.stats / Excel と照合済み)
{
  const near = (x, y, tol = 1e-3) => Math.abs(x - y) <= tol;
  const d = st.describe([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  ok(near(d.q1, 3.25) && near(d.median, 5.5) && near(d.sd, 3.0277), `describe が既知値と違う (${JSON.stringify(d)})`);
  ok(near(st.tCritical(10), 2.2281) && near(st.tCritical(30), 2.0423), "tCritical が t 分布表と違う");
  ok(near(st.tTwoSided(2, 20), 0.0593), "t 分布の p 値が既知値と違う");
  // scipy.stats.ttest_ind(a, b, equal_var=False) → t=-2.07401, p=0.06428, df=10.20919
  const w = st.welch([19.8, 20.4, 19.6, 17.8, 18.5, 18.9, 18.3, 18.9, 19.5, 22.0], [28.2, 26.6, 20.1, 23.3, 25.2, 22.1, 17.7, 27.6, 20.6, 13.7]);
  ok(near(w.t, -2.07401) && near(w.p, 0.06428) && near(w.df, 10.20919), `welch が scipy と違う (t=${w.t} p=${w.p} df=${w.df})`);
  // scipy.stats.mannwhitneyu(method="asymptotic") → U=10.5, p=0.015885 (同順位あり)
  const mw = st.mannWhitney([1, 2, 3, 4, 5, 6, 7, 8], [3, 5, 7, 9, 11, 12, 13, 15, 15]);
  ok(mw.u === 10.5 && near(mw.p, 0.015885, 1e-6) && near(mw.r, -0.70833), `mannWhitney が scipy と違う (${JSON.stringify(mw)})`);
  ok([0.0999, 0.1, 0.2999, 0.3, 0.4999, 0.5, -0.5].map(st.rankEffectLabel).join() === "ほぼ無し,小,小,中,中,大,大", "rankEffectLabel の 0.1 / 0.3 / 0.5 境界が不正");
  ok([0.1999, 0.2, 0.3999, 0.4, 0.6999, 0.7, -0.7].map(st.corrLabel).join() === "ほぼ無い,弱い,弱い,中程度の,中程度の,強い,強い", "corrLabel の Pearson 用境界が不正");
  // scipy.stats.chi2_contingency(correction=False) → 2x2: χ²=2.82857 p=0.092601 V=0.160357 / 2x3: χ²=12.52778 p=0.0019038 V=0.337474
  const c2 = st.chisq([[20, 15], [30, 45]]), c3 = st.chisq([[10, 20, 30], [20, 20, 10]]);
  ok(near(c2.chi2, 2.82857) && near(c2.p, 0.092601, 1e-6) && near(c2.v, 0.160357, 1e-6) && c2.df === 1, `chisq (2x2) が scipy と違う (${JSON.stringify(c2)})`);
  ok(near(c3.chi2, 12.52778) && near(c3.p, 0.0019038, 1e-7) && near(c3.v, 0.337474, 1e-6) && c3.df === 2, `chisq (2x3) が scipy と違う (${JSON.stringify(c3)})`);
  ok(st.chisq([[1, 2], [2, 1]]).lowExpected, "chisq が期待度数の不足を知らせない");
  ok(st.holm([0.01, 0.04, 0.03, 0.2]).every((p, i) => near(p, [0.04, 0.09, 0.09, 0.2][i], 1e-12)), "holm の調整 p 値が違う");
  ok(near(st.pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1) && near(st.spearman([1, 2, 3, 4], [1, 4, 9, 16]), 1), "相関係数が既知値と違う");
  const ci = st.rateCI(5, 10);
  ok(near(ci.lower, 0.2366) && near(ci.upper, 0.7634), "Wilson の信頼区間が既知値と違う");
  ok(st.pareto([{ v: 50 }, { v: 30 }, { v: 15 }, { v: 5 }], "v").map((r) => r.rank).join("") === "AABC", "パレートの ABC 区分が違う");

  // 公開関数の定義域外は NaN を返さず明示的に拒否し、全ゼロだけは「集中なし」として有限値を返す。
  const throws = (make) => { try { make(); return false; } catch { return true; } };
  const zeroPareto = st.pareto([{ v: 0 }, { v: 0 }], "v");
  ok(zeroPareto.every((row) => row.share === 0 && row.cum === 0 && row.rank === "C"), `全ゼロ pareto が有限の「集中なし」にならない (${JSON.stringify(zeroPareto)})`);
  ok(throws(() => st.pareto([{ v: -1 }, { v: 2 }], "v")), "pareto が負値を受け付けた");
  ok(throws(() => st.pearson([1, 2, 3], [1, 2, 3, 4])) && throws(() => st.linreg([1, 2, 3], [1, 2])), "対応する配列の長さ不一致を受け付けた");
  ok(throws(() => st.pearson([1, 2, Infinity], [1, 2, 3])), "相関が非有限値を受け付けた");
  ok(throws(() => st.pearson([1, 1, 1], [1, 2, 3])) && throws(() => st.pearson([1, 2, 3], [4, 4, 4])), "pearson が定数列の未定義な相関を受け付けた");
  ok(throws(() => st.linreg([1, 1, 1], [1, 2, 3])) && throws(() => st.linreg([1, 2, 3], [4, 4, 4])), "linreg が定数列の未定義な回帰を受け付けた");
  ok(throws(() => st.welch([1, 1, 1], [1, 1, 1])) && throws(() => st.welch([1, 1, 1], [2, 2, 2])), "welch が分散ゼロの未定義な比較を受け付けた");
  const oneConstantA = st.welch([4, 4, 4], [1, 2, 3]), oneConstantB = st.welch([1, 2, 3], [4, 4, 4]);
  ok(
    [oneConstantA, oneConstantB].every((result) => ["t", "df", "p", "d", "lower", "upper"].every((key) => Number.isFinite(result[key])))
      && near(oneConstantA.df, 2) && near(oneConstantA.t, Math.sqrt(12)) && near(oneConstantB.t, -Math.sqrt(12)),
    `welch が片群だけ定数の定義可能な比較を返せない (${JSON.stringify({ oneConstantA, oneConstantB })})`,
  );
  const constantCi = st.meanCI([5, 5, 5]);
  ok(constantCi.mean === 5 && constantCi.lower === 5 && constantCi.upper === 5, `meanCI が定数列の区間を返せない (${JSON.stringify(constantCi)})`);
  ok(throws(() => st.chisq([[0, 0], [1, 2]])) && throws(() => st.chisq([[0, 0], [0, 0]])), "chisq が合計0の行・表を受け付けた");
  ok(throws(() => st.rateCI(2, 1)) && throws(() => st.rateCI(0, 0)) && throws(() => st.rateCI(0.5, 1)), "rateCI が二項度数の定義域外を受け付けた");
  const largeDescribe = st.describe(Array.from({ length: 200_000 }, (_, i) => i));
  ok(largeDescribe.min === 0 && largeDescribe.max === 199_999, "describe が大規模配列の min/max を単一走査できない");
}

// 6b. 差の分解: どれも「要因の合計 = 結論の差」になること (要因ランキングの数字が結論と食い違わない)
{
  const near = (x, y) => Math.abs(x - y) < 1e-9 * Math.max(1, Math.abs(y));
  const b = st.bridge([{ label: "売上", base: 1000, cur: 1062 }, { label: "修繕費", base: 100, cur: 185, sign: -1 }, { label: "燃料費", base: 200, cur: 219, sign: -1 }]);
  ok(b.delta === -42 && near(b.steps.reduce((t, x) => t + x.value, 0), b.delta) && b.steps[1].value === -85, `bridge の合計が差と一致しない (${JSON.stringify(b)})`);
  const dt = st.driverTree({ 台数: 20, 稼働日: 22, 日車売上: 5 }, { 台数: 21, 稼働日: 20, 日車売上: 5.5 });
  ok(near(dt.steps.reduce((t, x) => t + x.value, 0), dt.delta) && dt.steps[1].value < 0, `driverTree の寄与の合計が差と一致しない (${JSON.stringify(dt)})`);
  const same = st.driverTree({ a: 2, b: 3 }, { a: 2, b: 3 });
  ok(same.delta === 0 && same.steps.every((x) => x.value === 0), "driverTree で変化なしのとき寄与が0にならない");
  let threw = false;
  try { st.driverTree({ a: 0 }, { a: 1 }); } catch { threw = true; }
  ok(threw, "driverTree が0 (対数を取れない) を受け付けた");
}

// 7. analysis.mjs の経路: charts + compose で組んだソースが一発で合格する
{
  const vals = [52, 58, 61, 63, 64, 66, 66, 67, 68, 69, 70, 71, 72, 74, 75, 77, 79, 81, 88, 30];
  const d = st.describe(vals);
  const pa = st.pareto(vals.map((v, i) => ({ id: `車${i + 1}`, v })), "v");
  const f1 = composeFactor({
    causes: [{ text: "月末に大型の案件が集中した", level: "データで確認" }, { text: "軽油価格が上がった", level: "公表資料", source: { title: "価格調査", url: "https://example.go.jp/a" } }, { text: "運転手の配置が偏ったと考えられる", level: "想定" }],
    toc: "分布", impact: -100, hypotheses: ["H1"], h2: "実車率のばらつきが大きく、下位が全体を押し下げている", meaning: "下位の車の案件を入れ替えない限り、平均は目標に届かない",
    interpretation: "下位車両の低さが全体平均を押し下げている", claim: { id: "H1", text: "下位車両への案件配分が偏っている", verdict: "採用" },
    figures: [
      figure({ title: "実車率の分布", legend: "赤=目標未満", svg: histogram({ values: vals, bins: [20, 40, 60, 80, 100], unit: "%", aria: "実車率の分布。60〜80%に集中", highlight: (lo) => lo < 60 }) }),
      figure({ title: "車種別の箱ひげ", legend: "赤丸=外れ値", svg: boxplot({ groups: [{ label: "小型", values: vals.slice(0, 10) }, { label: "大型", values: vals.slice(10) }], unit: "%", aria: "箱ひげ", threshold: { value: 75, label: "目標 75%" } }) }),
    ],
    table: table({ columns: [{ label: "指標" }, { label: "値", num: true, digits: 1 }], rows: [["平均", d.mean], ["中央値", d.median]] }),
    stats: [{ label: "n", value: `${d.n}台` }, { label: "中央値", value: `${d.median}%`, sub: "半数の車両はこの値以下" }, { label: "標準偏差", value: `${d.sd.toFixed(1)}pt`, sub: "車両ごとの差は平均から約9pt" }],
    facts: [`中央値 ${num(d.median + "%")}、前月 ${num("71%")}`, `最低 ${num(d.min + "%", { loss: true })}`], data: "運行日報.csv", calc: "実車距離 ÷ 総走行距離",
  });
  const f2 = composeFactor({
    toc: "関係", impact: -50, hypotheses: ["H3"], h2: "走行距離が長い車ほど実車率も高い傾向がある", meaning: "長距離の運用を増やす判断の材料になるが、因果は未確認",
    interpretation: "距離と実車率には弱い関連があるが因果は未確認", claim: { id: "H3", text: "長距離運用ほど実車率が高い", verdict: "採用" },
    figures: [
      figure({ title: "距離と実車率", legend: "破線=回帰直線", svg: scatter({ points: vals.map((v, i) => ({ x: 1000 + i * 50, y: v, label: `車${i + 1}` })), xLabel: "距離", yLabel: "実車率", aria: "散布図" }) }),
      figure({ title: "パレート図", legend: "赤=A区分", svg: paretoChart({ rows: pa, labelOf: (r) => r.id, valueOf: (r) => r.v, unit: "%", aria: "パレート図", top: 8 }) }),
      figure({ title: "上位", legend: "横棒", svg: hbar({ items: [{ label: "a", value: 3 }, { label: "b", value: 1 }], aria: "横棒" }) }),
    ],
    stats: [{ label: "n", value: "20台" }, { label: "相関", value: "r=0.30", sub: "一緒に動く傾向。原因とは限らない" }],
    facts: [`相関 ${num("0.30")}`, `R² ${num("0.09")}`], data: "運行日報.csv", calc: "ピアソンの相関",
  });
  const composed = source({
    title: "合成テスト",
    parts: [
      header({ crumb: "サンプル運送｜テスト", title: "合成テスト", target: "20台・1ヶ月", created: "2026-05-31" }),
      conclusion({ h2: "実車率は目標を5pt下回る", unit: "万円/月", hero: { label: "目標差", value: "▲5", unit: "pt" }, kpis: [{ label: "台数", value: "20", unit: "台" }], overview: { comparison: "20台を目標75%と比較", finding: "実車率は目標を5pt下回った", interpretation: "下位車両が全体を押し下げている", limitation: "案件配分が原因かは追加確認が必要" }, caution: "給油量が欠損している" }),
      f1, f2,
      actions({ h2: "2つの打ち手で差を縮める", items: [{ title: "下位の車に案件を寄せる", from: "1,2", source: "pending", effect: "+3pt", owner: "要確認", due: "要確認" }, { title: "距離の長い車の運用を広げる", from: "関係", source: "pending", effect: "+1pt", owner: "要確認", due: "要確認" }] }),
      footer({ crumb: "サンプル運送｜テスト", data: "運行日報.csv（2026年5月）" }),
    ],
  });
  let r;
  try { r = checkReport(buildReport(composed)); } catch (e) { r = { errors: [`ビルド例外: ${e.message}`], warnings: [] }; }
  ok(r.errors.length === 0, `charts + compose で組んだソースが不合格: ${r.errors.join(" / ")}`);
  ok(r.warnings.every((w) => w.startsWith("W04")), `charts + compose で組んだソースに想定外の警告: ${r.warnings.join(" / ")}`);
  // 打ち手の根拠は要因の名前 (data-toc) でも指せ、ビルドが番号に直す (要因の並びがデータで変わっても壊れない)
  let built = "";
  try { built = buildReport(composed); } catch {}
  ok(/data-from="2"[\s\S]*?href="#[^"]+">要因 2 の根拠を見る/.test(built), "data-from の要因名 (関係) が要因 2 に変換されない");
  let threw = false;
  try { composeFactor({ toc: "x", impact: -1, hypotheses: ["H1"], h2: "x", meaning: "m", interpretation: "i", claim: { id: "H1", text: "c", verdict: "採用" }, figures: ["<figure></figure>"], stats: [{ label: "中央値", value: "1" }], facts: ["a"], data: "d", calc: "c" }); } catch { threw = true; }
  ok(threw, "compose.factor が n の無い統計の要約を受け付けた");
  const base = { toc: "x", impact: -1, hypotheses: ["H1"], h2: "x", meaning: "m", interpretation: "i", claim: { id: "H1", text: "c", verdict: "採用" }, figures: ["<figure></figure>"], stats: [{ label: "n", value: "1" }], facts: ["a"], data: "d", calc: "c" };
  let noMeaning = false; try { const { meaning, ...rest } = base; composeFactor(rest); } catch { noMeaning = true; }
  ok(noMeaning, "compose.factor が判断への意味 (meaning) の無い要因を受け付けた");
  let noHypotheses = false; try { const { hypotheses, ...rest } = base; composeFactor(rest); } catch { noHypotheses = true; }
  ok(noHypotheses, "compose.factor が仮説 ID の無い claim を受け付けた");
  let noInterpretation = false; try { const { interpretation, ...rest } = base; composeFactor(rest); } catch { noInterpretation = true; }
  ok(noInterpretation, "compose.factor が解釈の無い要因を受け付けた");
  let noClaim = false; try { const { claim, ...rest } = base; composeFactor(rest); } catch { noClaim = true; }
  ok(noClaim, "compose.factor が仮説 ID のあるのに claim の無い要因を受け付けた");
  const { hypotheses: _hypotheses, claim: _claim, ...descriptiveBase } = base;
  let descriptiveFactor = "";
  try { descriptiveFactor = composeFactor(descriptiveBase); } catch {}
  ok(descriptiveFactor.includes('data-kind="factor"') && !descriptiveFactor.includes("data-hypotheses") && !descriptiveFactor.includes("statement claim"), "compose.factor が仮説・claim無しの記述要因を作れない");
  const shortestSource = composed
    .replace(/\s*<section data-kind="action"[\s\S]*?<\/section>/, "")
    .replace(/ data-hypotheses="[^"]*"/g, "")
    .replace(/\s*<div class="statement claim"[\s\S]*?<\/div>/g, "");
  let shortestReport;
  try { shortestReport = checkReport(buildReport(shortestSource)); } catch (e) { shortestReport = { errors: [e.message], warnings: [] }; }
  ok(shortestReport.errors.length === 0, `仮説・claim・打ち手無しの最短レポートが不合格 (${shortestReport.errors.join(" / ")})`);
  let noOverview = false;
  try { conclusion({ h2: "差は5pt", unit: "pt", hero: { label: "差", value: "5" }, kpis: [{ label: "n", value: "20" }] }); } catch { noOverview = true; }
  ok(noOverview, "compose.conclusion が初心者向け概要の無い結論を受け付けた");
  for (const [name, causes] of [["出典の無い公表資料", [{ text: "a", level: "公表資料" }]], ["許可外の根拠の強さ", [{ text: "a", level: "推測" }]], ["5項目のなぜ起きたか", Array(5).fill({ text: "a", level: "想定" })]]) {
    let t = false; try { composeFactor({ ...base, causes }); } catch { t = true; }
    ok(t, `compose.factor が${name}を受け付けた`);
  }
}

// 情報量の統計上限と解釈字数は、生成から最終検査まで同じ契約で扱う。
{
  const baseFactor = { toc: "比較", impact: 1, h2: "比較値は1だけ異なる", figures: [figure({ title: "比較", svg: hbar({ items: [{ label: "比較値", value: 1 }], aria: "値は1" }) })], facts: ["件数は12", "差は1"], interpretation: "比較の違いを示す", meaning: "次も比較を続ける", data: "入力.csv", calc: "比較値の差" };
  const reportSource = (detail, stats) => source({ title: "情報量の検査", parts: [
    header({ crumb: "検査", title: "情報量の検査", target: "12件", created: "2026-09-28", detail }),
    conclusion({ h2: "比較値は1だけ異なる", unit: "値", hero: { label: "差", value: "1" }, kpis: [{ label: "n", value: "12" }], overview: { comparison: "12件を比較", finding: "差は1", interpretation: "違いを示す", limitation: "原因は未確認" } }),
    composeFactor({ ...baseFactor, stats }), footer({ crumb: "検査", data: "入力.csv" }),
  ] });
  const stats = (n) => Array.from({ length: n }, (_, i) => ({ label: i ? `値${i}` : "n", value: "12" }));
  for (const [detail, contract] of Object.entries(REPORT_DETAILS)) {
    ok(checkReport(buildReport(reportSource(detail, stats(contract.statsMax)))).errors.length === 0, `${detail}の統計上限${contract.statsMax}件を生成・検査できない`);
    for (const n of [contract.statsMin - 1, contract.statsMax + 1]) {
      let rejected = false;
      try { rejected = checkReport(buildReport(reportSource(detail, stats(n)))).errors.some((e) => e.startsWith("E19")); } catch { rejected = true; }
      ok(rejected, `${detail}の統計件数${n}を拒否できない`);
    }
  }
  for (const value of [1e-7, -1e-7, 1e21, Number.MIN_VALUE, -Number.MIN_VALUE]) {
    const valid = reportSource("標準", stats(2)).replace('data-impact="1"', `data-impact="${serializeImpact(value)}"`);
    ok(checkReport(buildReport(valid)).errors.length === 0, `指数表記になるimpact ${value}を生成・検査できない`);
  }
  let rejected = false;
  try { composeFactor({ ...baseFactor, stats: stats(2), interpretation: "あ".repeat(LIMITS.interpretation + 1) }); } catch { rejected = true; }
  ok(rejected, "composeの解釈字数上限が共有契約に従わない");
  for (const [field, limit] of [["interpretation", LIMITS.interpretation], ["meaning", LIMITS.line]]) {
    const change = (n) => buildReport(reportSource("標準", stats(2))).replace(field === "interpretation" ? /(<div class="statement interpretation">[\s\S]*?<span class="statement-text">)[\s\S]*?(<\/span><\/div>)/ : /(<span class="meaning-text">)[\s\S]*?(<\/span>)/, `$1${"あ".repeat(n)}$2`);
    ok(!checkReport(change(limit)).errors.some((e) => e.startsWith("E15")) && checkReport(change(limit + 1)).errors.some((e) => e.startsWith("E15")), `${field}の表示字数境界を最終検査できない`);
  }
}

// 8. 出力先の規則と雛形
{
  const lw = (p) => layoutWarnings(p).map((w) => w.slice(0, 3)).join();
  ok(layoutWarnings("/x/2026-05-kuusha/2026-05-kuusha.src.html").length === 1, "規則どおりの名前なのに名前の警告が出る (analysis.mjs 不在の1件だけのはず)");
  ok(lw("/x/tpl.src.html") === "W06,W06", "規則外のファイル名を W06 にできない");
  ok(layoutWarnings("/x/other/2026-05-kuusha.src.html").length === 2, "フォルダ名の食い違いを W06 にできない");
  const tmp = mkdtempSync(join(tmpdir(), "rds-"));
  try {
    const gen = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/new-report.mjs"), tmp, "2026-05", "kuusha"], { encoding: "utf8" });
    ok(gen.status === 0, `new-report.mjs が失敗: ${gen.stderr}`);
    const scaffoldSource = readFileSync(join(tmp, "2026-05-kuusha/analysis.mjs"), "utf8");
    const scaffoldBrief = JSON.parse(readFileSync(join(tmp, "2026-05-kuusha/brief.json"), "utf8"));
    ok(!/REPORT_LABEL\s*=\s*["']サンプル運送/.test(scaffoldSource) && scaffoldSource.includes("TODO 組織名"), "雛形の表示ラベルに固定の組織名が残っている");
    ok(scaffoldSource.includes('hypotheses: ["H1"]'), "雛形の factor 例に仮説 trace がない");
    ok(scaffoldSource.includes("hypothesisClaim(BRIEF, RESULTS") && scaffoldSource.includes("interpretation:"), "雛形に仮説・主張と解釈の入力欄がない");
    ok(scaffoldSource.includes("acts.length ? [actions(") && scaffoldSource.includes(": []),"), "雛形が打ち手0件で action セクションを省略できない");
    ok(scaffoldSource.includes("overview:") && scaffoldSource.includes("limitation:"), "雛形に初心者向け概要の入力欄がない");
    ok(scaffoldSource.includes("rankEffectLabel") && scaffoldSource.includes("mergeBackgroundFiles"), "雛形が順位効果量と背景CSV統合の共通関数を使っていない");
    ok(scaffoldSource.includes("結果 → 中間 → 原因") && scaffoldSource.includes("原因 → 中間 → 結果") && scaffoldSource.includes('solid: "identity"'), "雛形に原因の探索/表示方向と flow の実線条件がない");
    ok(scaffoldBrief.plan.情報量 === "標準", "brief.json の情報量の初期値が標準ではない");
    ok(scaffoldBrief.plan.背景分析 === false, "brief.json の背景分析が既定で無効になっていない");
    ok(scaffoldSource.includes("fileURLToPath(import.meta.url)"), "雛形が file URL を標準変換せず pathname として扱っている");
    const chk = spawnSync(process.execPath, ["--check", join(tmp, "2026-05-kuusha/analysis.mjs")], { encoding: "utf8" });
    ok(chk.status === 0, `雛形の analysis.mjs が構文エラー: ${chk.stderr}`);
    const run = spawnSync(process.execPath, [join(tmp, "2026-05-kuusha/analysis.mjs")], { encoding: "utf8" });
    ok(run.status !== 0 && run.stderr.includes("profile.json がありません"), `profile.json 無しで雛形の analysis.mjs が止まらない (${run.stderr.slice(0, 200)})`);
    const again = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/new-report.mjs"), tmp, "2026-05", "kuusha"], { encoding: "utf8" });
    ok(again.status === 2, "既存フォルダを上書きしようとした");
    const bad = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/new-report.mjs"), tmp, "2026-5", "Kuusha"], { encoding: "utf8" });
    ok(bad.status === 2, "規則外の名前を受け付けた");
    // init は異種 schema を profile で先に止め、中途な完成名フォルダを残さない。
    const dataA = join(tmp, "a.csv"), dataB = join(tmp, "b.csv");
    writeFileSync(dataA, "年月,車両\n2026-06,A\n");
    writeFileSync(dataB, "年月,売上\n2026-06,100\n");
    const init = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/report.mjs"), "init", tmp, "2026-06", "mixed", dataA, dataB], { encoding: "utf8" });
    ok(init.status !== 0 && !existsSync(join(tmp, "2026-06-mixed")), "異種 schema の init 失敗後に完成名フォルダが残った");
    // 日本語・空白を含む出力先でも、init 済みの profile / manifest / brief を実パスで読める。
    const unicodeRoot = join(tmp, "日本語 レポート"), unicodeData = join(tmp, "入力 データ.csv");
    writeFileSync(unicodeData, "年月,車両,売上\n2026-06,A,100\n2026-06,B,120\n");
    const unicodeInit = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/report.mjs"), "init", unicodeRoot, "2026-06", "unicode", unicodeData], { encoding: "utf8" });
    const unicodeDir = join(unicodeRoot, "2026-06-unicode");
    ok(unicodeInit.status === 0, `非ASCIIパスの init が失敗: ${unicodeInit.stderr}`);
    const manifest = JSON.parse(readFileSync(join(unicodeDir, INPUT_MANIFEST_FILE), "utf8"));
    ok(manifest.files?.[0]?.path === unicodeData && manifest.files?.[0]?.sha256 === sha256(readFileSync(unicodeData)), "init の入力manifestが受領済みパスとhashを保持しない");
    const unicodeRun = spawnSync(process.execPath, [join(unicodeDir, "analysis.mjs")], { encoding: "utf8" });
    ok(unicodeRun.status !== 0 && unicodeRun.stderr.includes("brief.json が検査に通りません") && !unicodeRun.stderr.includes("brief.json がありません"), `非ASCIIパスの雛形が同階層ファイルを読めない (${unicodeRun.stderr.slice(0, 240)})`);
    // 検査不合格では既存の最終HTMLを上書きしない。
    const invalidSource = join(tmp, "invalid.src.html"), previousOutput = join(tmp, "invalid.html");
    writeFileSync(invalidSource, src.replace("<footer>", '<a href="https://example.com">外部</a><footer>'));
    writeFileSync(previousOutput, "previous-valid\n");
    const invalidBuild = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/build-report.mjs"), invalidSource, previousOutput], { encoding: "utf8" });
    ok(invalidBuild.status === 1 && readFileSync(previousOutput, "utf8") === "previous-valid\n", "検査不合格のHTMLが最終パスへ公開された");
    // 見本を出力先なしでビルドしても、スキルの中に成果物を書かない
    const inSkill = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/build-report.mjs"), join(SKILL_DIR, "assets/template.src.html")], { encoding: "utf8" });
    ok(inSkill.status === 2 && !existsSync(join(SKILL_DIR, "assets/template.html")), "スキルのフォルダの中へ出力した");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

// initが許可したCSV/JSON/D1 JSONを、生成されたanalysisのreaderで同じ行として読む。
{
  const tmp = mkdtempSync(join(tmpdir(), "rds-inputs-"));
  const expected = [{ 値: "1" }, { 値: "2" }];
  const formats = [
    ["csv", "csv", "値\n1\n2\n"],
    ["json", "json", JSON.stringify([{ 値: 1 }, { 値: 2 }])],
    ["d1", "json", JSON.stringify([{ results: [{ 値: 1 }, { 値: 2 }], success: true }])],
    ["d1-object", "json", JSON.stringify({ results: [{ 値: 1 }, { 値: 2 }] })],
    ["d1-empty", "json", JSON.stringify([{ results: [], success: true }])],
  ];
  try {
    for (const [slug, ext, content] of formats) {
      const data = join(tmp, `${slug}.${ext}`), dir = join(tmp, `2026-09-${slug}`);
      writeFileSync(data, content);
      const init = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/report.mjs"), "init", tmp, "2026-09", slug, data], { encoding: "utf8" });
      ok(init.status === 0, `${slug}のinitが失敗 (${init.stderr})`);
      if (init.status !== 0) continue;
      const briefFile = join(dir, "brief.json"), brief = JSON.parse(readFileSync(briefFile, "utf8"));
      Object.assign(brief.plan, { 問い: "値の分布を確認する", 読み手: "担当者", 判断: "次に確認する値を決める", 指標: "値", 単位: "件", 基準: "なし", 範囲: "2026-09" });
      writeFileSync(briefFile, JSON.stringify(brief));
      const analysisFile = join(dir, "analysis.mjs"), generated = readFileSync(analysisFile, "utf8");
      writeFileSync(analysisFile, generated.split("// ---- 2. 計算:")[0] + '\nconsole.log(JSON.stringify(rows));\n');
      const run = spawnSync(process.execPath, [analysisFile], { encoding: "utf8" });
      const expectedRows = slug === "d1-empty" ? [] : expected;
      ok(run.status === 0 && run.stdout.trim() === JSON.stringify(expectedRows), `${slug}を雛形readerが同じ行配列にできない (${run.stderr || run.stdout})`);
      ok(JSON.stringify(readInputRows(dir)) === JSON.stringify(expectedRows) && readInputManifest(dir).files[0].path === data, `${slug}の共有入力readerとmanifestが一致しない`);
      writeFileSync(data, content + " ");
      const changed = spawnSync(process.execPath, [analysisFile], { encoding: "utf8" });
      ok(changed.status !== 0 && changed.stderr.includes("init 後に変更"), `${slug}の雛形readerが生入力の変更を見逃した`);
      writeFileSync(data, content);
    }
    const data = join(tmp, "csv.csv"), dir = join(tmp, "2026-09-csv"), manifestFile = join(dir, INPUT_MANIFEST_FILE);
    const manifest = writeInputManifest(dir, [data]);
    ok(JSON.stringify(readInputManifest(dir)) === JSON.stringify(inputManifest([data])) && manifest.files.length === 1, "既存report用のmanifest保存・共有検証が往復できない");
    const malformed = [
      { ...manifest, version: 999 },
      { ...manifest, files: [] },
      { ...manifest, files: [manifest.files[0], manifest.files[0]] },
      { ...manifest, files: [{ ...manifest.files[0], path: "relative.csv" }] },
      { ...manifest, files: [{ ...manifest.files[0], sha256: "bad" }] },
    ];
    for (const bad of malformed) {
      writeFileSync(manifestFile, JSON.stringify(bad));
      let rejected = false; try { readInputManifest(dir); } catch { rejected = true; }
      ok(rejected, "不正なmanifestを共有readerが受理した");
    }
    writeInputManifest(dir, [data]);
    let duplicate = false; try { inputManifest([data, data]); } catch { duplicate = true; }
    ok(duplicate, "manifest作成時に入力の重複を受理した");
    const invalidJson = join(tmp, "invalid.json"); writeFileSync(invalidJson, "[null]");
    let invalid = false; try { readRows(invalidJson); } catch { invalid = true; }
    ok(invalid, "JSONの非オブジェクト行を受理した");
    for (const [slug, wrappers] of [
      ["d1-multiple", [{ results: [{ 値: 1 }] }, { results: [{ 値: 2 }] }]],
      ["d1-heterogeneous", [{ results: [{ 値: 1 }] }, { results: [{ 別の列: "x" }] }]],
      ["d1-mixed", [{ results: [{ 値: 1 }] }, { 値: 2 }]],
    ]) {
      const file = join(tmp, `${slug}.json`);
      writeFileSync(file, JSON.stringify(wrappers));
      let rejected = false;
      try { readRows(file); } catch (error) { rejected = error.message.includes("複数の D1 結果"); }
      ok(rejected, `${slug}の一部だけを黙って採用した`);
      const init = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/report.mjs"), "init", tmp, "2026-09", slug, file], { encoding: "utf8" });
      ok(init.status === 2 && init.stderr.includes("複数の D1 結果") && !existsSync(join(tmp, `2026-09-${slug}`)), `${slug}をinitで明示拒否できない`);
    }

    // 実際に生成された計算例を実行し、profileと同じセル・欠測規則で数値を得る。
    const numericData = join(tmp, "numeric.csv"), numericDir = join(tmp, "2026-09-numeric");
    writeFileSync(numericData, '値,項目\n10,a\n,b\n"1,000",c\n');
    const init = spawnSync(process.execPath, [join(SKILL_DIR, "scripts/report.mjs"), "init", tmp, "2026-09", "numeric", numericData], { encoding: "utf8" });
    ok(init.status === 0, `数値セルの回帰用initが失敗 (${init.stderr})`);
    if (init.status === 0) {
      const briefFile = join(numericDir, "brief.json"), brief = JSON.parse(readFileSync(briefFile, "utf8"));
      Object.assign(brief.plan, { 問い: "値の分布を確認する", 読み手: "担当者", 判断: "次に確認する値を決める", 指標: "値", 単位: "件", 基準: "なし", 範囲: "2026-09" });
      writeFileSync(briefFile, JSON.stringify(brief));
      const analysisFile = join(numericDir, "analysis.mjs"), generated = readFileSync(analysisFile, "utf8");
      const calculation = generated.split("\n").filter((line) => /^\/\/ const (parsed|x|excluded) =/.test(line)).map((line) => line.replace(/^\/\/ /, "").replace('r["列"]', 'r["値"]')).join("\n");
      ok(calculation.includes("parseNumericCell") && calculation.includes("const excluded"), "雛形の数値例に共有readerか除外数がない");
      writeFileSync(analysisFile, generated.split("// ---- 2. 計算:")[0] + calculation + '\nconsole.log(JSON.stringify({ n: x.length, mean: describe(x).mean, excluded }));\n');
      const run = spawnSync(process.execPath, [analysisFile], { encoding: "utf8" });
      const numericProfile = JSON.parse(readFileSync(join(numericDir, "profile.json"), "utf8")).files[0].columns.find((column) => column.name === "値");
      ok(run.status === 0 && run.stdout.trim() === JSON.stringify({ n: numericProfile.valid_numeric_n, mean: numericProfile.mean, excluded: numericProfile.missing }), `雛形とprofileの数値解析が異なる (${run.stderr || run.stdout})`);
      ok(numericProfile.mean === 505 && numericProfile.missing === 1, "空欄を0にせず桁区切りの数値を保持できない");
    }
    const numericValues = ["10", "", null, "1,000", "0", "-12.5", " 2 ", "4", "5", "6", "7", "8", "不明", "Infinity"];
    const jsonData = join(tmp, "numeric-boundary.json");
    writeFileSync(jsonData, JSON.stringify(numericValues.map((値, i) => ({ 値, 項目: String(i) }))));
    const rows = readRows(jsonData), values = rows.map((row) => parseNumericCell(row.値)).filter(Number.isFinite);
    const numericProfile = profileRows(rows).columns.find((column) => column.name === "値");
    ok(numericProfile.type === "number" && numericProfile.valid_numeric_n === values.length && numericProfile.mean === Math.round(st.describe(values).mean * 1000) / 1000, "JSONの正常値・不正値・欠測でprofileと計算の数値規則が異なる");
    ok(numericProfile.missing === 2 && numericProfile.invalid_numeric_n === 2 && values.includes(0), "数値の0、欠測、不正値を区別して数えられない");
  } finally {
    rmSync(tmp, { recursive: true, force: true });
  }
}

// 数値セルは0を保持し、欠測・不正値を補完しない。CSV/JSONの文字列化後も同じ契約を使う。
for (const [value, expected] of [["", null], ["  ", null], [null, null], [undefined, null], ["不明", null], ["Infinity", null], ["1e309", null], [",", null], ["0", 0], [0, 0], ["1,000", 1000], ["-12.5", -12.5], [" 2 ", 2]]) {
  ok(parseNumericCell(value) === expected, `数値セル ${String(value)} を ${expected} として読めない`);
}

// 9. 図のデータの端
{
  const bad = (svg) => /NaN|Infinity|undefined|(?:width|height)="-/.test(svg);
  const edge = [
    ["hbar 負の値", () => hbar({ items: [{ label: "売上", value: 62 }, { label: "修繕費", value: -85 }, { label: "燃料費", value: -19 }], unit: "万円", aria: "増減" })],
    ["hbar 全部0", () => hbar({ items: [{ label: "a", value: 0 }, { label: "b", value: 0 }], aria: "0" })],
    ["hbar 1項目・長いラベル", () => hbar({ items: [{ label: "とても長い項目名".repeat(4), value: 5 }], aria: "1件" })],
    ["columns 負の値", () => columns({ groups: [{ label: "前年", bars: [{ value: -3 }] }, { label: "今年", bars: [{ value: 4 }] }], unit: "pt", aria: "対比" })],
    ["columns 全部0", () => columns({ groups: [{ label: "a", bars: [{ value: 0 }] }], aria: "0" })],
    ["waterfall", () => waterfall({ start: { label: "前月", value: 643 }, steps: [{ label: "売上", value: 62 }, { label: "修繕費", value: -85 }], end: { label: "今月" }, unit: "万円", aria: "増減" })],
    ["waterfall 負へ落ちる", () => waterfall({ start: { label: "前月", value: 10 }, steps: [{ label: "損失", value: -30 }], end: { label: "今月" }, aria: "赤字" })],
    ["line 比較つき", () => line({ points: [3, 4, 5].map((v, i) => ({ label: `0${i + 1}月`, value: v })), compare: { label: "前年", values: [2, 4, 6] }, aria: "比較" })],
    ["line 出来事", () => line({ points: [3, 4, 5].map((v, i) => ({ label: `${i}`, value: v })), events: [{ at: 0, label: "施行" }, { at: 1.5, label: "改定" }], aria: "出来事" })],
    ["multiline", () => multiline({ labels: ["a", "b", "c"], series: [{ label: "出生", values: [3, 2, 1] }, { label: "死亡", values: [3, 3, 1], tone: "danger" }], events: [{ at: 1, label: "流行" }], aria: "推移" })],
    ["stacked", () => stacked({ rows: [{ label: "大型", parts: [3, 0, 1] }, { label: "空", parts: [0, 0, 0] }], series: ["燃料", "修繕", "人件"], aria: "構成" })],
    ["stacked 100%", () => stacked({ rows: [{ label: "空", parts: [0, 0] }], series: ["a", "b"], percent: true, aria: "構成比" })],
    ["dumbbell 同じ値", () => dumbbell({ items: [{ label: "a", from: 5, to: 5 }], fromLabel: "前", toLabel: "後", aria: "変化" })],
    ["forest", () => forest({ items: [{ label: "差", est: 0, lo: 0, hi: 0 }, { label: "比", est: 1.2, lo: 0.9, hi: 1.6 }], ref: { value: 1, label: "同じ" }, aria: "区間" })],
    ["butterfly 0", () => butterfly({ items: [{ label: "0-9", left: 0, right: 0 }], leftLabel: "男", rightLabel: "女", aria: "対比" })],
    ["heatmap 全部0", () => heatmap({ rows: ["a"], cols: ["x", "y"], values: [[0, 0]], aria: "表" })],
    ["scatter 4象限", () => scatter({ points: [1, 2, 3].map((i) => ({ x: i, y: i * i })), xLabel: "x", yLabel: "y", fit: false, refs: { x: { value: 2, label: "平均" }, y: { value: 4, label: "平均" } }, aria: "関係" })],
    ["flow", () => flow({ nodes: [{ id: "a", label: "背景", col: 0 }, { id: "b", label: "指標", col: 1, sub: "▲3", tone: "danger" }], edges: [{ from: "a", to: "b", dashed: true }], aria: "筋" })],
  ];
  for (const [name, make] of edge) {
    let svg = "";
    try { svg = make(); } catch (e) { ok(false, `[図 ${name}] 例外: ${e.message}`); continue; }
    ok(svg.startsWith("<svg") && !bad(svg), `[図 ${name}] 壊れた SVG (NaN・負の幅など)`);
  }
  const quadrant = scatter({ points: [1, 2, 3].map((i) => ({ x: i, y: i * i })), xLabel: "x", yLabel: "y", fit: false, refs: { x: { value: 2, label: "平均" }, y: { value: 4, label: "平均" } }, aria: "分類" });
  ok(!quadrant.includes(">r=") && !quadrant.includes("R²=") && !quadrant.includes("s-threshold"), "scatter fit=false が回帰統計または回帰線を表示した");
  const fitted = scatter({ points: [1, 2, 3].map((i) => ({ x: i, y: i * i })), xLabel: "x", yLabel: "y", aria: "関係" });
  ok(fitted.includes(">r=") && fitted.includes("R²=") && fitted.includes("s-threshold"), "scatter fit=true の回帰統計または回帰線が欠けた");
  const flowNodes = [{ id: "a", label: "背景", col: 0 }, { id: "b", label: "指標", col: 1 }];
  ok(flow({ nodes: flowNodes, edges: [{ from: "a", to: "b" }], aria: "仮説" }).includes('class="s-dash"'), "flow の説明仮説が既定で破線にならない");
  for (const solid of ["identity", "definition", "mechanically-verified"]) {
    ok(flow({ nodes: flowNodes, edges: [{ from: "a", to: "b", solid }], aria: "検証済み" }).includes('class="s-sub"'), `flow の ${solid} 指定が実線にならない`);
  }
  let threw = false;
  try { line({ points: [{ label: "05月", value: 3 }], aria: "1点" }); } catch { threw = true; }
  ok(threw, "1点だけの折れ線を受け付けた (推移にならないので例外にする)");
  // 入力の誤りは例外にする (黙って壊れた図を出さない)
  for (const [name, make] of [
    ["出来事が範囲外", () => line({ points: [{ label: "a", value: 1 }, { label: "b", value: 2 }], events: [{ at: 3, label: "x" }], aria: "x" })],
    ["系列が6つ", () => multiline({ labels: ["a", "b"], series: Array.from({ length: 6 }, (_, i) => ({ label: `${i}`, values: [1, 2] })), aria: "x" })],
    ["構成の個数違い", () => stacked({ rows: [{ label: "a", parts: [1] }], series: ["x", "y"], aria: "x" })],
    ["区間の外の推定値", () => forest({ items: [{ label: "a", est: 5, lo: 0, hi: 1 }], aria: "x" })],
    ["右から左への矢印", () => flow({ nodes: [{ id: "a", label: "a", col: 1 }, { id: "b", label: "b", col: 0 }], edges: [{ from: "a", to: "b" }], aria: "x" })],
    ["長すぎる箱", () => flow({ nodes: [{ id: "a", label: "長い説明".repeat(40), col: 0 }], aria: "x" })],
    ["許可外の実線根拠", () => flow({ nodes: [{ id: "a", label: "a", col: 0 }, { id: "b", label: "b", col: 1 }], edges: [{ from: "a", to: "b", solid: "assumed" }], aria: "x" })],
  ]) {
    let t = false;
    try { make(); } catch { t = true; }
    ok(t, `[図 ${name}] 例外にならなかった`);
  }
  // 密集した折れ線: 値ラベルは間引くが、最後の点は必ず出す。横軸ラベルは重ならない数に減らす
  const pts = Array.from({ length: 24 }, (_, i) => ({ label: `${24 + Math.floor((i + 8) / 12)}/${String(((i + 8) % 12) + 1).padStart(2, "0")}`, value: 22 + (i % 3) * 0.1 + (i > 21 ? 4 : 0), tone: i > 21 ? "danger" : undefined }));
  const svg = line({ points: pts, digits: 1, aria: "密集" });
  const vl = [...svg.matchAll(/class="vl[^"]*"[^>]*>([^<]+)</g)].map((m) => m[1]);
  const ax = [...svg.matchAll(/class="lb">([^<]+)</g)].map((m) => m[1]);
  ok(vl.length >= 2 && vl.length < 24 && vl.at(-1) === sfmt(pts.at(-1).value, 1), `密集した折れ線の値ラベルの間引きが不正 (${vl.length}件、最後 ${vl.at(-1)})`);
  ok(ax.length < 24 && ax.includes(pts.at(-1).label), `密集した折れ線の横軸ラベルの間引きが不正 (${ax.length}件)`);
}

// 要因が多すぎたら警告 (W07) で絞らせる
{
  const f4 = src.replace(/(<section data-kind="action")/, `${factor(-1)}\n\n$1`);
  let r;
  try { r = checkReport(buildReport(f4)); } catch (e) { r = { errors: [e.message], warnings: [] }; }
  ok(r.warnings.some((w) => w.startsWith("W07")), `要因4つで W07 が出ない (${[...r.errors, ...r.warnings].join(" / ")})`);
}

// 出所が pending なら、エラーにせず警告 (W04) でヒアリングを促す
{
  const pending = checkReport(buildReport(src.replace('data-source="data"', 'data-source="pending"').replace("<dd>2026年11月の配車から</dd>", "<dd>要確認</dd>")));
  ok(pending.errors.length === 0 && pending.warnings.some((w) => w.startsWith("W04")), `pending の打ち手が W04 警告にならない (${[...pending.errors, ...pending.warnings].join(" / ")})`);
}
// 強い因果語があっても、明示的な留保がある文は誤って E21 にしない。
for (const cautious of ["荷主変更により実車率が減少した可能性がある", "荷主変更が実車率低下を招いたかもしれない"]) {
  const cautiousSource = src.replace("小型車の空車増加が、全体の実車率低下に最も強く関係している", cautious);
  const cautiousResult = checkReport(buildReport(cautiousSource));
  ok(!cautiousResult.errors.some((e) => e.startsWith("E21")), `留保つき因果表現を E21 にした: 「${cautious}」`);
}
for (const [code, name, mutate, stage] of cases) {
  let html;
  try {
    html = stage === "src" ? buildReport(mutate(src)) : mutate(a);
  } catch (e) {
    ok(false, `[${name}] ビルドが例外で止まった: ${e.message}`);
    continue;
  }
  ok(html !== a, `[${name}] 変異が適用されていない (テンプレートが変わった可能性)`);
  const r = checkReport(html);
  ok(r.errors.some((e) => e.startsWith(code)), `[${name}] ${code} を検出できない (検出: ${r.errors.join(" / ") || "なし"})`);
}

// ソースの型違反・ビルドが付ける部品の手書きは入力エラーにする
const noActionSource = src.replace(/\s*<!-- 打ち手:[\s\S]*?<section data-kind="action"[\s\S]*?<\/section>/, "");
let noActionResult;
let noActionHtml = "";
try { noActionHtml = buildReport(noActionSource); noActionResult = checkReport(noActionHtml); } catch (e) { noActionResult = { errors: [e.message] }; }
ok(noActionResult.errors.length === 0 && !/<div class="cta-row">/.test(noActionHtml) && !/class="btn btn-primary"/.test(noActionHtml), `打ち手なしの最短レポートが合格しない (${noActionResult.errors.join(" / ")})`);
const inputCases = [
  ["style の手書き", src.replace("<header", "<style>p{}</style><header")],
  ["目次の手書き", src.replace("<header", '<nav class="toc"></nav><header')],
  ["番号チップの手書き", src.replace("<h2>営業利益", '<span class="secno">結論</span><h2>営業利益')],
  ["見出し帯の手書き", src.replace("<h2>営業利益", '<div class="sec-head"></div><h2>営業利益')],
  ["section 無し", "<title>t</title><p>x</p>"],
  ["data-kind 無し", src.replace('data-kind="action" ', "")],
  ["結論が先頭でない", src.replace('data-kind="conclusion"', 'data-kind="factor" data-impact="-1"')],
  ["要因が0個", src.replace(/<section data-kind="factor"[\s\S]*?<\/section>/g, "")],
  ["data-impact が数値でない", src.replace('data-impact="-150"', 'data-impact="大きい"')],
  ["data-unit 無し", src.replace(' data-unit="万円/月"', "")],
  ["打ち手が0件", src.replace(/<li class="act"[\s\S]*?<\/li>/g, "")],
  ["data-from 無し", src.replace(' data-from="1"', "")],
  ["data-from が存在しない要因", src.replace('data-from="1"', 'data-from="9"')],
  ["data-from が存在しない要因名", src.replace('data-from="1"', 'data-from="空車"')],
  ["data-source 不正", src.replace('data-source="data"', 'data-source="guess"')],
  ["act-meta の順序違い", src.replace("<div><dt>担当</dt><dd>配車</dd></div>\n        <div><dt>期限</dt><dd>2026年11月の配車から</dd></div>", "<div><dt>期限</dt><dd>2026年11月の配車から</dd></div>\n        <div><dt>担当</dt><dd>配車</dd></div>")],
  ["CTA の手書き", src.replace("<footer>", '<div class="cta-row"></div><footer>')],
  ["header.doc 無し", src.replace('<header class="doc" data-detail="standard">', "<header>")],
];
for (const [name, bad] of inputCases) {
  let threw = false;
  try { buildReport(bad); } catch (e) { threw = e instanceof InputError; }
  ok(threw, `[${name}] を入力エラーにできない`);
}

// 丸めて0になる値に ▲・+・- を付けない (本文と統計の要約で符号が食い違わない)
ok(sfmt(-0.04, 1, "pt", true) === "0.0pt" && sfmt(0.04, 0, "", true) === "0", `sfmt が0に符号を付ける (${sfmt(-0.04, 1, "pt", true)})`);
ok(sfmt(-0.06, 1) === "▲0.1" && sfmt(2, 0, "", true) === "+2", "sfmt が0でない値の符号を落とす");

// 10. LLM の出力の検査。正しい例は合格し、欠陥を1つずつ入れた例はそれぞれ不合格になること
{
  const csv = parseCsv('a,b\n"x,y","line 1\nline 2"\n');
  ok(csv.length === 1 && csv[0].a === "x,y" && csv[0].b === "line 1\nline 2", "CSV の引用符内カンマ・改行を読めない");
  for (const [name, body] of [
    ["引用符未閉鎖", 'a,b\n"x,y\n'],
    ["見出し重複", "a,a\n1,2\n"],
    ["行幅不足", "a,b\n1\n"],
    ["行幅超過", "a,b\n1,2,3\n"],
  ]) {
    let rejected = false;
    try { parseCsv(body); } catch { rejected = true; }
    ok(rejected, `CSV の構造破損 [${name}] を拒否できない`);
  }
  const pf = profileRows([
    { 年月: "2026-07", 車両: "A", 燃料費: "10", メモ: "x1" },
    { 年月: "2026-08", 車両: "A", 燃料費: "12", メモ: "x2" },
    { 年月: "2026-08", 車両: "B", 燃料費: "", メモ: "x3" },
    { 年月: "2026-08", 車両: "A", 燃料費: "9", メモ: "x4" },
  ]);
  const type = Object.fromEntries(pf.columns.map((c) => [c.name, c.type]));
  ok(type.年月 === "period" && type.車両 === "category" && type.燃料費 === "number" && type.メモ === "text", `profile の型判定が違う (${JSON.stringify(type)})`);
  ok(pf.columns.find((c) => c.name === "燃料費").missing === 1, "profile が欠損を数えない");
  const mixedNumeric = profileRows(Array.from({ length: 10 }, (_, i) => ({ 金額: i < 8 ? String(i + 1) : i === 8 ? "不明" : "?" }))).columns[0];
  ok(mixedNumeric.type === "number" && mixedNumeric.valid_numeric_n === 8 && mixedNumeric.invalid_numeric_n === 2 && mixedNumeric.invalid_samples.join() === "不明,?", `numeric列の暗黙除外をprofileへ残せない (${JSON.stringify(mixedNumeric)})`);
  const profile = { files: [{ file: "d.csv", ...pf }] };
  const H = (id, 対立 = false) => ({ id, 枝: "燃料費", 主張: "走行が増えた", 反証条件: "走行の差が燃料費の差の半分未満", 型: "分解", 関数: ["driverTree"], 図: "waterfall", 列: ["車両", "燃料費"], 対立 });
  const CANDS = [["量と率", "焦点"], ["経済・価格", "焦点"], ["制度・規則", "深掘り"], ["競合・市場", "深掘り"], ["組織・運用", "深掘り"], ["外部の衝撃", "捨てる"]]
    .map(([型, 扱い], i) => ({ 枝: "燃料費", 候補: `候補${i}`, 型, 扱い, ...(扱い === "捨てる" ? { 理由: "確かめる手段が無い" } : {}) }));
  const brief = { plan: { 問い: "8月の利益はなぜ減ったか", 読み手: "社長", 判断: "どの費目に手を打つか", 指標: "営業利益", 単位: "万円/月", 基準: "2026-07", 範囲: "2026-08", 情報量: "標準", 背景分析: true, 分解: "利益 = 売上 − 燃料費", 焦点: "軽油価格の上昇で燃料費が増え、利益が減った" }, 候補: CANDS, hypotheses: [H("H1"), H("H2", true), { ...H("H3"), 層: "背景", 列: ["軽油価格"] }, { ...H("H4", true), 層: "背景", 列: ["軽油価格"] }], unknowns: [] };
  const BGR = [
    { 系列: "軽油価格", 期間: "2026-07", 値: "150", 単位: "円/L", 基準: "月平均", 出典: "公的な価格調査", URL: "https://example.go.jp/a.csv", 注記: "" },
    { 系列: "軽油価格", 期間: "2026-08", 値: "160", 単位: "円/L", 基準: "月平均", 出典: "公的な価格調査", URL: "https://example.go.jp/a.csv", 注記: "" },
    { 系列: "出来事", 期間: "2026-08-01", 値: "", 単位: "", 基準: "施行日", 出典: "告示", URL: "https://example.go.jp/b", 注記: "補助金の縮小" },
  ];
  ok(checkBrief(brief, profile, BGR).length === 0, `正しい brief が不合格 (${checkBrief(brief, profile, BGR).join(" / ")})`);
  // 調査の前 (--pre): 背景データが無くても、背景データ以外の誤りだけを見る
  ok(checkBrief(brief, profile, [], { pre: true }).length === 0, "--pre なのに背景データが無いことで不合格になった");
  ok(checkBrief(brief, profile, []).length > 0, "--pre でないのに背景データの欠けを見逃した");
  { const b = structuredClone(brief); b.plan.判断 = ""; ok(checkBrief(b, profile, [], { pre: true }).length > 0, "--pre で plan の空欄を見逃した"); }
  const mut = (f, bgr = BGR) => { const b = structuredClone(brief); f(b); return checkBrief(b, profile, bgr).length > 0; };
  const briefCases = [
    ["plan の空欄", (b) => { b.plan.判断 = ""; }],
    ["情報量が不正", (b) => { b.plan.情報量 = "全部"; }],
    ["相対の範囲", (b) => { b.plan.範囲 = "先月"; }],
    ["unknowns が残る", (b) => { b.unknowns = ["目標値"]; }],
    ["仮説が1つ", (b) => { b.hypotheses = [H("H1", true)]; }],
    ["対立仮説が無い", (b) => { for (const h of b.hypotheses) h.対立 = false; }],
    ["背景分析フラグが不正", (b) => { b.plan.背景分析 = "必要"; }],
    ["焦点が無い (背景分析あり)", (b) => { delete b.plan.焦点; }],
    ["背景の仮説が無い (背景分析あり)", (b) => { b.hypotheses = b.hypotheses.slice(0, 2); }],
    ["背景の対立仮説が無い", (b) => { b.hypotheses[3].対立 = false; }],
    ["許可外の層", (b) => { b.hypotheses[0].層 = "推測"; }],
    ["背景データに無い系列", (b) => { b.hypotheses[2].列 = ["為替"]; }],
    ["id の重複", (b) => { b.hypotheses[1].id = "H1"; }],
    ["許可外の問いの型", (b) => { b.hypotheses[0].型 = "SWOT"; }],
    ["存在しない関数", (b) => { b.hypotheses[0].関数 = ["magic"]; }],
    ["存在しない図", (b) => { b.hypotheses[0].図 = "pie"; }],
    ["データに無い列", (b) => { b.hypotheses[0].列 = ["天候"]; }],
    ["判定できない反証条件", (b) => { b.hypotheses[0].反証条件 = "そう思えない場合"; }],
    ["候補が少ない (背景分析あり)", (b) => { b.候補 = b.候補.slice(0, 5); }],
    ["候補の型が偏る", (b) => { for (const c of b.候補) c.型 = "量と率"; }],
    ["許可外の候補の型", (b) => { b.候補[0].型 = "気合い"; }],
    ["焦点の候補が無い", (b) => { for (const c of b.候補) if (c.扱い === "焦点") c.扱い = "深掘り"; }],
    ["捨てた理由が無い", (b) => { delete b.候補[5].理由; }],
  ];
  for (const [name, f] of briefCases) ok(mut(f), `brief の [${name}] を検出できない`);
  const bgCases = [
    ["出典の URL が無い", (r) => { r[0].URL = ""; }],
    ["http の URL", (r) => { r[0].URL = "http://example.go.jp/a"; }],
    ["基準が空", (r) => { r[0].基準 = ""; }],
    ["通常系列の期間が空", (r) => { r[0].期間 = ""; }],
    ["期間の形式が不正", (r) => { r[0].期間 = "2026-7"; }],
    ["存在しない日付", (r) => { r[0].期間 = "2026-02-30"; }],
    ["通常系列の単位が空", (r) => { r[0].単位 = ""; }],
    ["系列と期間が重複", (r) => { r[1].期間 = r[0].期間; }],
    ["同一系列の単位が混在", (r) => { r[1].単位 = "円"; }],
    ["同一系列の基準が混在", (r) => { r[1].基準 = "月末時点"; }],
    ["値が数値でない", (r) => { r[0].値 = "約150"; }],
    ["出来事の名前が無い", (r) => { r[2].注記 = ""; }],
  ];
  for (const [name, f] of bgCases) { const r = structuredClone(BGR); f(r); ok(mut(() => {}, r), `背景データの [${name}] を検出できない`); }
  const sameAcrossFiles = mergeBackgroundFiles([{ name: "背景データ.csv", rows: [BGR[0]] }, { name: "背景データ-反証.csv", rows: [structuredClone(BGR[0])] }]);
  ok(sameAcrossFiles.errors.length === 0 && sameAcrossFiles.rows.length === 1, "異なる背景CSVの完全一致行を1件に統合できない");
  const duplicateInFile = mergeBackgroundFiles([{ name: "背景データ.csv", rows: [BGR[0], structuredClone(BGR[0])] }]);
  ok(duplicateInFile.errors.length === 1 && duplicateInFile.rows.length === 1, "同一背景CSV内の系列・期間重複を拒否できない");
  const conflicting = structuredClone(BGR[0]); conflicting.値 = "151";
  const conflictAcrossFiles = mergeBackgroundFiles([{ name: "背景データ.csv", rows: [BGR[0]] }, { name: "背景データ-反証.csv", rows: [conflicting] }]);
  ok(conflictAcrossFiles.errors.length === 1 && conflictAcrossFiles.rows.length === 1, "異なる背景CSVの系列・期間競合を拒否できない");
  const fac = (toc, badges) => `<section data-kind="factor" data-toc="${toc}" data-impact="-1"><h2>x</h2>${badges == null ? "" : `<ul class="causes">${badges.map((b) => `<li><span class="badge ${b}">x</span></li>`).join("")}</ul>`}</section>`;
  ok(checkCauses(brief, fac("燃料費", ["badge-success", "badge-warning"]) + fac("売上", ["badge-active", "badge-success"])).length === 0, "確かめた項目のある要因を不合格にした");
  ok(checkCauses(brief, fac("燃料費", ["badge-success", "badge-active", "badge-warning", "badge-warning"])).length === 0, "想定がちょうど半分の causes を不合格にした");
  ok(checkCauses(brief, fac("燃料費", ["badge-success", "badge-warning", "badge-warning"])).some((e) => e.includes("半分を超え")), "想定が半分を超える causes を検出できない");
  ok(checkCauses(brief, fac("燃料費", ["badge-active"])).length === 1, "1段だけの仕組み (原因 → 結果 が無い) を検出できない");
  ok(checkCauses(brief, fac("燃料費", null)).length === 1, "なぜ起きたかの無い要因を検出できない");
  ok(checkCauses(brief, fac("燃料費", ["badge-warning"])).some((e) => e.includes("確かめた項目")), "想定だけのなぜ起きたかを検出できない");

  const results = { delta: -5, steps: [{ label: "売上", value: 3 }, { label: "燃料費", value: -8 }], hypotheses: [{ id: "H1", 判定: "採用", 数字: { 差: -8 } }, { id: "H2", 判定: "棄却", 数字: { 差: 1 } }, { id: "H3", 判定: "採用", 数字: { 寄与: -6 } }, { id: "H4", 判定: "棄却", 数字: { 寄与: -1 } }] };
  const linkedClaim = hypothesisClaim(brief, results, "H1");
  ok(linkedClaim.text === brief.hypotheses[0].主張 && linkedClaim.verdict === "採用", "hypothesisClaim が brief の主張と results の判定を接続しない");
  ok(checkResults(results, brief).length === 0, `正しい results が不合格 (${checkResults(results, brief).join(" / ")})`);
  const rmut = (f) => { const r = structuredClone(results); f(r); return checkResults(r, brief).length > 0; };
  const resultCases = [
    ["steps の合計が delta と不一致", (r) => { r.steps[0].value = 4; }],
    ["steps の label が空", (r) => { r.steps[0].label = ""; }],
    ["steps の value が非数値", (r) => { r.steps[0].value = "not-a-number"; }],
    ["steps の label が重複", (r) => { r.steps[1].label = r.steps[0].label; }],
    ["判定の無い仮説", (r) => { r.hypotheses.pop(); }],
    ["results の仮説 id が空", (r) => { r.hypotheses[0].id = ""; }],
    ["results の仮説 id が重複", (r) => { r.hypotheses[1].id = r.hypotheses[0].id; }],
    ["許可外の判定", (r) => { r.hypotheses[0].判定 = "たぶん"; }],
    ["根拠の数字が無い", (r) => { r.hypotheses[0].数字 = {}; }],
  ];
  for (const [name, f] of resultCases) ok(rmut(f), `results の [${name}] を検出できない`);
  ok(rmut((r) => { r.hypotheses[1].判定 = "採用"; }), "同じ枝で主な仮説と対立仮説が両方「採用」なのを検出できない");
  // 記述上の分解と背景分析は独立。分解だけなら候補・背景仮説・外部調査・causesを要求しない。
  const noSplit = structuredClone(brief);
  delete noSplit.plan.分解;
  ok(checkBrief(noSplit, profile, BGR).length === 0 && checkCauses(noSplit, fac("燃料費", null)).length === 1, "分解なしの背景分析を独立して扱えない");
  const decompositionOnly = structuredClone(brief);
  decompositionOnly.plan.背景分析 = false;
  delete decompositionOnly.plan.焦点;
  decompositionOnly.候補 = [];
  decompositionOnly.hypotheses = decompositionOnly.hypotheses.slice(0, 2);
  ok(checkBrief(decompositionOnly, profile, [], { pre: true }).length === 0 && checkCauses(decompositionOnly, fac("燃料費", null)).length === 0, "分解だけの問いに背景分析を強制した");
  const descriptiveOnly = structuredClone(decompositionOnly);
  delete descriptiveOnly.plan.分解;
  descriptiveOnly.hypotheses = [];
  ok(checkBrief(descriptiveOnly, profile, [], { pre: true }).length === 0, `単純な記述レポートで仮説0個を受け付けない (${checkBrief(descriptiveOnly, profile, [], { pre: true }).join(" / ")})`);
  ok(checkCauses(descriptiveOnly, fac("燃料費", ["badge-success", "badge-active"])).some((e) => e.includes("背景分析")), "背景分析=false の causes 出力を拒否できない");
  // 分解の無い問い (分布・関係など) では delta を求めないが、最終 HTML の要因には対応する steps が要る。
  const sec = (toc, impact, hypotheses = ["H1"], verdict = "採用") => `<section id="s" data-kind="factor" data-toc="${toc}" data-impact="${impact}" data-hypotheses="${hypotheses.join(",")}"><div class="statement claim" data-hypothesis-id="${hypotheses[0] || ""}" data-verdict="${verdict}"><span class="statement-text">${esc(brief.hypotheses.find((h) => h.id === hypotheses[0])?.主張 || "仮説")}</span></div></section>`;
  const noSplitResults = { steps: [{ label: "燃料費", value: -8 }], hypotheses: results.hypotheses };
  ok(checkResults(noSplitResults, noSplit, sec("燃料費", -8)).length === 0, "分解の無い問いの impact 一覧を不合格にした");
  ok(checkResults({ hypotheses: results.hypotheses }, noSplit, sec("燃料費", -8)).some((e) => e.includes("results.steps")), "分解の無い問いで最終要因に対応する steps の欠落を検出できない");
  const factors = sec("燃料費", -8, ["H1", "H3"]) + sec("売上", 3, ["H3"]);
  ok(checkResults(results, brief, factors).length === 0, "steps と採用仮説へ追跡できる要因を不合格にした");
  ok(checkImpacts(results, brief, sec("層", -99)).some((e) => e.includes("results.steps")), "results.steps に存在しない要因を検出できない");
  ok(checkImpacts(results, brief, sec("燃料費", -85)).some((e) => e.includes("一致しません")), "steps と食い違う影響を検出できない");
  ok(checkResults(results, brief, sec("燃料費", -8, ["H9"])).some((e) => e.includes("brief.hypotheses")), "未知の仮説 ID を検出できない");
  ok(checkResults(results, brief, sec("燃料費", -8, [])).some((e) => e.includes("data-hypotheses")), "空の仮説 ID を検出できない");
  const descriptiveSection = '<section id="s" data-kind="factor" data-toc="燃料費" data-impact="-8"></section>';
  ok(checkImpacts({ steps: [{ label: "燃料費", value: -8 }], hypotheses: [] }, descriptiveOnly, descriptiveSection).length === 0, "仮説・claim無しの要因を不合格にした");
  ok(checkResults(results, brief, sec("燃料費", -8, ["H1", "H1"])).some((e) => e.includes("重複")), "重複した仮説 ID を検出できない");
  const rejected = structuredClone(results);
  rejected.hypotheses.find((h) => h.id === "H4").判定 = "保留";
  ok(checkResults(rejected, brief, sec("燃料費", -8, ["H2", "H4"])).some((e) => e.includes("「採用」の仮説")), "要因の仮説が全て棄却/保留なのを検出できない");
  const changedClaim = sec("燃料費", -8).replace(esc(brief.hypotheses[0].主張), "検証した主張とは異なる内容");
  ok(checkImpacts(results, brief, changedClaim).some((e) => e.includes("本文")), "ID・判定が同じ別の仮説本文を受理した");
  const encodedBrief = { plan: { 情報量: "標準" }, hypotheses: [{ id: 'H&1', 主張: 'R&Dの中央値は"3"未満' }] };
  const encodedResults = { steps: [{ label: 'R&D <比較>', value: 1e-7 }], hypotheses: [{ id: 'H&1', 判定: "採用" }] };
  const encodedFactor = composeFactor({ toc: 'R&D <比較>', impact: 1e-7, hypotheses: ['H&1'], claim: hypothesisClaim(encodedBrief, encodedResults, 'H&1'), h2: "比較値に差がある", meaning: "比較を続ける", interpretation: "違いがある", figures: ["<figure></figure>"], stats: [{ label: "n", value: "12" }], facts: ["値は1", "値は2"], data: "入力", calc: "比較" });
  ok(checkImpacts(encodedResults, encodedBrief, buildReport(source({ title: "接続", parts: [header({ crumb: "テスト", title: "接続", target: "12件", created: "2026-09-28" }), conclusion({ h2: "値は1を示す", unit: "値", hero: { label: "値", value: "1" }, kpis: [{ label: "n", value: "12" }], overview: { comparison: "12件を比較", finding: "値は1", interpretation: "違いがある", limitation: "原因は未確認" } }), encodedFactor, footer({ crumb: "テスト", data: "入力" })] }))).length === 0, "entityを含むID・主張・要因名と指数impactの生成後接続が壊れた");
  const ratio = { steps: [{ label: "比率", value: 0.1 }], hypotheses: [{ id: "H1", 判定: "採用" }] };
  ok(checkImpacts(ratio, brief, sec("比率", 0.1000000005)).length === 0, "小数の微小な計算誤差を不合格にした");
  ok(checkImpacts({ steps: [{ label: "比率", value: -0.1 }], hypotheses: ratio.hypotheses }, brief, sec("比率", "−0.1")).length === 0, "Unicodeマイナスの impact を工程間で同じ値として扱えない");
  ok(checkImpacts(ratio, brief, sec("比率", 0.100000002)).some((e) => e.includes("一致しません")), "小数指標の許容差境界を超えた不一致を検出できない");
  const large = { steps: [{ label: "大きな数", value: 1_000_000 }], hypotheses: [{ id: "H1", 判定: "採用" }] };
  ok(checkImpacts(large, brief, sec("大きな数", 1_000_000.0005)).length === 0, "大きな数の微小な相対誤差を不合格にした");
  ok(checkImpacts(large, brief, sec("大きな数", 1_000_000.002)).some((e) => e.includes("一致しません")), "大きな数の相対許容差境界を超えた不一致を検出できない");

  // 独立レビューは、全4条件 PASS と最終 HTML の hash を一緒に固定する。
  const reviewed = "<p>draft</p>", html = "<p>report</p>";
  const passConditions = () => Object.fromEntries(REVIEW_CONDITIONS.map((condition) => [condition, "PASS"]));
  const review = {
    target: sha256(html),
    条件: passConditions(),
    findings: [
      { 条件: "矛盾なし", severity: "must", status: "fixed", 箇所: "要因 1", 指摘: "x", 提案: "見出しを直す" },
      { 条件: "整合性あり", severity: "should", status: "open", 箇所: "結論", 指摘: "y", 提案: "重複を削る" },
    ],
  };
  ok(checkReview(review, html).length === 0, `正しい review が不合格 (${checkReview(review, html).join(" / ")})`);
  const vmut = (f, h = html) => { const v = structuredClone(review); f(v); return checkReview(v, h).length > 0; };
  ok(vmut((v) => { v.target = sha256(reviewed); }), "修正前 HTML の古い target hash を検出できない");
  ok(vmut((v) => { v.findings[0].status = "open"; }), "対応の無い must を検出できない");
  for (const condition of REVIEW_CONDITIONS) ok(vmut((v) => { delete v.条件[condition]; }), `review.条件.${condition} の欠落を検出できない`);
  for (const field of REVIEW_FINDING_FIELDS) ok(vmut((v) => { delete v.findings[0][field]; }), `finding.${field} の欠落を検出できない`);
  ok(vmut((v) => { delete v.条件; }), "条件全体の欠落を検出できない");
  ok(vmut((v) => { delete v.findings; }), "findings の欠落を検出できない");
  ok(vmut((v) => { v.条件["矛盾なし"] = "UNKNOWN"; }), "4条件の未知値を検出できない");
  ok(vmut((v) => { v.条件["未知の条件"] = "PASS"; }), "未知の条件キーを検出できない");
  ok(vmut((v) => { v.条件["漏れなし"] = "FAIL"; }), "4条件の FAIL を検出できない");
  ok(vmut((v) => { v.findings[0].条件 = "美しさ"; }), "finding の未知の条件を検出できない");
  ok(vmut((v) => { v.findings[1].severity = "nice"; }), "許可外の severity を検出できない");
  ok(vmut((v) => { v.findings[0].status = "deferred"; }), "許可外の status を検出できない");
  ok(vmut((v) => { delete v.target; }), "target の無い review を検出できない");
  // accepted は明示的に受容した must として警告対象に残す。
  const keep = { target: sha256(html), 条件: passConditions(), findings: [{ 条件: "漏れなし", severity: "must", status: "accepted", 箇所: "要因 2", 指摘: "z", 提案: "追加データを集める" }] };
  ok(checkReview(keep, html).length === 0, `accepted の must を不合格にした (${checkReview(keep, html).join(" / ")})`);
  ok(unfixedMusts(keep).length === 1 && unfixedMusts(review).length === 0, "直さずに渡す must を数え違えた");
  ok(checkReview(keep, html + " ").length > 0, "最終 HTML と target の hash 不一致を検出できない");
  ok(checkStrictCompletion('<li class="act card" data-source="pending"></li>').length === 1 && checkStrictCompletion('<li class="act card" data-source="data"></li>').length === 0, "厳格doneが未確定アクションだけを拒否できない");
}

// 12. build 証跡は、記録後の成果物・背景データ集合・実描画結果のどれかが変われば無効になる。
{
  const dir = mkdtempSync(join(tmpdir(), "rds-state-")), name = "2026-08-trace";
  const artifact = (file) => join(dir, file);
  const originalAnalysis = "export const value = 1;\n";
  const rawInput = artifact("raw-input.csv"), originalRawInput = "年月,値\n2026-08,1\n";
  const background = "系列,期間,値,単位,基準,出典,URL,注記\n軽油価格,2026-08,160,円/L,月平均,調査,https://example.go.jp/a,\n";
  try {
    mkdirSync(artifact("screens"));
    writeFileSync(rawInput, originalRawInput);
    for (const [file, body] of Object.entries({
      "analysis.mjs": originalAnalysis,
      "profile.json": "{}\n",
      "brief.json": "{}\n",
      [INPUT_MANIFEST_FILE]: `${JSON.stringify({ version: INPUT_MANIFEST_VERSION, files: [{ path: rawInput, sha256: sha256(originalRawInput) }] }, null, 2)}\n`,
      "results.json": "{}\n",
      "背景データ.csv": background,
      [`${name}.src.html`]: "<title>source</title>\n",
      [`${name}.html`]: "<title>report</title>\n",
    })) writeFileSync(artifact(file), body);
    for (const width of RENDER_WIDTHS) writeFileSync(artifact(`screens/${name}-${width}.png`), `png-${width}`);

    const state = recordBuildState(dir, name);
    ok(existsSync(artifact(BUILD_STATE_FILE)) && state.report === name && verifyBuildState(dir, name).ok, "build 証跡を記録・検証できない");

    writeFileSync(artifact("analysis.mjs"), "export const value = 2;\n");
    ok(!verifyBuildState(dir, name).ok, "build 後の成果物改変を検出できない");
    writeFileSync(artifact("analysis.mjs"), originalAnalysis);

    writeFileSync(rawInput, "年月,値\n2026-08,2\n");
    ok(!verifyBuildState(dir, name).ok, "build 後の生入力改変を検出できない");
    writeFileSync(rawInput, originalRawInput);

    writeFileSync(artifact("背景データ-反証.csv"), background.replace("軽油価格", "為替"));
    ok(!verifyBuildState(dir, name).ok, "build 後の背景データ追加を検出できない");
    rmSync(artifact("背景データ-反証.csv"));

    rmSync(artifact("背景データ.csv"));
    ok(!verifyBuildState(dir, name).ok, "build 後の背景データ削除を検出できない");
    writeFileSync(artifact("背景データ.csv"), background);

    const screenshot = artifact(`screens/${name}-${RENDER_WIDTHS[0]}.png`);
    rmSync(screenshot);
    ok(!verifyBuildState(dir, name).ok, "build 後のスクリーンショット欠落を検出できない");
    writeFileSync(screenshot, `png-${RENDER_WIDTHS[0]}`);

    ok(verifyBuildState(dir, name).ok, "改変を元に戻しても build 証跡が回復しない");
    clearBuildState(dir);
    ok(!existsSync(artifact(BUILD_STATE_FILE)) && !verifyBuildState(dir, name).ok, "clear 後の build 証跡欠落を検出できない");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

// ---- 13. ヒアリングシートと実行部隊向け資料 ----
let handoutChecks = 0;
{
  const ok = (cond, msg) => { handoutChecks++; if (!cond) failures.push(msg); };
  const has = (issues, kind, who) => issues.some((x) => x.kind === kind && (!who || x.who === who));
  const sample = readFileSync(join(SKILL_DIR, "assets/hearing.sample.md"), "utf8");
  const sheet = parseSheet(sample);
  ok(sheetIssues(sheet).length === 0 && sheet.problems.length === 0 && sheet.confirmed, "見本のシートに指摘が出る");

  // 作ったシートを読み戻すと、同じ中身になる (AI が書いた下書きがユーザーの編集後も失われない)
  const draft = { meta: { 元のレポート: "x", 作成日: "2026-09-28" }, confirmed: true, sections: { actions: { items: [{ 誰が: "経理", 何を: "請求書を確かめる", いつまでに: "10月末", できたかの目安: "結果を伝えた" }, { 誰が: "配車担当", 何を: "配車表を作る", いつまでに: "毎週月曜", できたかの目安: "表を渡した" }] } }, refs: { purpose: ["参考"] } };
  const round = parseSheet(renderSheet(draft));
  ok(JSON.stringify(round.sections.actions) === JSON.stringify(draft.sections.actions), "シートを作って読み戻すと、やることの下書きが変わる");
  ok(round.meta.元のレポート === "x" && round.confirmed && round.problems.length === 0, "シートの見出し情報か了承の印を読み戻せない");

  // 空のシート: ユーザーが決めるまとまりだけを聞き、AI が下書きするまとまりは聞かずに直す。任意のまとまりと、直す途中の了承は聞かない
  const empty = sheetIssues(parseSheet(renderSheet()));
  const decided = QUESTIONS.filter((q) => q.decide).map((q) => q.title);
  const drafted = QUESTIONS.filter((q) => !q.decide && (q.optional ?? []).length < q.fields.length).map((q) => q.title);
  ok(askGroups(empty).map((g) => g.section).join("・") === decided.join("・"), `空のシートで聞くことが、ユーザーが決めるまとまりと一致しない (${askGroups(empty).map((g) => g.section).join("・")})`);
  ok(empty.filter((x) => x.who === "fix").map((x) => x.section).join("・") === drafted.join("・"), "空のシートで AI が直すことが、AI が下書きするまとまりと一致しない");
  ok(!empty.some((x) => x.section === "困ったら" || x.kind === "未確認"), "任意のまとまりか、直す途中の了承を聞いている");
  // 1回の往復で聞く数: まとまりごとに1問へ束ねるので、多くても「決めるまとまり + 全体の了承」問。これが上限を超えない
  ok(decided.length + 1 <= ASK_LIMIT, `1回の往復で聞くことが ${ASK_LIMIT} 問に収まらない`);

  const edit = (from, to) => {
    ok(sample.includes(from), `selftest の置き換え元が見本に無い: ${from.slice(0, 20)}`);
    return parseSheet(sample.replace(from, to));
  };
  const variants = [
    ["統計の言葉", edit("運賃の見直しを話し合う", "中央値より安い運賃の見直しを話し合う"), "言い換え", "fix"],
    ["▲", edit("赤字の月が続いているので", "▲の月が続いているので"), "言い換え", "fix"],
    ["小数", edit("1か月試し", "1.5か月試し"), "言い換え", "fix"],
    ["分析の言葉", edit("運賃の見直しを話し合う", "運賃の仮説を話し合う"), "言い換え", "fix"],
    ["比べた群の言葉", edit("ほかの車の仕事を回す", "中位群の車の仕事を回す"), "言い換え", "fix"],
    ["1件に動作が2つ", edit("入っているかを確かめる", "入っているかを確かめ、入っていなければ請求する"), "分ける", "fix"],
    ["絵文字", edit("運賃の見直しを話し合う", "運賃の見直しを話し合う🚚"), "言い換え", "fix"],
    ["決める欄のわからない", edit("- 期限: 11月末", "- 期限: わからない"), "聞き直し", "ask"],
    ["下書きする欄のわからない", edit("- 相手: 配車担当と10トン車のドライバー", "- 相手: わからない"), "聞き直し", "fix"],
    ["期限の形", edit("- いつまでに: 10月末\n- できたかの目安: 確かめた", "- いつまでに: なるべく早く\n- できたかの目安: 確かめた"), "期限", "ask"],
    ["振り返りの形", edit("- 振り返り: 毎週月曜の朝礼", "- 振り返り: ときどき"), "期限", "fix"],
    ["長すぎる欄", edit("- 誰が: 社長", `- 誰が: ${"あ".repeat(TEXT_MAX + 1)}`), "長すぎ", "fix"],
    ["長すぎる題名", edit("- 題名: 10トン車の運び方を見直す 10〜11月の取り組み", `- 題名: ${"あ".repeat(TITLE_MAX + 1)}`), "長すぎ", "fix"],
    ["見せない情報の漏れ", edit("取引の多い荷主さん", "東西物流さん"), "見せない情報", "fix"],
    ["未確認", edit("- [x] この内容で資料にする", "- [ ] この内容で資料にする"), "未確認", "ask"],
    ["決める欄が空", edit("- 誰が: 社長", "- 誰が: "), "未記入", "ask"],
    ["下書きする欄が空", edit("- できたかの目安: 確かめた結果を社長に伝えた", "- できたかの目安: "), "未記入", "fix"],
    ["見せない情報が空", edit("- 語句: 東西物流、1台あたりの赤字額", "- 語句: "), "未記入", "ask"],
    ["ゴールが多すぎ", edit("## 4. やること", "### ゴール 3\n- 内容: a\n- 期限: 10月末\n### ゴール 4\n- 内容: b\n- 期限: 10月末\n\n## 4. やること"), "多すぎ", "fix"],
    ["知らない見出し", edit("## 5. 困ったら〔任意〕", "## 5. 困ったとき〔任意〕"), "形式", "fix"],
    ["知らない欄", edit("- 誰が: 社長", "- 担当: 社長"), "形式", "fix"],
    ["知らないチェック", edit("## 確認", "- [x] 確認\n\n## 確認"), "形式", "fix"],
  ];
  for (const [name, variant, kind, who] of variants) ok(has(sheetIssues(variant), kind, who), `ヒアリング: 「${name}」を ${kind} (${who === "ask" ? "聞く" : "AI が直す"}) にできない`);
  // 書き方の揺れは受け入れる: 〔〕を消した見出し、丸ごと空の件、「なし」の見せない情報
  ok(sheetIssues(edit("## 5. 困ったら〔任意〕", "## 5. 困ったら")).length === 0, "〔〕を消した見出しを読めない");
  ok(sheetIssues(edit("## 5. 困ったら", "### やること 4\n- 誰が: \n- 何を: \n\n## 5. 困ったら")).length === 0, "丸ごと空の件を未記入として聞いている");
  const none = edit("- 語句: 東西物流、1台あたりの赤字額", "- 語句: なし");
  ok(sheetIssues(none).length === 0 && handoutModel(none).hidden.length === 0, "見せない情報の「なし」を受け入れられない");
  // 同じまとまりの質問は1問に束ねる
  const twoGoals = parseSheet(sample.replace("- 期限: 2026-10-31", "- 期限: わからない").replace("- 期限: 11月末", "- 期限: 未定"));
  const goalGroups = askGroups(sheetIssues(twoGoals)).filter((g) => g.section === "ゴール");
  ok(goalGroups.length === 1 && goalGroups[0].items.length === 2, "同じまとまりの質問を1問に束ねていない");
  // 了承済みでも直すべき点は消えない。了承は AI が直すことが無くなってから聞き、聞くことと同じ回に聞ける
  const unticked = sample.replace("- [x] この内容で資料にする", "- [ ] この内容で資料にする");
  ok(has(sheetIssues(parseSheet(sample.replace("赤字の月が続いているので", "▲の月が続いているので"))), "言い換え"), "了承済みのシートでも言い換えの指摘は残す");
  ok(!has(sheetIssues(parseSheet(unticked.replace("赤字の月が続いているので", "▲の月が続いているので"))), "未確認"), "AI が直す途中のシートに了承を求めている");
  const withAsk = sheetIssues(parseSheet(unticked.replace("- 期限: 11月末", "- 期限: わからない")));
  ok(has(withAsk, "未確認") && has(withAsk, "聞き直し"), "了承をほかの質問と同じ回に聞けない");
  ok(!has(sheetIssues(edit("運賃の見直しを話し合う", "荷主さんと、赤字にならない運賃を話し合う")), "分ける"), "「ならない」の打ち消しを、動作が2つと誤検出する");
  ok(plainIssues("2026.10.31 までに").length === 0, "日付の「.」を小数と誤検出する");
  ok(plainIssues("売上を10%上げる").length === 0, "統計でない普通の数字を止めている");
  ok(FRONTLINE_WORDS.every((pair) => Array.isArray(pair) && pair.length === 2 && pair.every((w) => typeof w === "string" && w.trim())), "FRONTLINE_WORDS は [使わない言葉, 言い換え] の組にする");
  for (const [word] of FRONTLINE_WORDS) ok(plainIssues(`${word}を見直す`).length > 0, `FRONTLINE_WORDS の「${word}」を検出できない`);

  // 下書き: compose の打ち手を読み、前の月のシートから変わりにくい欄を引き継ぐ
  const acts = [
    { title: "赤字の<10tW>の荷主と運賃を話し合う", from: "1", source: "data", effect: "月20万円", owner: "社長", due: "10月末" },
    { title: "配車を組み直す", from: "2", source: "pending", effect: "月5万円", owner: "要確認", due: "要確認" },
  ];
  const actHtml = actions({ h2: "運賃と配車を見直す", items: acts });
  ok(JSON.stringify(readActs(actHtml)) === JSON.stringify(acts.map(({ title, owner, due }) => ({ title, owner, due }))), "hearing.mjs が compose.mjs の打ち手を読み取れない (形の約束が崩れた)");
  const root = mkdtempSync(join(tmpdir(), "rds-hearing-"));
  try {
    const month = (name, text) => {
      mkdirSync(join(root, name), { recursive: true });
      if (text) writeFileSync(join(root, name, "hearing.md"), text);
      return join(root, name);
    };
    month("2026-04-vehicle-pl", sample.replace("配車責任者", "4月の相談先"));
    month("2026-05-vehicle-pl", sample);
    month("2026-07-vehicle-pl", sample.replace("配車責任者", "7月の相談先"));
    month("2026-05-other", sample.replace("配車責任者", "別の資料の相談先"));
    const dir = month("2026-06-vehicle-pl");
    writeFileSync(join(dir, "2026-06-vehicle-pl.src.html"), `<section data-kind="conclusion"><h2>10トン車の&lt;一部&gt;が赤字</h2></section>\n${actHtml}`);
    const next = draftFromReport(dir);
    ok(next.sections.help?.items?.[0]?.相談先 === "配車責任者" && next.sections.hidden?.items?.[0]?.語句 === "東西物流、1台あたりの赤字額", "前の月のシートから相談先・見せない情報を引き継げない (より前の月・後の月・別の資料を選んでいる)");
    ok(next.sections.cover?.items?.[0]?.相手 === "配車担当と10トン車のドライバー" && !next.sections.cover.items[0].題名 && !next.sections.goals, "引き継ぐのは変わりにくい欄だけ (題名・ゴールは月ごとに決める)");
    ok(next.sections.actions?.items?.map((a) => a.何を).join("|") === acts.map((a) => a.title).join("|") && next.refs.purpose?.[0]?.includes("10トン車の<一部>が赤字"), "レポートの打ち手と結論を下書きに写せない");

    // CLI: 回答待ちは 3、了承済みは 0、打ち間違いのフォルダは作らずに 2
    const cli = (script, target) => spawnSync(process.execPath, [join(SKILL_DIR, "scripts", script), target], { encoding: "utf8" });
    ok(cli("hearing.mjs", join(root, "2026-08-vehicle-pl")).status === 3 && existsSync(join(root, "2026-08-vehicle-pl/hearing.md")), "新しいフォルダでシートを作り、回答待ち (3) で止まらない");
    ok(cli("build-handout.mjs", join(root, "2026-08-vehicle-pl")).status === 3, "了承前のシートから資料を作っている");
    ok(cli("hearing.mjs", join(root, "2026-05-vehicle-pl")).status === 0, "了承済みのシートでヒアリング完了 (0) にならない");
    ok(cli("build-handout.mjs", join(root, "2026-05-vehicle-pl")).status === 0 && existsSync(join(root, "2026-05-vehicle-pl/2026-05-vehicle-pl-handout.html")), "了承済みのシートから資料を作れない");
    for (const typo of ["2026-13-x", "Vehicle PL", "typo/2026-06-x"]) {
      ok(cli("hearing.mjs", join(root, typo)).status === 2 && !existsSync(join(root, typo.split("/")[0])), `打ち間違いのフォルダ「${typo}」を作っている`);
    }
  } finally {
    rmSync(root, { recursive: true, force: true });
  }

  // 資料: 見本から決定的に作れ、利用者の文はエスケープされ、検査の各規則が効く
  const model = handoutModel(sheet);
  const html = buildHandout(model);
  ok(html === buildHandout(handoutModel(parseSheet(sample))), "同じシートからの資料が一致しない");
  const clean = checkHandout(html, model);
  ok(clean.errors.length === 0, `見本の資料が不合格: ${clean.errors.join(" / ")}`);
  const order = [...html.matchAll(/<section id="([^"]+)" data-kind="([^"]+)">\s*<div class="sec-head"><span class="secno">([^<]+)</g)].map((x) => `${x[1] === x[2] ? x[2] : "id違い"}:${x[3]}`);
  ok(order.join(" ") === Object.entries(HANDOUT_KINDS).map(([k, v]) => `${k}:${v}`).join(" "), `資料の並びかチップの文言が HANDOUT_KINDS と違う (${order.join(" ")})`);
  ok(!/<script>alert/.test(buildHandout({ ...model, purpose: "<script>alert(1)</script>" })), "利用者の文をエスケープしていない");
  // 生成器の形で決まること (checkHandout では見ない): やることの欄・件数、インラインの style
  const main = html.match(/<main\b[\s\S]*<\/main>/)[0];
  const lis = [...main.matchAll(/<li class="act\b[\s\S]*?<\/li>/g)].map((x) => x[0]);
  ok(lis.length === model.actions.length && lis.every((li, i) => li.includes(`<span class="act-who badge badge-tag">${model.actions[i].who}</span>`) && ["いつまでに", "できたかの目安"].every((dt) => li.includes(`<dt>${dt}</dt>`))), "やることの件数か欄 (番号の隣の担当・いつまでに・できたかの目安) が資料に出ていない");
  // 期限は現場で読む形にする。年は作成日と同じなら省き、読めない書き方はそのまま出す
  const dues = [["2026-10-31", "10月31日"], ["2026-10末", "10月末"], ["2026年10月中旬", "10月中旬"], ["2026-11", "11月"], ["2027-01末", "2027年1月末"], ["毎週月曜", "毎週月曜"], ["11月末", "11月末"]];
  for (const [value, want] of dues) ok(plainDue(value, "2026") === want, `期限「${value}」を「${want}」にできない (${plainDue(value, "2026")})`);
  ok(plainDue("2026-10末", "") === "2026年10月末", "作成日が無いときに年を省いている");
  ok(main.includes('<span class="goal-due-h">いつまでに</span>10月31日'), "ゴールの期限を「いつまでに」と現場で読む形で出していない");
  ok((main.match(/<li class="goal\b/g) ?? []).length === model.goals.length, "ゴールの件数が資料と一致しない");
  ok(!/<[a-z][^>]*\sstyle=/i.test(main), "資料の本文にインラインの style がある (見た目は report.css に書く)");
  const noHelp = { ...model, help: "", review: "" };
  ok(checkHandout(buildHandout(noHelp), noHelp).errors.length === 0 && !buildHandout(noHelp).match(/<main\b[\s\S]*<\/main>/)[0].includes('data-kind="help"'), "困ったらが無い資料を作れない");
  const handoutCases = [
    ["H03", { ...model, actions: [{ ...model.actions[0], what: "相関の高い荷主と話す" }] }],
    ["H04", { ...model, goals: [{ text: "東西物流と話し合いを終える", due: "10月末" }] }],
  ];
  for (const [code, bad] of handoutCases) ok(checkHandout(buildHandout(bad), bad).errors.some((e) => e.startsWith(code)), `資料の検査が ${code} を検出できない`);
  // 資料には report.css が埋め込まれ、CSS にも [data-kind="goal"] がある。<section> のタグで置き換える
  const unordered = html.replace('<section id="goal" data-kind="goal">', '<section id="goal" data-kind="todo">');
  ok(unordered !== html && checkHandout(unordered, model).errors.some((e) => e.startsWith("H01")), "資料の検査がセクションの並びの崩れを検出できない");
  const headless = html.replace(/<div class="sec-head"><span class="secno">ゴール<\/span>/, "<div>");
  ok(headless !== html && checkHandout(headless, model).errors.some((e) => e.startsWith("H02")), "資料の検査が見出し帯の欠落を検出できない");

  // 入口と、LLM が読む手順書への転記
  ok(/\bhearing\b/.test(USAGE) && /\bhandout\b/.test(USAGE), "report.mjs の使い方に hearing / handout が無い");
  const handoutPrompt = readFileSync(join(SKILL_DIR, "prompts/handout.md"), "utf8");
  ok(handoutPrompt.includes(`各欄は${TEXT_MAX}字まで、題名は${TITLE_MAX}字まで`), "prompts/handout.md の字数が hearing.mjs と違う");
  for (const prompt of ["handout", "analyst"]) {
    ok(readFileSync(join(SKILL_DIR, `prompts/${prompt}.md`), "utf8").includes(`1回に多くても${ASK_LIMIT}問`), `prompts/${prompt}.md の1回に聞く数が lib.mjs の ASK_LIMIT と違う`);
  }
}

for (const f of failures) console.log(`  NG ${f}`);
console.log(failures.length ? `selftest: 不合格 (${failures.length})` : `selftest: 合格 (違反検出 ${cases.length} 件 + 入力エラー ${inputCases.length} 件 + ヒアリングと資料 ${handoutChecks} 件)`);
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(failures.length ? 1 : 0);
