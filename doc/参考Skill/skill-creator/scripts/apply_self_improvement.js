#!/usr/bin/env node
/**
 * 自己改善適用スクリプト
 *
 * LLMが設計した改善計画を実際に適用する。
 * 決定論的な処理（LLM不要）。
 *
 * 使用方法:
 *   node scripts/apply_self_improvement.js --plan <path> [options]
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般エラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 適用失敗
 */

import {
  readFileSync,
  writeFileSync,
  existsSync,
  mkdirSync,
  copyFileSync,
} from "fs";
import { dirname, join, basename } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(`
自己改善適用スクリプト

Usage:
  node apply_self_improvement.js --plan <path> [options]

Options:
  --plan <path>     改善計画JSONファイルパス（必須）
  --dry-run         実行せずに内容を表示
  --auto-only       自動適用可能なもののみ適用
  --backup          変更前にバックアップを作成
  --all             全ての変更を適用（レビュー済み前提）
  --verbose         詳細出力
  -h, --help        ヘルプ表示
`);
}

// バックアップを作成
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

// 変更を適用
function applyChange(change, options) {
  const { dryRun = false, backup = false, verbose = false } = options;

  const targetPath = resolvePath(change.target.file);

  if (verbose) {
    console.log(`\n変更ID: ${change.id}`);
    console.log(`  対象: ${change.target.file}`);
    console.log(`  タイプ: ${change.type}`);
    console.log(`  理由: ${change.reason}`);
  }

  // dry-runの場合は表示のみ
  if (dryRun) {
    console.log(`\n[dry-run] ${change.id}:`);
    console.log(`  ファイル: ${change.target.file}`);
    console.log(`  操作: ${change.type}`);
    if (change.content.before) {
      console.log(`  変更前: ${change.content.before.substring(0, 100)}...`);
    }
    if (change.content.after) {
      console.log(`  変更後: ${change.content.after.substring(0, 100)}...`);
    }
    return { success: true, dryRun: true };
  }

  try {
    // バックアップ
    let backupPath = null;
    if (backup && existsSync(targetPath)) {
      const backupDir = join(dirname(targetPath), ".backup");
      backupPath = createBackup(targetPath, backupDir);
      if (verbose && backupPath) {
        console.log(`  バックアップ: ${backupPath}`);
      }
    }

    // 変更適用
    switch (change.type) {
      case "add": {
        // 新規追加またはファイル末尾に追加
        if (!existsSync(targetPath)) {
          const dir = dirname(targetPath);
          if (!existsSync(dir)) {
            mkdirSync(dir, { recursive: true });
          }
          writeFileSync(targetPath, change.content.after, "utf-8");
        } else {
          const content = readFileSync(targetPath, "utf-8");
          writeFileSync(
            targetPath,
            content + "\n" + change.content.after,
            "utf-8"
          );
        }
        break;
      }

      case "modify": {
        if (!existsSync(targetPath)) {
          throw new Error(`ファイルが存在しません: ${targetPath}`);
        }
        let content = readFileSync(targetPath, "utf-8");

        if (change.content.before) {
          // 特定の文字列を置換
          if (!content.includes(change.content.before)) {
            throw new Error(
              `変更対象の文字列が見つかりません: ${change.content.before.substring(0, 50)}...`
            );
          }
          content = content.replace(
            change.content.before,
            change.content.after
          );
        } else if (change.target.lineRange) {
          // 行範囲を置換
          const lines = content.split("\n");
          const { start, end } = change.target.lineRange;
          const newLines = change.content.after.split("\n");
          lines.splice(start - 1, end - start + 1, ...newLines);
          content = lines.join("\n");
        } else {
          throw new Error("変更対象が指定されていません");
        }

        writeFileSync(targetPath, content, "utf-8");
        break;
      }

      case "delete": {
        if (!existsSync(targetPath)) {
          // 既に存在しない場合は成功扱い
          break;
        }

        if (change.content.before) {
          // 特定の文字列を削除
          let content = readFileSync(targetPath, "utf-8");
          content = content.replace(change.content.before, "");
          writeFileSync(targetPath, content, "utf-8");
        } else {
          // ファイル全体を削除は危険なのでスキップ
          throw new Error("ファイル全体の削除は手動で行ってください");
        }
        break;
      }

      default:
        throw new Error(`不明な変更タイプ: ${change.type}`);
    }

    return { success: true, backupPath };
  } catch (err) {
    return { success: false, error: err.message };
  }
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const planPath = getArg(args, "--plan");
  const dryRun = args.includes("--dry-run");
  const autoOnly = args.includes("--auto-only");
  const backup = args.includes("--backup");
  const applyAll = args.includes("--all");
  const verbose = args.includes("--verbose");

  if (!planPath) {
    console.error("Error: --plan は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedPlan = resolvePath(planPath);

  if (!existsSync(resolvedPlan)) {
    console.error(`Error: 改善計画ファイルが存在しません: ${resolvedPlan}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const plan = JSON.parse(readFileSync(resolvedPlan, "utf-8"));

    if (!plan.changes || !Array.isArray(plan.changes)) {
      console.error("Error: 改善計画に changes が含まれていません");
      process.exit(EXIT_CODES.ARGS_ERROR);
    }

    console.log(`改善計画: ${plan.skillName || "unknown"}`);
    console.log(`変更数: ${plan.changes.length}`);

    if (dryRun) {
      console.log("\n[dry-run モード] 変更は適用されません\n");
    }

    // 適用対象の変更をフィルタリング
    let changesToApply = plan.changes;

    if (autoOnly) {
      changesToApply = plan.changes.filter((c) => c.autoApplicable === true);
      console.log(
        `自動適用可能: ${changesToApply.length}/${plan.changes.length}`
      );
    } else if (!applyAll) {
      // デフォルトは低リスクのみ
      changesToApply = plan.changes.filter((c) => c.riskLevel === "low");
      console.log(`低リスク変更: ${changesToApply.length}/${plan.changes.length}`);
    }

    if (changesToApply.length === 0) {
      console.log("\n適用可能な変更がありません");
      process.exit(EXIT_CODES.SUCCESS);
    }

    // 実行順序に従って適用
    const executionOrder =
      plan.executionOrder || changesToApply.map((c) => c.id);
    const results = [];

    for (const changeId of executionOrder) {
      const change = changesToApply.find((c) => c.id === changeId);
      if (!change) continue;

      const result = applyChange(change, { dryRun, backup, verbose });
      results.push({ changeId, ...result });

      if (!result.success && !dryRun) {
        console.error(`\n✗ ${changeId} の適用に失敗: ${result.error}`);
        // 失敗しても続行（他の変更は独立している場合が多い）
      } else if (result.success && !dryRun) {
        console.log(`✓ ${changeId} を適用しました`);
      }
    }

    // サマリ
    const successCount = results.filter((r) => r.success).length;
    const failCount = results.filter((r) => !r.success).length;

    console.log(`\n完了: ${successCount}成功, ${failCount}失敗`);

    if (failCount > 0 && !dryRun) {
      process.exit(EXIT_CODES.APPLY_FAILED);
    }

    // 検証コマンドの表示
    if (plan.postValidation && plan.postValidation.length > 0 && !dryRun) {
      console.log("\n検証コマンド:");
      plan.postValidation.forEach((cmd) => console.log(`  ${cmd}`));
    }

    process.exit(EXIT_CODES.SUCCESS);
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
