#!/usr/bin/env node

/**
 * スキル使用記録スクリプト
 *
 * 18-skills.md §7.3 に準拠したフィードバック記録を行います。
 * LOGS fragment に実行ログを追記し、EVALS.jsonのメトリクスを更新します。
 *
 * 使用例:
 *   node log_usage.js --result success --phase "Phase 4" --notes "完了"
 *   node log_usage.js --result failure --phase "Phase 3" --error "ValidationError"
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { randomBytes } from "crypto";
import { join } from "path";
import {
  EXIT_CODES,
  getArg,
  hasArg,
  getSkillDir,
  nowISO,
} from "./utils.js";

const SKILL_DIR = getSkillDir(import.meta.url);

function escapeBranch(branch) {
  const escaped = branch
    .toLowerCase()
    .replace(/\//g, "-")
    .replace(/[^a-z0-9_-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "");
  return (escaped || "unknown").slice(0, 64);
}

function compactTimestamp(now) {
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getUTCFullYear()}${pad(now.getUTCMonth() + 1)}${pad(now.getUTCDate())}-${pad(now.getUTCHours())}${pad(now.getUTCMinutes())}${pad(now.getUTCSeconds())}`;
}

function writeLogFragment(body, timestamp) {
  const branch = escapeBranch(process.env.GIT_BRANCH || process.env.BRANCH || "unknown");
  const author = process.env.GIT_AUTHOR_EMAIL || process.env.USER || "claude-code";
  const dir = join(SKILL_DIR, "LOGS");
  mkdirSync(dir, { recursive: true });
  for (let i = 0; i < 4; i += 1) {
    const nonce = randomBytes(4).toString("hex");
    const file = join(dir, `${compactTimestamp(new Date(timestamp))}-${branch}-${nonce}.md`);
    if (existsSync(file)) continue;
    const content = `---\ntimestamp: ${timestamp.replace(/\.\d{3}Z$/, "Z")}\nbranch: ${branch}\nauthor: ${author}\ntype: log\n---\n${body.trimEnd()}\n`;
    writeFileSync(file, content, "utf-8");
    return;
  }
  throw new Error("fragment path collision unresolved after 4 attempts");
}

function showHelp() {
  console.log(`
スキル使用記録スクリプト (18-skills.md §7.3 準拠)

Usage:
  node log_usage.js [options]

Options:
  --result <success|failure>  実行結果（必須）
  --phase <name>              実行したPhase名（任意）
  --agent <name>              実行したエージェント名（任意）
  --duration <ms>             実行時間（ミリ秒、任意）
  --error <type>              エラータイプ（failure時、任意）
  --notes <text>              追加のフィードバックメモ（任意）
  -h, --help                  このヘルプを表示

Examples:
  node log_usage.js --result success
  node log_usage.js --result failure --phase "Phase 3" --notes "検証エラー"
  node log_usage.js --result success --phase "Phase 4" --agent "skill-creator"

Files updated:
  - LOGS fragment: 実行記録を追記
  - EVALS.json: メトリクスを更新（存在する場合）
  `);
}

function ensureEvalsFile() {
  const evalsPath = join(SKILL_DIR, "EVALS.json");
  if (!existsSync(evalsPath)) {
    const initialEvals = {
      skill_name: "skill-creator",
      current_level: 1,
      levels: {
        1: {
          name: "Beginner",
          requirements: { min_usage_count: 0, min_success_rate: 0 },
        },
        2: {
          name: "Intermediate",
          requirements: { min_usage_count: 5, min_success_rate: 0.6 },
        },
        3: {
          name: "Advanced",
          requirements: { min_usage_count: 15, min_success_rate: 0.75 },
        },
        4: {
          name: "Expert",
          requirements: { min_usage_count: 30, min_success_rate: 0.85 },
        },
      },
      metrics: {
        total_usage_count: 0,
        success_count: 0,
        failure_count: 0,
        average_satisfaction: 0,
        last_evaluated: null,
      },
    };
    writeFileSync(evalsPath, JSON.stringify(initialEvals, null, 2), "utf-8");
    console.log("✓ EVALS.json を新規作成しました");
  }
  return evalsPath;
}

async function main() {
  const args = process.argv.slice(2);

  if (hasArg(args, "-h", "--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  // 引数解析
  const result = getArg(args, "--result");
  const phase = getArg(args, "--phase") || "unknown";
  const agent = getArg(args, "--agent") || "unknown";
  const notes = getArg(args, "--notes") || "";

  // 引数検証
  if (!result || !["success", "failure"].includes(result)) {
    console.error(
      "Error: --result は success または failure を指定してください",
    );
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const timestamp = nowISO();

  // 1. LOGS fragment に追記
  try {
    const logEntry = `
## [${timestamp}]

- **Agent**: ${agent}
- **Phase**: ${phase}
- **Result**: ${result === "success" ? "✓ 成功" : "✗ 失敗"}
- **Notes**: ${notes || "なし"}

---
`;
    writeLogFragment(logEntry, timestamp);
    console.log(`✓ fragment ログに記録を追記しました`);
  } catch (err) {
    console.error(`Error: fragment ログの作成に失敗しました: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }

  // 2. EVALS.json を更新
  try {
    const evalsPath = ensureEvalsFile();
    const evalsData = JSON.parse(readFileSync(evalsPath, "utf-8"));

    // メトリクス更新
    evalsData.metrics.total_usage_count += 1;
    if (result === "success") {
      evalsData.metrics.success_count += 1;
    } else {
      evalsData.metrics.failure_count += 1;
    }
    evalsData.metrics.last_evaluated = timestamp;

    // 成功率計算
    const successRate =
      evalsData.metrics.total_usage_count > 0
        ? evalsData.metrics.success_count / evalsData.metrics.total_usage_count
        : 0;

    console.log(
      `✓ メトリクス更新: 使用回数=${evalsData.metrics.total_usage_count}, 成功率=${(successRate * 100).toFixed(1)}%`,
    );

    // 3. レベルアップ条件チェック
    const currentLevel = evalsData.current_level;
    const nextLevel = currentLevel + 1;

    if (evalsData.levels[nextLevel]) {
      const requirements = evalsData.levels[nextLevel].requirements;
      const canLevelUp =
        evalsData.metrics.total_usage_count >= requirements.min_usage_count &&
        successRate >= requirements.min_success_rate;

      if (canLevelUp) {
        evalsData.current_level = nextLevel;
        console.log(
          `🎉 レベルアップ: Level ${currentLevel} → Level ${nextLevel} (${evalsData.levels[nextLevel].name})`,
        );
      }
    }

    // EVALS.json を保存
    writeFileSync(evalsPath, JSON.stringify(evalsData, null, 2), "utf-8");
    console.log(`✓ EVALS.json を更新しました`);
  } catch (err) {
    console.error(`Error: EVALS.json の処理に失敗しました: ${err.message}`);
    process.exit(EXIT_CODES.ERROR);
  }

  console.log(`\n✓ フィードバック記録完了: ${result}`);
  process.exit(EXIT_CODES.SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_CODES.ERROR);
});
