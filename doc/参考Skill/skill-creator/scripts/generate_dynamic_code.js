#!/usr/bin/env node
/**
 * 動的コード生成スクリプト
 *
 * テンプレートと変数定義から実行可能なコードを生成する。
 * LLMによる設計結果をスクリプトで確実に展開する。
 *
 * 使用方法:
 *   node scripts/generate_dynamic_code.js --template <path> --variables <path> --output <path>
 *
 * 終了コード:
 *   0: 成功
 *   1: 一般エラー
 *   2: 引数エラー
 *   3: ファイル不在
 *   4: 検証失敗
 */

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "fs";
import { dirname } from "path";
import { EXIT_CODES, getArg, resolvePath } from "./utils.js";

function showHelp() {
  console.log(`
動的コード生成スクリプト

Usage:
  node generate_dynamic_code.js --template <path> --variables <path> --output <path>

Options:
  --template <path>   テンプレートファイルパス（必須）
  --variables <path>  変数定義JSONファイルパス（必須）
  --output <path>     出力先ファイルパス（必須）
  --strict            未定義変数をエラーにする
  --verbose           詳細出力
  -h, --help          ヘルプ表示
`);
}


// 変換フィルター
function applyFilter(value, filter) {
  const str = String(value);
  switch (filter) {
    case "uppercase":
      return str.toUpperCase();
    case "lowercase":
      return str.toLowerCase();
    case "camelCase":
      return str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
    case "pascalCase":
      const camel = str.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
      return camel.charAt(0).toUpperCase() + camel.slice(1);
    case "snakeCase":
      return str.replace(/-/g, "_");
    case "kebabCase":
      return str.replace(/_/g, "-").toLowerCase();
    case "trim":
      return str.trim();
    default:
      return str;
  }
}

// テンプレート処理
function processTemplate(template, variables, options = {}) {
  let result = template;
  const { strict = false, verbose = false } = options;
  const undefinedVars = [];

  // if/else 処理
  result = result.replace(
    /\{\{#if\s+(\w+)\}\}([\s\S]*?)(?:\{\{else\}\}([\s\S]*?))?\{\{\/if\}\}/g,
    (match, condition, ifContent, elseContent = "") => {
      const value = variables[condition];
      return value ? ifContent : elseContent;
    }
  );

  // each 処理
  result = result.replace(
    /\{\{#each\s+(\w+)\}\}([\s\S]*?)\{\{\/each\}\}/g,
    (match, arrayName, content) => {
      const arr = variables[arrayName] || [];
      if (!Array.isArray(arr)) return "";
      return arr
        .map((item, index) => {
          let itemContent = content;
          itemContent = itemContent.replace(
            /\{\{this\}\}/g,
            typeof item === "object" ? JSON.stringify(item) : item
          );
          itemContent = itemContent.replace(/\{\{@index\}\}/g, String(index));
          if (typeof item === "object") {
            Object.keys(item).forEach((key) => {
              itemContent = itemContent.replace(
                new RegExp(`\\{\\{this\\.${key}\\}\\}`, "g"),
                item[key]
              );
            });
          }
          return itemContent;
        })
        .join("");
    }
  );

  // フィルター処理: {{var | filter}}
  result = result.replace(
    /\{\{(\w+)\s*\|\s*(\w+)\}\}/g,
    (match, key, filter) => {
      const value = variables[key];
      if (value === undefined) {
        undefinedVars.push(key);
        return match;
      }
      return applyFilter(value, filter);
    }
  );

  // デフォルト値: {{var:default}}
  result = result.replace(/\{\{(\w+):([^}]+)\}\}/g, (match, key, defaultVal) => {
    return variables[key] !== undefined ? variables[key] : defaultVal;
  });

  // 基本置換: {{var}}
  result = result.replace(/\{\{(\w+)\}\}/g, (match, key) => {
    if (variables[key] === undefined) {
      undefinedVars.push(key);
      return match;
    }
    return variables[key];
  });

  if (strict && undefinedVars.length > 0) {
    const unique = [...new Set(undefinedVars)];
    throw new Error(`未定義の変数: ${unique.join(", ")}`);
  }

  if (verbose && undefinedVars.length > 0) {
    const unique = [...new Set(undefinedVars)];
    console.warn(`⚠ 未定義の変数（そのまま残る）: ${unique.join(", ")}`);
  }

  return result;
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes("-h") || args.includes("--help")) {
    showHelp();
    process.exit(EXIT_CODES.SUCCESS);
  }

  const templatePath = getArg(args, "--template");
  const variablesPath = getArg(args, "--variables");
  const outputPath = getArg(args, "--output");
  const strict = args.includes("--strict");
  const verbose = args.includes("--verbose");

  if (!templatePath) {
    console.error("Error: --template は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!variablesPath) {
    console.error("Error: --variables は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  if (!outputPath) {
    console.error("Error: --output は必須です");
    process.exit(EXIT_CODES.ARGS_ERROR);
  }

  const resolvedTemplate = resolvePath(templatePath);
  const resolvedVariables = resolvePath(variablesPath);
  const resolvedOutput = resolvePath(outputPath);

  if (!existsSync(resolvedTemplate)) {
    console.error(`Error: テンプレートが存在しません: ${resolvedTemplate}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  if (!existsSync(resolvedVariables)) {
    console.error(`Error: 変数ファイルが存在しません: ${resolvedVariables}`);
    process.exit(EXIT_CODES.FILE_NOT_FOUND);
  }

  try {
    const template = readFileSync(resolvedTemplate, "utf-8");
    const variablesData = JSON.parse(readFileSync(resolvedVariables, "utf-8"));

    // variables.variables または直接のオブジェクトに対応
    const variables = variablesData.variables || variablesData;

    if (verbose) {
      console.log(`テンプレート: ${templatePath}`);
      console.log(`変数: ${Object.keys(variables).length}個`);
    }

    const result = processTemplate(template, variables, { strict, verbose });

    // 出力ディレクトリ作成
    const outputDir = dirname(resolvedOutput);
    if (!existsSync(outputDir)) {
      mkdirSync(outputDir, { recursive: true });
    }

    writeFileSync(resolvedOutput, result, "utf-8");
    console.log(`✓ 生成完了: ${outputPath}`);
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
