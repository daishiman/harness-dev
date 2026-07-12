#!/usr/bin/env node
/**
 * log_usage.js - 契約書生成スキルの使用記録
 *
 * フィードバックループ用スクリプト。
 * 使用回数、成功/失敗、生成された契約書の種類を記録する。
 *
 * Usage:
 *   node scripts/log_usage.js --status success --type ai-business
 *   node scripts/log_usage.js --status error --reason "missing-info"
 *   node scripts/log_usage.js --help
 *
 * Exit codes:
 *   0 - Success
 *   1 - General error
 *   2 - Argument error
 */

const { writeFileSync, readFileSync, existsSync } = require("fs");
const { join } = require("path");

const LOGS_PATH = join(__dirname, "..", "LOGS.md");

// 引数解析
const args = process.argv.slice(2);

if (args.includes("-h") || args.includes("--help")) {
  console.log(`
Usage: node log_usage.js [options]

Options:
  --status <success|error>   使用結果のステータス (required)
  --type <type>              契約書の種類 (ai-business|it|consulting|design|other)
  --reason <reason>          エラー理由 (status=error時)
  --clauses <number>         生成された条項数
  -h, --help                 このヘルプを表示

Exit codes:
  0 - Success
  1 - General error
  2 - Argument error
  `);
  process.exit(0);
}

// 引数取得
function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) return null;
  return args[index + 1];
}

const status = getArg("status");
const type = getArg("type") || "other";
const reason = getArg("reason") || "";
const clauses = getArg("clauses") || "28";

if (!status || !["success", "error"].includes(status)) {
  console.error("Error: --status must be 'success' or 'error'");
  process.exit(2);
}

// ログエントリ作成
const timestamp = new Date().toISOString();
const entry = `| ${timestamp} | ${status} | ${type} | ${clauses} | ${reason || "-"} |`;

// ログファイル更新
try {
  let content = "";

  if (existsSync(LOGS_PATH)) {
    content = readFileSync(LOGS_PATH, "utf-8");
  } else {
    // 新規作成時のヘッダー
    content = `# Contract Generator Usage Logs

## フィードバックループ記録

| Timestamp | Status | Type | Clauses | Reason |
|-----------|--------|------|---------|--------|
`;
  }

  // エントリを追加
  const lines = content.split("\n");
  const headerEndIndex = lines.findIndex((line) => line.startsWith("|---"));

  if (headerEndIndex !== -1) {
    lines.splice(headerEndIndex + 1, 0, entry);
  } else {
    lines.push(entry);
  }

  writeFileSync(LOGS_PATH, lines.join("\n"));

  console.log(`Logged: ${status} - ${type} (${clauses} clauses)`);
  process.exit(0);
} catch (error) {
  console.error(`Error writing log: ${error.message}`);
  process.exit(1);
}
