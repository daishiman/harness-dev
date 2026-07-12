#!/usr/bin/env node

/**
 * {{スクリプト名}}
 *
 * {{スクリプトの目的と機能説明}}
 *
 * 使用例:
 *   node scripts/{{script-name}}.js --input <file> [options]
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般的なエラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 処理失敗
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_DIR = join(__dirname, "..");

const EXIT_SUCCESS = 0;
const EXIT_ERROR = 1;
const EXIT_ARGS_ERROR = 2;
const EXIT_FILE_NOT_FOUND = 3;
const EXIT_PROCESS_FAILED = 4;

/**
 * ヘルプメッセージを表示
 */
function showHelp() {
  console.log(`
{{スクリプト名}}

Usage:
  node {{script-name}}.js --input <file> [options]

Options:
  --input <file>    入力ファイルパス（必須）
  --output <file>   出力先（デフォルト: stdout）
  --template <file> テンプレートファイル（任意）
  --verbose         詳細な出力を表示
  -h, --help        このヘルプを表示

Examples:
  node scripts/{{script-name}}.js --input data.json
  node scripts/{{script-name}}.js --input data.json --output result.md
`);
}

/**
 * コマンドライン引数を取得
 * @param {string[]} args - 引数配列
 * @param {string} name - 引数名
 * @returns {string|null} 引数値
 */
function getArg(args, name) {
  const index = args.indexOf(name);
  return index !== -1 && args[index + 1] ? args[index + 1] : null;
}

/**
 * パスを解決
 * @param {string} p - パス
 * @returns {string} 解決されたパス
 */
function resolvePath(p) {
  if (p.startsWith("/")) {
    return p;
  }
  // assets/ で始まる場合はスキルディレクトリからの相対パス
  if (p.startsWith("assets/") || p.startsWith("schemas/")) {
    return join(SKILL_DIR, p);
  }
  return resolve(process.cwd(), p);
}

/**
 * テンプレート変数を置換
 * @param {string} template - テンプレート文字列
 * @param {object} data - 変数データ
 * @returns {string} 置換後の文字列
 */
function replaceVariables(template, data) {
  return template.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    return data[key] !== undefined ? data[key] : match;
  });
}

/**
 * メイン処理
 * @param {object} input - 入力データ
 * @param {object} options - オプション
 * @returns {object} 処理結果
 */
function process(input, options) {
  // TODO: ここに処理ロジックを実装
  const result = {
    success: true,
    data: input,
    timestamp: new Date().toISOString()
  };

  return result;
}

/**
 * エントリーポイント
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_SUCCESS);
  }

  const inputPath = getArg(args, "--input");
  const outputPath = getArg(args, "--output");
  const templatePath = getArg(args, "--template");
  const verbose = args.includes("--verbose");

  // 必須引数チェック
  if (!inputPath) {
    console.error("Error: --input は必須です");
    process.exit(EXIT_ARGS_ERROR);
  }

  // 入力ファイルの存在確認
  const resolvedInput = resolvePath(inputPath);
  if (!existsSync(resolvedInput)) {
    console.error(`Error: 入力ファイルが存在しません: ${resolvedInput}`);
    process.exit(EXIT_FILE_NOT_FOUND);
  }

  try {
    // 入力ファイル読み込み
    const inputData = JSON.parse(readFileSync(resolvedInput, "utf-8"));

    if (verbose) {
      console.log(`入力: ${inputPath}`);
      console.log(`データ: ${JSON.stringify(inputData, null, 2).substring(0, 200)}...`);
    }

    // テンプレート読み込み（指定時）
    let template = null;
    if (templatePath) {
      const resolvedTemplate = resolvePath(templatePath);
      if (!existsSync(resolvedTemplate)) {
        console.error(`Error: テンプレートが存在しません: ${resolvedTemplate}`);
        process.exit(EXIT_FILE_NOT_FOUND);
      }
      template = readFileSync(resolvedTemplate, "utf-8");
    }

    // 処理実行
    const result = process(inputData, { template, verbose });

    if (!result.success) {
      console.error("Error: 処理に失敗しました");
      process.exit(EXIT_PROCESS_FAILED);
    }

    // 出力
    const output = JSON.stringify(result.data, null, 2);

    if (outputPath) {
      const resolvedOutput = resolvePath(outputPath);
      const outputDir = dirname(resolvedOutput);
      if (!existsSync(outputDir)) {
        mkdirSync(outputDir, { recursive: true });
      }
      writeFileSync(resolvedOutput, output, "utf-8");
      console.log(`✓ 出力完了: ${outputPath}`);
    } else {
      console.log(output);
    }

    process.exit(EXIT_SUCCESS);
  } catch (err) {
    if (err instanceof SyntaxError) {
      console.error(`Error: JSONの解析に失敗しました: ${err.message}`);
    } else {
      console.error(`Error: ${err.message}`);
    }
    process.exit(EXIT_ERROR);
  }
}

main().catch((err) => {
  console.error(`Error: ${err.message}`);
  process.exit(EXIT_ERROR);
});
