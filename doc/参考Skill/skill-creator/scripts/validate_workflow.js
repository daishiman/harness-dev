#!/usr/bin/env node

/**
 * ワークフロー検証スクリプト
 *
 * ワークフロー設計JSONが有効かを検証します。
 *
 * 使用例:
 *   node scripts/validate_workflow.js --input .tmp/workflow.json
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

function showHelp() {
  console.log(`
ワークフロー検証スクリプト

Usage:
  node validate_workflow.js --input <workflow-json> [options]

Options:
  --input <path>   ワークフローJSONファイルのパス（必須）
  --verbose        詳細な検証結果を表示
  -h, --help       このヘルプを表示

Validation checks:
  - 必須フィールドの存在（skillName, pattern, tasks, phases）
  - タスク名の一意性
  - 依存関係の整合性（存在しないタスクへの依存がない）
  - 循環依存の検出
  - 並列グループの整合性
  - 全タスクがいずれかのフェーズに属している

Examples:
  node scripts/validate_workflow.js --input .tmp/workflow.json
  node scripts/validate_workflow.js --input .tmp/workflow.json --verbose
`);
}

function detectCircularDependencies(tasks) {
  const visited = new Set();
  const recursionStack = new Set();
  const cycles = [];

  function dfs(taskName, path = []) {
    if (recursionStack.has(taskName)) {
      const cycleStart = path.indexOf(taskName);
      cycles.push(path.slice(cycleStart).concat(taskName));
      return;
    }
    if (visited.has(taskName)) return;

    visited.add(taskName);
    recursionStack.add(taskName);
    path.push(taskName);

    const task = tasks.find((t) => t.name === taskName);
    if (task && task.dependsOn) {
      for (const dep of task.dependsOn) {
        dfs(dep, [...path]);
      }
    }

    recursionStack.delete(taskName);
  }

  for (const task of tasks) {
    if (!visited.has(task.name)) {
      dfs(task.name);
    }
  }

  return cycles;
}

function validateWorkflow(workflow) {
  const errors = [];
  const warnings = [];

  // 必須フィールドの検証
  if (!workflow.skillName) {
    errors.push("skillNameが必須です");
  }
  if (!workflow.pattern) {
    errors.push("patternが必須です");
  }
  if (!workflow.tasks || !Array.isArray(workflow.tasks)) {
    errors.push("tasksが必須です（配列）");
  }
  if (!workflow.phases || !Array.isArray(workflow.phases)) {
    errors.push("phasesが必須です（配列）");
  }

  if (errors.length > 0) {
    return { errors, warnings };
  }

  const tasks = workflow.tasks;
  const phases = workflow.phases;

  // タスク名の一意性
  const taskNames = tasks.map((t) => t.name);
  const duplicates = taskNames.filter((name, index) => taskNames.indexOf(name) !== index);
  if (duplicates.length > 0) {
    errors.push(`重複するタスク名: ${[...new Set(duplicates)].join(", ")}`);
  }

  // 各タスクの検証
  const taskNameSet = new Set(taskNames);
  for (const task of tasks) {
    if (!task.name) {
      errors.push("タスクにnameが必須です");
      continue;
    }
    if (!task.type || !["llm", "script"].includes(task.type)) {
      errors.push(`${task.name}: typeはllmまたはscriptである必要があります`);
    }
    if (!task.responsibility) {
      warnings.push(`${task.name}: responsibilityが未定義です`);
    }
    if (!task.executionPattern || !["seq", "par", "cond", "loop", "agg"].includes(task.executionPattern)) {
      warnings.push(`${task.name}: executionPatternが不正または未定義です`);
    }

    // 依存関係の検証
    if (task.dependsOn) {
      for (const dep of task.dependsOn) {
        if (!taskNameSet.has(dep)) {
          errors.push(`${task.name}: 存在しないタスクへの依存: ${dep}`);
        }
      }
    }
  }

  // 循環依存の検出
  const cycles = detectCircularDependencies(tasks);
  if (cycles.length > 0) {
    for (const cycle of cycles) {
      errors.push(`循環依存を検出: ${cycle.join(" -> ")}`);
    }
  }

  // フェーズの検証
  const allPhaseTasks = new Set();
  for (const phase of phases) {
    if (!phase.name) {
      errors.push("フェーズにnameが必須です");
    }
    if (!phase.tasks || !Array.isArray(phase.tasks)) {
      errors.push(`${phase.name || "unknown"}: tasksが必須です（配列）`);
      continue;
    }
    for (const taskName of phase.tasks) {
      if (!taskNameSet.has(taskName)) {
        errors.push(`${phase.name}: 存在しないタスクがフェーズに含まれています: ${taskName}`);
      }
      allPhaseTasks.add(taskName);
    }
  }

  // すべてのタスクがいずれかのフェーズに属しているか
  for (const taskName of taskNames) {
    if (!allPhaseTasks.has(taskName)) {
      warnings.push(`${taskName}: どのフェーズにも属していません`);
    }
  }

  // 並列グループの検証
  if (workflow.parallelGroups) {
    for (const group of workflow.parallelGroups) {
      if (!group.name) {
        warnings.push("並列グループにnameが未定義です");
      }
      if (!group.tasks || !Array.isArray(group.tasks)) {
        errors.push(`${group.name || "unknown"}: 並列グループにtasksが必須です`);
        continue;
      }
      for (const taskName of group.tasks) {
        if (!taskNameSet.has(taskName)) {
          errors.push(`${group.name}: 存在しないタスクが並列グループに含まれています: ${taskName}`);
        }
      }
      if (group.syncPoint && !taskNameSet.has(group.syncPoint)) {
        errors.push(`${group.name}: syncPointが存在しないタスクを参照: ${group.syncPoint}`);
      }
    }
  }

  return { errors, warnings };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const verbose = args.includes("--verbose");
  const inputPath = getArg(args, "--input");

  if (!inputPath) {
    console.error("Error: --input は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedInput = resolvePath(inputPath);

  if (!existsSync(resolvedInput)) {
    console.error(`Error: ファイルが存在しません: ${resolvedInput}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const workflow = JSON.parse(readFileSync(resolvedInput, "utf-8"));
    const { errors, warnings } = validateWorkflow(workflow);

    if (verbose) {
      console.log(`ワークフロー: ${workflow.skillName || "unknown"}`);
      console.log(`パターン: ${workflow.pattern || "unknown"}`);
      console.log(`タスク数: ${(workflow.tasks || []).length}`);
      console.log(`フェーズ数: ${(workflow.phases || []).length}`);
    }

    if (warnings.length > 0) {
      console.log("\n⚠ 警告:");
      warnings.forEach((w) => console.log(`  - ${w}`));
    }

    if (errors.length > 0) {
      console.log("\n✗ エラー:");
      errors.forEach((e) => console.log(`  - ${e}`));
      console.log(`\n結果: ✗ 検証失敗`);
      process.exit(EXIT_CODES.VALIDATION_FAILED);
    }

    console.log(`\n✓ ワークフロー検証成功: ${inputPath}`);
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
