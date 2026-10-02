#!/usr/bin/env node
// 読み手向けの意味を保つ回帰。selftest.mjs は同じ ok(condition, message) を渡す。
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { SKILL_DIR } from "./lib.mjs";
import { markTerms } from "./glossary.mjs";
import { hiddenWords, parseSheet, sheetIssues } from "./hearing.mjs";
import { buildHandout, checkHandout, handoutModel } from "./build-handout.mjs";

export function runContentChecks(ok) {
  // 汎用の効果量をdと決めつけず、V・順位効果の既存の説明も使えること。
  const effect = markTerms('<section><p>効果量 Cramér の V=0.5、順位効果 r=0.5</p></section>');
  const general = effect.used.find((term) => term.id === "gl-effect");
  ok(general?.label === "効果量" && !/0\.2|0\.5|0\.8/.test(general.how), "汎用の効果量にdの名称・閾値を固定しない");
  ok(effect.used.some((term) => term.id === "gl-chisq") && effect.used.some((term) => term.id === "gl-mw"), "Vと順位効果にはそれぞれの説明を残す");
  ok(!effect.used.some((term) => term.id === "gl-corr"), "順位効果 r を相関係数の説明へ結び付けない");
  ok(markTerms('<section><p>Cohen の d=-0.8</p></section>').used.some((term) => term.id === "gl-effect"), "dの説明への入口を失わない");

  // 1文字の名前や識別子も、利用者が非表示に指定したらシートと出力の両方で止める。
  const sample = readFileSync(join(SKILL_DIR, "assets/hearing.sample.md"), "utf8");
  const clean = parseSheet(sample);
  ok(sheetIssues(clean).length === 0, "記入済みの資料見本はヒアリング検査を通る");
  for (const word of ["A", "7", "あ", "A社"]) {
    const sheet = parseSheet(sample);
    sheet.sections.cover.items[0].題名 = `${word}への資料`;
    sheet.sections.hidden.items[0].語句 = word;
    ok(hiddenWords(sheet).includes(word), `非表示指定「${word}」を黙って捨てない`);
    ok(sheetIssues(sheet).some((issue) => issue.kind === "見せない情報"), `シート内の非表示語句「${word}」を検出する`);
    const model = handoutModel(sheet);
    ok(checkHandout(buildHandout(model), model).errors.some((error) => error.startsWith("H04 ")), `出力内の非表示語句「${word}」を検出する`);
  }
  const empty = { sections: { hidden: { items: [{ 語句: "、 なし、わからない、 " }] } } };
  ok(hiddenWords(empty).length === 0, "空欄・なし・回答待ちの語は非表示指定に数えない");
  const model = handoutModel(clean);
  ok(checkHandout(buildHandout(model), model).errors.length === 0, "指定語句を含まない見本資料は生成検査を通る");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const failures = [];
  let count = 0;
  runContentChecks((condition, message) => { count += 1; if (!condition) failures.push(message); });
  for (const message of failures) console.error(`NG: ${message}`);
  console.log(failures.length ? `content checks: FAIL (${failures.length}/${count})` : `content checks: PASS (${count})`);
  process.exitCode = failures.length ? 1 : 0;
}
