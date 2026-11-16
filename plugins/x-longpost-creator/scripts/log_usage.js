#!/usr/bin/env node

/**
 * スキル使用記録スクリプト
 *
 * スキルの実行結果（成功・失敗・失敗理由）を記録先へ追記します。
 * 記録先の解決規則は下の resolveLogPath を参照。
 *
 * Usage:
 *   node log_usage.js --result success --phase "Phase 4"
 *   node log_usage.js --result failure --phase "Phase 3" --error "ValidationError"
 */

const fs = require("fs");
const path = require("path");

const EXIT_SUCCESS = 0;
const EXIT_ARGS_ERROR = 2;

/**
 * 記録先を解決する。
 *
 * 記録は plugin 本体（配布物）の中には書かない。plugin ディレクトリを実行時に
 * 書き換えると、配布された全環境で差分が出て「plugin の実体 = 配布物」が崩れる。
 * よって XLP_LOG_FILE → ${XLP_OUTPUT_DIR}/x-longpost-usage-log.md の順で解決し、
 * どちらも未設定なら記録先が存在しないものとして null を返す（推測パスへ書かない）。
 */
function resolveLogPath() {
  if (process.env.XLP_LOG_FILE) return process.env.XLP_LOG_FILE;
  if (process.env.XLP_OUTPUT_DIR) {
    return path.join(process.env.XLP_OUTPUT_DIR, "x-longpost-usage-log.md");
  }
  return null;
}

function showHelp() {
  console.log(`
Usage: node log_usage.js [options]

Options:
  --result <success|failure>  実行結果（必須）
  --phase <name>              実行したPhase名（任意）
  --agent <name>              実行したエージェント名（任意）
  --notes <text>              追加のフィードバックメモ（任意）
  --error <text>              エラー内容（failureの場合）
  -h, --help                  このヘルプを表示
  `);
}

function parseArgs(args) {
  const result = {};
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "-h" || args[i] === "--help") {
      result.help = true;
    } else if (args[i] === "--result" && args[i + 1]) {
      result.result = args[++i];
    } else if (args[i] === "--phase" && args[i + 1]) {
      result.phase = args[++i];
    } else if (args[i] === "--agent" && args[i + 1]) {
      result.agent = args[++i];
    } else if (args[i] === "--notes" && args[i + 1]) {
      result.notes = args[++i];
    } else if (args[i] === "--error" && args[i + 1]) {
      result.error = args[++i];
    }
  }
  return result;
}

function main() {
  const args = process.argv.slice(2);
  const parsed = parseArgs(args);

  if (parsed.help) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const result = parsed.result;
  const phase = parsed.phase || "unknown";
  const agent = parsed.agent || "unknown";
  const notes = parsed.notes || "";
  const error = parsed.error || "";

  if (!result || !["success", "failure"].includes(result)) {
    console.error("Error: --result は success または failure を指定してください");
    process.exit(EXIT_ARGS_ERROR);
  }

  const timestamp = new Date().toISOString();
  let logEntry = `
## [${timestamp}]
- Agent: ${agent}
- Phase: ${phase}
- Result: ${result}`;

  if (error) {
    logEntry += `
- Error: ${error}`;
  }

  logEntry += `
- Notes: ${notes || "なし"}
---
`;

  const logsPath = resolveLogPath();
  if (!logsPath) {
    console.error(
      "SKIP 記録先が未設定のため使用記録を書き込みません（XLP_LOG_FILE または XLP_OUTPUT_DIR を設定してください）"
    );
    process.exit(EXIT_SUCCESS);
  }

  const header = `# Skill Usage Logs

このファイルにはスキルの使用記録が追記されます。

---
`;
  const isNew = !fs.existsSync(logsPath);
  fs.mkdirSync(path.dirname(logsPath), { recursive: true });
  fs.appendFileSync(logsPath, (isNew ? header : "") + logEntry, "utf-8");
  console.log(`OK フィードバックを記録しました: ${result} -> ${logsPath}`);

  process.exit(EXIT_SUCCESS);
}

main();
