#!/usr/bin/env node

/**
 * agents/*.md生成スクリプト
 *
 * Task定義JSONからagents/*.mdを生成します。
 *
 * 使用例:
 *   node scripts/generate_agent.js --task .tmp/tasks/analyze.json --output .claude/skills/my-skill/agents/analyze.md
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname, basename } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(`
agents/*.md生成スクリプト

Usage:
  node generate_agent.js --task <task-json> --output <output-path>

Options:
  --task <path>    Task定義JSONファイルのパス（必須）
  --output <path>  出力先agents/*.mdのパス（必須）
  -h, --help       このヘルプを表示

Task JSON形式:
  {
    "name": "analyze-request",
    "displayName": "Request Analyzer",
    "expertise": "要求分析",
    "background": "背景説明",
    "purpose": "目的",
    "responsibilities": [{ "task": "責務", "output": "成果物" }],
    "references": [{ "name": "書籍名", "application": "適用方法" }],
    "steps": [{ "step": 1, "action": "アクション" }],
    "checklist": [{ "item": "項目", "criteria": "基準" }],
    "constraints": [{ "name": "制約", "description": "説明" }],
    "input": { "name": "入力名", "source": "提供元", "validation": "検証ルール", "onMissing": "欠損時処理" },
    "output": { "name": "出力名", "destination": "受領先", "content": "内容" },
    "outputTemplate": "出力テンプレート"
  }

Examples:
  node scripts/generate_agent.js --task .tmp/tasks/analyze.json --output agents/analyze.md
`);
}


function generateAgentMd(task) {
  const name = task.name || "unknown";
  const displayName = task.displayName || name;
  const expertise = task.expertise || "TODO";
  const background = task.background || "TODO: 背景を記述";
  const purpose = task.purpose || "TODO: 目的を記述";

  // 責務テーブル
  const responsibilities = task.responsibilities || [{ task: "TODO", output: "TODO" }];
  const respTable = responsibilities.map((r) => `| ${r.task} | ${r.output} |`).join("\n");

  // 参考文献テーブル
  const references = task.references || [];
  const refTable = references.length > 0
    ? references.map((r) => `| ${r.name} | ${r.application} |`).join("\n")
    : "| TODO: 書籍/ドキュメント | TODO: 適用方法 |";

  // 思考プロセステーブル
  const steps = task.steps || [{ step: 1, action: "TODO: アクションを記述" }];
  const stepsTable = steps.map((s) => `| ${s.step} | ${s.action} |`).join("\n");

  // チェックリストテーブル
  const checklist = task.checklist || [{ item: "出力検証", criteria: "すべての必須項目が含まれている" }];
  const checkTable = checklist.map((c) => `| ${c.item} | ${c.criteria} |`).join("\n");

  // 制約テーブル
  const constraints = task.constraints || [];
  const constraintTable = constraints.length > 0
    ? constraints.map((c) => `| ${c.name} | ${c.description} |`).join("\n")
    : "| 単一責務 | このTaskは1つの責務のみを担う |";

  // 入力テーブル
  const input = task.input || { name: "TODO", source: "TODO", validation: "TODO", onMissing: "TODO" };
  const inputRow = `| ${input.name} | ${input.source} | ${input.validation} | ${input.onMissing} |`;

  // 出力テーブル
  const output = task.output || { name: "TODO", destination: "TODO", content: "TODO" };
  const outputRow = `| ${output.name} | ${output.destination} | ${output.content} |`;

  // 出力テンプレート
  const outputTemplate = task.outputTemplate || `{
  "taskName": "${name}",
  "result": "TODO"
}`;

  const content = `# Task仕様書：${displayName}

## 1. メタ情報

| 項目     | 内容                |
| -------- | ------------------- |
| 名前     | ${displayName}      |
| 専門領域 | ${expertise}        |

> 注記: 「名前」は思考様式の参照ラベル。本人を名乗らず、方法論のみ適用する。

---

## 2. プロフィール

### 2.1 背景

${background}

### 2.2 目的

${purpose}

### 2.3 責務

| 責務 | 成果物 |
| ---- | ------ |
${respTable}

---

## 3. 知識ベース

### 3.1 参考文献

| 書籍/ドキュメント | 適用方法 |
| ----------------- | -------- |
${refTable}

---

## 4. 実行仕様

### 4.1 思考プロセス

| ステップ | アクション |
| -------- | ---------- |
${stepsTable}

### 4.2 チェックリスト

| 項目 | 基準 |
| ---- | ---- |
${checkTable}

### 4.3 ビジネスルール（制約）

| 制約 | 説明 |
| ---- | ---- |
${constraintTable}

---

## 5. インターフェース

### 5.1 入力

| データ名 | 提供元 | 検証ルール | 欠損時処理 |
| -------- | ------ | ---------- | ---------- |
${inputRow}

### 5.2 出力

| 成果物名 | 受領先 | 内容 |
| -------- | ------ | ---- |
${outputRow}

#### 出力テンプレート

\`\`\`json
${outputTemplate}
\`\`\`
`;

  return content;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const taskPath = getArg(args, "--task");
  const outputPath = getArg(args, "--output");

  if (!taskPath) {
    console.error("Error: --task は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!outputPath) {
    console.error("Error: --output は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedTask = resolvePath(taskPath);
  const resolvedOutput = resolvePath(outputPath);

  if (!existsSync(resolvedTask)) {
    console.error(`Error: Task定義ファイルが存在しません: ${resolvedTask}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const task = JSON.parse(readFileSync(resolvedTask, "utf-8"));

    // 必須フィールドの検証
    if (!task.name) {
      console.error("Error: Task定義にnameが含まれていません");
      process.exit(EXIT_CODES.VALIDATION_FAILED);
    }

    const content = generateAgentMd(task);

    // 出力ディレクトリの作成
    const outputDir = dirname(resolvedOutput);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(resolvedOutput, content, "utf-8");
    console.log(`✓ agents/${basename(resolvedOutput)}を生成しました`);
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
