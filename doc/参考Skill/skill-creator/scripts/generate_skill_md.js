#!/usr/bin/env node

/**
 * SKILL.md生成スクリプト
 *
 * 構造計画JSONからSKILL.mdを生成します。
 *
 * 使用例:
 *   node scripts/generate_skill_md.js --plan .tmp/structure-plan.json --output .claude/skills/my-skill/SKILL.md
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";
import {
  validateSkillMdContent,
  MAX_DESC_LENGTH,
  MAX_ANCHORS,
  MAX_TRIGGER_KEYWORDS,
} from "./utils/validate-skill-md.js";
import { toDoubleQuotedScalar } from "./utils/yaml-escape.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

function showHelp() {
  console.log(`
SKILL.md生成スクリプト

Usage:
  node generate_skill_md.js --plan <plan-json> --output <output-path>

Options:
  --plan <path>    構造計画JSONファイルのパス（必須）
  --output <path>  出力先SKILL.mdのパス（必須）
  --template <path> テンプレートファイルのパス（任意）
  -h, --help       このヘルプを表示

Examples:
  node scripts/generate_skill_md.js --plan .tmp/structure-plan.json --output .claude/skills/my-skill/SKILL.md
`);
}


function capitalize(str) {
  return str.split("-").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

function generateSkillMd(plan) {
  const today = new Date().toISOString().split("T")[0];
  const skillName = plan.skillName;
  const dirs = plan.directories || {};
  const files = plan.files || [];
  const workflow = plan.workflow || {};

  // Frontmatter生成
  const anchorsAll = workflow.anchors || [];
  const trigger = workflow.trigger || { description: "TODO: 発動条件", keywords: ["TODO"] };
  const triggerKeywordsAll = trigger.keywords || [];

  // Codex 検証準拠: Anchors > 5 件 / Trigger keywords > 15 件は references/ に退避し、
  // SKILL.md には主要のみを残す（description ≤ 1024 字制約を満たすため）。
  const anchors = anchorsAll.slice(0, MAX_ANCHORS);
  const anchorsOverflow = anchorsAll.slice(MAX_ANCHORS);
  const triggerKeywords = triggerKeywordsAll.slice(0, MAX_TRIGGER_KEYWORDS);
  const triggerKeywordsOverflow = triggerKeywordsAll.slice(MAX_TRIGGER_KEYWORDS);

  const anchorLines = anchors.length > 0
    ? anchors.map((a) => `  • ${a.name} / 適用: ${a.application} / 目的: ${a.purpose}`).join("\n")
    : "  • TODO: アンカー名 / 適用: 適用範囲 / 目的: 目的";

  const triggerLine = trigger.description + "\n  " + triggerKeywords.join(", ");

  // ワークフロー図生成
  const phases = workflow.phases || [];
  const workflowDiagram = phases.length > 0
    ? phases.map((p, i) => `Phase ${i + 1}: ${p.name}\n${p.tasks.map((t) => `  - ${t}`).join("\n")}`).join("\n\n")
    : "TODO: ワークフローを定義";

  // Task一覧生成
  const tasks = workflow.tasks || [];
  const llmTasks = tasks.filter((t) => t.type === "llm");
  const scriptTasks = tasks.filter((t) => t.type === "script");

  const llmTaskTable = llmTasks.length > 0
    ? llmTasks.map((t) => `| ${t.name} | ${t.responsibility} | ${t.input || "-"} | ${t.output || "-"} | ${t.validationScript || "-"} |`).join("\n")
    : "| TODO | TODO | TODO | TODO | - |";

  const scriptTaskTable = scriptTasks.length > 0
    ? scriptTasks.map((t) => `| \`${t.name}.js\` | ${t.responsibility} | ${t.input || "-"} | ${t.output || "-"} | 0:成功 |`).join("\n")
    : "| TODO | TODO | TODO | TODO | 0:成功 |";

  // agents/テーブル生成
  const agentFiles = files.filter((f) => f.type === "agent");
  const agentTable = agentFiles.length > 0
    ? agentFiles.map((f) => `| ${basename(f.path, ".md")} | [${f.path}](${f.path}) | ${f.responsibility} |`).join("\n")
    : "";

  // scripts/テーブル生成
  const scriptFiles = files.filter((f) => f.type === "script");
  const scriptTable = scriptFiles.length > 0
    ? scriptFiles.map((f) => `| \`${basename(f.path)}\` | ${f.responsibility} | \`node ${f.path}\` |`).join("\n")
    : "";

  // references/テーブル生成
  const refFiles = files.filter((f) => f.type === "reference");
  const refTable = refFiles.length > 0
    ? refFiles.map((f) => `| ${basename(f.path, ".md")} | [${f.path}](${f.path}) | ${f.responsibility} |`).join("\n")
    : "";

  // assets/テーブル生成
  const assetFiles = files.filter((f) => f.type === "asset");
  const assetTable = assetFiles.length > 0
    ? assetFiles.map((f) => `| \`${basename(f.path)}\` | ${f.responsibility} |`).join("\n")
    : "";

  // schemas/テーブル生成
  const schemaFiles = files.filter((f) => f.type === "schema");
  const schemaTable = schemaFiles.length > 0
    ? schemaFiles.map((f) => `| ${basename(f.path, ".json")} | [${f.path}](${f.path}) | ${f.responsibility} |`).join("\n")
    : "";

  const descriptionText = `${workflow.summary || "TODO: スキルの概要説明"}

Anchors:
${anchorLines}

Trigger:
${triggerLine}`;

  const content = `---
name: ${skillName}
description: ${toDoubleQuotedScalar(descriptionText)}
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
---

# ${capitalize(skillName)}

## 概要

${workflow.summary || "TODO: スキルの目的を1-2文で説明"}

## ワークフロー

\`\`\`
${workflowDiagram}
\`\`\`

## Task一覧

### LLM Tasks（判断が必要）

| Task | 責務 | 入力 | 出力 | 検証スクリプト |
|------|------|------|------|----------------|
${llmTaskTable}

### Script Tasks（決定論的実行）

| Script | 責務 | 入力 | 出力 | 終了コード |
|--------|------|------|------|------------|
${scriptTaskTable}

## ベストプラクティス

### すべきこと

| 推奨事項 | 理由 |
|----------|------|
| LLM出力は必ずスキーマ検証 | 曖昧さを排除し再現性確保 |
| Script TaskはLLMに依存しない | 100%決定論的実行を保証 |
| 各Taskは独立して実行可能に | 部分的な再実行を可能に |

### 避けるべきこと

| 禁止事項 | 問題点 |
|----------|--------|
| LLM出力を検証せず次へ進む | エラーの連鎖を招く |
| 複数責務を1タスクに詰め込む | 再実行・デバッグが困難に |

## リソース参照
${scriptTable ? `
### scripts/（決定論的処理）

| スクリプト | 機能 | 使用例 |
|------------|------|--------|
${scriptTable}
` : ""}
${agentTable ? `
### agents/（LLM Task仕様）

| Task | パス | 責務 |
|------|------|------|
${agentTable}
` : ""}
${schemaTable ? `
### schemas/（入出力スキーマ）

| スキーマ | パス | 用途 |
|----------|------|------|
${schemaTable}
` : ""}
${assetTable ? `
### assets/（テンプレート）

| テンプレート | 用途 |
|--------------|------|
${assetTable}
` : ""}
${refTable ? `
### references/（詳細知識）

| リソース | パス | 読込条件 |
|----------|------|----------|
${refTable}
` : ""}

## 変更履歴

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | ${today} | 初版作成 |
`;

  // Codex 検証準拠: 書き込み前に R-01〜R-05 を強制（description ≤ 1024 字 / YAML 構文）。
  const validation = validateSkillMdContent(content);
  if (!validation.ok) {
    throw new Error(
      `[skill-creator] generate_skill_md.js: SKILL.md 検証失敗 (description ≥ ${MAX_DESC_LENGTH} 字超過などの可能性):\n  - ${validation.errors.join("\n  - ")}`,
    );
  }

  return {
    content,
    anchorsOverflow,
    triggerKeywordsOverflow,
  };
}

/**
 * 退避が必要な Anchors / Trigger keywords を references/ に書き出す。
 *
 * @param {string} skillDir - SKILL.md があるディレクトリ
 * @param {Array} anchorsOverflow
 * @param {string[]} triggerKeywordsOverflow
 */
function writeOverflowReferences(skillDir, anchorsOverflow, triggerKeywordsOverflow) {
  if (anchorsOverflow.length > 0) {
    const referencesDir = join(skillDir, "references");
    if (!existsSync(referencesDir)) mkdirSync(referencesDir, { recursive: true });
    const lines = [
      "# Anchors（退避）",
      "",
      "SKILL.md description の文字数制約 (≤ 1024 字) を満たすため、上限 (5 件) を超えた Anchors をここに退避する。",
      "",
      ...anchorsOverflow.map((a) => `- ${a.name} / 適用: ${a.application} / 目的: ${a.purpose}`),
      "",
    ];
    writeFileSync(join(referencesDir, "anchors.md"), lines.join("\n"), "utf-8");
  }

  if (triggerKeywordsOverflow.length > 0) {
    const referencesDir = join(skillDir, "references");
    if (!existsSync(referencesDir)) mkdirSync(referencesDir, { recursive: true });
    const lines = [
      "# Trigger keywords（退避）",
      "",
      "SKILL.md description の文字数制約 (≤ 1024 字) を満たすため、上限 (15 件) を超えた Trigger keywords をここに退避する。",
      "",
      ...triggerKeywordsOverflow.map((k) => `- ${k}`),
      "",
    ];
    writeFileSync(join(referencesDir, "triggers.md"), lines.join("\n"), "utf-8");
  }
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const planPath = getArg(args, "--plan");
  const outputPath = getArg(args, "--output");

  if (!planPath) {
    console.error("Error: --plan は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!outputPath) {
    console.error("Error: --output は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedPlan = resolvePath(planPath);
  const resolvedOutput = resolvePath(outputPath);

  if (!existsSync(resolvedPlan)) {
    console.error(`Error: 構造計画ファイルが存在しません: ${resolvedPlan}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const plan = JSON.parse(readFileSync(resolvedPlan, "utf-8"));

    // 必須フィールドの検証
    if (!plan.skillName) {
      console.error("Error: 構造計画にskillNameが含まれていません");
      process.exit(EXIT_CODES.VALIDATION_FAILED);
    }

    const { content, anchorsOverflow, triggerKeywordsOverflow } = generateSkillMd(plan);

    // 出力ディレクトリの作成
    const outputDir = dirname(resolvedOutput);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(resolvedOutput, content, "utf-8");

    // Anchors / Trigger keywords の退避（上限超過分）
    writeOverflowReferences(outputDir, anchorsOverflow, triggerKeywordsOverflow);
    console.log(`✓ SKILL.mdを生成しました: ${outputPath}`);
    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    if (err instanceof SyntaxError) {
      console.error(`Error: JSONの解析に失敗しました: ${err.message}`);
    } else {
      console.error(`Error: ${err.message}`);
    }
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
