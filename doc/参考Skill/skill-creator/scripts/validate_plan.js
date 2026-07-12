#!/usr/bin/env node

/**
 * 構造計画検証スクリプト
 *
 * 構造計画JSONが有効かを検証します。
 *
 * 使用例:
 *   node scripts/validate_plan.js --input .tmp/structure-plan.json
 *
 * 終了コード:
 *   0: 検証成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, existsSync } from "fs";
import { dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

function showHelp() {
  console.log(`
構造計画検証スクリプト

Usage:
  node validate_plan.js --input <plan-json> [options]

Options:
  --input <path>   構造計画JSONファイルのパス（必須）
  --verbose        詳細な検証結果を表示
  -h, --help       このヘルプを表示

Validation checks:
  - 必須フィールドの存在（skillName, directories, files）
  - スキル名がハイフンケースで64文字以内
  - ファイルパスが有効な相対パス
  - ディレクトリ設定の整合性
  - 各ファイルの責務が定義されている
  - 重複するファイルパスがない

Examples:
  node scripts/validate_plan.js --input .tmp/structure-plan.json
  node scripts/validate_plan.js --input .tmp/structure-plan.json --verbose
`);
}

function validatePlan(plan) {
  const errors = [];
  const warnings = [];

  // 必須フィールドの検証
  if (!plan.skillName) {
    errors.push("skillNameが必須です");
  } else {
    // スキル名の形式検証
    if (plan.skillName.length > 64) {
      errors.push(`skillNameが64文字を超えています: ${plan.skillName.length}文字`);
    }
    if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(plan.skillName)) {
      errors.push(`skillNameがハイフンケースではありません: ${plan.skillName}`);
    }
  }

  if (!plan.directories) {
    errors.push("directoriesが必須です");
  }

  if (!plan.files || !Array.isArray(plan.files)) {
    errors.push("filesが必須です（配列）");
  }

  if (errors.length > 0) {
    return { errors, warnings };
  }

  const directories = plan.directories;
  const files = plan.files;

  // ディレクトリ設定の検証
  const validDirs = ["agents", "scripts", "references", "assets", "schemas"];
  for (const dir of validDirs) {
    if (directories[dir]) {
      if (typeof directories[dir].required !== "boolean") {
        warnings.push(`directories.${dir}.requiredがbooleanではありません`);
      }
      if (!directories[dir].reason) {
        warnings.push(`directories.${dir}.reasonが未定義です`);
      }
    }
  }

  // ファイルパスの検証
  const filePaths = new Set();
  const validTypes = ["skill-md", "agent", "script", "reference", "asset", "schema"];
  const validPatterns = ["seq", "par", "cond", "loop", "agg"];

  for (const file of files) {
    if (!file.path) {
      errors.push("ファイルにpathが必須です");
      continue;
    }

    // 重複チェック
    if (filePaths.has(file.path)) {
      errors.push(`重複するファイルパス: ${file.path}`);
    }
    filePaths.add(file.path);

    // パス形式の検証
    if (file.path.startsWith("/")) {
      errors.push(`絶対パスは使用できません: ${file.path}`);
    }
    if (file.path.includes("../")) {
      errors.push(`../を含むパスは使用できません: ${file.path}`);
    }

    // タイプの検証
    if (!file.type || !validTypes.includes(file.type)) {
      errors.push(`${file.path}: typeが不正です（${validTypes.join(", ")}のいずれか）`);
    }

    // 責務の検証
    if (!file.responsibility) {
      warnings.push(`${file.path}: responsibilityが未定義です`);
    }

    // agentの場合、executionPatternの検証
    if (file.type === "agent" && file.executionPattern) {
      if (!validPatterns.includes(file.executionPattern)) {
        warnings.push(`${file.path}: executionPatternが不正です（${validPatterns.join(", ")}のいずれか）`);
      }
    }

    // ディレクトリとの整合性
    const fileDir = file.path.split("/")[0];
    if (fileDir === "agents" && directories.agents && !directories.agents.required) {
      warnings.push(`${file.path}: agents/は必要なしと設定されていますがファイルが定義されています`);
    }
    if (fileDir === "scripts" && directories.scripts && !directories.scripts.required) {
      warnings.push(`${file.path}: scripts/は必要なしと設定されていますがファイルが定義されています`);
    }
    if (fileDir === "references" && directories.references && !directories.references.required) {
      warnings.push(`${file.path}: references/は必要なしと設定されていますがファイルが定義されています`);
    }
    if (fileDir === "assets" && directories.assets && !directories.assets.required) {
      warnings.push(`${file.path}: assets/は必要なしと設定されていますがファイルが定義されています`);
    }
    if (fileDir === "schemas" && directories.schemas && !directories.schemas.required) {
      warnings.push(`${file.path}: schemas/は必要なしと設定されていますがファイルが定義されています`);
    }
  }

  // SKILL.mdが含まれているか
  const hasSkillMd = files.some((f) => f.path === "SKILL.md" || f.type === "skill-md");
  if (!hasSkillMd) {
    errors.push("SKILL.md（type: skill-md）がファイル一覧に含まれていません");
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
    const plan = JSON.parse(readFileSync(resolvedInput, "utf-8"));
    const { errors, warnings } = validatePlan(plan);

    if (verbose) {
      console.log(`スキル名: ${plan.skillName || "unknown"}`);
      console.log(`ファイル数: ${(plan.files || []).length}`);
      const dirs = plan.directories || {};
      const requiredDirs = Object.entries(dirs)
        .filter(([_, v]) => v && v.required)
        .map(([k]) => k);
      console.log(`必要なディレクトリ: ${requiredDirs.join(", ") || "なし"}`);
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

    console.log(`\n✓ 構造計画検証成功: ${inputPath}`);
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
