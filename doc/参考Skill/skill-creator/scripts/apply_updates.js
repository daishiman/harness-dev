#!/usr/bin/env node

/**
 * 更新適用スクリプト
 *
 * 更新計画JSONに基づいてスキルファイルを更新します。
 *
 * 使用例:
 *   node scripts/apply_updates.js --plan .tmp/update-plan.json
 *   node scripts/apply_updates.js --plan .tmp/update-plan.json --dry-run
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 更新失敗
 */

import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  unlinkSync,
  renameSync,
  copyFileSync
} from "fs";
import { resolve, dirname, join, basename } from "path";
import { fileURLToPath } from "url";
import { EXIT_CODES, getArg } from "./utils.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function showHelp() {
  console.log(`
更新適用スクリプト

Usage:
  node apply_updates.js --plan <json-file> [options]

Options:
  --plan <file>     更新計画JSONファイル（必須）
  --dry-run         実際のファイル更新は行わず、計画を表示のみ
  --backup          更新前にバックアップを作成
  --output <path>   更新結果の出力先（デフォルト: .tmp/update-result.json）
  -h, --help        このヘルプを表示

Update Plan Format:
  {
    "skillPath": ".claude/skills/my-skill",
    "updates": [
      { "order": 1, "file": "SKILL.md", "category": "modify", "content": "..." }
    ]
  }

Categories:
  add     - 新規ファイル作成
  modify  - 既存ファイル更新
  delete  - ファイル削除
  rename  - ファイルリネーム
`);
}

function createBackup(filePath, backupDir) {
  if (!existsSync(filePath)) return null;

  if (!existsSync(backupDir)) {
    mkdirSync(backupDir, { recursive: true });
  }

  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const backupPath = join(backupDir, `${basename(filePath)}.${timestamp}.bak`);
  copyFileSync(filePath, backupPath);
  return backupPath;
}

function applyUpdate(update, skillPath, options) {
  const { dryRun, backup, backupDir } = options;
  const result = {
    file: update.file,
    category: update.category,
    success: false,
    message: "",
    backupPath: null
  };

  const filePath = join(skillPath, update.file);
  const resolvedPath = resolve(process.cwd(), filePath);

  try {
    switch (update.category) {
      case "add": {
        if (existsSync(resolvedPath)) {
          result.message = "ファイルが既に存在します（スキップ）";
          result.success = true;
          break;
        }

        if (dryRun) {
          result.message = `[DRY-RUN] 作成予定: ${filePath}`;
          result.success = true;
          break;
        }

        // ディレクトリ作成
        const dir = dirname(resolvedPath);
        if (!existsSync(dir)) {
          mkdirSync(dir, { recursive: true });
        }

        writeFileSync(resolvedPath, update.content, "utf-8");
        result.message = `作成完了: ${filePath}`;
        result.success = true;
        break;
      }

      case "modify": {
        if (!existsSync(resolvedPath)) {
          result.message = `ファイルが存在しません: ${filePath}`;
          result.success = false;
          break;
        }

        if (backup) {
          result.backupPath = createBackup(resolvedPath, backupDir);
        }

        if (dryRun) {
          result.message = `[DRY-RUN] 更新予定: ${filePath}`;
          result.success = true;
          break;
        }

        writeFileSync(resolvedPath, update.content, "utf-8");
        result.message = `更新完了: ${filePath}`;
        result.success = true;
        break;
      }

      case "delete": {
        if (!existsSync(resolvedPath)) {
          result.message = `ファイルが存在しません（スキップ）: ${filePath}`;
          result.success = true;
          break;
        }

        if (backup) {
          result.backupPath = createBackup(resolvedPath, backupDir);
        }

        if (dryRun) {
          result.message = `[DRY-RUN] 削除予定: ${filePath}`;
          result.success = true;
          break;
        }

        unlinkSync(resolvedPath);
        result.message = `削除完了: ${filePath}`;
        result.success = true;
        break;
      }

      case "rename": {
        if (!existsSync(resolvedPath)) {
          result.message = `ファイルが存在しません: ${filePath}`;
          result.success = false;
          break;
        }

        const newPath = join(skillPath, update.newFile);
        const resolvedNewPath = resolve(process.cwd(), newPath);

        if (backup) {
          result.backupPath = createBackup(resolvedPath, backupDir);
        }

        if (dryRun) {
          result.message = `[DRY-RUN] リネーム予定: ${filePath} → ${newPath}`;
          result.success = true;
          break;
        }

        // 新しいディレクトリが必要な場合は作成
        const newDir = dirname(resolvedNewPath);
        if (!existsSync(newDir)) {
          mkdirSync(newDir, { recursive: true });
        }

        renameSync(resolvedPath, resolvedNewPath);
        result.message = `リネーム完了: ${filePath} → ${newPath}`;
        result.success = true;
        break;
      }

      default:
        result.message = `未知のカテゴリ: ${update.category}`;
        result.success = false;
    }
  } catch (err) {
    result.message = `エラー: ${err.message}`;
    result.success = false;
  }

  return result;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const planPath = getArg(args, "--plan");
  const outputPath = getArg(args, "--output") || ".tmp/update-result.json";
  const dryRun = args.includes("--dry-run");
  const backup = args.includes("--backup");

  if (!planPath) {
    console.error("Error: --plan は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedPlan = resolve(process.cwd(), planPath);
  if (!existsSync(resolvedPlan)) {
    console.error(`Error: 計画ファイルが存在しません: ${resolvedPlan}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // 計画読み込み
  let plan;
  try {
    plan = JSON.parse(readFileSync(resolvedPlan, "utf-8"));
  } catch (err) {
    console.error(`Error: JSONの解析に失敗しました: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }

  if (!plan.skillPath || !plan.updates || !Array.isArray(plan.updates)) {
    console.error("Error: 計画JSONの形式が不正です（skillPath, updates が必須）");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // バックアップディレクトリ
  const backupDir = join(plan.skillPath, ".backup");

  // 更新を順序通りに適用
  const sortedUpdates = [...plan.updates].sort((a, b) => (a.order || 0) - (b.order || 0));
  const results = [];

  console.log(dryRun ? "=== DRY-RUN モード ===" : "=== 更新適用開始 ===");
  console.log(`スキルパス: ${plan.skillPath}`);
  console.log(`更新数: ${sortedUpdates.length}`);
  if (backup) console.log(`バックアップ: ${backupDir}`);
  console.log("");

  for (const update of sortedUpdates) {
    const result = applyUpdate(update, plan.skillPath, { dryRun, backup, backupDir });
    results.push(result);

    const icon = result.success ? "✓" : "✗";
    console.log(`${icon} [${update.order || "-"}] ${update.file}: ${result.message}`);
  }

  // 結果集計
  const successCount = results.filter((r) => r.success).length;
  const failCount = results.filter((r) => !r.success).length;

  const output = {
    timestamp: new Date().toISOString(),
    dryRun,
    skillPath: plan.skillPath,
    summary: {
      total: results.length,
      success: successCount,
      failed: failCount
    },
    results
  };

  // 出力ディレクトリ作成
  const outputDir = dirname(resolve(process.cwd(), outputPath));
  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // 結果を出力
  writeFileSync(resolve(process.cwd(), outputPath), JSON.stringify(output, null, 2), "utf-8");

  console.log("");
  console.log("=== 完了 ===");
  console.log(`成功: ${successCount}, 失敗: ${failCount}`);
  console.log(`結果出力: ${outputPath}`);

  if (failCount > 0) {
    process.exit(EXIT_CODES.APPLY_FAILED);
  }

  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
