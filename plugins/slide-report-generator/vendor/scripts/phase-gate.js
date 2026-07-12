#!/usr/bin/env node
/**
 * Phase Gate Runner — Phase間の進行可否を判定
 *
 * Phase 2.5 仕様確定ゲートの実体。
 * P2 → P3 / P3 → P3.5 / P3.5 → 完了 の3ゲートを管理する。
 *
 * Usage:
 *   node phase-gate.js <project-dir> --from P2 --to P3
 *   node phase-gate.js <project-dir> --from P3 --to P3_5
 *   node phase-gate.js <project-dir> --from P3_5 --to complete
 *   node phase-gate.js <project-dir> --from P2 --to P3 --strict --report gate.json
 *
 * 終了コード:
 *   0: PASS（次フェーズに進行可）
 *   1: FAIL（差し戻し）
 *   2: WARN（要確認）
 *   3: 引数/環境エラー
 */

import { existsSync, readFileSync, writeFileSync } from "fs";
import { join, resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { spawnSync } from "child_process";
import { parseArgs, hasFlag } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const GATES = {
  "P2->P3": { name: "Phase 2.5 仕様確定ゲート", run: gateP2toP3 },
  "P3->P3_5": { name: "Phase 3 → 3.5 ゲート (HTML scaffold 確認)", run: gateP3toP3_5 },
  "P3_5->complete": { name: "Phase 3.5 → 完了ゲート (UI品質検証)", run: gateP3_5toComplete }
};

// ==================================================
// Gate 1: P2 → P3 (仕様確定ゲート)
// ==================================================

function gateP2toP3(projectDir, options) {
  const result = { gate: "P2->P3", checks: [], status: "PASS" };
  const structureMd = join(projectDir, "structure.md");
  const structureJson = join(projectDir, "structure.json");
  const approvedMarker = join(projectDir, ".approved");

  // 1. structure.md または structure.json 存在
  const hasMd = existsSync(structureMd);
  const hasJson = existsSync(structureJson);
  if (!hasMd && !hasJson) {
    result.checks.push({ name: "structure存在", status: "FAIL", detail: "structure.md / structure.json のいずれかが必要" });
    result.status = "FAIL";
    return result;
  }
  result.checks.push({
    name: "structure存在",
    status: "PASS",
    detail: `${hasMd ? "structure.md" : ""}${hasMd && hasJson ? " + " : ""}${hasJson ? "structure.json" : ""}`
  });

  // 2. validate-structure.js 実行（必須PASS）
  const targetPath = hasMd ? structureMd : structureJson;
  const args = [join(__dirname, "validate-structure.js"), targetPath];
  if (hasJson) args.push("--schema");
  if (options.strict) args.push("--strict");

  const validation = spawnSync("node", args, { encoding: "utf-8" });
  const exitCode = validation.status;
  const output = (validation.stdout || "") + (validation.stderr || "");

  if (exitCode === 0) {
    result.checks.push({ name: "validate-structure.js", status: "PASS", detail: "V-001〜V-030 検証OK" });
  } else if (exitCode === 2) {
    result.checks.push({ name: "validate-structure.js", status: "WARN", detail: "WARN項目あり（要目視確認）" });
    if (result.status === "PASS") result.status = "WARN";
  } else {
    result.checks.push({ name: "validate-structure.js", status: "FAIL", detail: `exit=${exitCode} - 詳細は validate-structure.js を直接実行` });
    result.status = "FAIL";
  }
  result._validationOutput = output;

  // 3. ユーザー承認マーカー（.approved）
  if (existsSync(approvedMarker)) {
    const ts = readFileSync(approvedMarker, "utf-8").trim() || "(空)";
    result.checks.push({ name: "ユーザー承認", status: "PASS", detail: `.approved マーカー: ${ts}` });
  } else {
    result.checks.push({
      name: "ユーザー承認",
      status: "FAIL",
      detail: ".approved マーカーが存在しません。structure-validator エージェントでユーザー承認を取得してください"
    });
    result.status = "FAIL";
  }

  return result;
}

// ==================================================
// Gate 2: P3 → P3.5 (HTML scaffold 確認)
// ==================================================

function gateP3toP3_5(projectDir, options) {
  const result = { gate: "P3->P3_5", checks: [], status: "PASS" };
  const required = [
    { name: "index.html", path: join(projectDir, "index.html") },
    { name: "styles.css", path: join(projectDir, "styles.css") },
    { name: "scripts.js", path: join(projectDir, "scripts.js") }
  ];

  for (const f of required) {
    if (existsSync(f.path)) {
      result.checks.push({ name: `${f.name}存在`, status: "PASS" });
    } else {
      result.checks.push({ name: `${f.name}存在`, status: "FAIL", detail: f.path });
      result.status = "FAIL";
    }
  }

  // index.html に slide-area 構造があるか簡易チェック
  const indexHtml = join(projectDir, "index.html");
  if (existsSync(indexHtml)) {
    const html = readFileSync(indexHtml, "utf-8");
    if (!html.includes("slide-area")) {
      result.checks.push({ name: "slide-area構造", status: "FAIL", detail: "index.html に .slide-area が見当たりません [SR-4-01]" });
      result.status = "FAIL";
    } else {
      result.checks.push({ name: "slide-area構造", status: "PASS" });
    }
    // V-020: CSS/JS分離（インライン<style>/<script>禁止）
    if (/<style[\s>]/i.test(html)) {
      result.checks.push({ name: "V-020 CSS分離", status: "FAIL", detail: "インライン <style> 検出" });
      result.status = "FAIL";
    }
    // V-020: 実行可能インラインJSのみ禁止。src= or type="application/json"（データブロック）は許容
    if (/<script(?![^>]*\bsrc=)(?![^>]*type\s*=\s*["']application\/json["'])[^>]*>[\s\S]*?<\/script>/i.test(html)) {
      result.checks.push({ name: "V-020 JS分離", status: "FAIL", detail: "インライン <script> 検出" });
      result.status = "FAIL";
    }
  }

  return result;
}

// ==================================================
// Gate 3: P3.5 → 完了 (UI品質検証)
// ==================================================

function gateP3_5toComplete(projectDir, options) {
  const result = { gate: "P3_5->complete", checks: [], status: "PASS" };
  const verifyScript = join(__dirname, "verify-slides.js");
  const indexHtml = join(projectDir, "index.html");

  if (!existsSync(indexHtml)) {
    result.checks.push({ name: "index.html存在", status: "FAIL", detail: indexHtml });
    result.status = "FAIL";
    return result;
  }

  if (!existsSync(verifyScript)) {
    result.checks.push({ name: "verify-slides.js存在", status: "FAIL", detail: verifyScript });
    result.status = "FAIL";
    return result;
  }

  const verify = spawnSync("node", [verifyScript, indexHtml], { encoding: "utf-8" });
  if (verify.status === 0) {
    result.checks.push({ name: "verify-slides.js", status: "PASS", detail: "全項目PASS" });
  } else {
    result.checks.push({
      name: "verify-slides.js",
      status: "FAIL",
      detail: `exit=${verify.status} - 詳細は verify-slides.js を直接実行`
    });
    result.status = "FAIL";
  }
  result._verifyOutput = (verify.stdout || "") + (verify.stderr || "");

  return result;
}

// ==================================================
// レポート出力
// ==================================================

function printResult(result, gateInfo) {
  const ICON = { PASS: "✅", FAIL: "❌", WARN: "⚠️ " };
  console.log("");
  console.log("═".repeat(64));
  console.log(`  ${gateInfo.name}: ${ICON[result.status]} ${result.status}`);
  console.log("═".repeat(64));
  result.checks.forEach(c => {
    console.log(`  ${ICON[c.status] || "  "} ${c.name}${c.detail ? `: ${c.detail}` : ""}`);
  });
  console.log("");
  if (result.status === "FAIL") {
    console.log("⛔ ゲート不合格: 前フェーズに差し戻してください。");
  } else if (result.status === "WARN") {
    console.log("⚠️  ゲート条件付き合格: 警告を確認してから進行してください。");
  } else {
    console.log("✅ ゲート合格: 次フェーズに進行可能です。");
  }
  console.log("");
}

// ==================================================
// CLI
// ==================================================

function showHelp() {
  console.log(`
Phase Gate Runner — Phase間の進行可否判定

Usage:
  node phase-gate.js <project-dir> --from <PHASE> --to <PHASE> [options]

Phases:
  P2, P3, P3_5, complete

Options:
  --strict        WARN を FAIL 扱いに格上げ
  --report <path> JSON レポート出力
  -h, --help      ヘルプ

サポートされるゲート:
  P2  → P3        : Phase 2.5 仕様確定ゲート（validate-structure.js + .approved）
  P3  → P3_5      : HTML scaffold 確認（index.html/styles.css/scripts.js）
  P3_5 → complete : UI品質検証（verify-slides.js）

終了コード:
  0: PASS
  1: FAIL
  2: WARN
  3: 引数/環境エラー
`);
}

function main() {
  const { flags, positional, options } = parseArgs();

  if (hasFlag(flags, "help", "h")) {
    showHelp();
    process.exit(0);
  }

  const projectDir = resolve(positional[0] || ".");
  const from = options.from;
  const to = options.to;

  if (!from || !to) {
    console.error("Error: --from <PHASE> --to <PHASE> が必須です");
    showHelp();
    process.exit(3);
  }

  if (!existsSync(projectDir)) {
    console.error(`Error: ディレクトリが存在しません: ${projectDir}`);
    process.exit(3);
  }

  const gateKey = `${from}->${to}`;
  const gateInfo = GATES[gateKey];
  if (!gateInfo) {
    console.error(`Error: 未対応の遷移: ${gateKey}`);
    console.error(`サポート: ${Object.keys(GATES).join(", ")}`);
    process.exit(3);
  }

  console.log(`📁 プロジェクト: ${projectDir}`);
  console.log(`🚪 ゲート: ${gateKey}`);

  const opts = { strict: hasFlag(flags, "strict") };
  const result = gateInfo.run(projectDir, opts);

  printResult(result, gateInfo);

  if (options.report) {
    writeFileSync(options.report, JSON.stringify(result, null, 2), "utf-8");
    console.log(`📄 レポート: ${options.report}`);
  }

  let exitCode = 0;
  if (result.status === "FAIL") exitCode = 1;
  else if (result.status === "WARN") exitCode = opts.strict ? 1 : 2;
  process.exit(exitCode);
}

main();
