#!/usr/bin/env node
// LLM が書いた分析の設計 (brief.json)・計算結果 (results.json)・独立レビュー (review.json) を検査する。
// LLM の判断の中身は検査できないので、形と根拠のつながりを検査する (prompts/analyst.md・prompts/review.md)。
//
//   node scripts/check-llm.mjs brief  <フォルダ>   設計: 問いが埋まり、仮説に反証条件があり、列が profile.json に実在する。
//                                                 背景の仮説 (層: 背景) の列は 背景データ.csv の系列に実在し、その行に出典の URL がある
//   node scripts/check-llm.mjs results <フォルダ>  上に加え (レビューの前)、全仮説に判定があり、(分解があれば) steps の合計が delta に一致し、
//                                                 同じ枝の主な仮説と対立仮説が両方「採用」でなく、HTML の要因が step と採用仮説へ追跡でき、
//                                                 (plan.背景分析=trueなら) どの要因の背景の説明仮説にも確かめた項目 (データで確認・公表資料) が2段以上ある
//   node scripts/check-llm.mjs review <フォルダ>   上に加え、独立レビューの4条件が全て PASS、must に未解決がなく、
//                                                 target が現在の最終 HTML の sha256 と一致することを検査する。
// 終了コード: 0=合格 1=不合格 2=入力エラー
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import * as stats from "./stats.mjs";
import * as charts from "./charts.mjs";
import {
  hasPendingActions, isFilled as filled, nearlyEqual, parseImpact,
  REPORT_DETAILS, reviewContractErrors, sha256, parseCsv, BG_RE, decodeEntities, textOf,
} from "./lib.mjs";

// 問いの型 (references/statistics.md §2)。型が決まれば手法・関数・図が決まる
export const TYPES = ["分布", "比較", "関係", "分解", "推移", "集中", "異常"];
const PLAN_KEYS = ["問い", "読み手", "判断", "指標", "単位", "基準", "範囲", "情報量", "背景分析"];
const H_KEYS = ["id", "枝", "主張", "反証条件", "型", "関数", "図", "列"];
const RELATIVE = /先月|今月|前月|来月|昨年|去年|今年|来年|先週|今週|昨日|今日|最近|直近/;
const VERDICTS = ["採用", "棄却", "保留"];
const LAYERS = ["内訳", "背景"];
// 背景の候補の型 (references/causes.md §2)。分解があるときは、候補を6つ以上・4つ以上の型から出す (1つの見方に偏らせない)
export const CAUSE_TYPES = ["量と率", "構成", "世代・周期", "制度・規則", "経済・価格", "外部の衝撃", "行動", "競合・市場", "代替・技術", "組織・運用", "測定"];
const HANDLING = ["焦点", "深掘り", "捨てる"];
export const BG_FILE = "背景データ.csv";
const BG_COLS = ["系列", "期間", "値", "単位", "基準", "出典", "URL", "注記"];
const BG_PERIOD = /^(\d{4})(?:-(0[1-9]|1[0-2])(?:-(0[1-9]|[12]\d|3[01]))?)?$/;

const validBackgroundPeriod = (value) => {
  const match = String(value || "").match(BG_PERIOD);
  if (!match || !match[3]) return Boolean(match);
  const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  return day <= [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1];
};

const backgroundKey = (row) => `${row.系列}\u0000${row.期間}`;
const backgroundSignature = (row) => JSON.stringify(
  Object.keys(row).filter((key) => !key.startsWith("_")).sort().map((key) => [key, row[key]]),
);

/**
 * 複数の背景 CSV を、ファイル内の重複は拒否し、ファイル間の完全一致行だけ1件へ統合する。
 * files = [{ name, rows }] 。同じ系列・期間の内容が競合したら errors に入れ、rows は先の1件を保つ。
 */
export function mergeBackgroundFiles(files) {
  const rows = [], errors = [], seen = new Map();
  for (const file of files || []) {
    const local = new Set();
    for (const [index, raw] of (file?.rows || []).entries()) {
      const name = file?.name || BG_FILE;
      const row = { ...raw, _at: raw._at || `${name} ${index + 2}行目` };
      const key = backgroundKey(row), signature = backgroundSignature(row);
      if (local.has(key)) {
        errors.push(`${row._at} (${row.系列 || "?"}): 同じファイル内で系列「${row.系列 || "?"}」と期間「${row.期間 || "?"}」が重複しています`);
        continue;
      }
      local.add(key);
      const prior = seen.get(key);
      if (!prior) {
        seen.set(key, { name, signature, at: row._at });
        rows.push(row);
      } else if (prior.name !== name && prior.signature !== signature) {
        errors.push(`${row._at} (${row.系列 || "?"}): 系列「${row.系列 || "?"}」と期間「${row.期間 || "?"}」の内容が ${prior.at} と競合しています`);
      }
    }
  }
  return { rows, errors };
}

// 背景データ.csv (prompts/research.md) の形: 列が揃い、どの行にも出典と https の URL と基準があり、値が数値 (出来事は注記が必須)
export function checkBackground(rows) {
  const E = [];
  const seen = new Set(), contracts = new Map();
  if (rows.length && BG_COLS.some((c) => !(c in rows[0]))) E.push(`${BG_FILE} の列は ${BG_COLS.join(",")} にする`);
  for (const [i, r] of rows.entries()) {
    const at = `${r._at || `${BG_FILE} ${i + 2}行目`} (${r.系列 || "?"})`;
    if (!filled(r.出典) || !/^https:\/\/\S+$/.test(r.URL || "")) E.push(`${at}: 出典と https:// の URL が必要です (出典の無い数字は使わない)`);
    if (!filled(r.基準)) E.push(`${at}: 基準 (暦年・時点・速報/確定) が空です`);
    if (!validBackgroundPeriod(r.期間)) E.push(`${at}: 期間は YYYY / YYYY-MM / YYYY-MM-DD のどれかにする (${r.期間 || "空"})`);
    if (r.系列 !== "出来事" && !filled(r.単位)) E.push(`${at}: 通常系列の単位が空です`);
    if (r.系列 === "出来事" ? !filled(r.注記) : !Number.isFinite(Number(r.値)) || !filled(r.値)) E.push(`${at}: ${r.系列 === "出来事" ? "出来事の名前 (注記)" : "値 (数値)"} がありません`);
    const key = `${r.系列}\u0000${r.期間}`;
    if (seen.has(key)) E.push(`${at}: 系列「${r.系列 || "?"}」と期間「${r.期間 || "?"}」が重複しています`);
    seen.add(key);
    if (r.系列 !== "出来事" && filled(r.系列)) {
      const prior = contracts.get(r.系列);
      if (prior && prior.単位 !== r.単位) E.push(`${at}: 系列「${r.系列}」の単位が「${prior.単位}」と「${r.単位}」で混在しています`);
      if (prior && prior.基準 !== r.基準) E.push(`${at}: 系列「${r.系列}」の基準が「${prior.基準}」と「${r.基準}」で混在しています`);
      if (!prior) contracts.set(r.系列, { 単位: r.単位, 基準: r.基準 });
    }
  }
  return E;
}

// brief.候補 (references/thinking.md §2): 広く出したか (6つ以上・型4つ以上)、焦点が1つの筋にあるか、捨てた理由があるか
export function checkCandidates(cs) {
  if (!Array.isArray(cs) || cs.length < 6) return [`brief.候補 を6つ以上出す (${Array.isArray(cs) ? cs.length : 0}個。references/causes.md §2 の型と3つの軸で広げる)`];
  const E = [];
  for (const [i, c] of cs.entries()) {
    const at = `候補 ${i + 1} (${c.候補 || "?"})`;
    for (const k of ["枝", "候補", "型", "扱い"]) if (!filled(c[k])) E.push(`${at}: ${k} が空です`);
    if (filled(c.型) && !CAUSE_TYPES.includes(c.型)) E.push(`${at}: 型は ${CAUSE_TYPES.join(" / ")} のどれか`);
    if (filled(c.扱い) && !HANDLING.includes(c.扱い)) E.push(`${at}: 扱いは ${HANDLING.join("・")} のどれか`);
    if (c.扱い === "捨てる" && !filled(c.理由)) E.push(`${at}: 捨てる理由を書く`);
  }
  const types = new Set(cs.map((c) => c.型).filter((t) => CAUSE_TYPES.includes(t)));
  if (types.size < 4) E.push(`brief.候補 の型が ${types.size} 種類だけです。4種類以上の型から出す (データの外: 制度・経済・外部の衝撃・競合 なども当てる)`);
  if (!cs.some((c) => c.扱い === "焦点")) E.push("brief.候補 に 扱い「焦点」がありません");
  return E;
}

export function checkBrief(brief, profile, background = [], { pre = false } = {}) {
  const E = [];
  const plan = brief?.plan || {};
  for (const k of PLAN_KEYS) if (!filled(plan[k])) E.push(`plan.${k} が空です`);
  if (typeof plan.背景分析 !== "boolean") E.push("plan.背景分析 は true か false にする");
  if (filled(plan.情報量) && !REPORT_DETAILS[plan.情報量]) E.push(`plan.情報量 は ${Object.keys(REPORT_DETAILS).join("・")} のどれかにする (${plan.情報量})`);
  if (filled(plan.範囲) && (RELATIVE.test(plan.範囲) || !/\d{4}|全/.test(plan.範囲))) E.push(`plan.範囲 は絶対の日付か「全件」で書く (${plan.範囲})`);
  if (filled(brief?.unknowns)) E.push(`unknowns が残っています (${brief.unknowns.join(" / ")})。AskUserQuestion で聞いて反映する`);
  const hypothesesAreArray = Array.isArray(brief?.hypotheses);
  const hs = hypothesesAreArray ? brief.hypotheses : [];
  if (!hypothesesAreArray) E.push("hypotheses は配列にする");
  // 単純な記述レポートは仮説なしで完成できる。仮説を使う場合だけ、従来の反証可能性を守る。
  if ((plan.背景分析 === true || hs.length) && (hs.length < 2 || hs.length > 8)) E.push(`hypotheses は背景分析時または使う場合は2〜8個、単純な記述時は0個 (${hs.length}個)`);
  if (hs.length && !hs.some((h) => h.対立 === true)) E.push("対立仮説 (対立: true) が1つもありません。主な仮説と別の説明を最低1つ立てる");
  const columns = new Set((profile?.files || []).flatMap((f) => f.columns.map((c) => c.name)));
  const series = new Set(background.map((r) => r.系列));
  const bg = hs.filter((h) => h.層 === "背景");
  const needsBackground = plan.背景分析 === true;
  // 差の理由を問うなら、どこで動いたか (内訳) だけでなく、なぜ動いたか (背景) を主な説明と対立の説明で立てる
  if (needsBackground && !(bg.some((h) => h.対立 === true) && bg.some((h) => h.対立 !== true))) E.push("plan.背景分析 が true なので、層「背景」の主な仮説と対立仮説を最低1つずつ立てる (references/causes.md)");
  if (needsBackground && !filled(plan.焦点)) E.push("plan.背景分析 が true なので、plan.焦点 (今回確かめる説明の筋の1文) を書く (references/thinking.md §2)");
  if (!needsBackground && bg.length) E.push("plan.背景分析 が false なのに層「背景」の仮説があります。背景を問う場合だけ true にする");
  if (bg.length && !pre) E.push(...checkBackground(background));
  if (needsBackground) E.push(...checkCandidates(brief.候補));
  const ids = new Set();
  for (const h of hs) {
    const at = `仮説 ${h.id || "(id なし)"}`;
    for (const k of H_KEYS) if (!filled(h[k])) E.push(`${at}: ${k} が空です`);
    if (ids.has(h.id)) E.push(`${at}: id が重複しています`);
    ids.add(h.id);
    if (filled(h.型) && !TYPES.includes(h.型)) E.push(`${at}: 型「${h.型}」は ${TYPES.join(" / ")} のどれかにする`);
    for (const f of [].concat(h.関数 || [])) if (typeof stats[f] !== "function") E.push(`${at}: 関数 ${f} は stats.mjs にありません`);
    if (filled(h.図) && typeof charts[h.図] !== "function") E.push(`${at}: 図 ${h.図} は charts.mjs にありません`);
    if (!LAYERS.includes(h.層 ?? "内訳")) E.push(`${at}: 層は ${LAYERS.join("・")} のどちらか`);
    if (h.層 === "背景") for (const c of [].concat(h.列 || [])) { if (!pre && !series.has(c)) E.push(`${at}: 系列「${c}」が ${BG_FILE} にありません (prompts/research.md で調べる。集まらなければ仮説を直す)`); }
    else for (const c of [].concat(h.列 || [])) if (!columns.has(c)) E.push(`${at}: 列「${c}」は profile.json にありません (データに無い列を前提にしない)`);
    if (filled(h.反証条件) && !/\d|半分|以上|以下|未満|超|上回|下回|逆|差|相関|有意|区間/.test(h.反証条件)) E.push(`${at}: 反証条件が計算で判定できる形になっていません (数字や比較で書く)`);
  }
  return E;
}

export function checkResults(results, brief, html) {
  const E = [];
  // 分解 (plan.分解) を立てたときだけ、差とその分解を必須にする。分布・関係などの問いには差が無い
  const steps = Array.isArray(results?.steps) ? results.steps : [];
  if (filled(brief?.plan?.分解)) {
    if (!Number.isFinite(results?.delta)) E.push("results.delta が数値ではありません (plan.分解 があるので必須)");
    if (!steps.length) E.push("results.steps (結論の差の分解) がありません (plan.分解 があるので必須)");
  }
  const stepLabels = new Set();
  let validStepValues = true;
  for (const [index, step] of steps.entries()) {
    const at = `results.steps ${index + 1}件目`;
    if (!step || typeof step !== "object" || Array.isArray(step)) {
      E.push(`${at} がオブジェクトではありません`);
      validStepValues = false;
      continue;
    }
    if (!filled(step.label)) E.push(`${at}.label が空です`);
    else if (stepLabels.has(step.label)) E.push(`${at}.label「${step.label}」が重複しています`);
    else stepLabels.add(step.label);
    if (typeof step.value !== "number" || !Number.isFinite(step.value)) {
      E.push(`${at}.value は有限の数値にする`);
      validStepValues = false;
    }
  }
  const sum = validStepValues ? steps.reduce((t, step) => t + step.value, 0) : null;
  if (sum != null && steps.length && Number.isFinite(results?.delta) && Math.abs(sum - results.delta) > 1e-6 * Math.max(1, Math.abs(results.delta))) E.push(`results.steps の合計 ${sum} が delta ${results.delta} と一致しません (分解に漏れか重なりがある)`);

  const judged = Array.isArray(results?.hypotheses) ? results.hypotheses : [];
  if (!Array.isArray(results?.hypotheses)) E.push("results.hypotheses が配列ではありません");
  const judgedIds = new Set();
  for (const [index, hypothesis] of judged.entries()) {
    const at = `results.hypotheses ${index + 1}件目`;
    if (!hypothesis || typeof hypothesis !== "object" || Array.isArray(hypothesis)) {
      E.push(`${at} がオブジェクトではありません`);
      continue;
    }
    if (!filled(hypothesis.id)) E.push(`${at}.id が空です`);
    else if (judgedIds.has(hypothesis.id)) E.push(`${at}.id「${hypothesis.id}」が重複しています`);
    else judgedIds.add(hypothesis.id);
  }
  const got = new Map(judged.map((h) => [h?.id, h]));
  for (const h of brief?.hypotheses || []) {
    const r = got.get(h.id);
    if (!r) E.push(`仮説 ${h.id} の判定が results.hypotheses にありません`);
    else {
      if (!VERDICTS.includes(r.判定)) E.push(`仮説 ${h.id} の判定「${r.判定}」は ${VERDICTS.join("・")} のどれかにする`);
      if (!r.数字 || !Object.values(r.数字).some((v) => Number.isFinite(v))) E.push(`仮説 ${h.id} の判定に根拠の数字 (数字) がありません`);
    }
  }
  // 主な仮説と対立仮説は両立しない説明なので、同じ枝で両方「採用」なら反証条件が甘い (どちらかは棄却されるはず)
  const adopted = (h) => got.get(h.id)?.判定 === "採用";
  for (const b of new Set((brief?.hypotheses || []).map((h) => h.枝))) {
    const hs = (brief.hypotheses || []).filter((h) => h.枝 === b && adopted(h));
    if (hs.some((h) => h.対立 === true) && hs.some((h) => h.対立 !== true)) E.push(`枝「${b}」で主な仮説と対立仮説 (${hs.map((h) => h.id).join("・")}) が両方「採用」です。同じ数字で互いに排他な反証条件にするか、判定を「保留」にする`);
  }
  if (html != null) E.push(...checkImpacts(results, brief, html));
  return E;
}

// HTML の要因が、同じ名前の step と採用された仮説の両方へ追跡できること。
export function checkImpacts(results, brief, html) {
  const E = [];
  const htmlText = String(html);
  const actualDetail = htmlText.match(/<header class="doc"[^>]*data-detail="([^"]+)"/)?.[1];
  const expectedDetail = REPORT_DETAILS[brief?.plan?.情報量]?.token;
  if (expectedDetail && /<header\b/.test(htmlText) && actualDetail !== expectedDetail) E.push(`HTML の情報量 ${actualDetail || "なし"} が brief.plan.情報量「${brief.plan.情報量}」(${expectedDetail}) と一致しません`);
  const steps = new Map((results?.steps || []).map((s) => [s.label, Number(s.value)]));
  const briefIds = new Set((brief?.hypotheses || []).map((h) => h.id));
  const resultHypotheses = new Map((results?.hypotheses || []).map((h) => [h.id, h]));
  for (const m of htmlText.matchAll(/<section\b([^>]*)>([\s\S]*?)<\/section>/g)) {
    const attrs = m[1], inner = m[2];
    if (!/\bdata-kind="factor"/.test(attrs)) continue;
    const toc = decodeEntities(attrs.match(/data-toc="([^"]*)"/)?.[1] || ""), raw = attrs.match(/data-impact="([^"]*)"/)?.[1];
    const rawIds = attrs.match(/data-hypotheses="([^"]*)"/)?.[1];
    const ids = rawIds == null ? [] : decodeEntities(rawIds).split(",").map((id) => id.trim());
    if (!steps.has(toc)) {
      E.push(`要因「${toc || "?"}」に対応する results.steps がありません`);
    } else {
      const impact = parseImpact(raw)?.value;
      if (!nearlyEqual(impact, steps.get(toc))) E.push(`要因「${toc}」の影響 ${raw} が results.steps の ${steps.get(toc)} と一致しません`);
    }
    if (rawIds != null && (!ids.length || ids.some((id) => !id))) E.push(`要因「${toc || "?"}」の data-hypotheses は省略するか、仮説 ID を1つ以上入れる`);
    if (new Set(ids.filter(Boolean)).size !== ids.filter(Boolean).length) E.push(`要因「${toc || "?"}」の data-hypotheses に同じ仮説 ID を重複させない`);
    for (const id of ids.filter(Boolean)) {
      if (!briefIds.has(id)) E.push(`要因「${toc || "?"}」の仮説 ${id} が brief.hypotheses にありません`);
      if (!resultHypotheses.has(id)) E.push(`要因「${toc || "?"}」の仮説 ${id} が results.hypotheses にありません`);
    }
    if (ids.filter(Boolean).length && !ids.some((id) => resultHypotheses.get(id)?.判定 === "採用")) E.push(`要因「${toc || "?"}」に「採用」の仮説がありません`);
    const claim = inner.match(/<div class="statement claim"[^>]*data-hypothesis-id="([^"]+)"[^>]*data-verdict="([^"]+)"[^>]*>[\s\S]*?<span class="statement-text">([\s\S]*?)<\/span><\/div>/);
    if (!ids.filter(Boolean).length && claim) E.push(`要因「${toc || "?"}」に仮説 ID が無いのに仮説・主張があります`);
    else if (ids.filter(Boolean).length && !claim) E.push(`要因「${toc || "?"}」に表示用の仮説・主張がありません`);
    else if (claim) {
      const claimId = decodeEntities(claim[1]), claimVerdict = decodeEntities(claim[2]);
      const expectedClaim = (brief?.hypotheses || []).find((item) => item.id === claimId)?.主張;
      if (expectedClaim != null && textOf(claim[3]) !== String(expectedClaim).replace(/\s+/g, " ").trim()) {
        E.push(`要因「${toc || "?"}」の表示用仮説 ${claimId} の本文が brief.hypotheses の主張と一致しません。hypothesisClaim()で接続する`);
      }
      if (!ids.includes(claimId)) E.push(`要因「${toc || "?"}」の表示用仮説 ${claimId} が data-hypotheses にありません`);
      if (!briefIds.has(claimId)) E.push(`要因「${toc || "?"}」の表示用仮説 ${claimId} が brief.hypotheses にありません`);
      const actual = resultHypotheses.get(claimId)?.判定;
      if (actual !== claimVerdict) E.push(`要因「${toc || "?"}」の表示判定 ${claimVerdict} が results.hypotheses の ${actual || "判定なし"} と一致しません`);
      if (claimVerdict !== "採用") E.push(`要因「${toc || "?"}」の表示用仮説 ${claimId} は採用済みにする (${claimVerdict})`);
    }
  }
  return E;
}

// 差の理由を問う分析では、どの要因の背景の説明仮説にも、確かめた項目 (データで確認か公表資料) が1つ以上あり、2段以上ある (内訳の言い換えで終わらせない)
export function checkCauses(brief, html) {
  if (brief?.plan?.背景分析 !== true) {
    return /<ul class="causes">/.test(String(html))
      ? ["plan.背景分析 が false なのに背景の説明仮説 (ul.causes) があります。単純な記述レポートでは省略する"]
      : [];
  }
  const E = [];
  for (const m of String(html).matchAll(/<section\b[^>]*data-kind="factor"[^>]*data-toc="([^"]*)"[^>]*>([\s\S]*?)<\/section>/g)) {
    const ul = m[2].match(/<ul class="causes">([\s\S]*?)<\/ul>/);
    if (!ul || !/badge-(?:success|active)/.test(ul[1])) E.push(`要因「${m[1]}」の背景の説明仮説に、確かめた項目 (データで確認・公表資料) がありません。factor({ causes }) で説明の筋を書く`);
    if (ul) {
      const total = (ul[1].match(/<li\b/g) || []).length;
      const assumed = (ul[1].match(/<span class="badge badge-warning">/g) || []).length;
      if (total < 2) E.push(`要因「${m[1]}」の背景の説明仮説が1段だけです。原因候補 → 中間 → 結果 の2段以上で、仕組みを書く (prompts/analyst.md「C. 解釈」の「背景の説明仮説」)`);
      if (assumed > total / 2) E.push(`要因「${m[1]}」の背景の説明仮説は、想定が ${assumed}/${total} 件で半分を超えています。データで確認・公表資料を半分以上にする`);
    }
  }
  return E;
}

// target は常に配布する最終 HTML の sha256。fixed を含め、古い HTML の hash は受理しない。
export function checkReview(review, html) {
  return reviewContractErrors(review, sha256(html));
}

/** 通常 build では許す意思決定ドラフトを、厳格 done では配布完成と混同しない。 */
export function checkStrictCompletion(html) {
  return hasPendingActions(html) ? ["厳格完了では data-source=\"pending\" の打ち手を残せません。担当・期限を確定して再 build する"] : [];
}

// 合格でも、渡すときにユーザーへ伝える、明示的に受容した must の一覧
export const unfixedMusts = (review) => (review?.findings || []).filter((f) => f.severity === "must" && f.status === "accepted");

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));

function main(argv) {
  const [mode, dirArg, flag] = argv;
  const pre = mode === "brief" && flag === "--pre"; // 調査の前: 背景データの照合だけを後回しにする (SKILL.md の Quickstart)
  if (!["brief", "results", "review"].includes(mode) || !dirArg || !existsSync(dirArg)) {
    console.error("使い方: node scripts/check-llm.mjs <brief|results|review> <レポートのフォルダ> [--pre (brief を調査の前に検査)]");
    return 2;
  }
  const dir = resolve(dirArg), name = basename(dir);
  const need = ["profile.json", "brief.json", ...(mode === "brief" ? [] : ["results.json", `${name}.html`]), ...(mode === "review" ? ["review.json"] : [])];
  const missing = need.filter((f) => !existsSync(join(dir, f)));
  if (missing.length) {
    console.error(`入力エラー: ${missing.join("・")} がありません (手順は SKILL.md の Quickstart)`);
    return 2;
  }
  let errors, unfixed = [];
  try {
    const brief = readJson(join(dir, "brief.json"));
    // 背景データ.csv (裏づけ) と 背景データ-反証.csv (反証・別の説明) を合わせて読む (prompts/research.md)
    const bgFiles = readdirSync(dir).filter((f) => BG_RE.test(f)).sort()
      .map((f) => ({ name: f, rows: parseCsv(readFileSync(join(dir, f), "utf8")) }));
    const background = mergeBackgroundFiles(bgFiles);
    errors = [...background.errors, ...checkBrief(brief, readJson(join(dir, "profile.json")), background.rows, { pre })];
    if (mode !== "brief") {
      const html = readFileSync(join(dir, `${name}.html`), "utf8"), results = readJson(join(dir, "results.json"));
      errors.push(...checkResults(results, brief, html), ...checkCauses(brief, html));
    }
    if (mode === "review") {
      const review = readJson(join(dir, "review.json"));
      const finalHtml = readFileSync(join(dir, `${name}.html`));
      errors.push(...checkReview(review, finalHtml), ...checkStrictCompletion(finalHtml));
      unfixed = unfixedMusts(review);
    }
  } catch (e) {
    console.error(`入力エラー: JSON を読めません (${e.message})`);
    return 2;
  }
  for (const e of errors) console.log(`  NG ${e}`);
  const label = pre ? `${mode} --pre` : mode;
  for (const f of unfixed) console.log(`  W  受容した must (${f.条件 || "?"}): ${f.指摘} — ${f.提案}`);
  console.log(errors.length ? `LLM 検査 (${label}): 不合格 (${errors.length})` : `LLM 検査 (${label}): 合格${unfixed.length ? ` (受容した must ${unfixed.length} 件。渡すときにユーザーへ伝える)` : ""}`);
  return errors.length ? 1 : 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main(process.argv.slice(2)));
