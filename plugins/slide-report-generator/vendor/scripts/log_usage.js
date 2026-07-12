#!/usr/bin/env node

/**
 * スキル使用記録スクリプト
 *
 * 18-skills.md §7.3 に準拠したフィードバック記録を行います。
 */

import { appendFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

const EXIT_SUCCESS = 0;
const EXIT_ARGS_ERROR = 2;

function showHelp() {
  console.log(`
Usage: node log_usage.js [options]

Options:
  --result <success|failure>  実行結果（必須）
  --phase <name>              実行したPhase名（任意）
  --agent <name>              実行したエージェント名（任意）
  --notes <text>              追加のフィードバックメモ（任意）
  -h, --help                  このヘルプを表示
  `);
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const getArg = (name) => {
    const index = args.indexOf(name);
    return index !== -1 && args[index + 1] ? args[index + 1] : null;
  };

  const result = getArg("--result");
  const phase = getArg("--phase") || "unknown";
  const agent = getArg("--agent") || "unknown";
  const notes = getArg("--notes") || "";

  if (!result || !["success", "failure"].includes(result)) {
    console.error("Error: --result は success または failure を指定してください");
    process.exit(EXIT_ARGS_ERROR);
  }

  const timestamp = new Date().toISOString();
  const logEntry = `
## [${timestamp}]
- Agent: ${agent}
- Phase: ${phase}
- Result: ${result}
- Notes: ${notes || "なし"}
---
`;

  const logsPath = join(SKILL_DIR, "LOGS.md");

  try {
    appendFileSync(logsPath, logEntry, "utf-8");
    console.log(`✓ フィードバックを記録しました: ${result}`);
  } catch (err) {
    // LOGS.md が存在しない場合は新規作成
    const header = `# Skill Usage Logs

このファイルにはスキルの使用記録が追記されます。

---
`;
    appendFileSync(logsPath, header + logEntry, "utf-8");
    console.log(`✓ LOGS.md を作成し、フィードバックを記録しました`);
  }

  process.exit(EXIT_SUCCESS);
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(1);
});
