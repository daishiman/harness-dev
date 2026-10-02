#!/usr/bin/env node
// 通常変更と CI 向けの高速スモークテスト。重い変異・統計・描画回帰は selftest.mjs に分離する。
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { buildReport } from "./build-report.mjs";
import { checkReport } from "./check-report.mjs";
import { REVIEW_CONDITIONS, reviewContractErrors, sha256, SKILL_DIR } from "./lib.mjs";
import { pipelineSteps } from "./report.mjs";
import { verifyVendor } from "./sync-kit.mjs";
import { parseSheet, sheetIssues } from "./hearing.mjs";
import { buildHandout, checkHandout, handoutModel } from "./build-handout.mjs";

export function smokeTest() {
  const failures = [];
  let checks = 0;
  const ok = (condition, message) => {
    checks += 1;
    if (!condition) failures.push(message);
  };

  ok(verifyVendor().ok, "vendor CSS が SOURCE.json と一致しない");

  try {
    const source = readFileSync(join(SKILL_DIR, "assets/template.src.html"), "utf8");
    const html = buildReport(source);
    ok(html === buildReport(source), "同じソースからの生成結果が一致しない");
    const checked = checkReport(html);
    ok(checked.errors.length === 0 && checked.warnings.length === 0, `テンプレート検査が不合格: ${[...checked.errors, ...checked.warnings].join(" / ")}`);
  } catch (error) {
    ok(false, `テンプレートを生成できない: ${error.message}`);
  }

  try {
    const sheet = parseSheet(readFileSync(join(SKILL_DIR, "assets/hearing.sample.md"), "utf8"));
    const issues = sheetIssues(sheet);
    ok(issues.length === 0, `見本のヒアリングシートに指摘が出る: ${issues.map((x) => `${x.where} ${x.text}`).join(" / ")}`);
    const model = handoutModel(sheet);
    const checked = checkHandout(buildHandout(model), model);
    ok(checked.errors.length === 0, `見本の実行部隊向け資料が不合格: ${checked.errors.join(" / ")}`);
  } catch (error) {
    ok(false, `見本の実行部隊向け資料を生成できない: ${error.message}`);
  }

  const build = pipelineSteps("build", "/tmp/2026-05-sample", "2026-05-sample");
  const verify = pipelineSteps("verify", "/tmp/2026-05-sample", "2026-05-sample");
  ok(build.length === 3 && !build.some(([script]) => script === "verify-render.mjs"), "通常 build に実描画が混入している");
  ok(verify.some(([script]) => script === "verify-render.mjs") && verify.some(([script, action]) => script === "build-state.mjs" && action === "record"), "verify に実描画または証跡記録がない");

  const htmlHash = sha256("final report");
  const review = {
    target: htmlHash,
    条件: Object.fromEntries(REVIEW_CONDITIONS.map((condition) => [condition, "PASS"])),
    findings: [],
  };
  ok(reviewContractErrors(review, htmlHash).length === 0, "正常な review 契約が不合格になる");
  ok(reviewContractErrors(review, sha256("changed report")).length > 0, "古い review の対象 hash を検出できない");

  return { checks, failures };
}

function main() {
  const result = smokeTest();
  if (result.failures.length) {
    for (const failure of result.failures) console.error(`NG: ${failure}`);
    console.error(`smoke-test: 不合格 (${result.failures.length}/${result.checks}項目)`);
    return 1;
  }
  console.log(`smoke-test: 合格 (${result.checks}項目)`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) process.exit(main());
