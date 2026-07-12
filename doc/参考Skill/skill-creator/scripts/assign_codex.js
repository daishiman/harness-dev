#!/usr/bin/env node
/**
 * Assign Codex Skill - Codex (GPT-5.2) にタスクを割り当てるスクリプト
 *
 * 使用方法:
 *   node assign_codex.js --task <タスク内容> [options]
 *
 * オプション:
 *   --task, -t        実行するタスク内容（必須）
 *   --context, -x     短いコンテキスト（直接指定）
 *   --context-file    長いコンテキスト用ファイルパス
 *   --output, -o      出力先ディレクトリ
 *   --model           使用するモデル（デフォルト: gpt-5.2）
 *   --timeout         タイムアウト秒数（デフォルト: 1200）
 *   --dry-run         実行せずにコマンドを表示
 *   --verbose, -v     詳細ログ出力
 *   -h, --help        ヘルプを表示
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般エラー
 *   2: 引数エラー
 *   3: 事前条件エラー
 *   4: Codex実行エラー
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import { EXIT_CODES } from "./utils.js";

// ============================================================================
// 設定
// ============================================================================

const CONFIG = {
  model: "gpt-5.2",
  timeoutMs: 1200000, // 20分
  maxBuffer: 50 * 1024 * 1024, // 50MB
  outputDirPrefix: "codex/assign-codex",
  tempFileName: ".codex-prompt-temp.md",
};

// ============================================================================
// ユーティリティ
// ============================================================================

/** @param {string} message */
const log = (message) => console.error(`[Codex] ${message}`);

/** @param {string} message */
const logVerbose = (message, verbose) => verbose && console.error(`[Codex:verbose] ${message}`);

/**
 * 安全なファイル削除
 * @param {string} filePath
 */
const safeUnlink = (filePath) => {
  try {
    if (existsSync(filePath)) unlinkSync(filePath);
  } catch {
    // 削除失敗は無視
  }
};

/**
 * タスク名をファイル名に安全に変換
 * @param {string} task
 * @returns {string}
 */
const sanitizeTaskName = (task) =>
  task
    .replace(/[^a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 30) || "task";

/**
 * 今日の日付をYYYYMMDD形式で取得
 * @returns {string}
 */
const getTodayString = () => new Date().toISOString().slice(0, 10).replace(/-/g, "");

// ============================================================================
// コア機能
// ============================================================================

function showHelp() {
  console.log(`
Assign Codex Skill - Codex (GPT-5.2) にタスクを割り当てる

Usage:
  node assign_codex.js --task <タスク内容> [options]

Options:
  --task, -t        実行するタスク内容（必須）
  --context, -x     短いコンテキスト（直接指定）
  --context-file    長いコンテキスト用ファイルパス
  --output, -o      出力先ディレクトリ
  --model           使用するモデル（デフォルト: ${CONFIG.model}）
  --timeout         タイムアウト秒数（デフォルト: ${CONFIG.timeoutMs / 1000}）
  --dry-run         実行せずにコマンドを表示
  --verbose, -v     詳細ログ出力
  -h, --help        ヘルプを表示

Examples:
  node assign_codex.js --task "READMEを生成して"
  node assign_codex.js --task "コードレビュー" --context-file context.md
  node assign_codex.js --task "テスト作成" --output ./codex-output --verbose
`);
}

/**
 * 引数をパース
 * @returns {Record<string, any>}
 */
function parseArguments() {
  try {
    const { values } = parseArgs({
      options: {
        task: { type: "string", short: "t" },
        context: { type: "string", short: "x" },
        "context-file": { type: "string" },
        output: { type: "string", short: "o" },
        model: { type: "string" },
        timeout: { type: "string" },
        "dry-run": { type: "boolean" },
        verbose: { type: "boolean", short: "v" },
        help: { type: "boolean", short: "h" },
      },
      strict: true,
    });
    return values;
  } catch (error) {
    console.error(`引数エラー: ${error.message}`);
    process.exit(EXIT_CODES.ARGS_ERROR);
  }
}

/**
 * 事前条件をチェック
 * @returns {{ passed: boolean, errors: string[] }}
 */
function checkPrerequisites() {
  const errors = [];
  const checks = [
    {
      name: "gitリポジトリ",
      command: "git rev-parse --is-inside-work-tree",
      errorMsg: "gitリポジトリではありません。`git init` を実行してください。",
    },
    {
      name: "Codex CLI",
      command: "which codex",
      errorMsg: "Codex CLIがインストールされていません。",
    },
  ];

  for (const check of checks) {
    try {
      execSync(check.command, { encoding: "utf-8", stdio: ["pipe", "pipe", "pipe"] });
    } catch {
      errors.push(check.errorMsg);
    }
  }

  return { passed: errors.length === 0, errors };
}

/**
 * 出力ディレクトリを作成
 * @param {string} task
 * @param {string | undefined} customOutput
 * @returns {string}
 */
function createOutputDir(task, customOutput) {
  const outputDir = customOutput
    ? resolve(customOutput)
    : resolve(process.cwd(), `${CONFIG.outputDirPrefix}-${getTodayString()}-${sanitizeTaskName(task)}`);

  if (!existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  return outputDir;
}

/**
 * コンテキストを取得
 * @param {string | undefined} contextArg
 * @param {string | undefined} contextFile
 * @returns {string}
 */
function getContext(contextArg, contextFile) {
  if (contextFile) {
    if (!existsSync(contextFile)) {
      console.error(`警告: コンテキストファイルが見つかりません: ${contextFile}`);
      return contextArg || "";
    }
    return readFileSync(contextFile, "utf-8");
  }
  return contextArg || "";
}

/**
 * プロンプトを構築
 * @param {string} task
 * @param {string} context
 * @returns {string}
 */
function buildPrompt(task, context) {
  return context ? `${task}\n\n## コンテキスト\n${context}` : task;
}

/**
 * Codexを呼び出し
 * @param {object} options
 * @param {string} options.prompt
 * @param {string} options.outputDir
 * @param {string} options.model
 * @param {number} options.timeout
 * @param {boolean} options.dryRun
 * @param {boolean} options.verbose
 * @returns {Promise<{ status: string, content: string, durationMs?: number, exitCode?: number }>}
 */
async function callCodex({ prompt, outputDir, model, timeout, dryRun, verbose }) {
  const tempPromptPath = join(outputDir, CONFIG.tempFileName);

  try {
    writeFileSync(tempPromptPath, prompt, "utf-8");
    logVerbose(`一時ファイル作成: ${tempPromptPath}`, verbose);

    // プロンプトをBase64エンコードしてシェル補間を回避
    const promptBase64 = Buffer.from(prompt).toString("base64");
    const command = `echo "${promptBase64}" | base64 -d | codex exec --dangerously-bypass-approvals-and-sandbox --model "${model}" -`;

    if (dryRun) {
      log("Dry Run モード - 実行をスキップ");
      console.log("\n実行されるコマンド:");
      console.log(`codex exec --dangerously-bypass-approvals-and-sandbox --model "${model}" "<prompt>"`);
      console.log("\nプロンプト内容:");
      console.log(prompt);
      return { status: "dry-run", content: "Dry run mode - 実行されませんでした" };
    }

    log(`${model} にリクエスト中...`);
    const startTime = Date.now();

    const result = execSync(command, {
      encoding: "utf-8",
      maxBuffer: CONFIG.maxBuffer,
      timeout,
      stdio: ["pipe", "pipe", "pipe"],
    });

    const durationMs = Date.now() - startTime;
    log(`成功 (${(durationMs / 1000).toFixed(1)}秒)`);

    return { status: "fulfilled", content: result.trim(), durationMs, exitCode: 0 };
  } catch (error) {
    const durationMs = Date.now() - (error.startTime || Date.now());
    const errorMessage = error.stderr || error.message || "不明なエラー";

    log(`エラー: ${errorMessage.slice(0, 200)}`);
    logVerbose(`詳細: ${JSON.stringify({ code: error.code, signal: error.signal })}`, verbose);

    return {
      status: "rejected",
      content: errorMessage,
      durationMs,
      exitCode: error.status || 1,
    };
  } finally {
    safeUnlink(tempPromptPath);
    logVerbose("一時ファイル削除完了", verbose);
  }
}

/**
 * 結果を保存（schemas/codex-result.json準拠）
 * @param {object} options
 * @param {string} options.outputDir
 * @param {string} options.task
 * @param {string} options.context
 * @param {object} options.codexResult
 * @param {string} options.model
 * @param {boolean} options.verbose
 * @returns {object}
 */
function saveResults({ outputDir, task, context, codexResult, model, verbose }) {
  const timestamp = new Date().toISOString();
  const isSuccess = codexResult.status === "fulfilled";
  const codexContent = isSuccess ? codexResult.content : `（エラー: ${codexResult.content}）`;

  // 1. タスク内容を保存
  const taskPath = join(outputDir, "task.md");
  writeFileSync(taskPath, `# タスク\n\n${task}`, "utf-8");
  logVerbose(`保存: ${taskPath}`, verbose);

  // 2. Codex結果を保存
  const codexPath = join(outputDir, "codex-response.md");
  writeFileSync(codexPath, `# Codex (${model}) の実行結果\n\n${codexContent}`, "utf-8");
  logVerbose(`保存: ${codexPath}`, verbose);

  // 3. 統合結果（Markdown）
  const resultMd = [
    `# Assign Codex: ${task}`,
    "",
    "## タスク",
    task,
    "",
    ...(context ? ["## 共有コンテキスト", context, ""] : []),
    `## Codex (${model}) の実行結果`,
    codexContent,
    "",
    "---",
    `*生成日時: ${timestamp}*`,
    `*モデル: ${model}*`,
    `*ステータス: ${codexResult.status}*`,
    ...(codexResult.durationMs ? [`*実行時間: ${(codexResult.durationMs / 1000).toFixed(1)}秒*`] : []),
  ].join("\n");

  const resultMdPath = join(outputDir, "result.md");
  writeFileSync(resultMdPath, resultMd, "utf-8");
  logVerbose(`保存: ${resultMdPath}`, verbose);

  // 4. 統合結果（JSON - schemas/codex-result.json準拠）
  const resultJson = {
    success: isSuccess,
    task,
    model,
    outputDir,
    files: {
      taskFile: taskPath,
      responseFile: codexPath,
      resultMd: resultMdPath,
      resultJson: join(outputDir, "result.json"),
    },
    response: {
      content: codexResult.content,
      truncated: codexResult.content.length > 100000,
      length: codexResult.content.length,
    },
    execution: {
      startTime: new Date(Date.now() - (codexResult.durationMs || 0)).toISOString(),
      endTime: timestamp,
      durationMs: codexResult.durationMs || 0,
      exitCode: codexResult.exitCode || 0,
    },
    ...(isSuccess ? {} : {
      error: {
        message: codexResult.content,
        code: codexResult.exitCode?.toString() || "UNKNOWN",
      },
    }),
    timestamp,
  };

  const resultJsonPath = join(outputDir, "result.json");
  writeFileSync(resultJsonPath, JSON.stringify(resultJson, null, 2), "utf-8");
  log(`結果保存: ${outputDir}`);

  return resultJson;
}

// ============================================================================
// メイン処理
// ============================================================================

async function main() {
  const args = parseArguments();

  if (args.help) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  if (!args.task) {
    console.error("エラー: --task オプションは必須です");
    showHelp();
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  // 事前条件チェック
  const prereqResult = checkPrerequisites();
  if (!prereqResult.passed) {
    console.error("事前条件エラー:");
    prereqResult.errors.forEach((e) => console.error(`  - ${e}`));
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  // パラメータ準備
  const task = args.task;
  const context = getContext(args.context, args["context-file"]);
  const model = args.model || CONFIG.model;
  const timeout = args.timeout ? parseInt(args.timeout, 10) * 1000 : CONFIG.timeoutMs;
  const dryRun = args["dry-run"] || false;
  const verbose = args.verbose || false;

  // 開始ログ
  console.error("=== Assign Codex Skill ===");
  console.error(`タスク: ${task.slice(0, 50)}${task.length > 50 ? "..." : ""}`);
  console.error(`モデル: ${model}`);
  console.error(`タイムアウト: ${timeout / 1000}秒`);
  if (context) console.error(`コンテキスト: ${context.length}文字`);
  if (dryRun) console.error("モード: Dry Run");
  console.error("");

  // 出力ディレクトリ作成
  const outputDir = createOutputDir(task, args.output);
  logVerbose(`出力先: ${outputDir}`, verbose);

  // Codex呼び出し
  const prompt = buildPrompt(task, context);
  const codexResult = await callCodex({ prompt, outputDir, model, timeout, dryRun, verbose });

  // 結果保存
  const resultJson = saveResults({ outputDir, task, context, codexResult, model, verbose });

  // 標準出力にJSON出力（パイプライン連携用）
  console.log(JSON.stringify(resultJson, null, 2));

  console.error("\n=== 完了 ===");

  if (!resultJson.success) {
    process.exit(EXIT_CODES.CODEX_ERROR);
  }
}

main().catch((error) => {
  console.error("予期せぬエラー:", error?.message ?? error);
  process.exit(EXIT_CODES.ERROR);
});
